"""Tests de connectivite des integrations externes (paralleles)."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Depends

from ..security import require_admin
from ..connectors import thehive, cortex, misp, intelx, dehashed, ail, lacus, spiderfoot

router = APIRouter(prefix="/integrations", tags=["integrations"])

_PROBES = {
    "thehive": thehive.healthcheck,
    "cortex": cortex.healthcheck,
    "misp": misp.healthcheck,
    "spiderfoot": spiderfoot.healthcheck,
    "ail": ail.healthcheck,
    "lacus": lacus.healthcheck,
    "intelx": intelx.healthcheck,
    "dehashed": dehashed.healthcheck,
}


@router.get("/health")
def integrations_health(_u: str = Depends(require_admin)) -> dict:
    out: dict = {}
    with ThreadPoolExecutor(max_workers=len(_PROBES)) as pool:
        futures = {pool.submit(fn): name for name, fn in _PROBES.items()}
        for fut in as_completed(futures, timeout=15):
            name = futures[fut]
            try:
                out[name] = fut.result()
            except Exception as e:
                out[name] = {"status": "error", "error": str(e)[:200]}
    return out
