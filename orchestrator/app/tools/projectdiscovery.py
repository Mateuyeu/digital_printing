"""Wrappers ProjectDiscovery via container Docker.
Tous les outils sortent en JSONL (-j -silent) parsable.
"""
from __future__ import annotations
import logging
from .runner import DockerRunner
from ..config import get_settings

log = logging.getLogger("tools.projectdiscovery")
_settings = get_settings()
_image = _settings.scanner_pd_image


def _runner() -> DockerRunner:
    return DockerRunner(network="dp_core")


# ---------------------------------------------------------------------------
# Subfinder - enumeration de sous-domaines passive
# ---------------------------------------------------------------------------
def subfinder(domains: list[str], *, timeout: int = 600) -> list[dict]:
    if not domains:
        return []
    domain_list = "\n".join(domains)
    cmd = ["sh", "-c", f"echo '{domain_list}' | subfinder -silent -json -all"]
    res = _runner().run(_image, cmd, timeout=timeout)
    if res.exit_code != 0:
        log.warning("subfinder exit=%s stderr=%s", res.exit_code, res.stderr[:500])
    return res.parse_jsonl()


# ---------------------------------------------------------------------------
# DNSX - resolution DNS et enrichissement
# ---------------------------------------------------------------------------
def dnsx(hosts: list[str], *, timeout: int = 600) -> list[dict]:
    if not hosts:
        return []
    host_list = "\n".join(hosts)
    cmd = ["sh", "-c", f"echo '{host_list}' | dnsx -silent -json -a -aaaa -cname -ns -mx -resp"]
    res = _runner().run(_image, cmd, timeout=timeout)
    if res.exit_code != 0:
        log.warning("dnsx exit=%s stderr=%s", res.exit_code, res.stderr[:500])
    return res.parse_jsonl()


# ---------------------------------------------------------------------------
# Naabu - port scan TCP
# ---------------------------------------------------------------------------
def naabu(targets: list[str], *, ports: str = "top-1000",
          rate: int | None = None, timeout: int = 1800) -> list[dict]:
    if not targets:
        return []
    rate = rate or _settings.naabu_rate
    target_list = "\n".join(targets)
    cmd = ["sh", "-c",
           f"echo '{target_list}' | naabu -silent -json -p {ports} -rate {rate} -retries 1"]
    res = _runner().run(_image, cmd, timeout=timeout)
    if res.exit_code != 0:
        log.warning("naabu exit=%s stderr=%s", res.exit_code, res.stderr[:500])
    return res.parse_jsonl()


# ---------------------------------------------------------------------------
# Httpx - probing HTTP, fingerprint, screenshots
# ---------------------------------------------------------------------------
def httpx(targets: list[str], *,
          threads: int | None = None,
          extra_args: list[str] | None = None,
          timeout: int = 1800) -> list[dict]:
    if not targets:
        return []
    threads = threads or _settings.httpx_threads
    target_list = "\n".join(targets)
    base_args = (
        "-silent -json -follow-redirects -status-code -title -tech-detect "
        "-server -content-length -tls-grab -ip -cdn -web-server "
        f"-threads {threads}"
    )
    extra = " ".join(extra_args or [])
    cmd = ["sh", "-c", f"echo '{target_list}' | httpx {base_args} {extra}"]
    res = _runner().run(_image, cmd, timeout=timeout)
    if res.exit_code != 0:
        log.warning("httpx exit=%s stderr=%s", res.exit_code, res.stderr[:500])
    return res.parse_jsonl()


# ---------------------------------------------------------------------------
# Nuclei - vulnerability scanner
# ---------------------------------------------------------------------------
def nuclei(targets: list[str], *,
           severity: str = "low,medium,high,critical",
           tags: str | None = None,
           rate_limit: int | None = None,
           timeout: int = 3600) -> list[dict]:
    if not targets:
        return []
    rate_limit = rate_limit or _settings.nuclei_rate_limit
    target_list = "\n".join(targets)
    args = [
        "-silent", "-jsonl",
        "-severity", severity,
        "-rate-limit", str(rate_limit),
        "-timeout", "10",
        "-no-color",
        "-disable-update-check",
        "-stats-json",
    ]
    if tags:
        args += ["-tags", tags]
    cmd = ["sh", "-c", f"echo '{target_list}' | nuclei {' '.join(args)}"]
    res = _runner().run(_image, cmd, timeout=timeout, mem_limit="4g")
    if res.exit_code != 0:
        log.warning("nuclei exit=%s stderr=%s", res.exit_code, res.stderr[:500])
    return res.parse_jsonl()


# ---------------------------------------------------------------------------
# Katana - crawler / JS endpoint discovery
# ---------------------------------------------------------------------------
def katana(targets: list[str], *,
           depth: int | None = None,
           js_crawl: bool = True,
           timeout: int = 1800) -> list[dict]:
    if not targets:
        return []
    depth = depth or _settings.katana_depth
    target_list = "\n".join(targets)
    args = ["-silent", "-jsonl", "-d", str(depth), "-c", "10", "-timeout", "10"]
    if js_crawl:
        args.append("-jc")
    cmd = ["sh", "-c", f"echo '{target_list}' | katana {' '.join(args)}"]
    res = _runner().run(_image, cmd, timeout=timeout)
    if res.exit_code != 0:
        log.warning("katana exit=%s stderr=%s", res.exit_code, res.stderr[:500])
    return res.parse_jsonl()


# ---------------------------------------------------------------------------
# Cvemap - lookup CVE par produit/vendor
# ---------------------------------------------------------------------------
def cvemap(query: str, *, timeout: int = 300) -> list[dict]:
    """query peut etre un product, vendor, ou CVE id."""
    cmd = ["cvemap", "-silent", "-json", "-q", query, "-l", "100"]
    res = _runner().run(_image, cmd, timeout=timeout)
    if res.exit_code != 0:
        log.warning("cvemap exit=%s stderr=%s", res.exit_code, res.stderr[:500])
    parsed = res.parse_jsonl()
    if not parsed and res.stdout.strip():
        try:
            import json as _json
            data = _json.loads(res.stdout)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "result" in data:
                return data["result"]
        except Exception:
            pass
    return parsed
