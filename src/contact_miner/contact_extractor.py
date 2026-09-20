from __future__ import annotations

import re
from email.utils import getaddresses
from typing import Iterable

from .company_normalizer import (
    company_from_domain,
    company_key,
    domain_from_email,
    is_generic_job_mailbox,
    is_noise_address,
    local_part,
    normalize_company,
    normalize_email,
)
from .confidence import score_candidate
from .email_cleaner import signature_block
from .models import ContactCandidate, ParsedEmail

EMAIL_PATTERN = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}")
_WORD = r"[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'’-]*"
_PARTICLE = r"(?:de|da|di|du|van|von|der|den|ben|bin|el|al|la|le|ibn)"
NAME_LINE = re.compile(rf"^{_WORD}(?:[ \t]+(?:{_WORD}|{_PARTICLE})){{1,4}}$")
NAME_BEFORE_ADDRESS = re.compile(rf"({_WORD}(?:[ \t]+(?:{_WORD}|{_PARTICLE})){{1,3}})[ \t]*[(<\[:,–-]?[ \t]*$")
ROLE_PATTERN = re.compile(
    r"(?i)\b(recruiter|recruitment|recruiting|talent acquisition|talent partner|sourcer|hr|human resources|"
    r"people partner|ressources humaines|chargée? de recrutement|responsable recrutement|founder|co-founder|"
    r"fondat(?:eur|rice)|ceo|cto|coo|chief \w+ officer|pdg|directeur|directrice|director|head of|team lead|"
    r"lead|manager|responsable|engineer|ingénieur|développeur|developer|scientist|researcher|chercheur|"
    r"professor|professeur|lecturer|maître de conférences|phd|intern|stagiaire|analyst|consultant|architect)\b"
)
CONTACT_TYPE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("recruiter", re.compile(r"(?i)recruit|recrut|talent|sourc")),
    ("hr", re.compile(r"(?i)\bhr\b|human resources|ressources humaines|people partner|\brh\b")),
    ("founder", re.compile(r"(?i)found|fondat")),
    ("ceo", re.compile(r"(?i)\bceo\b|chief executive|\bpdg\b|directeur général")),
    ("professor", re.compile(r"(?i)professor|professeur|lecturer|maître de conférences")),
    ("researcher", re.compile(r"(?i)research|chercheur|\bphd\b")),
    ("hiring_manager", re.compile(r"(?i)hiring manager|team lead|head of|\blead\b")),
    ("manager", re.compile(r"(?i)manager|responsable|director|directeur|directrice|\bcto\b|\bcoo\b|chief")),
    ("engineer", re.compile(r"(?i)engineer|ingénieur|developer|développeur|scientist|architect|analyst")),
)
_NOT_NAME_WORDS = {
    "hi", "hello", "dear", "hey", "bonjour", "salut", "cher", "chère", "madame", "monsieur", "regards", "best",
    "thanks", "thank", "merci", "cordialement", "team", "équipe", "equipe", "l'équipe", "the", "service",
    "department", "département", "recruitment", "recrutement", "recruiting", "recruiter", "recruiters", "careers", "hr", "rh", "talent",
    "acquisition", "sent", "from", "envoyé", "subject", "objet", "mobile", "phone", "tel", "tél", "linkedin",
    "www", "http", "https", "unsubscribe", "address", "adresse", "please", "note", "your", "our", "notre", "votre",
}
_INTERNSHIP_TERMS = re.compile(r"(?i)\b(internship|intern|stage|stagiaire|pfe|trainee|alternance|apprenti)")
_JOB_TITLE_TERMS = re.compile(r"(?i)engineer|developer|scientist|analyst|ingénieur|développeur")
_STATUS_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rejected", re.compile(r"(?i)unfortunately|not (?:to )?move forward|regret to|other candidates|malheureusement|pas donner suite|ne pas retenir|n'a pas été retenue?")),
    ("offer", re.compile(r"(?i)pleased to offer|offer letter|lettre d'offre|nous avons le plaisir de vous (?:proposer|confirmer)")),
    ("interview", re.compile(r"(?i)\binterview\b|\bentretien\b|schedule a call|technical test|test technique")),
    ("received", re.compile(r"(?i)received your application|application (?:was |has been )?received|bien reçu votre candidature|avons bien reçu")),
)
MAX_HEADER_RECIPIENTS = 15


