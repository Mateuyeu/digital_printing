from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, and_

from ..db import get_db
from ..models import Client, Finding, Severity
from ..schemas import FindingOut
from ..security import require_admin
from ..workers import tasks as celery_tasks

router = APIRouter(prefix="/clients/{slug}/findings", tags=["findings"])


def _client_or_404(db: Session, slug: str) -> Client:
    client = db.scalar(select(Client).where(Client.slug == slug))
    if not client:
        raise HTTPException(404, "Client not found")
    return client


@router.get("", response_model=list[FindingOut])
def list_findings(slug: str,
                  severity: Severity | None = None,
                  kind: str | None = None,
                  limit: int = Query(default=200, le=2000),
                  db: Session = Depends(get_db),
                  _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    stmt = select(Finding).where(Finding.client_id == client.id)
    conds = []
    if severity:
        conds.append(Finding.severity == severity)
    if kind:
        conds.append(Finding.kind == kind)
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.order_by(desc(Finding.last_seen)).limit(limit)
    return db.scalars(stmt).all()


@router.post("/{finding_id}/push-thehive")
def push_to_thehive(slug: str, finding_id: int, db: Session = Depends(get_db),
                    _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    finding = db.scalar(select(Finding).where(
        Finding.id == finding_id, Finding.client_id == client.id))
    if not finding:
        raise HTTPException(404, "Finding not found")
    task = celery_tasks.push_finding_to_thehive.delay(finding.id)
    return {"task_id": task.id, "finding_id": finding.id}


@router.post("/{finding_id}/push-misp")
def push_to_misp(slug: str, finding_id: int, db: Session = Depends(get_db),
                 _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    finding = db.scalar(select(Finding).where(
        Finding.id == finding_id, Finding.client_id == client.id))
    if not finding:
        raise HTTPException(404, "Finding not found")
    task = celery_tasks.push_finding_to_misp.delay(finding.id)
    return {"task_id": task.id, "finding_id": finding.id}
