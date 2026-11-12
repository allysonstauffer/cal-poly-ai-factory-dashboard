"""Tests for runai_client and workloads. All HTTP is faked; no network access."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from requests.adapters import BaseAdapter

from runai_client import RunaiClient, RunaiConfig, RunaiError, scrub_hosts
from workloads import fetch_all_workloads

FIXTURE = Path(__file__).parent / "fixtures" / "workloads_fake.json"
FAKE_HOST = "runai.fake-cluster.example.invalid"
FAKE_BASE_URL = f"https://{FAKE_HOST}"


def load_fake_workloads() -> list[dict]:
    return json.loads(FIXTURE.read_text())["workloads"]


def make_response(request: requests.PreparedRequest, status: int, body: dict | None = None):
    resp = requests.Response()
    resp.status_code = status
    resp.url = request.url
    resp.request = request
    resp.headers["Content-Type"] = "application/json"
    resp._content = json.dumps(body or {}).encode()
    return resp


class FakeAdapter(BaseAdapter):
    """Routes every request on the session to a handler and records it."""

    def __init__(self, handler):
        super().__init__()
        self.handler = handler
        self.requests: list[requests.PreparedRequest] = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        return self.handler(request)

    def close(self):
        pass

    def calls(self, method: str, path: str) -> list[requests.PreparedRequest]:
        return [r for r in self.requests if r.method == method and urlparse(r.url).path == path]


def make_client(handler) -> tuple[RunaiClient, FakeAdapter]:
    client = RunaiClient(
        RunaiConfig(base_url=FAKE_BASE_URL, client_id="fake-id", client_secret="fake-secret")
    )
    adapter = FakeAdapter(handler)
    client.session.mount("https://", adapter)
    client.session.mount("http://", adapter)
    return client, adapter


class FakeRunai:
    """Minimal fake server: token endpoint + paginated workloads."""

    def __init__(self, workloads: list[dict], unauthorized_tokens: set[str] = frozenset()):
        self.workloads = workloads
        self.unauthorized_tokens = set(unauthorized_tokens)
        self.tokens_issued = 0

    def __call__(self, request):
        path = urlparse(request.url).path
        if request.method == "POST" and path == "/api/v1/token":
            self.tokens_issued += 1
            return make_response(request, 200, {"accessToken": f"fake-token-{self.tokens_issued}"})
        if request.method == "GET" and path == "/api/v1/workloads":
            auth = request.headers.get("Authorization", "")
            token = auth.removeprefix("Bearer ")
            if not token or token in self.unauthorized_tokens:
                return make_response(request, 401, {"message": "unauthorized"})
            qs = parse_qs(urlparse(request.url).query)
            offset = int(qs.get("offset", ["0"])[0])
            limit = int(qs.get("limit", ["50"])[0])
            page = self.workloads[offset : offset + limit]
            body = {"workloads": page}
            if offset + limit < len(self.workloads):
                # Page-index style value: the client must not treat it as an offset.
                body["next"] = offset // limit + 1
            return make_response(request, 200, body)
        return make_response(request, 404)


# --- pagination ---------------------------------------------------------------


def test_fixture_is_fake_and_sized():
    workloads = load_fake_workloads()
    assert 6 <= len(workloads) <= 8
    for w in workloads:
        assert w["name"].startswith("fake-")
        assert w["submittedBy"].endswith("@example.invalid")


def test_fetch_all_collects_every_page():
    workloads = load_fake_workloads()  # 7 records
    server = FakeRunai(workloads)
    client, adapter = make_client(server)

    result = fetch_all_workloads(client, page_size=3)

    assert [w["id"] for w in result.workloads] == [w["id"] for w in workloads]
    assert result.pages_fetched == 3
    assert result.truncated is False
    gets = adapter.calls("GET", "/api/v1/workloads")
    offsets = [parse_qs(urlparse(r.url).query)["offset"][0] for r in gets]
    limits = {parse_qs(urlparse(r.url).query)["limit"][0] for r in gets}
    assert offsets == ["0", "3", "6"]
    assert limits == {"3"}
    assert server.tokens_issued == 1  # token cached across pages


def test_single_page_when_no_next():
    server = FakeRunai(load_fake_workloads())
    client, _ = make_client(server)
    result = fetch_all_workloads(client, page_size=500)
    assert len(result.workloads) == 7
    assert result.pages_fetched == 1


def test_max_pages_safety_limit_truncates():
    server = FakeRunai(load_fake_workloads())
    client, adapter = make_client(server)

    result = fetch_all_workloads(client, page_size=2, max_pages=2)

    assert len(result.workloads) == 4
    assert result.pages_fetched == 2
    assert result.truncated is True
    assert len(adapter.calls("GET", "/api/v1/workloads")) == 2


def test_empty_page_with_next_stops():
    def handler(request):
        if request.method == "POST":
            return make_response(request, 200, {"accessToken": "fake-token"})
        return make_response(request, 200, {"workloads": [], "next": 1})

    client, adapter = make_client(handler)
    result = fetch_all_workloads(client, page_size=10)
    assert result.workloads == []
    assert result.pages_fetched == 1


def test_duplicate_ids_across_pages_are_dropped():
    workloads = load_fake_workloads()
    pages = [
        {"workloads": workloads[0:3], "next": 1},
        {"workloads": workloads[2:5]},  # workloads[2] shifted into the next page
    ]

    def handler(request):
        if request.method == "POST":
            return make_response(request, 200, {"accessToken": "fake-token"})
        return make_response(request, 200, pages.pop(0))

    client, _ = make_client(handler)
    result = fetch_all_workloads(client, page_size=3)
    assert [w["id"] for w in result.workloads] == [w["id"] for w in workloads[0:5]]


@pytest.mark.parametrize("kwargs", [{"page_size": 0}, {"page_size": 501}, {"max_pages": 0}])
def test_invalid_arguments(kwargs):
    client, _ = make_client(lambda r: make_response(r, 500))
    with pytest.raises(ValueError):
        fetch_all_workloads(client, **kwargs)


# --- token caching and 401 retry ---------------------------------------------


def test_token_cached_between_requests():
    server = FakeRunai(load_fake_workloads())
    client, _ = make_client(server)
    client.get("/api/v1/workloads")
    client.get("/api/v1/workloads")
    assert server.tokens_issued == 1


def test_401_triggers_one_reauth_and_retry():
    server = FakeRunai(load_fake_workloads(), unauthorized_tokens={"fake-token-1"})
    client, adapter = make_client(server)

    data = client.get("/api/v1/workloads", params={"offset": 0, "limit": 50})

    assert len(data["workloads"]) == 7
    assert server.tokens_issued == 2
    gets = adapter.calls("GET", "/api/v1/workloads")
    assert [r.headers["Authorization"] for r in gets] == [
        "Bearer fake-token-1",
        "Bearer fake-token-2",
    ]
    # The token request itself must not carry the stale bearer token.
    for token_req in adapter.calls("POST", "/api/v1/token"):
        assert "Authorization" not in token_req.headers


def test_persistent_401_retries_only_once():
    server = FakeRunai(
        load_fake_workloads(), unauthorized_tokens={"fake-token-1", "fake-token-2", "fake-token-3"}
    )
    client, adapter = make_client(server)

    with pytest.raises(RunaiError, match="HTTP 401"):
        client.get("/api/v1/workloads")

    assert len(adapter.calls("GET", "/api/v1/workloads")) == 2
    assert server.tokens_issued == 2


def test_401_mid_pagination_recovers():
    workloads = load_fake_workloads()
    server = FakeRunai(workloads)
    client, _ = make_client(server)
    client.authenticate()
    server.unauthorized_tokens.add("fake-token-1")  # token "expires" before paging

    result = fetch_all_workloads(client, page_size=3)
    assert len(result.workloads) == 7
    assert server.tokens_issued == 2


def test_failed_auth_does_not_retry_forever():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return make_response(request, 401, {"message": "bad credentials fake-secret"})

    client, _ = make_client(handler)
    with pytest.raises(RunaiError) as excinfo:
        client.get("/api/v1/workloads")
    assert calls["n"] == 1
    assert "fake-secret" not in str(excinfo.value)


def test_non_get_requests_refused():
    client, adapter = make_client(lambda r: make_response(r, 200))
    with pytest.raises(RunaiError, match="non-read-only"):
        client._send("DELETE", "/api/v1/workloads/x")
    assert adapter.requests == []


# --- hostname scrubbing -------------------------------------------------------


def full_traceback(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def test_scrub_hosts_unit():
    text = (
        f"HTTPSConnectionPool(host='{FAKE_HOST}', port=443): Max retries exceeded "
        f"with url: /api/v1/token (https://{FAKE_HOST}:443/api/v1/token; "
        "http://other.example.invalid/x; resolved 10.20.30.40)"
    )
    out = scrub_hosts(text, [FAKE_HOST])
    assert FAKE_HOST not in out
    assert "other.example.invalid" not in out
    assert "10.20.30.40" not in out
    assert "/api/v1/token" in out  # paths are kept for debugging
    assert "host='<host>'" in out


def test_tls_error_message_and_traceback_are_scrubbed():
    def handler(request):
        raise requests.exceptions.SSLError(
            f"HTTPSConnectionPool(host='{FAKE_HOST}', port=443): Max retries exceeded with "
            f"url: /api/v1/token (Caused by SSLError(SSLCertVerificationError(1, "
            f"'certificate verify failed: unable to get local issuer certificate for "
            f"{FAKE_HOST.upper()} at 10.1.2.3')))"
        )

    client, _ = make_client(handler)
    with pytest.raises(RunaiError) as excinfo:
        client.authenticate()

    message = str(excinfo.value)
    assert "SSLError" in message
    assert "certificate verify failed" in message
    tb = full_traceback(excinfo.value)
    assert FAKE_HOST not in tb.lower()
    assert "10.1.2.3" not in tb
    assert "fake-secret" not in tb


def test_http_error_message_is_scrubbed():
    server = FakeRunai(load_fake_workloads())

    def handler(request):
        if request.method == "GET":
            return make_response(request, 500, {"detail": f"boom at {FAKE_HOST}"})
        return server(request)

    client, _ = make_client(handler)
    with pytest.raises(RunaiError) as excinfo:
        client.get("/api/v1/workloads")

    tb = full_traceback(excinfo.value)
    assert "HTTP 500" in str(excinfo.value)
    assert FAKE_HOST not in tb
    assert "fake-token-1" not in tb


def test_connection_error_during_get_is_scrubbed_and_hides_token():
    def handler(request):
        if request.method == "POST":
            return make_response(request, 200, {"accessToken": "fake-token-secretvalue"})
        raise requests.exceptions.ConnectionError(
            f"Failed to connect to https://{FAKE_HOST}/api/v1/workloads "
            "with header Bearer fake-token-secretvalue"
        )

    client, _ = make_client(handler)
    with pytest.raises(RunaiError) as excinfo:
        client.get("/api/v1/workloads")

    tb = full_traceback(excinfo.value)
    assert FAKE_HOST not in tb
    assert "fake-token-secretvalue" not in tb
    assert "/api/v1/workloads" in str(excinfo.value)
