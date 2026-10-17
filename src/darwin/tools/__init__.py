"""Darwin native tools."""

from darwin.tools.documents import parse_document
from darwin.tools.email import email_read, email_send
from darwin.tools.filesystem import list_directory, read_file, write_file
from darwin.tools.memory_tool import memory_recall, memory_save
from darwin.tools.notify_user import notify_user
from darwin.tools.sandbox import run_code, run_sandboxed, sandbox_containers, sandbox_stop
from darwin.tools.shell import run_shell

ALL_TOOLS = [
    read_file,
    write_file,
    list_directory,
    run_shell,
    run_sandboxed,
    run_code,
    sandbox_containers,
    sandbox_stop,
    parse_document,
    email_read,
    email_send,
    memory_recall,
    memory_save,
    notify_user,
]

__all__ = ["ALL_TOOLS", "run_shell", "parse_document", "notify_user"]
