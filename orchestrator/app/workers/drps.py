"""Pipelines DRPS : monitoring fuites, dark web, social, brand abuse.

Pipelines :
  - DRPS_LEAKS    -> IntelX + Dehashed (recherche par domain/email/keyword)
  - DRPS_AIL      -> trackers AIL (mots-cles), recuperation des matches recents
  - DRPS_DARKWEB  -> LACUS captures via Tor (.onion) ou I2P (.i2p)
  - DRPS_SOCIAL   -> AIL crawler ciblant Telegram/Discord/Session
"""
from __future__ import annotations
import logging
from datetime import datetime

from ..connectors import intelx, dehashed, ail, lacus
from .utils import (get_client_scopes, upsert_finding, mark_scan_running,
                    finalize_scan)
from ..models import ScanStatus, Severity

log = logging.getLogger("workers.drps")


# ---------------------------------------------------------------------------
def run_drps_leaks(scan_id: int, client_id: int, params: dict) -> dict:
    """Recherche des credentials/leaks : IntelX + Dehashed."""
    mark_scan_running(scan_id)
    scopes = get_client_scopes(client_id)
    terms = (scopes.get("domain", []) + scopes.get("email", []) +
             scopes.get("keyword", []) + scopes.get("brand", []))
    if not terms:
        finalize_scan(scan_id, status=ScanStatus.FAILED,
                      error="No domain/email/keyword scope")
        return {"error": "no_scope"}

    summary = {"intelx_records": 0, "dehashed_entries": 0}

    for term in terms:
        try:
            ix_records = intelx.search(term, max_results=200)
        except Exception as e:
            log.warning("intelx search failed for %s: %s", term, e)
            ix_records = []
        for rec in ix_records:
            summary["intelx_records"] += 1
            sid = rec.get("storageid") or rec.get("systemid") or ""
            bucket = rec.get("bucket", "")
            sev = (Severity.HIGH.value if "leak" in bucket.lower()
                   or "dump" in bucket.lower() else Severity.MEDIUM.value)
            upsert_finding(
                client_id=client_id, scan_id=scan_id, kind="leak_intelx",
                severity=sev,
                title=f"IntelX hit on '{term}' ({bucket})",
                description=rec.get("name", "") or rec.get("description", ""),
                asset=term, source="intelx",
                raw=rec,
                iocs=[{"type": "keyword", "value": term},
                      {"type": "intelx_storageid", "value": sid}],
                fp_parts=[str(client_id), "intelx", term, sid],
            )

        try:
            query = (f"domain:{term}" if "." in term and "@" not in term
                     else f"email:{term}" if "@" in term
                     else f"name:{term}")
            dh_entries = dehashed.search(query, size=100)
        except Exception as e:
            log.warning("dehashed search failed for %s: %s", term, e)
            dh_entries = []
        for entry in dh_entries:
            summary["dehashed_entries"] += 1
            email = entry.get("email", "")
            password = entry.get("password", "")
            sev = (Severity.CRITICAL.value if password else
                   Severity.HIGH.value if email else Severity.MEDIUM.value)
            upsert_finding(
                client_id=client_id, scan_id=scan_id, kind="leak_credential",
                severity=sev,
                title=f"Credential leak: {email or entry.get('username', term)}",
                description=f"Database: {entry.get('database_name', '?')}",
                asset=email or term, source="dehashed",
                raw=entry,
                iocs=[{"type": "email", "value": email}] if email else [
                    {"type": "credential", "value": entry.get("username", "")}],
                fp_parts=[str(client_id), "dehashed", email or "", entry.get("database_name", "")],
            )

    finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=summary)
    return summary


