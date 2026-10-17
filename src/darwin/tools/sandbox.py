"""Sandbox tools: run code in isolated containers across languages."""

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from darwin.sandbox import docker, list_containers, stop as _stop
from darwin.sandbox import run as _run

LANGUAGES = tuple(docker.IMAGES)
RUNNERS = {
    "python": ("main.py", "python /tmp/main.py"),
    "node": ("main.js", "node /tmp/main.js"),
    "bun": ("main.ts", "bun /tmp/main.ts"),
    "go": ("main.go", "go run /tmp/main.go"),
    "rust": ("main.rs", "sh -c 'rustc /tmp/main.rs -o /tmp/main && /tmp/main'"),
    "cpp": ("main.cpp", "sh -c 'g++ -std=c++17 /tmp/main.cpp -o /tmp/main && /tmp/main'"),
    "java": ("Main.java", "java /tmp/Main.java"),
    "bash": ("main.sh", "sh /tmp/main.sh"),
}


class RunSandboxedArgs(BaseModel):
    language: str = Field(description=f"Runtime to use: one of {', '.join(LANGUAGES)}")
    command: str = Field(min_length=1, description="Command to run inside the sandbox")
    timeout: int = Field(default=60, ge=1, le=600, description="Timeout in seconds")
    writable: bool = Field(default=False, description="Mount the workspace read-write (default reads only)")
    network: bool = Field(default=False, description="Allow network access (default off)")


class RunCodeArgs(BaseModel):
    language: str = Field(description=f"Language of the snippet: one of {', '.join(RUNNERS)}")
    code: str = Field(min_length=1, description="Source code to execute")
    timeout: int = Field(default=60, ge=1, le=600, description="Timeout in seconds")


class StopArgs(BaseModel):
    name: str = Field(min_length=1, description="Sandbox container name to stop and remove")


@tool(args_schema=RunSandboxedArgs)
def run_sandboxed(language: str, command: str, timeout: int = 60, writable: bool = False, network: bool = False) -> str:
    """Run a command in an isolated sandbox container (workspace read-only, no network by default)."""
    return _run(language, command, timeout, writable=writable, network=network)


@tool(args_schema=RunCodeArgs)
def run_code(language: str, code: str, timeout: int = 60) -> str:
    """Write a code snippet into the sandbox and execute it, returning stdout/stderr and the exit code."""
    if language not in RUNNERS:
        return f"unsupported language '{language}'; choose one of: {', '.join(RUNNERS)}"
    filename, runner = RUNNERS[language]
    return _run(language, f"cat > /tmp/{filename} && {runner}", timeout, stdin=code)


@tool
def sandbox_containers() -> str:
    """List Darwin's sandbox containers (running or exited)."""
    return list_containers()


@tool(args_schema=StopArgs)
def sandbox_stop(name: str) -> str:
    """Stop and remove a Darwin sandbox container by name."""
    return _stop(name)