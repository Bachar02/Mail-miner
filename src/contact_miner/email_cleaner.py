from __future__ import annotations

import re
from html import unescape

_REPLY_SEPARATOR = re.compile(r"(?i)^\s*(-{2,}\s*(original message|message d'origine|forwarded message|message transféré)\s*-{2,}|_{10,})\s*$")
_REPLY_INTRO = re.compile(r"(?i)^\s*(on|le)\s.+")
_REPLY_INTRO_END = re.compile(r"(?i)(wrote|a écrit|a ecrit)\s*:\s*$")
_OUTLOOK_FROM = re.compile(r"(?i)^\s*(from|de)\s*:\s*\S")
_OUTLOOK_NEXT = re.compile(r"(?i)^\s*(sent|date|envoyé|to|à|subject|objet|cc)\s*:")
_TRACKING = re.compile(r"(?i)https?://\S+|utm_[^\s]+")
_MOBILE_FOOTER = re.compile(r"(?i)^\s*(sent from my \w+|envoyé de mon \w+|get outlook for \w+)")
_SIGNOFF = re.compile(
    r"(?i)^\s*(--|-- |best|best regards|kind regards|warm regards|regards|best wishes|sincerely|thanks|thank you|"
    r"many thanks|cheers|cordialement|bien cordialement|bien à vous|salutations|sincères salutations|merci|"
    r"merci beaucoup|bonne journée)\s*[,.!]?\s*$"
)


def html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style|head)\b.*?>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h[1-6])>", "\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    return unescape(value).replace("\xa0", " ")


def _is_reply_boundary(lines: list[str], index: int) -> bool:
    line = lines[index]
    if _REPLY_SEPARATOR.match(line):
        return True
    if _REPLY_INTRO.match(line):
        # Gmail wraps long intros: "Le lun. 4 mars 2024 à 09:00, Name <\naddr> a écrit :"
        joined = " ".join(lines[index:index + 3])
        if _REPLY_INTRO_END.search(line) or re.search(r"(?i)(wrote|a [ée]crit)\s*:", joined[:400]):
            return True
    if _OUTLOOK_FROM.match(line):
        following = [candidate for candidate in lines[index + 1:index + 4] if candidate.strip()]
        return bool(following) and bool(_OUTLOOK_NEXT.match(following[0]))
    return False


def clean_body(text: str, html: str = "") -> str:
    """Return the new part of a message: quoted replies, tracking links and footers removed."""
    value = text.strip() or html_to_text(html).strip()
    raw_lines = value.splitlines()
    lines: list[str] = []
    for index, line in enumerate(raw_lines):
        if _is_reply_boundary(raw_lines, index):
            break
        if line.lstrip().startswith(">") or _MOBILE_FOOTER.match(line):
            continue
        line = _TRACKING.sub("", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip()


def signature_block(text: str) -> str:
    """Return the lines after the last sign-off, or the last lines of the message as a fallback."""
    lines = text.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if _SIGNOFF.match(lines[index]):
            block = "\n".join(lines[index + 1:]).strip()
            if block:
                return block
    return "\n".join(lines[-6:]).strip()