def clean_name(value: str | None, address: str | None = None) -> str | None:
    if not value:
        return None
    name = " ".join(value.replace("\n", " ").split()).strip(" '\"<>,;:|-")
    if not name or "@" in name or any(char.isdigit() for char in name) or len(name) > 80:
        return None
    if address and name.casefold() == local_part(address):  # display name is just the mailbox, e.g. "careers"
        return None
    if "," in name:  # "Doe, John" -> "John Doe"
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}".strip()
    if {token.casefold() for token in name.split()} & _NOT_NAME_WORDS:
        return None
    return name


def _looks_like_owner_name(name: str | None, address: str) -> bool:
    """A name is trusted for an address only when it plausibly belongs to it (shared token with the local part)."""
    if not name:
        return False
    local = company_key(local_part(address))
    return any(len(token) >= 3 and company_key(token) in local for token in name.split())


def infer_contact_type(role: str | None, email: str) -> str | None:
    if role:
        for contact_type, pattern in CONTACT_TYPE_RULES:
            if pattern.search(role):
                return contact_type
    if is_generic_job_mailbox(email):
        return "hr"
    return None


def _role_from_lines(lines: Iterable[str]) -> str | None:
    for line in lines:
        if len(line) > 90 or "@" in line:
            continue
        for segment in re.split(r"\s*[|•·,]\s*|\s+[-–—]\s+|\s+(?:at|chez|@)\s+", line):
            if ROLE_PATTERN.search(segment) and len(segment.split()) <= 7:
                return segment.strip(" .")
    return None


def _company_from_lines(lines: Iterable[str], domain: str | None) -> str | None:
    domain_company = company_key(company_from_domain(domain))
    if not domain_company:
        return None
    for line in lines:
        for segment in re.split(r"\s*[|•·,]\s*|\s+[-–—]\s+|\s+(?:at|chez)\s+", line):
            key = company_key(segment)
            if key.startswith(domain_company) and len(segment.split()) <= 5 and "@" not in segment:
                return normalize_company(segment)
    return None


def application_context(email: ParsedEmail, body: str) -> dict:
    text = f"{email.subject}\n{body}"
    status = "applied" if email.is_sent else None
    if not email.is_sent:
        status = next((name for name, pattern in _STATUS_RULES if pattern.search(text)), None)
    position = None
    subject = re.sub(r"(?i)^((re|fwd?|tr|réf)\s*:\s*)+", "", email.subject).strip()
    match = re.search(r"(?i)\b(?:for|pour)\s+(?:the|a|an|le|la|un|une|l')?\s*(.{3,80}?)(?:\s+(?:position|poste|was|has|a été|at|chez)\b|[.!]|$)", subject)
    if match and (_INTERNSHIP_TERMS.search(match.group(1)) or _JOB_TITLE_TERMS.search(match.group(1))):
        position = match.group(1).strip()
    elif _INTERNSHIP_TERMS.search(subject):
        position = re.sub(r"(?i)^(application|candidature(?: spontanée)?|your application|votre candidature)\s*[-:–]\s*", "", subject).strip() or None
    year = int(email.date[:4]) if email.date and email.date[:4].isdigit() else None
    return {
        "position_applied_for": position[:120] if position else None,
        "application_type": "internship" if _INTERNSHIP_TERMS.search(text) else "job",
        "application_year": year,
        "application_status": status,
    }


def _merge(found: dict[str, ContactCandidate], candidate: ContactCandidate) -> None:
    existing = found.get(candidate.email)
    if not existing:
        found[candidate.email] = candidate
        return
    for field in ("name", "company", "role", "contact_type", "company_domain"):
        if not getattr(existing, field) and getattr(candidate, field):
            setattr(existing, field, getattr(candidate, field))
    priority = {"signature": 3, "header": 2, "body": 1}
    if priority.get(candidate.source, 0) > priority.get(existing.source, 0):
        existing.source = candidate.source
    existing.evidence.extend(text for text in candidate.evidence if text not in existing.evidence)


