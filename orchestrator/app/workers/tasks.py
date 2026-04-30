"""Tasks Celery : dispatch des scans, push SOAR, generation rapports."""
from __future__ import annotations
import logging
from celery import Celery
from celery.schedules import crontab
from datetime import datetime
from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Scan, ScanStatus, ScanType, Finding, Client
from . import easm as easm_w
from . import drps as drps_w
from .utils import finalize_scan
from ..connectors import thehive as th_conn
from ..connectors import misp as misp_conn

settings = get_settings()
log = logging.getLogger("celery.tasks")

celery_app = Celery(
    "digital_printing",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
    worker_max_tasks_per_child=50,
    task_default_queue="easm",
    task_routes={
        "tasks.dispatch_scan": {"queue": "easm"},
        "tasks.push_finding_to_thehive": {"queue": "easm"},
        "tasks.push_finding_to_misp": {"queue": "easm"},
        "tasks.generate_client_report": {"queue": "reports"},
        "tasks.scheduled_drps_sweep": {"queue": "drps"},
        "tasks.scheduled_easm_recon": {"queue": "easm"},
    },
)

_DISPATCHER = {
    ScanType.EASM_DISCOVERY: easm_w.run_easm_discovery,
    ScanType.EASM_HTTP: easm_w.run_easm_http,
    ScanType.EASM_VULN: easm_w.run_easm_vuln,
    ScanType.EASM_CRAWL: easm_w.run_easm_crawl,
    ScanType.EASM_CVE: easm_w.run_easm_cve,
    ScanType.EASM_OSINT: easm_w.run_easm_osint,
    ScanType.DRPS_LEAKS: drps_w.run_drps_leaks,
    ScanType.DRPS_AIL: drps_w.run_drps_ail,
    ScanType.DRPS_DARKWEB: drps_w.run_drps_darkweb,
    ScanType.DRPS_SOCIAL: drps_w.run_drps_social,
    ScanType.FULL_RECON: easm_w.run_full_recon,
}


@celery_app.task(name="tasks.dispatch_scan", bind=True, max_retries=2)
def dispatch_scan(self, scan_id: int) -> dict:
    with SessionLocal() as db:
        scan = db.get(Scan, scan_id)
        if not scan:
            return {"error": "scan_not_found", "scan_id": scan_id}
        kind = scan.kind
        client_id = scan.client_id
        params = scan.parameters or {}

    log.info("Dispatching scan_id=%s kind=%s client_id=%s", scan_id, kind, client_id)
    fn = _DISPATCHER.get(kind)
    if not fn:
        finalize_scan(scan_id, status=ScanStatus.FAILED,
                      error=f"unknown scan kind {kind}")
        return {"error": "unknown_kind", "kind": kind.value}

    try:
        result = fn(scan_id, client_id, params)
        if params.get("auto_push_thehive"):
            push_recent_findings_to_thehive.delay(scan_id)
        if params.get("auto_push_misp"):
            push_recent_findings_to_misp.delay(scan_id)
        return result
    except Exception as e:
        log.exception("scan failed")
        finalize_scan(scan_id, status=ScanStatus.FAILED, error=str(e))
        raise self.retry(exc=e, countdown=60)


@celery_app.task(name="tasks.push_finding_to_thehive")
def push_finding_to_thehive(finding_id: int) -> dict:
    with SessionLocal() as db:
        f = db.get(Finding, finding_id)
        if not f:
            return {"error": "not_found"}
        client = db.get(Client, f.client_id)
        slug = client.slug if client else f"client-{f.client_id}"
        finding_dict = {
            "kind": f.kind, "title": f.title, "description": f.description,
            "asset": f.asset, "source": f.source, "severity": f.severity.value,
            "fingerprint": f.fingerprint, "iocs": f.iocs,
        }
    alert_id = th_conn.create_alert(client_slug=slug, finding=finding_dict)
    if alert_id:
        with SessionLocal() as db:
            f = db.get(Finding, finding_id)
            f.pushed_to_thehive = True
            f.thehive_alert_id = alert_id
            db.commit()
    return {"alert_id": alert_id}


