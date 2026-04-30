import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from .config import get_settings
from .db import init_db
from .routes import clients, scopes, scans, findings, reports, integrations

settings = get_settings()

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Initializing database schema...")
    init_db()
    log.info("Orchestrator ready - %s", settings.report_brand_name)
    yield


app = FastAPI(
    title="Digital Printing - EASM/DRPS Orchestrator",
    description="Multi-tenant FOSS-based EASM & DRPS platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/metrics", make_asgi_app())

app.include_router(clients.router, prefix="/api/v1")
app.include_router(scopes.router,  prefix="/api/v1")
app.include_router(scans.router,   prefix="/api/v1")
app.include_router(findings.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": "0.1.0", "brand": settings.report_brand_name}


@app.get("/")
def root():
    return {
        "name": settings.report_brand_name,
        "service": "EASM/DRPS Orchestrator",
        "endpoints": {
            "openapi": "/docs",
            "health": "/healthz",
            "metrics": "/metrics",
            "api": "/api/v1",
        },
    }
