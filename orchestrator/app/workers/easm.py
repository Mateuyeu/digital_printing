"""Pipelines EASM : reconnaissance externe.

Ordre standard d'un FULL_RECON pour un client :
  1. SUBFINDER  (domains -> subdomains)
  2. DNSX       (resolve)
  3. NAABU      (port scan top1000)
  4. HTTPX      (HTTP fingerprint)
  5. KATANA     (crawl)
  6. NUCLEI     (vuln scan)
  7. CVEMAP     (lookup CVE par tech detectee)
  8. THEHARVESTER (emails / leaks externes)
  9. SPIDERFOOT  (OSINT large)
"""
from __future__ import annotations
import logging
from datetime import datetime

from ..tools import projectdiscovery as pd
from ..tools import theharvester as th
from ..connectors import spiderfoot as sf
from .utils import (get_client_scopes, upsert_finding, get_client_slug,
                    mark_scan_running, finalize_scan)
from ..models import ScanStatus, Severity

log = logging.getLogger("workers.easm")


# ---------------------------------------------------------------------------
def run_easm_discovery(scan_id: int, client_id: int, params: dict) -> dict:
    """Subfinder + DNSX + Naabu pour decouvrir surface."""
    mark_scan_running(scan_id)
    scopes = get_client_scopes(client_id)
    domains = scopes.get("domain", [])
    seed_ips = scopes.get("ip", [])
    cidrs = scopes.get("cidr", [])

    if not domains and not seed_ips and not cidrs:
        finalize_scan(scan_id, status=ScanStatus.FAILED,
                      error="No domain/ip/cidr scope defined")
        return {"error": "no_scope"}

    summary = {"subdomains": 0, "resolved": 0, "ports": 0}

    subs = pd.subfinder(domains) if domains else []
    discovered_hosts = sorted({s.get("host") for s in subs if s.get("host")} | set(domains))
    summary["subdomains"] = len(subs)
    for s in subs:
        host = s.get("host")
        if not host:
            continue
        upsert_finding(client_id=client_id, scan_id=scan_id, kind="subdomain",
                       severity=Severity.INFO.value, title=host, asset=host,
                       source="subfinder",
                       raw=s, iocs=[{"type": "domain", "value": host}],
                       fp_parts=[str(client_id), "subdomain", host])

    resolved = pd.dnsx(discovered_hosts) if discovered_hosts else []
    summary["resolved"] = len(resolved)
    ip_set: set[str] = set(seed_ips)
    for r in resolved:
        host = r.get("host")
        for a in r.get("a", []) or []:
            ip_set.add(a)
            upsert_finding(client_id=client_id, scan_id=scan_id, kind="dns_record",
                           severity=Severity.INFO.value,
                           title=f"{host} -> {a}", asset=host, source="dnsx",
                           raw=r, iocs=[{"type": "ipv4", "value": a},
                                        {"type": "domain", "value": host}],
                           fp_parts=[str(client_id), "dns", host, a])

    targets = list(ip_set) + cidrs
    ports = pd.naabu(targets) if targets else []
    summary["ports"] = len(ports)
    for p in ports:
        host = p.get("host") or p.get("ip")
        port = p.get("port")
        if not host or not port:
            continue
        upsert_finding(client_id=client_id, scan_id=scan_id, kind="open_port",
                       severity=Severity.LOW.value,
                       title=f"{host}:{port}/tcp open",
                       asset=f"{host}:{port}", source="naabu",
                       raw=p, iocs=[{"type": "ipv4", "value": host}],
                       fp_parts=[str(client_id), "port", host, str(port)])

    finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=summary)
    return summary


# ---------------------------------------------------------------------------
def run_easm_http(scan_id: int, client_id: int, params: dict) -> dict:
    """Probing HTTPX sur les hosts/ports decouverts."""
    mark_scan_running(scan_id)
    scopes = get_client_scopes(client_id)
    targets = list({*scopes.get("domain", []), *scopes.get("ip", [])})
    if "targets" in params:
        targets = list(set(targets + list(params["targets"])))

    if not targets:
        finalize_scan(scan_id, status=ScanStatus.FAILED, error="No targets")
        return {"error": "no_targets"}

    results = pd.httpx(targets)
    techs_detected: set[str] = set()
    for r in results:
        url = r.get("url", "")
        host = r.get("host", "")
        title = r.get("title", "")
        status_code = r.get("status_code") or r.get("status-code")
        techs = r.get("tech", []) or r.get("technologies", []) or []
        for t in techs:
            techs_detected.add(t if isinstance(t, str) else t.get("name", ""))
        sev = Severity.INFO.value
        if status_code and 500 <= int(status_code) < 600:
            sev = Severity.LOW.value
        upsert_finding(client_id=client_id, scan_id=scan_id, kind="http_service",
                       severity=sev,
                       title=f"{url} ({status_code}) {title}",
                       description=f"techs: {', '.join(techs_detected) if techs else '-'}",
                       asset=url, source="httpx",
                       raw=r,
                       iocs=[{"type": "url", "value": url}],
                       fp_parts=[str(client_id), "http", url])

    finalize_scan(scan_id, status=ScanStatus.COMPLETED,
                  summary={"http_services": len(results),
                           "techs": sorted(techs_detected)})
    return {"http_services": len(results), "techs": sorted(techs_detected)}


