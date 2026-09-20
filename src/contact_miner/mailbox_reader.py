from __future__ import annotations

import hashlib
import logging
import mailbox
from datetime import timezone
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Iterator

from .models import ParsedEmail

logger = logging.getLogger(__name__)
_PARSER = BytesParser(policy=policy.default)


def decode_value(value: object) -> str:
    if value is None:
        return ""
    value = str(value)
    if "=?" not in value:
        return " ".join(value.split())
    try:
        return " ".join(str(make_header(decode_header(value))).split())
    except (AttributeError, LookupError, UnicodeError, ValueError, TypeError):
        return " ".join(value.split())


def _header(message: Message, name: str) -> str:
    try:
        return decode_value(message.get(name))
    except Exception:  # malformed header values must not drop the whole message
        return ""


def header_addresses(message: Message, name: str) -> list[str]:
    """Return addresses of a header as display strings (``Name <addr>``), keeping names."""
    try:
        values = [decode_value(value) for value in message.get_all(name, [])]
    except Exception:
        return []
    result = []
    for display, address in getaddresses(values):
        if "@" not in address:
            continue
        display = display.strip().strip("'\"").strip()
        result.append(f"{display} <{address}>" if display else address)
    return result


def _part_text(part: Message) -> str:
    try:
        content = part.get_content()
        return content if isinstance(content, str) else ""
    except (AttributeError, LookupError, UnicodeError, ValueError, KeyError):
        payload = part.get_payload(decode=True) or b""
        if not isinstance(payload, bytes):
            return ""
        try:
            return payload.decode(part.get_content_charset() or "utf-8", "replace")
        except LookupError:
            return payload.decode("utf-8", "replace")


def extract_bodies(message: Message) -> tuple[str, str]:
    plain: list[str] = []
    html: list[str] = []
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type == "text/plain":
            plain.append(_part_text(part))
        elif content_type == "text/html":
            html.append(_part_text(part))
    return "\n".join(plain), "\n".join(html)


def _normalize_date(raw: str) -> str | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _is_bulk(message: Message) -> bool:
    precedence = _header(message, "Precedence").casefold()
    auto_submitted = _header(message, "Auto-Submitted").casefold()
    return bool(
        _header(message, "List-Unsubscribe")
        or _header(message, "List-Id")
        or precedence in {"bulk", "list", "junk"}
        or (auto_submitted and auto_submitted != "no")
    )


def parse_message(message: Message, raw: bytes = b"") -> ParsedEmail:
    plain, html = extract_bodies(message)
    senders = header_addresses(message, "From")
    message_id = _header(message, "Message-ID")
    if not message_id:
        # Stable across runs so re-ingesting the same MBOX does not create duplicate rows.
        message_id = "generated-" + hashlib.sha256(raw or message.as_bytes()).hexdigest()[:24]
    labels = [label.strip() for label in _header(message, "X-Gmail-Labels").split(",") if label.strip()]
    return ParsedEmail(
        message_id=message_id,
        date=_normalize_date(_header(message, "Date")),
        subject=_header(message, "Subject"),
        sender=senders[0] if senders else _header(message, "From"),
        to=header_addresses(message, "To"),
        cc=header_addresses(message, "Cc"),
        reply_to=header_addresses(message, "Reply-To"),
        text_body=plain,
        html_body=html,
        references=_header(message, "References"),
        in_reply_to=_header(message, "In-Reply-To"),
        labels=labels,
        delivered_to=[address for _, address in getaddresses(header_addresses(message, "Delivered-To"))],
        is_bulk=_is_bulk(message),
    )


def iter_mbox(path: str | Path, limit: int | None = None) -> Iterator[ParsedEmail]:
    """Yield parsed messages, skipping individual messages that cannot be parsed."""
    box = mailbox.mbox(str(path), create=False)
    try:
        for index, key in enumerate(box.iterkeys()):
            if limit is not None and index >= limit:
                break
            try:
                raw = box.get_bytes(key)
                yield parse_message(_PARSER.parsebytes(raw), raw)
            except Exception as error:
                logger.warning("Skipping malformed message #%s: %s", index, error)
    finally:
        box.close()
