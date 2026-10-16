"""Session-scoped filesystem allowlist, shared by the tools and the permission gate."""

from pathlib import Path

from darwin.core.config import config


class SessionScope:
    """Directories the session may touch. Starts at the workspace root only."""

    def __init__(self) -> None:
        self.roots: list[Path] = [Path(config.WORKSPACE_ROOT).expanduser().resolve()]
        self.ephemeral: list[Path] = []

    def allows(self, path: str) -> bool:
        resolved = Path(path).expanduser().resolve()
        return any(resolved == root or root in resolved.parents for root in self.roots + self.ephemeral)

    def add(self, path: str, persistent: bool = True) -> None:
        resolved = Path(path).expanduser().resolve()
        target = self.roots if persistent else self.ephemeral
        if resolved not in target:
            target.append(resolved)

    def clear_ephemeral(self) -> None:
        self.ephemeral.clear()


scope = SessionScope()
