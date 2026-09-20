from __future__ import annotations

import json
import os
import re
from typing import Iterable, Protocol

from .company_normalizer import domain_from_email, is_noise_address, normalize_company, normalize_email
from .models import ContactCandidate, ParsedEmail

ALLOWED_TYPES = {"recruiter", "hr", "hiring_manager", "ceo", "founder", "engineer", "researcher", "professor", "manager", "employee", "other"}
MAX_SNIPPET_CHARS = 6000
_EMAIL = re.compile(r"^[\w.+'-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}$")
SYSTEM_PROMPT = (
    "You extract professional contacts from one email about internships or job applications. "
    "Only report people or recruiting mailboxes whose email address appears verbatim in the email. "
    "Use null for anything the email does not state explicitly; never guess names, roles, companies or countries. "
    "Do not report the mailbox owner (the applicant) or automated senders. "
    'Respond with a JSON object: {"contacts": [{"name", "email", "company", "role", "contact_type", "country", '
    '"company_domain", "position_applied_for", "application_type", "application_year", "evidence", "confidence"}]}. '
    "evidence is a short verbatim quote supporting the contact; confidence is between 0 and 1. "
    "Allowed contact_type values: " + ", ".join(sorted(ALLOWED_TYPES)) + "."
)


class LLMProvider(Protocol):
    def enrich(self, email: ParsedEmail, snippet: str) -> list[dict]: ...


class OpenAIProvider:
    def __init__(self, model: str):
        from openai import OpenAI

        self.model = model
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def enrich(self, email: ParsedEmail, snippet: str) -> list[dict]:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": snippet[:MAX_SNIPPET_CHARS]}],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        items = data if isinstance(data, list) else data.get("contacts", []) if isinstance(data, dict) else []
        return [item for item in items if isinstance(item, dict)]


def _text(value: object, limit: int = 200) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = " ".join(str(value).split())
    return text[:limit] if text and text.casefold() not in {"null", "none", "unknown", "n/a"} else None


def candidates_from_llm(items: Iterable[dict], message_id: str, snippet: str | None = None, owner_emails: Iterable[str] = (),
                        seen_at: str | None = None) -> list[ContactCandidate]:
    """Validate the model output. Contacts without an email, or whose email is not in the snippet, are dropped."""
    owners = {normalize_email(address) for address in owner_emails}
    haystack = (snippet or "").casefold()
    result = []
    for item in items:
        email = normalize_email(_text(item.get("email")) or "")
        if not _EMAIL.match(email) or email in owners or is_noise_address(email):
            continue
        if snippet is not None and email not in haystack:
            continue  # the model invented or altered the address
        contact_type = item.get("contact_type") if item.get("contact_type") in ALLOWED_TYPES else None
        try:
            confidence = min(max(float(item.get("confidence") or 0), 0.0), 0.95)
        except (TypeError, ValueError):
            confidence = 0.0
        try:
            year = int(item["application_year"]) if item.get("application_year") else None
        except (TypeError, ValueError):
            year = None
        evidence = item.get("evidence")
        evidence_list = [str(text)[:500] for text in evidence] if isinstance(evidence, list) else [str(evidence)[:500]] if evidence else []
        result.append(ContactCandidate(
            name=_text(item.get("name"), 80), email=email, source="llm", source_message_id=message_id,
            company=normalize_company(_text(item.get("company"))), role=_text(item.get("role")), contact_type=contact_type,
            country=_text(item.get("country"), 60), company_domain=domain_from_email(email),
            position_applied_for=_text(item.get("position_applied_for"), 120), application_type=_text(item.get("application_type"), 40),
            application_year=year if year and 1990 <= year <= 2100 else None, seen_at=seen_at,
            evidence=evidence_list, confidence=round(confidence, 2), confidence_reasons=["extracted by LLM from relevant email"],
        ))
    return result
