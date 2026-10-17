"""Lima backend: run commands inside a persistent VM (opt-in, never auto-started).

Lima is the fallback when Docker is unavailable: a lightweight Linux VM that sees the
workspace at /workspace and nothing else of the host. It is heavy to download, so `auto`
mode reports "not running" instead of starting one; an explicit `backend="lima"` (or
SANDBOX_BACKEND=lima) starts the VM on first use.
"""

import shutil
import subprocess
from pathlib import Path

from darwin.core.config import config
from darwin.guardrails import MAX_OUTPUT_CHARS, is_banned

VM = config.SANDBOX_VM_NAME


def available() -> bool:
    """True when the limactl CLI exists and the sandbox VM is already running."""
    if not shutil.which("limactl"):
        return False
    proc = _run(["limactl", "list", "--format", "{{.Name}} {{.Status}}"], 30)
    return any(line.split() == [VM, "Running"] for line in proc.stdout.splitlines())


def _run(argv: list[str], timeout: int, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout, input=stdin)


def _start(writable: bool) -> str:
    """Create/start the VM mounting only the workspace (Lima v2 --mount-only, v1 --set fallback)."""
    workspace = str(Path(config.WORKSPACE_ROOT).expanduser().resolve())
    try:
        version = _run(["limactl", "--version"], 30).stdout
    except subprocess.TimeoutExpired:
        return "timed out probing limactl"
    major = 1
    for token in version.replace("limactl version", "").strip().split("."):
        if token.isdigit():
            major = int(token)
            break
    if major >= 2:
        argv = ["limactl", "start", f"--name={VM}", "--tty=false", f"--mount-only={workspace}{':w' if writable else ''}"]
    else:
        argv = [
            "limactl",
            "start",
            f"--name={VM}",
            "--tty=false",
            "--set",
            f'.mounts=[{{location: "{workspace}", writable: {str(writable).lower()}}}]',
        ]
    try:
        proc = _run(argv, 600)
    except subprocess.TimeoutExpired:
        return "timed out starting the Lima VM"
    if proc.returncode != 0:
        return f"failed to start Lima VM: {proc.stderr.strip()[:MAX_OUTPUT_CHARS]}"
    return ""


def run(
    language: str,
    command: str,
    timeout: int,
    writable: bool = False,
    network: bool = False,
    stdin: str | None = None,
) -> str:
    """Run a command in the Lima VM, in a shell whose cwd is /workspace."""
    if is_banned(command):
        return "denied: command matches the banned-command policy"
    if not shutil.which("limactl"):
        return "sandbox unavailable: limactl is not installed"
    if not available():
        error = _start(writable)
        if error:
            return error

    cd = "cd /workspace && " if writable else ""
    try:
        proc = _run(["limactl", "shell", VM, "--", "sh", "-lc", f"{cd}{command}"], timeout, stdin)
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout}s"
    output = (proc.stdout + proc.stderr).strip()[:MAX_OUTPUT_CHARS]
    return f"exit code: {proc.returncode}\n{output or '(no output)'}"