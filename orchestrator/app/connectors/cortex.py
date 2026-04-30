"""Connecteur Cortex pour enrichissement (analyzers)."""
from __future__ import annotations
import logging
import requests

from ..config import get_settings

log = logging.getLogger("connectors.cortex")
_settings = get_settings()


def _headers() -> dict:
    return {"Authorization": f"Bearer {_settings.cortex_api_key}",
            "Content-Type": "application/json"}


def healthcheck() -> dict:
    if not _settings.cortex_url:
        return {"status": "disabled"}
    try:
        r = requests.get(f"{_settings.cortex_url}/api/status",
                         headers=_headers(), timeout=5)
        return {"status": "ok" if r.status_code == 200 else "down", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_analyzers() -> list[dict]:
    r = requests.get(f"{_settings.cortex_url}/api/analyzer",
                     headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def run_analyzer(analyzer_name: str, data_type: str, data: str, tlp: int = 2) -> dict:
    """Lance un analyzer Cortex et renvoie le rapport (synchrone court)."""
    payload = {"data": data, "dataType": data_type, "tlp": tlp, "message": "from-orchestrator"}
    r = requests.post(f"{_settings.cortex_url}/api/analyzer/_search",
                      json={"query": {"_field": "name", "_value": analyzer_name}},
                      headers=_headers(), timeout=10)
    r.raise_for_status()
    analyzers = r.json()
    if not analyzers:
        return {"status": "no-analyzer", "name": analyzer_name}
    aid = analyzers[0].get("id") or analyzers[0].get("_id")
    r = requests.post(f"{_settings.cortex_url}/api/analyzer/{aid}/run",
                      json=payload, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()
