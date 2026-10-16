"""Document ingestion: convert PDFs, Office docs and spreadsheets to Markdown."""

from pathlib import Path

from langchain_core.tools import tool
from markitdown import MarkItDown
from pydantic import BaseModel, Field

from darwin.guardrails import is_safe_path
from darwin.tools.filesystem import ROOT, MAX_READ_CHARS

_md = MarkItDown()


class ParseDocumentArgs(BaseModel):
    path: str = Field(min_length=1, description="Path to the document to convert")


@tool(args_schema=ParseDocumentArgs)
def parse_document(path: str) -> str:
    """Convert a document (PDF, DOCX, XLSX, etc.) inside the workspace to Markdown text."""
    full = Path(path).resolve()
    if not is_safe_path(str(full), ROOT):
        raise PermissionError(f"path outside workspace: {path}")
    return _md.convert(str(full)).text_content[:MAX_READ_CHARS]
