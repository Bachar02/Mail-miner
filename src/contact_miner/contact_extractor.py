from __future__ import annotations

import re
from email.utils import getaddresses

from .company_normalizer import company_from_domain, domain_from_email, normalize_email
from .confidence import score_candidate
from .email_cleaner import signature_block
from .models import ContactCandidate, ParsedEmail

NOISE_LOCALPARTS = {"noreply", "no-reply", "notifications", "notification", "mailer-daemon", "donotreply", "marketing", "newsletter"}
ROLE_PATTERN = re.compile(r"(?i)\b(recruiter|recruitment|talent acquisition|hr|human resources|founder|ceo|engineer|researcher|professor|manager|responsable recrutement)\b")
NAME_PATTERN = re.compile(r"\b([A-ZÀ-ÖØ-Þ][\wÀ-ÿ'-]+(?:\s+[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'-]+){1,3})\b")


def _is_noise(email: str) -> bool:
    local = normalize_email(email).split("@", 1)[0]
    return local in NOISE_LOCALPARTS


def _candidate(address: str, source: str, message_id: str, name: str | None, evidence: list[str]) -> ContactCandidate | None:
    email = normalize_email(address)
    if not email or "@" not in email or _is_noise(email):
        return None
    domain = domain_from_email(email)
    return score_candidate(ContactCandidate(name=name, email=email, source=source, source_message_id=message_id, company_domain=domain, company=company_from_domain(domain), evidence=evidence))


def _header_candidates(email: ParsedEmail) -> list[ContactCandidate]:
    values = [email.sender, *email.to, *email.cc, *email.reply_to]
    found: list[ContactCandidate] = []
    for name, address in getaddresses(values):
        candidate = _candidate(address, "header", email.message_id, name.strip() or None, [f"header address: {address}"])
        if candidate:
            found.append(candidate)
    return found


def extract_contacts(email: ParsedEmail, cleaned_body: str | None = None) -> list[ContactCandidate]:
    body = cleaned_body or email.text_body
    results = _header_candidates(email)
    signature = signature_block(body)
    signature_addresses = getaddresses(re.findall(r"[^\s<>@]+@[^\s<>@]+", signature))
    for _, address in signature_addresses:
        name_match = NAME_PATTERN.search(signature)
        role_match = ROLE_PATTERN.search(signature)
        candidate = _candidate(address, "signature", email.message_id, name_match.group(1) if name_match else None, [signature[:500]])
        if candidate:
            candidate.role = role_match.group(1) if role_match else None
            candidate = score_candidate(candidate)
            results.append(candidate)
    for match in NAME_PATTERN.finditer(body):
        window = body[max(0, match.start() - 120):match.end() + 160]
        address_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", window)
        if address_match:
            candidate = _candidate(address_match.group(), "body", email.message_id, match.group(1), [window[:500]])
            if candidate:
                results.append(candidate)
    return results
