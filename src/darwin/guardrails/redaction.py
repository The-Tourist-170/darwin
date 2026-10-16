"""PII and secret redaction: strip sensitive text before it reaches the model."""

import re

REDACT = re.compile(
    r"(?i)"
    r"(api[_-]?key|secret|token|password|bearer|aws_access_key_id)\s*[:=]\s*\S+"
    r"|AKIA[0-9A-Z]{16}"  # AWS access key
    r"|-----BEGIN[^-]*PRIVATE KEY-----[\s\S]*?-----END[^-]*PRIVATE KEY-----"  # private keys
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"  # JWT
    r"|\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"  # card-like numbers
    r"|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"  # emails
)


def redact(text: str) -> str:
    return REDACT.sub("[REDACTED]", text)
