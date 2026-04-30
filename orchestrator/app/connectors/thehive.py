"""Connecteur TheHive 5 via thehive4py."""
from __future__ import annotations
import logging
from datetime import datetime

from ..config import get_settings

log = logging.getLogger("connectors.thehive")
_settings = get_settings()


def _client():
    from thehive4py import TheHiveApi
    return TheHiveApi(url=_settings.thehive_url,
                      apikey=_settings.thehive_api_key,
                      organisation=_settings.thehive_org)


def healthcheck() -> dict:
    if not _settings.thehive_url or not _settings.thehive_api_key:
        return {"status": "disabled"}
    try:
        c = _client()
        status = c.status.get_public()
        return {"status": "ok", "version": status.get("versions", {}).get("TheHive", "?")}
    except Exception as e:
        return {"status": "error", "error": str(e)}


_SEVERITY_MAP = {"info": 1, "low": 2, "medium": 3, "high": 4, "critical": 4}


def create_alert(*, client_slug: str, finding: dict) -> str | None:
    """Cree une alerte TheHive a partir d'un finding. Retourne l'id de l'alerte."""
    try:
        c = _client()
    except Exception as e:
        log.error("TheHive client init failed: %s", e)
        return None

    sev = _SEVERITY_MAP.get(finding.get("severity", "info").lower(), 1)
    iocs = finding.get("iocs", []) or []
    observables = []
    for ioc in iocs:
        try:
            observables.append({
                "dataType": ioc.get("type", "other"),
                "data": ioc.get("value"),
                "tags": [f"client:{client_slug}", f"source:{finding.get('source', 'easm')}"],
                "tlp": 2,
            })
        except Exception:
            continue

    alert_payload = {
        "type": finding.get("kind", "easm-finding"),
        "source": finding.get("source", "digital-printing"),
        "sourceRef": finding.get("fingerprint", str(int(datetime.utcnow().timestamp()))),
        "title": f"[{client_slug}] {finding.get('title', 'finding')}",
        "description": finding.get("description") or finding.get("title", ""),
        "severity": sev,
        "tlp": 2,
        "pap": 2,
        "tags": [f"client:{client_slug}", f"kind:{finding.get('kind', 'unknown')}",
                 f"asset:{finding.get('asset', '')}"],
        "observables": observables,
    }
    try:
        alert = c.alert.create(alert=alert_payload)
        return alert.get("_id") or alert.get("id")
    except Exception as e:
        log.error("TheHive create_alert failed: %s", e)
        return None
