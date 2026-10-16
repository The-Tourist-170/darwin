"""Native OS file operations, confined to the workspace root."""

from pathlib import Path

from langchain_core.tools import tool

from darwin.guardrails import is_safe_path
from darwin.guardrails.schemas import ListDirectoryArgs, ReadFileArgs

ROOT = str(Path.cwd().resolve())
MAX_READ_CHARS = 100_000


@tool(args_schema=ReadFileArgs)
def read_file(path: str) -> str:
    """Read a text file inside the workspace and return its contents."""
    full = Path(path).resolve()
    if not is_safe_path(str(full), ROOT):
        raise PermissionError(f"path outside workspace: {path}")
    return full.read_text()[:MAX_READ_CHARS]


@tool(args_schema=ListDirectoryArgs)
def list_directory(path: str = ".") -> str:
    """List files and directories inside the workspace."""
    full = Path(path).resolve()
    if not is_safe_path(str(full), ROOT):
        raise PermissionError(f"path outside workspace: {path}")
    return "\n".join(sorted(p.name for p in full.iterdir()))


@tool
def write_file(path: str, content: str) -> str:
    """Write text to a file inside the workspace, creating parents as needed."""
    full = Path(path).resolve()
    if not is_safe_path(str(full), ROOT):
        raise PermissionError(f"path outside workspace: {path}")
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return f"wrote {full.relative_to(ROOT)}"
