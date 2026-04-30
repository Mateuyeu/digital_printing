"""Tests de connectivite des integrations externes."""
from fastapi import APIRouter, Depends

from ..security import require_admin
from ..connectors import thehive, cortex, misp, intelx, dehashed, ail, lacus, spiderfoot

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/health")
def integrations_health(_u: str = Depends(require_admin)) -> dict:
    return {
        "thehive": thehive.healthcheck(),
        "cortex": cortex.healthcheck(),
        "misp": misp.healthcheck(),
        "spiderfoot": spiderfoot.healthcheck(),
        "ail": ail.healthcheck(),
        "lacus": lacus.healthcheck(),
        "intelx": intelx.healthcheck(),
        "dehashed": dehashed.healthcheck(),
    }
