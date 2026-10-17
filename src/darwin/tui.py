"""Terminal UI for Darwin: rich output + prompt_toolkit input bar (opencode-style)."""

import asyncio
import json
import os
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

DEV = "Ayushya Saxena"
GITHUB = "The-Tourist-170"

WORDMARK = r"""
██████╗  █████╗ ██████╗ ██╗    ██╗██╗███╗   ██╗
██╔══██╗██╔══██╗██╔══██╗██║    ██║██║████╗  ██║
██║  ██║███████║██████╔╝██║ █╗ ██║██║██╔██╗ ██║
██║  ██║██╔══██║██╔══██╗██║███╗██║██║██║╚██╗██║
██████╔╝██║  ██║██║  ██║╚███╔███╔╝██║██║ ╚████║
╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝
"""

THEMES = {
    "tokyo-night": {
        "you": "#7aa2f7", "agent": "#9ece6a", "trace": "#565f89", "result": "#7dcfff",
        "cmd": "#e0af68", "meta": "#565f89", "banner": "#7aa2f7", "border": "#9ece6a",
    },
    "dracula": {
        "you": "#bd93f9", "agent": "#50fa7b", "trace": "#6272a4", "result": "#8be9fd",
        "cmd": "#f1fa8c", "meta": "#6272a4", "banner": "#bd93f9", "border": "#50fa7b",
    },
    "catppuccin": {
        "you": "#89b4fa", "agent": "#a6e3a1", "trace": "#6c7086", "result": "#89dceb",
        "cmd": "#f9e2af", "meta": "#6c7086", "banner": "#cba6f7", "border": "#a6e3a1",
    },
    "nord": {
        "you": "#88c0d0", "agent": "#a3be8c", "trace": "#4c566a", "result": "#8fbcbb",
        "cmd": "#ebcb8b", "meta": "#4c566a", "banner": "#81a1c1", "border": "#a3be8c",
    },
    "gruvbox": {
        "you": "#83a598", "agent": "#b8bb26", "trace": "#928374", "result": "#8ec07c",
        "cmd": "#fabd2f", "meta": "#928374", "banner": "#fe8019", "border": "#b8bb26",
    },
}

current_theme = "tokyo-night"
console = Console(highlight=False)
_pt_session: PromptSession | None = None

COMMANDS = WordCompleter(
    ["/new", "/sessions", "/session ", "/themes", "/theme ", "/exit"],
    ignore_case=True,
)


def _pt_style() -> Style:
    colors = THEMES[current_theme]
    return Style.from_dict(
        {
            "you": f"bold {colors['you']}",
            "meta": f"{colors['meta']}",
            "cmd": f"bold {colors['cmd']}",
            "dialog": f"bg:{colors['meta']} {colors['you']}",
            "dialog frame.label": f"bold {colors['banner']}",
        }
    )


def set_theme(name: str) -> str:
    """Switch theme; unknown names fall back to tokyo-night."""
    global console, current_theme, _pt_session
    key = name.strip().lower()
    current_theme = key if key in THEMES else "tokyo-night"
    styles = {style: f"bold {color}" for style, color in THEMES[current_theme].items()}
    styles.update({"trace": "dim", "meta": "dim"})
    console = Console(theme=Theme(styles), highlight=False)
    _pt_session = None
    return current_theme


def show_themes() -> None:
    for name in THEMES:
        console.print(f"  {'*' if name == current_theme else ' '} {name}", style="you" if name == current_theme else "meta")


set_theme(os.getenv("DARWIN_THEME", "tokyo-night"))


def _toolbar() -> HTML:
    return HTML(
        f"<you>/new</you> <meta>·</meta> <you>/sessions</you> <meta>·</meta> "
        f"<you>/themes</you> <meta>·</meta> <you>/exit</you>"
        f"   <meta>by {DEV} · github.com/{GITHUB}</meta>"
    )


def _get_session() -> PromptSession:
    global _pt_session
    if _pt_session is None:
        _pt_session = PromptSession(
            history=InMemoryHistory(),
            style=_pt_style(),
            bottom_toolbar=_toolbar,
            completer=COMMANDS,
            complete_while_typing=True,
        )
    return _pt_session


def _clip(text, limit: int = 200) -> str:
    flat = " ".join(str(text).split())
    return flat[:limit] + ("…" if len(flat) > limit else "")


def banner(servers: list[str], mcp_tools: int, native_tools: int, session: str) -> None:
    if not sys.stdout.isatty():
        print(f"[mcp] servers: {servers or 'none'} · tools: {mcp_tools} mcp / {native_tools} native")
        return
    console.print(WORDMARK, style="banner", highlight=False)
    console.print(f"  autonomous agentic engine · phase 3 · theme {current_theme}", style="meta")
    console.print(f"  by {DEV} · github.com/{GITHUB}", style="meta")
    console.print(
        f"  servers {len(servers)} · mcp tools {mcp_tools} · native tools {native_tools}"
        f" · session {session}\n",
        style="meta",
    )