def owner_addresses_for(email: ParsedEmail, owner_emails: Iterable[str] = ()) -> set[str]:
    owners = {normalize_email(address) for address in owner_emails if address}
    owners.update(normalize_email(address) for address in email.delivered_to)
    if email.is_sent:
        owners.update(normalize_email(address) for _, address in getaddresses([email.sender]) if address)
    return owners


def extract_contacts(email: ParsedEmail, cleaned_body: str | None = None, owner_emails: Iterable[str] = ()) -> list[ContactCandidate]:
    body = cleaned_body if cleaned_body is not None else email.text_body
    owners = owner_addresses_for(email, owner_emails)
    context = application_context(email, body)
    found: dict[str, ContactCandidate] = {}

    def make(address: str, source: str, name: str | None, evidence: str) -> ContactCandidate | None:
        address = normalize_email(address)
        if "@" not in address or address in owners or is_noise_address(address):
            return None
        domain = domain_from_email(address)
        return ContactCandidate(
            name=clean_name(name, address), email=address, source=source, source_message_id=email.message_id,
            company=company_from_domain(domain), company_domain=domain, seen_at=email.date,
            evidence=[evidence[:500]], **context,
        )

    sender = getaddresses([email.sender])
    sender_address = normalize_email(sender[0][1]) if sender and sender[0][1] else ""
    automated_sender = not sender_address or is_noise_address(sender_address) or email.is_bulk

    # 1. Headers. Mass mailings are skipped: their recipient lists are not personal contacts.
    recipients = [*email.to, *email.cc]
    header_values = [("From", email.sender), *(("Reply-To", value) for value in email.reply_to)]
    if len(recipients) <= MAX_HEADER_RECIPIENTS and not email.is_bulk:
        header_values += [*(("To", value) for value in email.to), *(("Cc", value) for value in email.cc)]
    for header_name, value in header_values:
        for display, address in getaddresses([value]):
            candidate = make(address, "header", display, f"{header_name}: {value}")
            if candidate:
                _merge(found, candidate)

    if automated_sender:
        return [score_candidate(candidate) for candidate in found.values()]

    # 2. Signature: it belongs to the sender of the message.
    signature = signature_block(body)
    signature_lines = [line.strip() for line in signature.splitlines() if line.strip()][:10]
    if sender_address in found:
        contact = found[sender_address]
        signature_name = next((clean_name(line) for line in signature_lines[:3] if NAME_LINE.match(line) and clean_name(line)), None)
        role = _role_from_lines(signature_lines)
        company = _company_from_lines(signature_lines, contact.company_domain)
        name_confirmed = bool(signature_name) and (
            (contact.name and company_key(signature_name) == company_key(contact.name))
            or _looks_like_owner_name(signature_name, sender_address)
            or _looks_like_owner_name(contact.name, sender_address)
        )
        if signature_name and not contact.name and _looks_like_owner_name(signature_name, sender_address):
            contact.name = signature_name
        elif signature_name and contact.name and not _looks_like_owner_name(contact.name, sender_address) and _looks_like_owner_name(signature_name, sender_address):
            contact.name = signature_name  # e.g. display name "Nour Recruiter" vs signature "Nour Gharbi"
        if role or company or name_confirmed:
            contact.role = contact.role or role
            contact.company = company or contact.company
            contact.source = "signature"
            contact.evidence.append("\n".join(signature_lines)[:500])

    # 3. Addresses written in the body, named only when a name sits right before the address.
    for line in body.splitlines():
        for match in EMAIL_PATTERN.finditer(line):
            prefix = line[:match.start()]
            name_match = NAME_BEFORE_ADDRESS.search(prefix)
            name = name_match.group(1) if name_match else None
            candidate = make(match.group().rstrip("."), "body", name, line.strip())
            if not candidate:
                continue
            role_window = prefix[:name_match.start()] if name_match else prefix
            role_match = ROLE_PATTERN.search(role_window[-60:])
            if role_match and name:
                candidate.role = role_window[-60:][role_match.start():].strip(" ,:(") or None
            if candidate.email == sender_address:
                candidate.name = None  # the sender's own address in the body adds evidence only
            _merge(found, candidate)

    for candidate in found.values():
        candidate.contact_type = candidate.contact_type or infer_contact_type(candidate.role, candidate.email)
    return [score_candidate(candidate) for candidate in found.values()]
