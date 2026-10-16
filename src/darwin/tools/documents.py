"""Document ingestion: convert PDFs, Office docs and spreadsheets to Markdown."""

from pathlib import Path

from langchain_core.tools import tool
from markitdown import MarkItDown
from pydantic import BaseModel, Field

from darwin.guardrails.scope import scope
from darwin.tools.filesystem import MAX_READ_CHARS

_md = MarkItDown()


class ParseDocumentArgs(BaseModel):
    path: str = Field(min_length=1, description="Path to the document to convert")


@tool(args_schema=ParseDocumentArgs)
def parse_document(path: str) -> str:
    """Convert a document (PDF, DOCX, XLSX, etc.) inside the workspace to Markdown text."""
    full = Path(path).expanduser().resolve()
    if not scope.allows(str(full)):
        raise PermissionError(f"path outside workspace: {path} (escalate via the permission prompt)")
    return _md.convert(str(full)).text_content[:MAX_READ_CHARS]
