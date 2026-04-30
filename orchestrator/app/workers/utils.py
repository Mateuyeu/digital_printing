"""Helpers communs aux workers."""
from __future__ import annotations
import hashlib
import logging
from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from ..db import SessionLocal
from ..models import Client, Scope, Finding, Severity, ScanStatus, Scan

log = logging.getLogger("workers.utils")


def fingerprint(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8", errors="ignore"))
        h.update(b"\x00")
    return h.hexdigest()[:48]


def get_client_scopes(client_id: int) -> dict[str, list[str]]:
    """Retourne les scopes par type pour un client."""
    out: dict[str, list[str]] = {}
    with SessionLocal() as db:
        rows = db.scalars(select(Scope).where(Scope.client_id == client_id, Scope.in_scope == True)).all()  # noqa: E712
        for r in rows:
            out.setdefault(r.kind.value, []).append(r.value)
    return out


def upsert_finding(*, client_id: int, scan_id: int | None,
                   kind: str, severity: str, title: str,
                   description: str = "", asset: str = "", source: str = "",
                   raw: dict | None = None,
                   iocs: list[dict] | None = None,
                   fp_parts: Iterable[str] | None = None) -> int:
    """Insere ou met a jour un finding (deduplique sur fingerprint)."""
    fp = fingerprint(*(fp_parts or [str(client_id), kind, asset, title]))
    sev_value = severity if severity in [s.value for s in Severity] else Severity.INFO.value

    with SessionLocal() as db:
        existing = db.scalar(select(Finding).where(
            Finding.client_id == client_id, Finding.kind == kind, Finding.fingerprint == fp))
        if existing:
            existing.last_seen = datetime.utcnow()
            existing.scan_id = scan_id or existing.scan_id
            if raw:
                existing.raw = raw
            db.commit()
            return existing.id
        f = Finding(client_id=client_id, scan_id=scan_id, kind=kind,
                    severity=sev_value, title=title[:512],
                    description=description, asset=asset[:512], source=source[:64],
                    fingerprint=fp, raw=raw or {}, iocs=iocs or [])
        db.add(f)
        db.commit()
        db.refresh(f)
        return f.id


def mark_scan_running(scan_id: int) -> None:
    with SessionLocal() as db:
        scan = db.get(Scan, scan_id)
        if scan:
            scan.status = ScanStatus.RUNNING
            scan.started_at = datetime.utcnow()
            db.commit()


def finalize_scan(scan_id: int, *, status: ScanStatus, summary: dict | None = None,
                  error: str | None = None) -> None:
    with SessionLocal() as db:
        scan = db.get(Scan, scan_id)
        if not scan:
            return
        scan.status = status
        scan.completed_at = datetime.utcnow()
        if summary:
            scan.summary = summary
        if error:
            scan.error = error[:5000]
        db.commit()


def get_client_slug(client_id: int) -> str:
    with SessionLocal() as db:
        c = db.get(Client, client_id)
        return c.slug if c else f"client-{client_id}"
