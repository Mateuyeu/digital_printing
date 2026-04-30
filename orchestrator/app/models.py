from datetime import datetime
from enum import Enum
from sqlalchemy import (
    String, Text, Integer, Boolean, DateTime, ForeignKey, JSON, Enum as SAEnum,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class ScopeType(str, Enum):
    DOMAIN = "domain"
    IP = "ip"
    CIDR = "cidr"
    ASN = "asn"
    KEYWORD = "keyword"
    EMAIL = "email"
    BRAND = "brand"
    EXECUTIVE = "executive"
    SOCIAL_HANDLE = "social_handle"
    CRYPTO_WALLET = "crypto_wallet"


class ScanType(str, Enum):
    EASM_DISCOVERY = "easm_discovery"           # subfinder + dnsx + naabu
    EASM_HTTP = "easm_http"                       # httpx
    EASM_VULN = "easm_vuln"                       # nuclei
    EASM_CRAWL = "easm_crawl"                     # katana
    EASM_CVE = "easm_cve"                         # cvemap
    EASM_OSINT = "easm_osint"                     # spiderfoot + theharvester
    DRPS_LEAKS = "drps_leaks"                     # intelx + dehashed
    DRPS_AIL = "drps_ail"                         # AIL framework
    DRPS_DARKWEB = "drps_darkweb"                 # LACUS via Tor/I2P
    DRPS_SOCIAL = "drps_social"                   # social monitoring via AIL/LACUS
    FULL_RECON = "full_recon"                     # pipeline complet


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Client(Base):
    """Tenant. Toutes les donnees sont scoppees par client_id."""
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    misp_org_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    thehive_org: Mapped[str | None] = mapped_column(String(64), nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scopes: Mapped[list["Scope"]] = relationship(back_populates="client", cascade="all,delete-orphan")
    scans: Mapped[list["Scan"]] = relationship(back_populates="client", cascade="all,delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="client", cascade="all,delete-orphan")


class Scope(Base):
    """Element de scope (domaine, IP, mot-cle, etc) par client."""
    __tablename__ = "scopes"
    __table_args__ = (
        UniqueConstraint("client_id", "kind", "value", name="uq_scope_client_kind_value"),
        Index("ix_scope_client_kind", "client_id", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[ScopeType] = mapped_column(SAEnum(ScopeType, native_enum=False, length=32), nullable=False)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    in_scope: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client: Mapped["Client"] = relationship(back_populates="scopes")


class Scan(Base):
    """Execution d'un scan ou pipeline pour un client."""
    __tablename__ = "scans"
    __table_args__ = (Index("ix_scan_client_status", "client_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[ScanType] = mapped_column(SAEnum(ScanType, native_enum=False, length=32), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(SAEnum(ScanStatus, native_enum=False, length=16),
                                               default=ScanStatus.PENDING)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client: Mapped["Client"] = relationship(back_populates="scans")
    findings: Mapped[list["Finding"]] = relationship(back_populates="scan", cascade="all,delete-orphan")


class Finding(Base):
    """Resultat unitaire (asset decouvert, vulnerabilite, fuite)."""
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_finding_client_kind", "client_id", "kind"),
        Index("ix_finding_severity", "severity"),
        UniqueConstraint("client_id", "kind", "fingerprint", name="uq_finding_dedup"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scans.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[Severity] = mapped_column(SAEnum(Severity, native_enum=False, length=16),
                                               default=Severity.INFO)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    asset: Mapped[str] = mapped_column(String(512), default="")
    source: Mapped[str] = mapped_column(String(64), default="")
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    iocs: Mapped[list] = mapped_column(JSON, default=list)
    pushed_to_thehive: Mapped[bool] = mapped_column(Boolean, default=False)
    pushed_to_misp: Mapped[bool] = mapped_column(Boolean, default=False)
    thehive_alert_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    misp_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client: Mapped["Client"] = relationship(back_populates="findings")
    scan: Mapped["Scan | None"] = relationship(back_populates="findings")


class Report(Base):
    """Rapport genere pour un client (PDF/HTML)."""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    html_path: Mapped[str] = mapped_column(String(1024), default="")
    pdf_path: Mapped[str] = mapped_column(String(1024), default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit trail (qui a fait quoi)."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str] = mapped_column(String(255), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
