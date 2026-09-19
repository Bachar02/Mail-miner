from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .company_normalizer import normalize_email
from .models import ContactCandidate, ParsedEmail

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS emails (id INTEGER PRIMARY KEY, message_id TEXT UNIQUE NOT NULL, date TEXT, subject TEXT, relevance_score REAL NOT NULL, relevance_reasons TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, name TEXT, email TEXT NOT NULL UNIQUE, company TEXT, role TEXT, contact_type TEXT, country TEXT, company_domain TEXT, confidence REAL NOT NULL DEFAULT 0, confidence_reasons TEXT NOT NULL DEFAULT '[]', contact_status TEXT NOT NULL DEFAULT 'review', notes TEXT, first_seen TEXT, last_seen TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE, company TEXT, position TEXT, application_type TEXT, application_year INTEGER, status TEXT, source_message_id TEXT, UNIQUE(contact_id, company, position, application_year, source_message_id));
CREATE TABLE IF NOT EXISTS evidence (id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE, message_id TEXT NOT NULL, evidence_type TEXT, evidence_text TEXT);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email); CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company); CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type); CREATE INDEX IF NOT EXISTS idx_contacts_domain ON contacts(company_domain); CREATE INDEX IF NOT EXISTS idx_contacts_confidence ON contacts(confidence);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def add_email(self, email: ParsedEmail, score: float, reasons: list[str]) -> None:
        self.connection.execute("INSERT OR REPLACE INTO emails(message_id,date,subject,relevance_score,relevance_reasons) VALUES(?,?,?,?,?)", (email.message_id, email.date, email.subject, score, json.dumps(reasons)))
        self.connection.commit()

    def upsert_contact(self, candidate: ContactCandidate) -> int:
        normalized = normalize_email(candidate.email)
        existing = self.connection.execute("SELECT * FROM contacts WHERE email = ?", (normalized,)).fetchone()
        timestamp = now()
        if existing:
            merged = {
                "name": existing["name"] or candidate.name, "company": existing["company"] or candidate.company,
                "role": existing["role"] or candidate.role, "contact_type": existing["contact_type"] or candidate.contact_type,
                "country": existing["country"] or candidate.country, "company_domain": existing["company_domain"] or candidate.company_domain,
                "confidence": max(existing["confidence"], candidate.confidence),
                "confidence_reasons": json.dumps(sorted(set(json.loads(existing["confidence_reasons"]) + candidate.confidence_reasons))),
                "last_seen": timestamp, "updated_at": timestamp, "id": existing["id"],
            }
            self.connection.execute("UPDATE contacts SET name=:name,company=:company,role=:role,contact_type=:contact_type,country=:country,company_domain=:company_domain,confidence=:confidence,confidence_reasons=:confidence_reasons,last_seen=:last_seen,updated_at=:updated_at WHERE id=:id", merged)
            contact_id = existing["id"]
        else:
            self.connection.execute("INSERT INTO contacts(name,email,company,role,contact_type,country,company_domain,confidence,confidence_reasons,first_seen,last_seen,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (candidate.name, normalized, candidate.company, candidate.role, candidate.contact_type, candidate.country, candidate.company_domain, candidate.confidence, json.dumps(candidate.confidence_reasons), timestamp, timestamp, timestamp, timestamp))
            contact_id = self.connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        for evidence_text in candidate.evidence:
            self.connection.execute("INSERT INTO evidence(contact_id,message_id,evidence_type,evidence_text) VALUES(?,?,?,?)", (contact_id, candidate.source_message_id, candidate.source, evidence_text[:1000]))
        if candidate.company or candidate.position_applied_for or candidate.application_year:
            self.connection.execute("INSERT OR IGNORE INTO applications(contact_id,company,position,application_type,application_year,source_message_id) VALUES(?,?,?,?,?,?)", (contact_id, candidate.company, candidate.position_applied_for, candidate.application_type, candidate.application_year, candidate.source_message_id))
        self.connection.commit()
        return contact_id

    def rows(self, table: str) -> list[sqlite3.Row]:
        if table not in {"contacts", "applications", "evidence", "emails"}:
            raise ValueError("unsupported table")
        return list(self.connection.execute(f"SELECT * FROM {table}"))

    def update_status(self, contact_id: int, status: str) -> None:
        self.connection.execute("UPDATE contacts SET contact_status=?, updated_at=? WHERE id=?", (status, now(), contact_id))
        self.connection.commit()
