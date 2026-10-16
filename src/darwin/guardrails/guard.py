"""Input/output interception."""

from darwin.guardrails.redaction import redact

INJECTION = (
    "ignore previous instructions",
    "ignore all prior",
    "system prompt",
    "you are now",
    "do anything",
)


def sanitize_input(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in INJECTION):
        raise ValueError("possible prompt injection detected")
    return redact(text)


def sanitize_output(text: str) -> str:
    return redact(text)
