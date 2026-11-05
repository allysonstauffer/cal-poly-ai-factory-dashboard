"""Minimal read-only client for the NVIDIA Run:ai REST API.

Credentials are read from environment variables (loaded from a local .env).
Tokens and secrets are never printed or written to disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from dotenv import load_dotenv


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
    """Read-only wrapper: authenticates once, then issues GET requests."""

    def __init__(self, config: RunaiConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()
        # Verify against the configured CA bundle if set; otherwise use certifi (verify_tls).
        self.session.verify = config.ca_bundle or config.verify_tls
        self._token: str | None = None

    def authenticate(self) -> None:
        resp = self.session.post(
            f"{self.config.base_url}/api/v1/token",
            json={
                "grantType": "client_credentials",
                "clientId": self.config.client_id,
                "clientSecret": self.config.client_secret,
            },
            timeout=self.timeout,
        )
        if not resp.ok:
            # Don't echo the response body; it may reflect submitted credentials.
            raise RuntimeError(f"Run:ai authentication failed (HTTP {resp.status_code}).")
        token = resp.json().get("accessToken")
        if not token:
            raise RuntimeError("Run:ai authentication response had no accessToken.")
        self._token = token
        self.session.headers["Authorization"] = f"Bearer {token}"

    def get(self, path: str, params: dict | None = None) -> dict:
        if self._token is None:
            self.authenticate()
        resp = self.session.get(
            f"{self.config.base_url}/{path.lstrip('/')}",
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def list_workloads(self, limit: int = 50) -> dict:
        return self.get("/api/v1/workloads", params={"limit": limit})
