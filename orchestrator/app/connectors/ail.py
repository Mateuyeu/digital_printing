"""Connecteur AIL Framework (analyse de fuites paste/forums/social).

AIL expose une API REST sur :7000.
"""
from __future__ import annotations
import logging
import requests

from ..config import get_settings

log = logging.getLogger("connectors.ail")
_settings = get_settings()


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if _settings.ail_api_key:
        h["Authorization"] = _settings.ail_api_key
    return h


def healthcheck() -> dict:
    if not _settings.ail_url:
        return {"status": "disabled"}
    try:
        r = requests.get(f"{_settings.ail_url}/api/v1/ping",
                         headers=_headers(),
                         verify=_settings.ail_verify_ssl,
                         timeout=5)
        return {"status": "ok" if r.status_code == 200 else "down",
                "code": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def add_tracker(*, term: str, ttype: str = "word", tags: list[str] | None = None) -> dict | None:
    """Cree un tracker AIL (mot-cle, regex, set, yara) pour surveillance continue."""
    payload = {"term": term, "type": ttype, "tags": tags or [], "level": 1, "description": ""}
    try:
        r = requests.post(f"{_settings.ail_url}/api/v1/add/tracker/term",
                          json=payload, headers=_headers(),
                          verify=_settings.ail_verify_ssl, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("ail add_tracker error: %s", e)
        return None


def search_objects(query: str, otype: str = "item", limit: int = 100) -> list[dict]:
    """Recherche dans les objets AIL (item=paste, etc)."""
    try:
        r = requests.get(f"{_settings.ail_url}/api/v1/search/{otype}",
                         params={"query": query, "size": limit},
                         headers=_headers(),
                         verify=_settings.ail_verify_ssl, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("results") or data.get("data") or []
    except Exception as e:
        log.warning("ail search_objects error: %s", e)
        return []


def submit_url(url: str, *, depth: int = 1, har: bool = True,
               proxy: str | None = None) -> dict | None:
    """Demande a AIL/LACUS de crawler une URL (clearnet/tor/i2p selon proxy)."""
    payload = {"url": url, "har": har, "depth": depth}
    if proxy:
        payload["proxy"] = proxy
    try:
        r = requests.post(f"{_settings.ail_url}/api/v1/add/crawler/task",
                          json=payload, headers=_headers(),
                          verify=_settings.ail_verify_ssl, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("ail submit_url error: %s", e)
        return None
