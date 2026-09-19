from __future__ import annotations

import re
from html import unescape


_REPLY_MARKERS = re.compile(r"(?im)^\s*(on .+ wrote:|le .+ a écrit :|from:|de :|-----original message-----)\s*$")
_TRACKING = re.compile(r"(?i)https?://\S+|utm_[^\s]+")


def html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    return unescape(re.sub(r"<[^>]+>", " ", value))


def clean_body(text: str, html: str = "") -> str:
    value = text.strip() or html_to_text(html).strip()
    lines: list[str] = []
    for line in value.splitlines():
        if _REPLY_MARKERS.match(line):
            break
        if line.lstrip().startswith(">"):
            continue
        line = _TRACKING.sub("", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip()


def signature_block(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^\s*(--|best regards|kind regards|sincerely|cordialement|bien cordialement)\s*$", line, re.I):
            return "\n".join(lines[index + 1:]).strip()
    return "\n".join(lines[-8:]).strip()
