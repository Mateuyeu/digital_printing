"""Utilitaire pour executer un scanner dans un container Docker ephemere.

L'orchestrator monte le socket Docker en RO ; le worker en RW pour lancer les
containers de scan. Les resultats remontent par stdout (JSON ou JSONL).
"""
from __future__ import annotations
import json
import logging
import shlex
import time
import uuid
from dataclasses import dataclass

import docker
from docker.errors import ContainerError, ImageNotFound

log = logging.getLogger("tools.runner")


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float

    def parse_jsonl(self) -> list[dict]:
        out: list[dict] = []
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


class DockerRunner:
    def __init__(self, network: str = "dp_core"):
        self.client = docker.from_env()
        self.network = network

    def run(self, image: str, cmd: str | list[str], *,
            stdin_input: str | None = None,
            timeout: int = 1800,
            mem_limit: str = "2g",
            extra_hosts: dict | None = None) -> RunResult:
        """Run image with cmd, capture stdout/stderr. Throws on docker errors only."""
        if isinstance(cmd, str):
            cmd_list = shlex.split(cmd)
        else:
            cmd_list = cmd

        log.info("docker run %s %s", image, " ".join(cmd_list))
        name = f"dp-scan-{uuid.uuid4().hex[:10]}"
        start = time.time()

        try:
            self.client.images.get(image)
        except ImageNotFound:
            log.warning("Image %s not found locally - attempting to pull", image)
            try:
                self.client.images.pull(image)
            except Exception as e:
                return RunResult(127, "", f"image not found: {e}", 0.0)

        try:
            container = self.client.containers.run(
                image=image,
                command=cmd_list,
                name=name,
                network=self.network,
                detach=True,
                stdin_open=stdin_input is not None,
                mem_limit=mem_limit,
                cap_drop=["ALL"],
                cap_add=["NET_RAW"],
                security_opt=["no-new-privileges"],
                extra_hosts=extra_hosts or {},
                stderr=True,
            )
        except ContainerError as e:
            return RunResult(e.exit_status, "", str(e), time.time() - start)

        try:
            if stdin_input is not None:
                sock = container.attach_socket(params={"stdin": 1, "stream": 1})
                sock._sock.sendall(stdin_input.encode())
                sock.close()
            try:
                result = container.wait(timeout=timeout)
                exit_code = result.get("StatusCode", -1)
            except Exception as e:
                log.warning("container wait failed: %s - killing", e)
                container.kill()
                exit_code = 124
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass

        return RunResult(exit_code, stdout, stderr, time.time() - start)
