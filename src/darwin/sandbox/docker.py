"""Docker sandbox backend: hardened `docker run` for a curated language allowlist.

Isolation is enforced here, not by the model: the workspace is the only mount (read-only
by default), the network is off, capabilities are dropped, the rootfs is read-only with a
capped tmpfs /tmp, and no host environment variables are forwarded. The agent supplies a
language key and a command string; every structural flag is built in this module.
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from darwin.core.config import config
from darwin.guardrails import MAX_OUTPUT_CHARS, is_banned

LABEL = "darwin.sandbox=1"
IMAGES = {
    "bash": "alpine:3.20",
    "python": "python:3.12-slim",
    "node": "node:22-slim",
    "bun": "oven/bun:1",
    "go": "golang:1.23-alpine",
    "rust": "rust:1.82-slim",
    "cpp": "gcc:14",
    "java": "eclipse-temurin:21-jdk",
}
# --read-only gives every language a read-only rootfs, so each needs a writable cache in tmpfs.
# go/rust keep their toolchain off the default PATH (added only by root's profile), so set it here.
CACHE_ENV = {
    "go": {
        "PATH": "/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "GOCACHE": "/tmp/go-cache",
        "GOPATH": "/tmp/go",
        "GOMODCACHE": "/tmp/go/pkg/mod",
    },
    "rust": {
        "PATH": "/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "CARGO_HOME": "/tmp/cargo",
        "CARGO_TARGET_DIR": "/tmp/target",
    },
    "node": {"npm_config_cache": "/tmp/npm"},
    "bun": {"BUN_INSTALL_CACHE_DIR": "/tmp/bun"},
}


def available() -> bool:
    """True when the docker CLI exists and its daemon answers."""
    if not shutil.which("docker"):
        return False
    return _run(["docker", "info"], 10).returncode == 0


def _run(argv: list[str], timeout: int, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout, input=stdin)


def _sandbox_argv(language: str, command: str, name: str, writable: bool, network: bool) -> list[str]:
    workspace = str(Path(config.WORKSPACE_ROOT).expanduser().resolve())
    argv = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--name",
        name,
        "--label",
        LABEL,
        "--network",
        "bridge" if network else "none",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(config.SANDBOX_PIDS_LIMIT),
        "--memory",
        config.SANDBOX_MEMORY,
        "--cpus",
        config.SANDBOX_CPUS,
        "--read-only",
        "--tmpfs",
        "/tmp:rw,exec,size=512m",
        "--workdir",
        "/workspace",
        "-e",
        "HOME=/tmp",
    ]
    env = CACHE_ENV.get(language, {})
    for key, value in env.items():
        if key != "PATH":
            argv += ["-e", f"{key}={value}"]
    prefix = f"export PATH={env['PATH']}; " if "PATH" in env else ""
    argv += [
        "-v",
        f"{workspace}:/workspace:{'rw' if writable else 'ro'}",
        IMAGES[language],
        "sh",
        "-c",
        f"{prefix}{command}",
    ]
    return argv


def _kill(name: str) -> None:
    for verb in ("kill", "rm"):
        try:
            subprocess.run(
                ["docker", verb, *(["-f"] if verb == "rm" else []), name],
                text=True,
                capture_output=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            pass


def run(
    language: str,
    command: str,
    timeout: int,
    writable: bool = False,
    network: bool = False,
    stdin: str | None = None,
) -> str:
    """Run a command in a hardened container; timeout always tears the container down."""
    if language not in IMAGES:
        return f"unknown language '{language}'; choose one of: {', '.join(IMAGES)}"
    if is_banned(command):
        return "denied: command matches the banned-command policy"
    if not available():
        return "sandbox unavailable: docker is not installed or the daemon is not running"

    name = f"darwin-{language}-{uuid.uuid4().hex[:6]}"
    try:
        proc = _run(_sandbox_argv(language, command, name, writable, network), timeout, stdin)
    except subprocess.TimeoutExpired:
        _kill(name)
        return f"timed out after {timeout}s"
    output = (proc.stdout + proc.stderr).strip()[:MAX_OUTPUT_CHARS]
    return f"exit code: {proc.returncode}\n{output or '(no output)'}"


def list_containers() -> str:
    """Darwin-owned sandbox containers (running or exited), one JSON object per line."""
    if not available():
        return "sandbox unavailable: docker is not installed or the daemon is not running"
    proc = _run(["docker", "ps", "-a", "--filter", f"label={LABEL}", "--format", "{{json .}}"], 30)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return "no sandbox containers"
    return "\n".join(lines)


def stop(name: str) -> str:
    """Stop and remove one container, but only if Darwin owns it (carries the label)."""
    if not available():
        return "sandbox unavailable: docker is not installed or the daemon is not running"
    owned = _run(["docker", "ps", "-a", "--filter", f"label={LABEL}", "--filter", f"name=^{name}$", "-q"], 30)
    if not owned.stdout.strip():
        return f"refusing: {name} is not a Darwin sandbox container"
    _kill(name)
    return f"stopped {name}"