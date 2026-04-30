from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from ..db import get_db
from ..models import Client, Scan, ScanStatus, AuditLog
from ..schemas import ScanRequest, ScanOut
from ..security import require_admin
from ..workers import tasks as celery_tasks

router = APIRouter(prefix="/clients/{slug}/scans", tags=["scans"])


def _client_or_404(db: Session, slug: str) -> Client:
    client = db.scalar(select(Client).where(Client.slug == slug))
    if not client:
        raise HTTPException(404, "Client not found")
    return client


@router.get("", response_model=list[ScanOut])
def list_scans(slug: str, limit: int = 50,
               db: Session = Depends(get_db), _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    return db.scalars(
        select(Scan).where(Scan.client_id == client.id).order_by(desc(Scan.created_at)).limit(limit)
    ).all()


@router.post("", response_model=ScanOut, status_code=status.HTTP_202_ACCEPTED)
def start_scan(slug: str, payload: ScanRequest, db: Session = Depends(get_db),
               user: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    scan = Scan(client_id=client.id, kind=payload.kind, parameters=payload.parameters,
                status=ScanStatus.PENDING)
    db.add(scan)
    db.commit()
    db.refresh(scan)

    task = celery_tasks.dispatch_scan.delay(scan.id)
    scan.celery_task_id = task.id
    db.add(AuditLog(actor=user, action="scan.start",
                    target=f"{slug}:{payload.kind}",
                    detail={"scan_id": scan.id, "task_id": task.id}))
    db.commit()
    db.refresh(scan)
    return scan


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(slug: str, scan_id: int, db: Session = Depends(get_db),
             _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    scan = db.scalar(select(Scan).where(Scan.id == scan_id, Scan.client_id == client.id))
    if not scan:
        raise HTTPException(404, "Scan not found")
    return scan
