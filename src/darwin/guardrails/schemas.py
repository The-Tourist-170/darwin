"""Pydantic schemas enforcing strict tool-argument validation."""

from pydantic import BaseModel, Field, field_validator


def _no_control_chars(v: str) -> str:
    if any(ord(c) < 32 for c in v):
        raise ValueError("path contains control characters")
    return v


class ReadFileArgs(BaseModel):
    path: str = Field(min_length=1, max_length=4096, description="File path to read (absolute or repo-relative)")

    _path = field_validator("path")(_no_control_chars)


class ListDirectoryArgs(BaseModel):
    path: str = Field(default=".", max_length=4096, description="Directory to list (defaults to current directory)")

    _path = field_validator("path")(_no_control_chars)