def status(label: str):
    return console.status(f"[{THEMES[current_theme]['banner']}]{label}", spinner="dots")


async def prompt_async() -> str | None:
    if not sys.stdout.isatty():
        try:
            return (await asyncio.to_thread(input, "\nyou > ")).strip()
        except EOFError:
            return None
    console.rule("[you]you[/you]", characters="─", style="trace")
    try:
        text = await _get_session().prompt_async([("class:you", "│ ❯ ")])
    except (EOFError, KeyboardInterrupt):
        return None
    finally:
        console.rule(characters="─", style="trace")
    return text.strip()


def reply(text: str) -> None:
    console.print()
    console.print(Panel(Markdown(text or " "), title="darwin", title_align="left", border_style="border"))


def trace_call(name: str, args: dict) -> None:
    console.print(f"  [trace]→ {name}[/trace] [dim]{_clip(json.dumps(args, ensure_ascii=False))}[/dim]")


def trace_result(name: str, text: str) -> None:
    console.print(f"  [result]← {name}[/result] [dim]{_clip(text)}[/dim]")


def notice(text: str) -> None:
    console.print(f"  [meta]{text}[/meta]")


async def approval_async(names: str) -> bool:
    try:
        if sys.stdout.isatty():
            answer = await _get_session().prompt_async([("class:cmd", f"  approve {names}? (y/n): ")])
        else:
            answer = await asyncio.to_thread(input, f"  approve {names}? (y/n): ")
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().lower() == "y"


async def escalation_async(payload: dict) -> dict:
    """JIT authorization prompt; returns the resume payload."""
    console.print(f"\n  [cmd]out-of-workspace access: {payload.get('tool')}[/cmd]")
    for target in payload.get("targets") or []:
        console.print(f"     target : {target}  ({payload.get('mode', 'read-only')})")
    if payload.get("intent"):
        console.print(f"     intent : {_clip(payload['intent'], 140)}")
    console.print("     [1] allow once   [2] allow for session   [3] deny")
    try:
        if sys.stdout.isatty():
            choice = await _get_session().prompt_async([("class:cmd", "     choice: ")])
        else:
            choice = await asyncio.to_thread(input, "     choice: ")
    except (EOFError, KeyboardInterrupt):
        choice = "3"
    choice = choice.strip()
    if choice == "1":
        return {"approved": True, "scope": "once"}
    if choice == "2":
        return {"approved": True, "scope": "session"}
    console.print("     [meta]denied[/meta]")
    return {"approved": False}


async def pick_theme(current: str) -> str | None:
    """Arrow-key theme picker; returns the chosen theme name or None."""
    values = [(name, name) for name in THEMES]
    if not sys.stdout.isatty():
        for index, (name, _) in enumerate(values, 1):
            print(f"  {index}. {name}")
        try:
            choice = (await asyncio.to_thread(input, "  theme # (blank cancels): ")).strip()
        except EOFError:
            return None
        return values[int(choice) - 1][0] if choice.isdigit() and 1 <= int(choice) <= len(values) else None

    dialog = radiolist_dialog(
        title="Darwin theme",
        text="↑/↓ select · Enter apply · Esc cancel",
        values=values,
        default=current,
    )
    return await asyncio.to_thread(dialog.run)


async def pick_session(rows: list[tuple[str, str, int]], current: str) -> str | None:
    """Arrow-key session picker; returns the chosen thread id or None."""
    if not rows:
        notice("no sessions yet")
        return None
    values = [(thread_id, f"{thread_id}  ·  {count} checkpoints  ·  {latest[:8]}") for thread_id, latest, count in rows]
    if not sys.stdout.isatty():
        for index, (thread_id, _) in enumerate(values, 1):
            print(f"  {index}. {thread_id}")
        try:
            choice = (await asyncio.to_thread(input, "  select # (blank cancels): ")).strip()
        except EOFError:
            return None
        return values[int(choice) - 1][0] if choice.isdigit() and 1 <= int(choice) <= len(values) else None

    dialog = radiolist_dialog(
        title="Darwin sessions",
        text="↑/↓ select · Enter switch · Esc cancel",
        values=values,
        default=current,
    )
    return await asyncio.to_thread(dialog.run)


def sessions_table(rows: list[tuple[str, str, int]]) -> None:
    table = Table(title="sessions", title_justify="left", border_style="dim", show_edge=False)
    table.add_column("thread id", style="you")
    table.add_column("latest checkpoint", style="meta")
    table.add_column("checkpoints", justify="right", style="meta")
    for thread_id, latest, count in rows:
        table.add_row(thread_id, _clip(latest, 28), str(count))
    console.print(table)
