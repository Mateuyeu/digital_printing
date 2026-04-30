"""Generateur de rapport HTML/PDF par client.

Le rapport agrège tous les findings sur une fenetre temporelle et produit:
  - HTML autonome (CSS inline, charts SVG)
  - PDF via wkhtmltopdf
"""
from __future__ import annotations
import logging
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select, func

from ..config import get_settings
from ..db import SessionLocal
from ..models import Client, Finding, Scope, Scan, Report, Severity

log = logging.getLogger("reports.generator")
settings = get_settings()

_TPL_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TPL_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
_SEVERITY_COLOR = {
    "critical": "#7f1d1d",
    "high": "#dc2626",
    "medium": "#f59e0b",
    "low": "#3b82f6",
    "info": "#6b7280",
}


def _gather_data(client_id: int, opts: dict) -> dict:
    period_days = int(opts.get("period_days", 30))
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)

    with SessionLocal() as db:
        client = db.get(Client, client_id)
        if not client:
            raise ValueError(f"client {client_id} not found")

        scopes = db.scalars(select(Scope).where(Scope.client_id == client_id)).all()
        findings = db.scalars(
            select(Finding).where(
                Finding.client_id == client_id,
                Finding.last_seen >= period_start,
            )
        ).all()
        scans = db.scalars(
            select(Scan).where(
                Scan.client_id == client_id,
                Scan.created_at >= period_start,
            ).order_by(Scan.created_at.desc())
        ).all()

        easm_kinds = {"subdomain", "dns_record", "open_port", "http_service",
                      "endpoint", "vulnerability", "cve", "email"}
        drps_kinds = {"leak_intelx", "leak_credential", "paste_match",
                       "darkweb_capture", "social_capture"}

        easm_findings = [f for f in findings if f.kind in easm_kinds
                         or f.kind.startswith("sf:")]
        drps_findings = [f for f in findings if f.kind in drps_kinds]

        sev_counts = Counter(f.severity.value for f in findings)
        kind_counts = Counter(f.kind for f in findings)

        top_vulns = sorted(
            [f for f in findings if f.kind == "vulnerability"
             or f.kind == "cve"],
            key=lambda x: (_SEVERITY_ORDER.index(x.severity.value)
                           if x.severity.value in _SEVERITY_ORDER else 99,
                           x.title))[:25]

        top_leaks = sorted(
            [f for f in drps_findings],
            key=lambda x: (_SEVERITY_ORDER.index(x.severity.value)
                           if x.severity.value in _SEVERITY_ORDER else 99,
                           -x.last_seen.timestamp()))[:25]

        all_ioc_count = 0
        ioc_types: Counter = Counter()
        for f in findings:
            for ioc in f.iocs or []:
                all_ioc_count += 1
                ioc_types[ioc.get("type", "unknown")] += 1

    return {
        "client": {
            "slug": client.slug, "name": client.name,
            "contact_email": client.contact_email,
            "description": client.description,
        },
        "scopes": [{"kind": s.kind.value, "value": s.value, "note": s.note} for s in scopes],
        "period": {
            "start": period_start.strftime("%Y-%m-%d %H:%M UTC"),
            "end": period_end.strftime("%Y-%m-%d %H:%M UTC"),
            "days": period_days,
        },
        "metrics": {
            "scans": len(scans),
            "findings_total": len(findings),
            "easm_findings": len(easm_findings),
            "drps_findings": len(drps_findings),
            "iocs": all_ioc_count,
            "by_severity": {k: sev_counts.get(k, 0) for k in _SEVERITY_ORDER},
            "by_kind": dict(kind_counts.most_common(15)),
            "by_ioc_type": dict(ioc_types.most_common()),
        },
        "easm_findings_count": len(easm_findings),
        "drps_findings_count": len(drps_findings),
        "scans": [{"id": s.id, "kind": s.kind.value, "status": s.status.value,
                   "started": s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "-",
                   "completed": s.completed_at.strftime("%Y-%m-%d %H:%M") if s.completed_at else "-",
                   "summary": s.summary} for s in scans],
        "top_vulns": [{"title": f.title, "asset": f.asset, "severity": f.severity.value,
                       "color": _SEVERITY_COLOR[f.severity.value],
                       "description": (f.description or "")[:300],
                       "source": f.source, "last_seen": f.last_seen.strftime("%Y-%m-%d")}
                      for f in top_vulns],
        "top_leaks": [{"title": f.title, "asset": f.asset, "severity": f.severity.value,
                       "color": _SEVERITY_COLOR[f.severity.value],
                       "description": (f.description or "")[:300],
                       "source": f.source, "last_seen": f.last_seen.strftime("%Y-%m-%d")}
                      for f in top_leaks],
        "iocs": [
            {"type": ioc.get("type"), "value": ioc.get("value"),
             "kind": f.kind, "asset": f.asset}
            for f in findings for ioc in (f.iocs or [])
        ][:500],
        "include_easm": opts.get("include_easm", True),
        "include_drps": opts.get("include_drps", True),
        "title": opts.get("title") or f"EASM/DRPS Report - {client.name}",
        "brand": settings.report_brand_name,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "severity_colors": _SEVERITY_COLOR,
        "severity_order": _SEVERITY_ORDER,
    }


def _render_html(ctx: dict) -> str:
    return _env.get_template("client_report.html").render(**ctx)


def _render_pdf(html_path: Path, pdf_path: Path) -> bool:
    try:
        from weasyprint import HTML
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return True
    except Exception as e:
        log.warning("weasyprint failed: %s", e)
        return False


def build_report(client_id: int, opts: dict) -> dict:
    ctx = _gather_data(client_id, opts)
    out_dir = Path(settings.report_output_dir) / "output" / ctx["client"]["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base = f"report-{ts}"
    html_path = out_dir / f"{base}.html"
    pdf_path = out_dir / f"{base}.pdf"

    html_path.write_text(_render_html(ctx), encoding="utf-8")
    pdf_ok = _render_pdf(html_path, pdf_path)

    with SessionLocal() as db:
        period_start = datetime.utcnow() - timedelta(days=int(opts.get("period_days", 30)))
        rep = Report(client_id=client_id, title=ctx["title"],
                     period_start=period_start,
                     period_end=datetime.utcnow(),
                     html_path=str(html_path),
                     pdf_path=str(pdf_path) if pdf_ok else "",
                     metrics=ctx["metrics"])
        db.add(rep)
        db.commit()
        db.refresh(rep)
        rep_id = rep.id

    return {"report_id": rep_id, "html": str(html_path),
            "pdf": str(pdf_path) if pdf_ok else "", "metrics": ctx["metrics"]}
