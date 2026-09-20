from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .company_normalizer import company_from_domain, normalize_email
from .models import ContactCandidate, ParsedEmail

REVIEW_STATUSES = ("review", "approved", "rejected", "do-not-contact")

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS emails (id INTEGER PRIMARY KEY, message_id TEXT UNIQUE NOT NULL, date TEXT, subject TEXT, relevance_score REAL NOT NULL, relevance_reasons TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, name TEXT, email TEXT NOT NULL UNIQUE, company TEXT, role TEXT, contact_type TEXT, country TEXT, company_domain TEXT, confidence REAL NOT NULL DEFAULT 0, confidence_reasons TEXT NOT NULL DEFAULT '[]', contact_status TEXT NOT NULL DEFAULT 'review', notes TEXT, first_seen TEXT, last_seen TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE, company TEXT, position TEXT, application_type TEXT, application_year INTEGER, status TEXT, source_message_id TEXT, UNIQUE(contact_id, company, position, application_year, source_message_id));
CREATE TABLE IF NOT EXISTS evidence (id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE, message_id TEXT NOT NULL, evidence_type TEXT, evidence_text TEXT);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email); CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company); CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type); CREATE INDEX IF NOT EXISTS idx_contacts_domain ON contacts(company_domain); CREATE INDEX IF NOT EXISTS idx_contacts_confidence ON contacts(confidence);
"""

# Re-running the pipeline on the same MBOX must not duplicate provenance rows. Older databases may already
# contain duplicates, so they are removed before the unique indexes are created.
MIGRATIONS = """
DELETE FROM evidence WHERE id NOT IN (SELECT MIN(id) FROM evidence GROUP BY contact_id, message_id, evidence_type, evidence_text);
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_unique ON evidence(contact_id, message_id, evidence_type, evidence_text);
DELETE FROM applications WHERE id NOT IN (SELECT MIN(id) FROM applications GROUP BY contact_id, source_message_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_unique ON applications(contact_id, source_message_id);
CREATE INDEX IF NOT EXISTS idx_evidence_contact ON evidence(contact_id);
CREATE INDEX IF NOT EXISTS idx_applications_contact ON applications(contact_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    """SQLite store. Writes are batched: call ``commit()`` (``close()`` commits too)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self.connection.executescript(MIGRATIONS)
        self.connection.commit()

    def commit(self) -> None:
        self.connection.commit()

    def close(self) -> None:
        self.connection.commit()
        self.connection.close()

    def add_email(self, email: ParsedEmail, score: float, reasons: list[str]) -> None:
        self.connection.execute(
            "INSERT INTO emails(message_id,date,subject,relevance_score,relevance_reasons) VALUES(?,?,?,?,?) "
            "ON CONFLICT(message_id) DO UPDATE SET date=excluded.date, subject=excluded.subject, "
            "relevance_score=excluded.relevance_score, relevance_reasons=excluded.relevance_reasons",
            (email.message_id, email.date, email.subject, score, json.dumps(reasons)),
        )

    def upsert_contact(self, candidate: ContactCandidate) -> int:
        normalized = normalize_email(candidate.email)
        existing = self.connection.execute("SELECT * FROM contacts WHERE email = ?", (normalized,)).fetchone()
        timestamp = now()
        seen = candidate.seen_at or timestamp
        if existing:
            domain_company = company_from_domain(existing["company_domain"])
            # A company stated in a signature/LLM result beats one inferred from the email domain.
            company = existing["company"]
            if candidate.company and (not company or (company == domain_company and candidate.company != domain_company)):
                company = candidate.company
            merged = {
                "name": existing["name"] or candidate.name, "company": company,
                "role": existing["role"] or candidate.role, "contact_type": existing["contact_type"] or candidate.contact_type,
                "country": existing["country"] or candidate.country, "company_domain": existing["company_domain"] or candidate.company_domain,
                # Confidence and its explanation come from the strongest single observation.
                "confidence": max(existing["confidence"], candidate.confidence),
                "confidence_reasons": json.dumps(candidate.confidence_reasons) if candidate.confidence >= existing["confidence"] else existing["confidence_reasons"],
                "first_seen": min(filter(None, (existing["first_seen"], seen))),
                "last_seen": max(filter(None, (existing["last_seen"], seen))),
                "updated_at": timestamp, "id": existing["id"],
            }
            self.connection.execute("UPDATE contacts SET name=:name,company=:company,role=:role,contact_type=:contact_type,country=:country,company_domain=:company_domain,confidence=:confidence,confidence_reasons=:confidence_reasons,first_seen=:first_seen,last_seen=:last_seen,updated_at=:updated_at WHERE id=:id", merged)
            contact_id = existing["id"]
            if company != existing["company"] and existing["company"]:
                self.connection.execute("UPDATE applications SET company=? WHERE contact_id=? AND company=?", (company, contact_id, existing["company"]))
        else:
            cursor = self.connection.execute("INSERT INTO contacts(name,email,company,role,contact_type,country,company_domain,confidence,confidence_reasons,first_seen,last_seen,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (candidate.name, normalized, candidate.company, candidate.role, candidate.contact_type, candidate.country, candidate.company_domain, candidate.confidence, json.dumps(candidate.confidence_reasons), seen, seen, timestamp, timestamp))
            contact_id = cursor.lastrowid
            company = candidate.company
        for evidence_text in candidate.evidence:
            self.connection.execute("INSERT OR IGNORE INTO evidence(contact_id,message_id,evidence_type,evidence_text) VALUES(?,?,?,?)", (contact_id, candidate.source_message_id, candidate.source, evidence_text[:1000]))
        if company or candidate.position_applied_for or candidate.application_year:
            self.connection.execute(
                "INSERT INTO applications(contact_id,company,position,application_type,application_year,status,source_message_id) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(contact_id, source_message_id) DO UPDATE SET company=excluded.company, position=COALESCE(excluded.position, position), "
                "application_type=excluded.application_type, application_year=excluded.application_year, status=COALESCE(excluded.status, status)",
                (contact_id, company, candidate.position_applied_for, candidate.application_type, candidate.application_year, candidate.application_status, candidate.source_message_id),
            )
        return contact_id

    def delete_contacts(self, emails: Iterable[str]) -> int:
        removed = 0
        for email in {normalize_email(value) for value in emails}:
            removed += self.connection.execute("DELETE FROM contacts WHERE email = ?", (email,)).rowcount
        return removed

    def rows(self, table: str) -> list[sqlite3.Row]:
        if table not in {"contacts", "applications", "evidence", "emails"}:
            raise ValueError("unsupported table")
        return list(self.connection.execute(f"SELECT * FROM {table} ORDER BY id"))

    def update_status(self, contact_id: int, status: str) -> None:
        if status not in REVIEW_STATUSES:
            raise ValueError(f"unsupported status: {status}")
        self.connection.execute("UPDATE contacts SET contact_status=?, updated_at=? WHERE id=?", (status, now(), contact_id))
        self.connection.commit()

    def update_notes(self, contact_id: int, notes: str) -> None:
        self.connection.execute("UPDATE contacts SET notes=?, updated_at=? WHERE id=?", (notes or None, now(), contact_id))
        self.connection.commit()