# ---------------------------------------------------------------------------
def run_drps_ail(scan_id: int, client_id: int, params: dict) -> dict:
    """Recupere les matches recents pour les trackers AIL.
    Si action='register', cree les trackers a partir des scopes du client."""
    mark_scan_running(scan_id)
    scopes = get_client_scopes(client_id)
    terms = (scopes.get("brand", []) + scopes.get("keyword", []) +
             scopes.get("domain", []) + scopes.get("executive", []))

    summary = {"trackers_registered": 0, "matches": 0}

    if params.get("action") == "register":
        for t in terms:
            res = ail.add_tracker(term=t, ttype="word",
                                  tags=[f"client:{client_id}"])
            if res:
                summary["trackers_registered"] += 1
        finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=summary)
        return summary

    # Sinon : recherche directe des items contenant les termes
    for term in terms:
        try:
            results = ail.search_objects(term, otype="item", limit=100)
        except Exception as e:
            log.warning("ail search failed: %s", e)
            results = []
        for r in results:
            summary["matches"] += 1
            obj_id = r.get("id") or r.get("object_id") or ""
            upsert_finding(
                client_id=client_id, scan_id=scan_id, kind="paste_match",
                severity=Severity.HIGH.value,
                title=f"AIL paste match for '{term}'",
                description=r.get("preview", "")[:1000],
                asset=term, source="ail",
                raw=r,
                iocs=[{"type": "keyword", "value": term},
                      {"type": "ail_object", "value": obj_id}],
                fp_parts=[str(client_id), "ail", term, obj_id],
            )

    finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=summary)
    return summary


# ---------------------------------------------------------------------------
def run_drps_darkweb(scan_id: int, client_id: int, params: dict) -> dict:
    """Capture LACUS sur des URLs Tor/I2P/clearnet pour brand monitoring.

    params['urls'] : liste d'URLs a capturer.
    params['proxy'] : 'tor' (defaut), 'i2p', None (clearnet).
    """
    mark_scan_running(scan_id)
    urls = params.get("urls") or []
    if not urls:
        finalize_scan(scan_id, status=ScanStatus.FAILED, error="No urls provided")
        return {"error": "no_urls"}

    proxy_kind = params.get("proxy", "tor")
    proxy = "socks5://tor:9050" if proxy_kind == "tor" else None

    summary = {"submitted": 0, "completed": 0, "errors": 0}
    captures: list[dict] = []
    for url in urls:
        try:
            uuid = lacus.submit_capture(url, proxy=proxy, depth=params.get("depth", 1))
        except Exception as e:
            log.warning("lacus submit error: %s", e)
            uuid = None
        if not uuid:
            summary["errors"] += 1
            continue
        summary["submitted"] += 1
        if params.get("wait", True):
            result = lacus.wait_for_capture(uuid,
                                             max_wait=params.get("max_wait", 600))
            if "error" not in result:
                summary["completed"] += 1
                captures.append({"url": url, "uuid": uuid, "result_keys": list(result.keys())})
                final_url = result.get("final_url") or url
                upsert_finding(
                    client_id=client_id, scan_id=scan_id, kind="darkweb_capture",
                    severity=Severity.MEDIUM.value,
                    title=f"Darkweb capture: {url}",
                    description=f"Captured via {proxy_kind} - final={final_url}",
                    asset=url, source="lacus",
                    raw={"uuid": uuid, "proxy": proxy_kind, "final_url": final_url,
                         "har_keys": list((result.get("har") or {}).keys())[:20]},
                    iocs=[{"type": "url", "value": url}, {"type": "url", "value": final_url}],
                    fp_parts=[str(client_id), "darkweb", url],
                )
            else:
                summary["errors"] += 1

    finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=summary)
    return summary


# ---------------------------------------------------------------------------
def run_drps_social(scan_id: int, client_id: int, params: dict) -> dict:
    """Brand monitoring sur reseaux alternatifs via AIL+LACUS.
    Pousse des trackers AIL sur les handles, nom executifs, marques,
    et soumet a LACUS les invitations Telegram/Discord/Session.
    """
    mark_scan_running(scan_id)
    scopes = get_client_scopes(client_id)
    handles = scopes.get("social_handle", [])
    brands = scopes.get("brand", []) + scopes.get("keyword", [])
    summary = {"trackers": 0, "captures": 0}

    for term in handles + brands:
        if ail.add_tracker(term=term, ttype="word",
                           tags=[f"client:{client_id}", "social"]):
            summary["trackers"] += 1

    for url in params.get("invite_urls", []) or []:
        uuid = lacus.submit_capture(url,
                                    proxy="socks5://tor:9050" if params.get("via_tor") else None)
        if uuid:
            summary["captures"] += 1
            upsert_finding(
                client_id=client_id, scan_id=scan_id, kind="social_capture",
                severity=Severity.MEDIUM.value,
                title=f"Social capture: {url}",
                description="Capture via LACUS",
                asset=url, source="lacus-social",
                raw={"uuid": uuid, "url": url},
                iocs=[{"type": "url", "value": url}],
                fp_parts=[str(client_id), "social", url],
            )

    finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=summary)
    return summary
