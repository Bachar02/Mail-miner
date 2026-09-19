from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ParsedEmail:
    message_id: str
    date: str | None
    subject: str
    sender: str
    to: list[str]
    cc: list[str]
    reply_to: list[str]
    text_body: str
    html_body: str
    references: str = ""
    in_reply_to: str = ""


@dataclass
class RelevanceResult:
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class ContactCandidate:
    name: str | None
    email: str
    source: str
    source_message_id: str
    company: str | None = None
    role: str | None = None
    contact_type: str | None = None
    country: str | None = None
    company_domain: str | None = None
    position_applied_for: str | None = None
    application_type: str | None = None
    application_year: int | None = None
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    confidence_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class PipelineStats:
    emails_processed: int = 0
    relevant_emails: int = 0
    candidate_contacts: int = 0
    contacts_created: int = 0
    duplicates_merged: int = 0
    errors: int = 0