# ---------------------------------------------------------------------------
def run_easm_vuln(scan_id: int, client_id: int, params: dict) -> dict:
    """Scan vuln Nuclei sur les URLs HTTPX."""
    mark_scan_running(scan_id)
    scopes = get_client_scopes(client_id)
    targets = params.get("targets") or list({*scopes.get("domain", []), *scopes.get("ip", [])})
    severity = params.get("severity", "low,medium,high,critical")
    tags = params.get("tags")

    if not targets:
        finalize_scan(scan_id, status=ScanStatus.FAILED, error="No targets")
        return {"error": "no_targets"}

    results = pd.nuclei(targets, severity=severity, tags=tags)
    counters = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for r in results:
        info = r.get("info", {}) or {}
        sev = (info.get("severity") or "info").lower()
        counters[sev] = counters.get(sev, 0) + 1
        url = r.get("matched-at") or r.get("host") or ""
        title = info.get("name", r.get("template-id", "vuln"))
        cves = info.get("classification", {}).get("cve-id", []) or []
        upsert_finding(
            client_id=client_id, scan_id=scan_id, kind="vulnerability",
            severity=sev,
            title=title,
            description=info.get("description", "") or "",
            asset=url, source="nuclei",
            raw=r,
            iocs=([{"type": "url", "value": url}] +
                  [{"type": "cve", "value": c} for c in cves]),
            fp_parts=[str(client_id), "vuln", r.get("template-id", title), url],
        )

    finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=counters)
    return counters


# ---------------------------------------------------------------------------
def run_easm_crawl(scan_id: int, client_id: int, params: dict) -> dict:
    mark_scan_running(scan_id)
    scopes = get_client_scopes(client_id)
    targets = params.get("targets") or scopes.get("domain", [])
    if not targets:
        finalize_scan(scan_id, status=ScanStatus.FAILED, error="No targets")
        return {"error": "no_targets"}

    results = pd.katana(targets, depth=params.get("depth", 3))
    js_endpoints = [r for r in results if str(r.get("endpoint", "")).endswith(".js")]
    for r in results:
        ep = r.get("endpoint") or r.get("url")
        if not ep:
            continue
        upsert_finding(client_id=client_id, scan_id=scan_id, kind="endpoint",
                       severity=Severity.INFO.value,
                       title=ep[:512], asset=ep, source="katana",
                       raw=r, iocs=[{"type": "url", "value": ep}],
                       fp_parts=[str(client_id), "endpoint", ep])
    finalize_scan(scan_id, status=ScanStatus.COMPLETED,
                  summary={"endpoints": len(results), "js_endpoints": len(js_endpoints)})
    return {"endpoints": len(results), "js_endpoints": len(js_endpoints)}


# ---------------------------------------------------------------------------
def run_easm_cve(scan_id: int, client_id: int, params: dict) -> dict:
    """Lookup CVE par produit/tech (depuis params['products'] ou techs detectees)."""
    mark_scan_running(scan_id)
    products = params.get("products") or []
    if not products:
        finalize_scan(scan_id, status=ScanStatus.FAILED,
                      error="No products provided in params")
        return {"error": "no_products"}

    total = 0
    for product in products:
        results = pd.cvemap(product)
        total += len(results)
        for r in results:
            cve_id = r.get("cve_id") or r.get("id") or "CVE-?"
            cvss_score = (r.get("cvss_score") or
                          r.get("cvss_metrics", {}).get("cvss31", {}).get("score") or 0)
            try:
                score = float(cvss_score)
            except Exception:
                score = 0.0
            sev = ("critical" if score >= 9 else
                   "high" if score >= 7 else
                   "medium" if score >= 4 else
                   "low" if score > 0 else "info")
            upsert_finding(
                client_id=client_id, scan_id=scan_id, kind="cve",
                severity=sev,
                title=f"{cve_id} ({product})",
                description=r.get("description", "") or "",
                asset=product, source="cvemap",
                raw=r,
                iocs=[{"type": "cve", "value": cve_id}],
                fp_parts=[str(client_id), "cve", cve_id, product],
            )

    finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary={"cves": total})
    return {"cves": total}


