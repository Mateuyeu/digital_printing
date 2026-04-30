from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from .models import ScopeType, ScanType, ScanStatus, Severity


class ClientCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str
    contact_email: str = ""
    description: str = ""
    misp_org_uuid: str | None = None
    thehive_org: str | None = None
    settings: dict = {}


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    contact_email: str
    description: str
    active: bool
    misp_org_uuid: str | None
    thehive_org: str | None
    settings: dict
    created_at: datetime


class ScopeIn(BaseModel):
    kind: ScopeType
    value: str
    note: str = ""
    in_scope: bool = True


class ScopeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    kind: ScopeType
    value: str
    note: str
    in_scope: bool
    created_at: datetime


class ScanRequest(BaseModel):
    kind: ScanType
    parameters: dict = {}


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    kind: ScanType
    status: ScanStatus
    celery_task_id: str | None
    parameters: dict
    summary: dict
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    scan_id: int | None
    kind: str
    severity: Severity
    title: str
    description: str
    asset: str
    source: str
    fingerprint: str
    iocs: list
    pushed_to_thehive: bool
    pushed_to_misp: bool
    first_seen: datetime
    last_seen: datetime


class ReportRequest(BaseModel):
    period_days: int = Field(default=30, ge=1, le=365)
    title: str | None = None
    include_drps: bool = True
    include_easm: bool = True
    push_pdf: bool = True


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    title: str
    period_start: datetime
    period_end: datetime
    html_path: str
    pdf_path: str
    metrics: dict
    created_at: datetime
