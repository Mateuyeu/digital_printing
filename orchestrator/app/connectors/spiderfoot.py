"""Connecteur SpiderFoot via API HTTP de la web app embarquee.

SpiderFoot expose:
  POST /api/scan         - lancer un scan
  GET  /api/scaneventresults?id=...  - resultats
  GET  /api/scanstatus?id=...
"""
from __future__ import annotations
import logging
import time
import requests
from requests.auth import HTTPBasicAuth

from ..config import get_settings

log = logging.getLogger("connectors.spiderfoot")
_settings = get_settings()


def _auth() -> HTTPBasicAuth | None:
    if _settings.spiderfoot_user and _settings.spiderfoot_password:
        return HTTPBasicAuth(_settings.spiderfoot_user, _settings.spiderfoot_password)
    return None


def healthcheck() -> dict:
    if not _settings.spiderfoot_url:
        return {"status": "disabled"}
    try:
        r = requests.get(f"{_settings.spiderfoot_url}/ping", auth=_auth(), timeout=5)
        return {"status": "ok" if r.status_code == 200 else "down", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def start_scan(target: str, modules: str = "sfp_dnsresolve,sfp_dnsbrute,sfp_subdomain_enum,"
                                            "sfp_whois,sfp_emailrep,sfp_pgp,sfp_haveibeenpwned,"
                                            "sfp_shodan,sfp_threatcrowd,sfp_securitytrails,"
                                            "sfp_company,sfp_socialprofiles,sfp_pastebin",
               scan_name: str | None = None,
               use_case: str = "all") -> str:
    """Demarre un scan SpiderFoot. Retourne le scan_id."""
    name = scan_name or f"dp-{int(time.time())}"
    payload = {
        "scanname": name,
        "scantarget": target,
        "modulelist": f"module_{modules}",
        "typelist": "type_*",
        "usecase": use_case,
    }
    r = requests.post(f"{_settings.spiderfoot_url}/startscan",
                      data=payload, auth=_auth(), timeout=30, allow_redirects=False)
    r.raise_for_status()
    if r.status_code in (302, 303):
        loc = r.headers.get("Location", "")
        if "id=" in loc:
            return loc.split("id=", 1)[1]
    try:
        data = r.json()
        if isinstance(data, list) and len(data) > 1:
            return str(data[1])
    except Exception:
        pass
    return r.text.strip()


def scan_status(scan_id: str) -> dict:
    r = requests.get(f"{_settings.spiderfoot_url}/scanstatus",
                     params={"id": scan_id}, auth=_auth(), timeout=10)
    r.raise_for_status()
    return r.json() if r.text.startswith("{") or r.text.startswith("[") else {"raw": r.text}


def scan_results(scan_id: str) -> list[dict]:
    r = requests.get(f"{_settings.spiderfoot_url}/scaneventresults",
                     params={"id": scan_id}, auth=_auth(), timeout=120)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return []


def wait_for_scan(scan_id: str, *, max_wait: int = 7200, poll: int = 30) -> str:
    """Bloque jusqu'a la fin du scan SpiderFoot. Retourne le statut final."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            status = scan_status(scan_id)
            state = status[0][5] if isinstance(status, list) and status else "UNKNOWN"
            if state in ("FINISHED", "ERROR-FAILED", "ABORTED", "ERROR"):
                return state
        except Exception as e:
            log.debug("scan_status error: %s", e)
        time.sleep(poll)
    return "TIMEOUT"
