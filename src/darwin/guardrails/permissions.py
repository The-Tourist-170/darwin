"""Granular permission rules (allow/ask/deny) plus deterministic scope checks.

Rules live in permissions.json as "Tool(glob)" strings:
  Read(...)   read-only tools      Write(...)  mutating tools
  Bash(...)   run_shell            <name>(...) an exact tool name
deny always wins and can never be overridden by an approval.
"""

import json
import re
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path

from darwin.core.config import config
from darwin.guardrails.scope import scope

NATIVE_READ_TOOLS = {"read_file", "list_directory", "parse_document", "sandbox_containers"}
PATH_KEYS = ("path", "file_path", "filepath", "directory", "paths", "target")
PATH_RE = re.compile(r"(?<![\w.%+-])(~/[\w./@+-]+|/[\w./@+-]+)")
IGNORED_PATHS = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/random", "/dev/urandom"}


@lru_cache(maxsize=1)
def load_rules() -> dict[str, list[str]]:
    path = Path(config.PERMISSIONS_PATH)
    if not path.exists():
        return {"allow": [], "ask": [], "deny": []}
    rules = json.loads(path.read_text()).get("permissions", {})
    return {kind: rules.get(kind, []) for kind in ("allow", "ask", "deny")}


def kind_of(tool_name: str) -> str:
    if tool_name == "run_shell":
        return "Bash"
    bare = tool_name.split("__", 1)[1] if "__" in tool_name else tool_name
    if bare in NATIVE_READ_TOOLS or bare in config.READ_ONLY_MCP_TOOLS:
        return "Read"
    return "Write"


def targets(tool_name: str, args: dict) -> list[str]:
    """Absolute paths this call touches (shell commands are scanned for absolute paths)."""
    if tool_name == "run_shell":
        return [p for p in PATH_RE.findall(args.get("command", "")) if p not in IGNORED_PATHS]
    found = []
    for key, value in args.items():
        if key in PATH_KEYS:
            found += [value] if isinstance(value, str) else list(value)
    return [str(Path(p).expanduser()) for p in found]


def _glob_match(pattern: str, text: str) -> bool:
    pattern = str(Path(pattern).expanduser())
    if "**" in pattern:
        return text.startswith(pattern.split("**", 1)[0])
    return fnmatch(text, pattern)


def _rule_matches(rule: str, kind: str, tool_name: str, args: dict, paths: list[str]) -> bool:
    match = re.fullmatch(r"(\w[\w-]*)\((.*)\)", rule.strip())
    if not match:
        return False
    rule_tool, pattern = match.group(1), match.group(2)
    if rule_tool not in (kind, tool_name):
        return False
    if kind == "Bash":
        return _glob_match(pattern, args.get("command", ""))
    resolved = [str(Path(p).expanduser().resolve()) for p in paths]
    return any(_glob_match(pattern, p) for p in resolved)


def decide(tool_name: str, args: dict, session_paths: list[str] | None = None) -> tuple[str, str, list[str]]:
    """Return (allow|ask|deny, reason, targets)."""
    kind = kind_of(tool_name)
    paths = targets(tool_name, args)
    rules = load_rules()

    for rule in rules["deny"]:
        if _rule_matches(rule, kind, tool_name, args, paths):
            return "deny", f"blocked by policy rule {rule}", paths

    # Explicit ask rules win over the in-scope short-circuit (e.g. Bash(sudo *)).
    for rule in rules["ask"]:
        if _rule_matches(rule, kind, tool_name, args, paths):
            return "ask", f"rule {rule} requires approval", paths

    outside = [p for p in paths if not _in_scope(p, session_paths or [])]
    if not outside:
        return "allow", "inside workspace", paths

    for rule in rules["allow"]:
        if _rule_matches(rule, kind, tool_name, args, paths):
            return "allow", f"allowed by rule {rule}", paths

    return "ask", f"outside workspace: {', '.join(outside)}", paths


def _in_scope(path: str, session_paths: list[str]) -> bool:
    if scope.allows(path):
        return True
    resolved = Path(path).expanduser().resolve()
    return any(
        resolved == Path(p).expanduser().resolve() or Path(p).expanduser().resolve() in resolved.parents
        for p in session_paths
    )
