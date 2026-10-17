"""Sandbox: isolated multi-runtime execution (Docker by default, Lima VMs opt-in)."""

from darwin.core.config import config
from darwin.sandbox import docker, lima


def resolve(backend: str | None = None) -> str:
    """Pick the backend: explicit request, else config, else docker when healthy."""
    choice = backend or config.SANDBOX_BACKEND
    if choice in ("docker", "lima"):
        return choice
    return "docker" if docker.available() else "lima"


def run(
    language: str,
    command: str,
    timeout: int,
    writable: bool = False,
    network: bool = False,
    backend: str | None = None,
    stdin: str | None = None,
) -> str:
    """Execute a command in the sandbox, delegating to the resolved backend."""
    if language not in docker.IMAGES:
        return f"unknown language '{language}'; choose one of: {', '.join(docker.IMAGES)}"
    if resolve(backend) == "lima":
        return lima.run(language, command, timeout, writable, network, stdin)
    return docker.run(language, command, timeout, writable, network, stdin)


def list_containers() -> str:
    return docker.list_containers()


def stop(name: str) -> str:
    return docker.stop(name)