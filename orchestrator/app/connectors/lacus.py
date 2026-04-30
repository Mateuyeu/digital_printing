"""Connecteur LACUS (capture engine Playwright + Tor + I2P).

LACUS expose une API REST sur :7100.
"""
from __future__ import annotations
import logging
import time
import requests

from ..config import get_settings

log = logging.getLogger("connectors.lacus")
_settings = get_settings()


def healthcheck() -> dict:
    if not _settings.lacus_url:
        return {"status": "disabled"}
    try:
        r = requests.get(f"{_settings.lacus_url}/", timeout=5)
        return {"status": "ok" if r.status_code == 200 else "down", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def submit_capture(url: str, *,
                    proxy: str | None = None,
                    depth: int = 1,
                    user_agent: str | None = None,
                    cookies: list | None = None,
                    headers: dict | None = None,
                    referer: str | None = None,
                    force: bool = False) -> str | None:
    """Soumet une URL pour capture. Retourne le UUID de la tache.

    proxy : 'socks5://tor:9050' pour clearnet via Tor (utilisable pour .onion).
    """
    payload = {
        "url": url,
        "depth": depth,
        "force": force,
    }
    if proxy:
        payload["proxy"] = proxy
    if user_agent:
        payload["user_agent"] = user_agent
    if cookies:
        payload["cookies"] = cookies
    if headers:
        payload["headers"] = headers
    if referer:
        payload["referer"] = referer

    try:
        r = requests.post(f"{_settings.lacus_url}/enqueue",
                          json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("uuid") or data.get("id") or (data if isinstance(data, str) else None)
    except Exception as e:
        log.warning("lacus submit error: %s", e)
        return None


def get_capture_status(uuid: str) -> dict:
    try:
        r = requests.get(f"{_settings.lacus_url}/capture_status/{uuid}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("lacus status error: %s", e)
        return {"error": str(e)}


def get_capture_result(uuid: str) -> dict:
    try:
        r = requests.get(f"{_settings.lacus_url}/capture_results/{uuid}", timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("lacus result error: %s", e)
        return {"error": str(e)}


def wait_for_capture(uuid: str, *, max_wait: int = 600, poll: int = 10) -> dict:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        status = get_capture_status(uuid)
        st = status.get("status") if isinstance(status, dict) else None
        if st in ("DONE", "ERROR", 1, 2):
            return get_capture_result(uuid)
        time.sleep(poll)
    return {"error": "timeout", "uuid": uuid}
