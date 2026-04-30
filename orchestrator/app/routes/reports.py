from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from pathlib import Path

from ..db import get_db
from ..models import Client, Report
from ..schemas import ReportRequest, ReportOut
from ..security import require_admin
from ..workers import tasks as celery_tasks

router = APIRouter(prefix="/clients/{slug}/reports", tags=["reports"])


def _client_or_404(db: Session, slug: str) -> Client:
    client = db.scalar(select(Client).where(Client.slug == slug))
    if not client:
        raise HTTPException(404, "Client not found")
    return client


@router.get("", response_model=list[ReportOut])
def list_reports(slug: str, db: Session = Depends(get_db), _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    return db.scalars(
        select(Report).where(Report.client_id == client.id).order_by(desc(Report.created_at))
    ).all()


@router.post("", status_code=202)
def request_report(slug: str, payload: ReportRequest,
                   db: Session = Depends(get_db), _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    task = celery_tasks.generate_client_report.delay(client.id, payload.model_dump())
    return {"task_id": task.id, "client": slug}


@router.get("/{report_id}/pdf")
def download_pdf(slug: str, report_id: int, db: Session = Depends(get_db),
                 _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    report = db.scalar(select(Report).where(
        Report.id == report_id, Report.client_id == client.id))
    if not report or not report.pdf_path or not Path(report.pdf_path).exists():
        raise HTTPException(404, "Report PDF not found")
    return FileResponse(report.pdf_path, media_type="application/pdf",
                        filename=Path(report.pdf_path).name)


@router.get("/{report_id}/html")
def download_html(slug: str, report_id: int, db: Session = Depends(get_db),
                  _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    report = db.scalar(select(Report).where(
        Report.id == report_id, Report.client_id == client.id))
    if not report or not report.html_path or not Path(report.html_path).exists():
        raise HTTPException(404, "Report HTML not found")
    return FileResponse(report.html_path, media_type="text/html",
                        filename=Path(report.html_path).name)
