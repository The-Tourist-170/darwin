"""Desktop notifications: osascript on macOS, stderr fallback elsewhere."""

import subprocess
import sys


def notify(title: str, message: str) -> None:
    """Show a local desktop notification so approvals work even when the user is away."""
    if sys.platform != "darwin":
        print(f"[notify] {title}: {message}", file=sys.stderr)
        return
    text = (f"{title}: {message}").replace("\\", "\\\\").replace('"', '\\"')
    result = subprocess.run(
        ["osascript", "-e", f'display notification "{text}"'], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[notify] osascript error: {result.stderr.strip()}", file=sys.stderr)
