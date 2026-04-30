"""Wrapper theHarvester via container Docker."""
from __future__ import annotations
import json
import logging
import re
from .runner import DockerRunner
from ..config import get_settings

log = logging.getLogger("tools.theharvester")
_settings = get_settings()
_image = _settings.scanner_harvester_image


def harvest(domain: str, *,
            sources: str = "crtsh,duckduckgo,bing,hackertarget,otx,rapiddns,urlscan,virustotal",
            limit: int = 500,
            timeout: int = 1800) -> dict:
    """Lance theHarvester. Retourne un dict avec hosts/emails/ips/etc."""
    cmd = ["-d", domain, "-b", sources, "-l", str(limit), "-f", "/tmp/harv.json"]
    runner = DockerRunner(network="dp_core")
    full_cmd = ["sh", "-c",
                f"theHarvester {' '.join(cmd)} >/dev/null 2>&1 ; cat /tmp/harv.json 2>/dev/null || true"]
    res = runner.run(_image, full_cmd, timeout=timeout, mem_limit="2g")
    out = res.stdout.strip()
    if not out:
        log.warning("theHarvester empty output stderr=%s", res.stderr[:500])
        return {"hosts": [], "emails": [], "ips": [], "urls": []}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", out, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"hosts": [], "emails": [], "ips": [], "urls": [], "raw": out[:5000]}
