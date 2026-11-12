"""Minimal read-only client for the NVIDIA Run:ai REST API.

Credentials are read from environment variables (loaded from a local .env).
Tokens and secrets are never printed or written to disk. Error messages raised
by this module have hostnames and IP addresses removed so they are safe to paste.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

HOST_PLACEHOLDER = "<host>"
TOKEN_PATH = "/api/v1/token"

_URL_HOST_RE = re.compile(r"(?i)\b(https?://)[^/\s'\"<>]+")
_HOST_KWARG_RE = re.compile(r"(host=)(['\"])[^'\"]*\2")
_IPV4_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def scrub_hosts(text: str, hosts: Iterable[str] = ()) -> str:
    """Remove hostnames and IPv4 addresses from text.

    Replaces each known host (case-insensitive), the host part of any URL,
    urllib3-style ``host='...'`` fragments, and dotted IPv4 addresses.
    """
    for host in sorted({h for h in hosts if h}, key=len, reverse=True):
        text = re.sub(re.escape(host), HOST_PLACEHOLDER, text, flags=re.IGNORECASE)
    text = _URL_HOST_RE.sub(rf"\1{HOST_PLACEHOLDER}", text)
    text = _HOST_KWARG_RE.sub(rf"\1\2{HOST_PLACEHOLDER}\2", text)
    text = _IPV4_RE.sub("<ip>", text)
    return text


class RunaiError(RuntimeError):
    """A Run:ai request failed. The message contains no hostnames, IPs, or tokens."""


@dataclass(frozen=True)
class RunaiConfig:
    base_url: str
    client_id: str
    client_secret: str
    verify_tls: bool = True
    ca_bundle: str | None = None

    def __post_init__(self) -> None:
        if self.ca_bundle and not self.verify_tls:
            raise RuntimeError(
                "Conflicting TLS settings: RUNAI_CA_BUNDLE is set but RUNAI_VERIFY_TLS=false. "
                "Remove RUNAI_VERIFY_TLS=false to verify against the CA bundle."
            )

    @classmethod
    def from_env(cls) -> "RunaiConfig":
        load_dotenv()
        missing = [
            name
            for name in ("RUNAI_BASE_URL", "RUNAI_CLIENT_ID", "RUNAI_CLIENT_SECRET")
            if not os.getenv(name)
        ]
        if missing:
            raise RuntimeError(
                f"Missing environment variables: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in your values."
            )
        ca_bundle = os.getenv("RUNAI_CA_BUNDLE", "").strip() or None
        if ca_bundle:
            ca_bundle = os.path.expanduser(ca_bundle)
            if not os.path.isfile(ca_bundle):
                raise RuntimeError(f"RUNAI_CA_BUNDLE file not found: {ca_bundle}")
        return cls(
            base_url=os.environ["RUNAI_BASE_URL"].rstrip("/"),
            client_id=os.environ["RUNAI_CLIENT_ID"],
            client_secret=os.environ["RUNAI_CLIENT_SECRET"],
            verify_tls=os.getenv("RUNAI_VERIFY_TLS", "true").strip().lower()
            not in ("false", "0", "no"),
            ca_bundle=ca_bundle,
        )


class RunaiClient:
    """Read-only wrapper: issues GET requests, plus the token POST.

    The access token is cached in memory for the life of the client. If a GET
    returns HTTP 401 (e.g. the token expired), the client fetches a fresh token
    and retries that request once.
    """

    def __init__(self, config: RunaiConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()
        # Verify against the configured CA bundle if set; otherwise use certifi (verify_tls).
        self.session.verify = config.ca_bundle or config.verify_tls
        self._token: str | None = None
        parsed = urlparse(config.base_url)
        self._hosts = tuple(h for h in (parsed.netloc, parsed.hostname) if h)

    def _scrub(self, text: str) -> str:
        if self._token:
            text = text.replace(self._token, "<token>")
        return scrub_hosts(text, self._hosts)

    def _send(self, method: str, path: str, **kwargs) -> requests.Response:
        if method not in ("GET",) and not (method == "POST" and path == TOKEN_PATH):
            raise RunaiError(f"Refusing non-read-only request: {method} {path}")
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        try:
            return self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            detail = self._scrub(f"{type(exc).__name__}: {exc}")
            # "from None" keeps the unscrubbed original exception out of the traceback.
            raise RunaiError(f"Run:ai {method} {self._scrub(path)} failed: {detail}") from None

    def authenticate(self) -> None:
        self._token = None
        self.session.headers.pop("Authorization", None)
        resp = self._send(
            "POST",
            TOKEN_PATH,
            json={
                "grantType": "client_credentials",
                "clientId": self.config.client_id,
                "clientSecret": self.config.client_secret,
            },
        )
        if not resp.ok:
            # Don't echo the response body; it may reflect submitted credentials.
            raise RunaiError(f"Run:ai authentication failed (HTTP {resp.status_code}).")
        try:
            token = resp.json().get("accessToken")
        except ValueError:
            raise RunaiError("Run:ai authentication response was not JSON.") from None
        if not token:
            raise RunaiError("Run:ai authentication response had no accessToken.")
        self._token = token
        self.session.headers["Authorization"] = f"Bearer {token}"

    def get(self, path: str, params: dict | None = None) -> dict:
        if self._token is None:
            self.authenticate()
        resp = self._send("GET", path, params=params)
        if resp.status_code == 401:
            self.authenticate()
            resp = self._send("GET", path, params=params)
        if not resp.ok:
            raise RunaiError(f"Run:ai GET {self._scrub(path)} failed (HTTP {resp.status_code}).")
        try:
            return resp.json()
        except ValueError:
            raise RunaiError(f"Run:ai GET {self._scrub(path)} returned non-JSON.") from None
