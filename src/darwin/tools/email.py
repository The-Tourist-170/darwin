"""Secure email: stdlib IMAP/SMTP, explicit credential isolation and outbound leak protection."""

import imaplib
import smtplib
from email import message_from_bytes, policy
from email.message import EmailMessage

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from darwin.core.config import config
from darwin.guardrails.redaction import redact


def _configured() -> bool:
    return bool(config.EMAIL_ADDRESS and config.EMAIL_PASSWORD and config.SMTP_HOST and config.IMAP_HOST)


def _imap() -> imaplib.IMAP4_SSL:
    mail = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    mail.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
    return mail


class ReadEmailArgs(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)


@tool(args_schema=ReadEmailArgs)
def email_read(limit: int = 5) -> str:
    """List recent emails: sender, subject, date and a short snippet."""
    if not _configured():
        return "email tools are disabled: set EMAIL_ADDRESS/EMAIL_PASSWORD/SMTP_HOST/IMAP_HOST in .env"
    mail = None
    try:
        mail = _imap()
        mail.select("INBOX")
        ids = mail.search(None, "ALL")[1][0].split()[-limit:][::-1]
        lines = []
        for mail_id in ids:
            raw = mail.fetch(mail_id, "(RFC822)")[1][0][1]
            msg = message_from_bytes(raw, policy=policy.default)  # EmailMessage: get_body works
            body_part = msg.get_body(preferencelist=("plain",)) or msg
            snippet = body_part.get_content()
            lines.append(f"from: {msg.get('From')}\nsubject: {msg.get('Subject')}\ndate: {msg.get('Date')}\n{snippet[:200]}")
        return "\n---\n".join(lines)
    except (imaplib.IMAP4.error, smtplib.SMTPException) as exc:
        return f"email access error: {exc}. If this says Invalid credentials, re-create the Gmail App Password and check IMAP is enabled (Gmail web settings -> Forwarding and POP/IMAP)."
    finally:
        if mail is not None:
            mail.logout()


class SendEmailArgs(BaseModel):
    to: str = Field(description="Recipient address")
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


@tool(args_schema=SendEmailArgs)
def email_send(to: str, subject: str, body: str) -> str:
    """Send an email. Outbound leak protection refuses bodies that look like they carry secrets."""
    if not _configured():
        return "email tools are disabled: set EMAIL_ADDRESS/EMAIL_PASSWORD/SMTP_HOST/IMAP_HOST in .env"
    if redact(body) != body:
        return (
            "Outbound leak protection: the message contains what looks like credentials, tokens or "
            "card numbers. Remove them and resend."
        )
    message = EmailMessage()
    message["To"], message["From"], message["Subject"] = to, config.EMAIL_ADDRESS, subject
    message.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, imaplib.IMAP4.error) as exc:
        return f"email send error: {exc}. If this says Invalid credentials, re-create the Gmail App Password and check IMAP is enabled (Gmail web settings -> Forwarding and POP/IMAP)."
    return f"sent to {to}"
