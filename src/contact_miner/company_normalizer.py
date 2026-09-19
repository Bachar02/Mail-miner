from __future__ import annotations

import re
from urllib.parse import urlparse


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    return value[1:-1] if value.startswith("<") and value.endswith(">") else value


def domain_from_email(email: str) -> str | None:
    normalized = normalize_email(email)
    return normalized.split("@", 1)[1] if "@" in normalized else None


def normalize_company(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" .,-")
    return cleaned or None


def company_from_domain(domain: str | None) -> str | None:
    if not domain or domain.casefold() in {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com"}:
        return None
    host = urlparse("//" + domain).hostname or domain
    return host.split(".")[0].replace("-", " ").title()
