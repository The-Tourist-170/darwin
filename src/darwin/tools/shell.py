"""Sandboxed shell: subprocess.run with timeout, exit-code check and truncation."""

import subprocess

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from darwin.guardrails import is_banned

MAX_OUTPUT_CHARS = 8_000


class RunShellArgs(BaseModel):
    command: str = Field(min_length=1, description="Shell command to run")
    timeout: int = Field(default=30, ge=1, le=120, description="Timeout in seconds")


@tool(args_schema=RunShellArgs)
def run_shell(command: str, timeout: int = 30) -> str:
    """Run a shell command and return stdout/stderr plus the exit code."""
    if is_banned(command):
        return "denied: command matches the banned-command policy"
    try:
        proc = subprocess.run(command, shell=True, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout}s"
    output = (proc.stdout + proc.stderr).strip()[:MAX_OUTPUT_CHARS]
    return f"exit code: {proc.returncode}\n{output or '(no output)'}"
