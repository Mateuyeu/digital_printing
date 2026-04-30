"""Connecteur MISP via PyMISP."""
from __future__ import annotations
import logging

from ..config import get_settings

log = logging.getLogger("connectors.misp")
_settings = get_settings()

_TYPE_MAP = {
    "domain": "domain",
    "hostname": "hostname",
    "ip": "ip-dst",
    "ipv4": "ip-dst",
    "ipv6": "ip-dst",
    "url": "url",
    "email": "email-src",
    "hash": "sha256",
    "md5": "md5",
    "sha1": "sha1",
    "sha256": "sha256",
    "btc": "btc",
    "credential": "leaked-credentials",
    "user-agent": "user-agent",
    "asn": "AS",
}

_THREAT_LEVEL = {"info": 4, "low": 3, "medium": 2, "high": 1, "critical": 1}


def _client():
    from pymisp import PyMISP
    return PyMISP(_settings.misp_url, _settings.misp_api_key,
                  ssl=_settings.misp_verify_ssl, debug=False)


def healthcheck() -> dict:
    if not _settings.misp_url or not _settings.misp_api_key:
        return {"status": "disabled"}
    try:
        m = _client()
        r = m.get_version()
        return {"status": "ok", "version": r.get("version") if isinstance(r, dict) else "?"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def push_event(*, client_slug: str, finding: dict) -> str | None:
    """Cree un evenement MISP avec les IOCs d'un finding. Retourne l'event uuid."""
    try:
        from pymisp import MISPEvent, MISPAttribute
        m = _client()
    except Exception as e:
        log.error("MISP client init failed: %s", e)
        return None

    event = MISPEvent()
    event.info = f"[{client_slug}] {finding.get('title', 'finding')}"
    event.distribution = 0
    event.threat_level_id = _THREAT_LEVEL.get(finding.get("severity", "info").lower(), 4)
    event.analysis = 2
    event.add_tag(f"client:{client_slug}")
    event.add_tag(f"source:{finding.get('source', 'easm')}")
    event.add_tag(f"kind:{finding.get('kind', 'unknown')}")
    event.add_tag("tlp:amber")

    for ioc in finding.get("iocs", []) or []:
        try:
            mtype = _TYPE_MAP.get(ioc.get("type", "").lower(), "other")
            attr = MISPAttribute()
            attr.type = mtype
            attr.value = ioc.get("value")
            attr.to_ids = mtype not in ("hostname", "domain") or finding.get("severity") in ("high", "critical")
            attr.comment = ioc.get("comment", "")
            event.add_attribute(**attr.to_dict())
        except Exception as e:
            log.debug("skipping ioc: %s", e)
            continue

    try:
        created = m.add_event(event, pythonify=True)
        return getattr(created, "uuid", None) or (created.get("Event", {}) if isinstance(created, dict) else {}).get("uuid")
    except Exception as e:
        log.error("MISP add_event failed: %s", e)
        return None
