"""Native OS file operations, confined to the workspace root."""

from pathlib import Path

from langchain_core.tools import tool

from darwin.core.config import config
from darwin.guardrails.schemas import ListDirectoryArgs, ReadFileArgs
from darwin.guardrails.scope import scope

ROOT = config.WORKSPACE_ROOT
MAX_READ_CHARS = 100_000


@tool(args_schema=ReadFileArgs)
def read_file(path: str) -> str:
    """Read a text file inside the workspace and return its contents."""
    full = Path(path).expanduser().resolve()
    if not scope.allows(str(full)):
        raise PermissionError(f"path outside workspace: {path} (escalate via the permission prompt)")
    return full.read_text()[:MAX_READ_CHARS]


@tool(args_schema=ListDirectoryArgs)
def list_directory(path: str = ".") -> str:
    """List files and directories inside the workspace."""
    full = Path(path).expanduser().resolve()
    if not scope.allows(str(full)):
        raise PermissionError(f"path outside workspace: {path} (escalate via the permission prompt)")
    return "\n".join(sorted(p.name for p in full.iterdir()))


@tool
def write_file(path: str, content: str) -> str:
    """Write text to a file inside the workspace, creating parents as needed."""
    full = Path(path).expanduser().resolve()
    if not scope.allows(str(full)):
        raise PermissionError(f"path outside workspace: {path} (escalate via the permission prompt)")
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return f"wrote {full}"
