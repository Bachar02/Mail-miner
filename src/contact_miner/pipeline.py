from __future__ import annotations

import logging
from pathlib import Path

from .company_normalizer import domain_from_email
from .contact_extractor import extract_contacts
from .database import Database
from .email_cleaner import clean_body
from .mailbox_reader import iter_mbox
from .models import PipelineStats
from .relevance import score_email

logger = logging.getLogger(__name__)


def run_deterministic(mbox_path: str | Path, db: Database, threshold: float = 2.0, limit: int | None = None) -> PipelineStats:
    stats = PipelineStats()
    for email in iter_mbox(mbox_path, limit):
        stats.emails_processed += 1
        try:
            relevance = score_email(email)
            db.add_email(email, relevance.score, relevance.reasons)
            if relevance.score < threshold:
                continue
            stats.relevant_emails += 1
            candidates = extract_contacts(email, clean_body(email.text_body, email.html_body))
            stats.candidate_contacts += len(candidates)
            for candidate in candidates:
                candidate.company_domain = candidate.company_domain or domain_from_email(candidate.email)
                db.upsert_contact(candidate)
                stats.contacts_created += 1
        except Exception as error:
            stats.errors += 1
            logger.warning("Could not process message %s: %s", email.message_id, error)
    logger.info("processed=%s relevant=%s candidates=%s errors=%s", stats.emails_processed, stats.relevant_emails, stats.candidate_contacts, stats.errors)
    return stats
