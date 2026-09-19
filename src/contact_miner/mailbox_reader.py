from __future__ import annotations

import mailbox
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Iterator

from .models import ParsedEmail


def decode_value(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (AttributeError, LookupError, UnicodeError, ValueError):
        return value.encode("utf-8", "replace").decode("utf-8", "replace").strip()


def header_addresses(message: Message, name: str) -> list[str]:
    return [address for _, address in getaddresses(message.get_all(name, [])) if address]


def _part_text(part: Message) -> str:
    try:
        content = part.get_content()
        return content if isinstance(content, str) else ""
    except (LookupError, UnicodeError, ValueError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode(part.get_content_charset() or "utf-8", "replace")


def extract_bodies(message: Message) -> tuple[str, str]:
    plain: list[str] = []
    html: list[str] = []
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        text = _part_text(part)
        if content_type == "text/plain":
            plain.append(text)
        elif content_type == "text/html":
            html.append(text)
    return "\n".join(plain), "\n".join(html)


def parse_message(message: Message) -> ParsedEmail:
    plain, html = extract_bodies(message)
    date = None
    if message.get("Date"):
        try:
            date = parsedate_to_datetime(message.get("Date")).isoformat()
        except (TypeError, ValueError, OverflowError):
            date = decode_value(message.get("Date"))
    return ParsedEmail(
        message_id=decode_value(message.get("Message-ID")) or f"generated-{id(message)}",
        date=date,
        subject=decode_value(message.get("Subject")),
        sender=decode_value(message.get("From")),
        to=header_addresses(message, "To"),
        cc=header_addresses(message, "Cc"),
        reply_to=header_addresses(message, "Reply-To"),
        text_body=plain,
        html_body=html,
        references=decode_value(message.get("References")),
        in_reply_to=decode_value(message.get("In-Reply-To")),
    )


def iter_mbox(path: str | Path, limit: int | None = None) -> Iterator[ParsedEmail]:
    box = mailbox.mbox(str(path), factory=None, create=False)
    try:
        for index, raw in enumerate(box):
            if limit is not None and index >= limit:
                break
            try:
                yield parse_message(raw)
            except Exception:
                continue
    finally:
        box.close()
