"""Connecteur Dehashed.

API doc: https://dehashed.com/docs
"""
from __future__ import annotations
import logging
import requests
from requests.auth import HTTPBasicAuth

from ..config import get_settings

log = logging.getLogger("connectors.dehashed")
_settings = get_settings()
_BASE = "https://api.dehashed.com"


def _auth() -> HTTPBasicAuth | None:
    if _settings.dehashed_email and _settings.dehashed_api_key:
        return HTTPBasicAuth(_settings.dehashed_email, _settings.dehashed_api_key)
    return None


def healthcheck() -> dict:
    if not _settings.dehashed_api_key or not _settings.dehashed_email:
        return {"status": "disabled"}
    try:
        r = requests.get(f"{_BASE}/search?query=test&size=1",
                         auth=_auth(), headers={"Accept": "application/json"}, timeout=10)
        return {"status": "ok" if r.status_code in (200, 400) else "down",
                "code": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def search(query: str, *, size: int = 100) -> list[dict]:
    """query: 'domain:example.com' / 'email:foo@bar.com' / etc."""
    if not _auth():
        return []
    try:
        r = requests.get(f"{_BASE}/search",
                         params={"query": query, "size": size},
                         auth=_auth(),
                         headers={"Accept": "application/json"},
                         timeout=30)
        r.raise_for_status()
        return r.json().get("entries", []) or []
    except Exception as e:
        log.warning("dehashed search error: %s", e)
        return []
