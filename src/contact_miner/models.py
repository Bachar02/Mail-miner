from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Gmail Takeout writes system labels in the account language.
SENT_LABELS = {"sent", "sent mail", "envoyés", "messages envoyés", "enviados", "gesendet", "inviati"}


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
    labels: list[str] = field(default_factory=list)
    delivered_to: list[str] = field(default_factory=list)
    is_bulk: bool = False

    @property
    def is_sent(self) -> bool:
        return any(label.casefold() in SENT_LABELS for label in self.labels)


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
    application_status: str | None = None
    seen_at: str | None = None
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
    contacts_in_database: int = 0
    duplicates_merged: int = 0
    owner_addresses_excluded: int = 0
    errors: int = 0