@celery_app.task(name="tasks.push_finding_to_misp")
def push_finding_to_misp(finding_id: int) -> dict:
    with SessionLocal() as db:
        f = db.get(Finding, finding_id)
        if not f:
            return {"error": "not_found"}
        client = db.get(Client, f.client_id)
        slug = client.slug if client else f"client-{f.client_id}"
        finding_dict = {
            "kind": f.kind, "title": f.title, "description": f.description,
            "asset": f.asset, "source": f.source, "severity": f.severity.value,
            "fingerprint": f.fingerprint, "iocs": f.iocs,
        }
    event_uuid = misp_conn.push_event(client_slug=slug, finding=finding_dict)
    if event_uuid:
        with SessionLocal() as db:
            f = db.get(Finding, finding_id)
            f.pushed_to_misp = True
            f.misp_event_id = event_uuid
            db.commit()
    return {"event_uuid": event_uuid}


@celery_app.task(name="tasks.push_recent_findings_to_thehive")
def push_recent_findings_to_thehive(scan_id: int) -> dict:
    with SessionLocal() as db:
        ids = [f.id for f in db.scalars(
            select(Finding).where(
                Finding.scan_id == scan_id, Finding.pushed_to_thehive == False  # noqa: E712
            )).all()]
    for fid in ids:
        push_finding_to_thehive.delay(fid)
    return {"queued": len(ids)}


@celery_app.task(name="tasks.push_recent_findings_to_misp")
def push_recent_findings_to_misp(scan_id: int) -> dict:
    with SessionLocal() as db:
        ids = [f.id for f in db.scalars(
            select(Finding).where(
                Finding.scan_id == scan_id, Finding.pushed_to_misp == False  # noqa: E712
            )).all()]
    for fid in ids:
        push_finding_to_misp.delay(fid)
    return {"queued": len(ids)}


@celery_app.task(name="tasks.generate_client_report")
def generate_client_report(client_id: int, opts: dict) -> dict:
    from ..reports.generator import build_report
    return build_report(client_id, opts)


@celery_app.task(name="tasks.scheduled_easm_recon")
def scheduled_easm_recon() -> dict:
    """Tache periodique : lancer FULL_RECON pour tous les clients actifs."""
    with SessionLocal() as db:
        clients = db.scalars(select(Client).where(Client.active == True)).all()  # noqa: E712
        results = []
        for c in clients:
            scan = Scan(client_id=c.id, kind=ScanType.FULL_RECON,
                        status=ScanStatus.PENDING,
                        parameters={"_scheduled": True, "auto_push_thehive": True,
                                    "auto_push_misp": True})
            db.add(scan)
            db.commit()
            db.refresh(scan)
            dispatch_scan.delay(scan.id)
            results.append({"client": c.slug, "scan_id": scan.id})
        return {"scheduled": results}


@celery_app.task(name="tasks.scheduled_drps_sweep")
def scheduled_drps_sweep() -> dict:
    """Tache periodique : sweep DRPS_LEAKS + DRPS_AIL pour tous les clients."""
    with SessionLocal() as db:
        clients = db.scalars(select(Client).where(Client.active == True)).all()  # noqa: E712
        results = []
        for c in clients:
            for kind in (ScanType.DRPS_LEAKS, ScanType.DRPS_AIL):
                scan = Scan(client_id=c.id, kind=kind,
                            status=ScanStatus.PENDING,
                            parameters={"_scheduled": True,
                                        "auto_push_thehive": True,
                                        "auto_push_misp": True})
                db.add(scan)
                db.commit()
                db.refresh(scan)
                dispatch_scan.delay(scan.id)
                results.append({"client": c.slug, "kind": kind.value,
                                "scan_id": scan.id})
        return {"scheduled": results}


celery_app.conf.beat_schedule = {
    "easm-weekly": {
        "task": "tasks.scheduled_easm_recon",
        "schedule": crontab(day_of_week="sun", hour=2, minute=0),
    },
    "drps-daily": {
        "task": "tasks.scheduled_drps_sweep",
        "schedule": crontab(hour=4, minute=0),
    },
}