# ---------------------------------------------------------------------------
def run_easm_osint(scan_id: int, client_id: int, params: dict) -> dict:
    """OSINT : theHarvester + SpiderFoot."""
    mark_scan_running(scan_id)
    scopes = get_client_scopes(client_id)
    domains = scopes.get("domain", [])
    summary = {"theharvester_emails": 0, "theharvester_hosts": 0,
               "spiderfoot_events": 0}

    for d in domains:
        try:
            data = th.harvest(d)
        except Exception as e:
            log.warning("theHarvester failed for %s: %s", d, e)
            continue
        for email in data.get("emails", []) or []:
            summary["theharvester_emails"] += 1
            upsert_finding(client_id=client_id, scan_id=scan_id, kind="email",
                           severity=Severity.LOW.value,
                           title=email, asset=d, source="theharvester",
                           raw={"email": email, "domain": d},
                           iocs=[{"type": "email", "value": email}],
                           fp_parts=[str(client_id), "email", email])
        for host in data.get("hosts", []) or []:
            summary["theharvester_hosts"] += 1
            upsert_finding(client_id=client_id, scan_id=scan_id, kind="subdomain",
                           severity=Severity.INFO.value,
                           title=host if isinstance(host, str) else str(host),
                           asset=str(host), source="theharvester",
                           raw={"host": host, "domain": d},
                           iocs=[{"type": "domain", "value": str(host)}],
                           fp_parts=[str(client_id), "subdomain", str(host)])

    if params.get("spiderfoot", True):
        for d in domains:
            try:
                sid = sf.start_scan(d, scan_name=f"dp-{client_id}-{d}")
                state = sf.wait_for_scan(sid, max_wait=params.get("sf_max_wait", 3600))
                if state == "FINISHED":
                    results = sf.scan_results(sid)
                    summary["spiderfoot_events"] += len(results)
                    for ev in results:
                        if not isinstance(ev, list) or len(ev) < 4:
                            continue
                        ev_type, data_field, _module, source_data = ev[1], ev[2], ev[3], ev[4]
                        upsert_finding(client_id=client_id, scan_id=scan_id,
                                       kind=f"sf:{ev_type}".lower()[:64],
                                       severity=Severity.INFO.value,
                                       title=f"{ev_type}: {str(data_field)[:200]}",
                                       asset=d, source="spiderfoot",
                                       raw={"event": ev_type, "data": data_field,
                                            "source": source_data},
                                       iocs=[],
                                       fp_parts=[str(client_id), "sf", ev_type, str(data_field)])
            except Exception as e:
                log.warning("spiderfoot failed for %s: %s", d, e)

    finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=summary)
    return summary


# ---------------------------------------------------------------------------
def run_full_recon(scan_id: int, client_id: int, params: dict) -> dict:
    """Pipeline complet EASM."""
    mark_scan_running(scan_id)
    summary = {"steps": {}}

    try:
        summary["steps"]["discovery"] = run_easm_discovery(
            _spawn_subscan(client_id, "easm_discovery"), client_id, params)
        summary["steps"]["http"] = run_easm_http(
            _spawn_subscan(client_id, "easm_http"), client_id, params)
        summary["steps"]["vuln"] = run_easm_vuln(
            _spawn_subscan(client_id, "easm_vuln"), client_id, params)
        summary["steps"]["crawl"] = run_easm_crawl(
            _spawn_subscan(client_id, "easm_crawl"), client_id, params)
        summary["steps"]["osint"] = run_easm_osint(
            _spawn_subscan(client_id, "easm_osint"), client_id, params)
        finalize_scan(scan_id, status=ScanStatus.COMPLETED, summary=summary)
    except Exception as e:
        log.exception("full_recon failed: %s", e)
        finalize_scan(scan_id, status=ScanStatus.PARTIAL, summary=summary, error=str(e))

    return summary


def _spawn_subscan(client_id: int, kind: str) -> int:
    from ..db import SessionLocal
    from ..models import Scan, ScanType, ScanStatus
    with SessionLocal() as db:
        s = Scan(client_id=client_id, kind=ScanType(kind), status=ScanStatus.PENDING,
                 parameters={"_spawned_by_full_recon": True})
        db.add(s)
        db.commit()
        db.refresh(s)
        return s.id
