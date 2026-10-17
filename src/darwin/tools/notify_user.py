"""notify_user: let the agent surface soft signals without blocking the run."""

import shlex

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from darwin.core.notify import notify


class NotifyArgs(BaseModel):
    message: str = Field(min_length=1, description="What to surface to the human")


@tool(args_schema=NotifyArgs)
def notify_user(message: str) -> str:
    """Show a desktop notification to the human (does not require or wait for approval)."""
    notify("Darwin", message)
    return f"notified: {message}"
