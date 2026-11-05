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
        return cls(
            base_url=os.environ["RUNAI_BASE_URL"].rstrip("/"),
            client_id=os.environ["RUNAI_CLIENT_ID"],
            client_secret=os.environ["RUNAI_CLIENT_SECRET"],
            verify_tls=os.getenv("RUNAI_VERIFY_TLS", "true").strip().lower()
            not in ("false", "0", "no"),
        )


class RunaiClient:
    """Read-only wrapper: authenticates once, then issues GET requests."""

    def __init__(self, config: RunaiConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = config.verify_tls
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
