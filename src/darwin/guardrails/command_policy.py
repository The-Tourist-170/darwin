"""Deterministic command policy: banned shell patterns are denied before execution."""

import re

BANNED = (
    r"\brm\s+(-\w*[rf]\w*\s*)+",  # rm with recursive/force flags in any order
    r"\bmkfs\b",
    r":\(\)\s*\{\s*:\|:&\s*\};",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bdd\s+if=",
)


def is_banned(command: str) -> bool:
    normalized = re.sub(r"\s+", " ", command)
    return any(re.search(p, normalized, re.IGNORECASE) for p in BANNED)
