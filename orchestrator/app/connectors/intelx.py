"""Connecteur Intelligence X (intelx.io).

API doc: https://intelx.io/api
"""
from __future__ import annotations
import logging
import time
import requests

from ..config import get_settings

log = logging.getLogger("connectors.intelx")
_settings = get_settings()


def _headers() -> dict:
    return {"x-key": _settings.intelx_api_key, "User-Agent": "digital-printing/0.1"}


def healthcheck() -> dict:
    if not _settings.intelx_api_key:
        return {"status": "disabled"}
    try:
        r = requests.get(f"{_settings.intelx_base_url}/authenticate/info",
                         headers=_headers(), timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {"status": "ok",
                    "credits": data.get("paths", {}).get("/intelligent/search", {}).get("Credit", 0)}
        return {"status": "down", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def search(term: str, *, max_results: int = 100,
           buckets: list[str] | None = None,
           timeout_s: int = 60) -> list[dict]:
    """Recherche dans IntelX. Retourne une liste de selectors."""
    if not _settings.intelx_api_key:
        return []
    payload = {
        "term": term,
        "buckets": buckets or [],
        "lookuplevel": 0,
        "maxresults": max_results,
        "timeout": 0,
        "datefrom": "",
        "dateto": "",
        "sort": 4,
        "media": 0,
        "terminate": [],
    }
    try:
        r = requests.post(f"{_settings.intelx_base_url}/intelligent/search",
                          json=payload, headers=_headers(), timeout=15)
        r.raise_for_status()
        sid = r.json().get("id")
        if not sid:
            return []
    except Exception as e:
        log.error("intelx search start failed: %s", e)
        return []

    deadline = time.time() + timeout_s
    records: list[dict] = []
    while time.time() < deadline:
        try:
            r = requests.get(f"{_settings.intelx_base_url}/intelligent/search/result",
                             params={"id": sid, "limit": max_results},
                             headers=_headers(), timeout=15)
            r.raise_for_status()
            data = r.json()
            records.extend(data.get("records", []))
            if data.get("status", 0) in (1, 2):
                break
        except Exception as e:
            log.warning("intelx poll error: %s", e)
        time.sleep(2)
    return records


def fetch_preview(storageid: str, bucket: str = "leaks.public") -> str:
    """Recupere le preview textuel d'un selector."""
    try:
        r = requests.get(f"{_settings.intelx_base_url}/file/preview",
                         params={"sid": storageid, "f": 0, "l": 8, "c": 1, "m": 24, "b": bucket},
                         headers=_headers(), timeout=15)
        return r.text if r.status_code == 200 else ""
    except Exception as e:
        log.warning("intelx preview error: %s", e)
        return ""
