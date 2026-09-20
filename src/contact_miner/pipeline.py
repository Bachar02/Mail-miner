from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Iterable

from .contact_extractor import extract_contacts, owner_addresses_for
from .database import Database
from .email_cleaner import clean_body
from .mailbox_reader import iter_mbox
from .models import PipelineStats
from .relevance import score_email

logger = logging.getLogger(__name__)
COMMIT_EVERY = 250


def run_deterministic(mbox_path: str | Path, db: Database, threshold: float = 2.0, limit: int | None = None,
                      owner_emails: Iterable[str] = ()) -> PipelineStats:
    """Score every message, extract contacts from relevant ones, and store them. No network access."""
    stats = PipelineStats()
    owners = {address.lower() for address in owner_emails}
    for email in iter_mbox(mbox_path, limit):
        stats.emails_processed += 1
        try:
            # The mailbox owner (Delivered-To, sender of Sent mail) is discovered as we go and never stored.
            owners |= owner_addresses_for(email)
            relevance = score_email(email)
            db.add_email(email, relevance.score, relevance.reasons)
            if relevance.score >= threshold:
                stats.relevant_emails += 1
                candidates = extract_contacts(email, clean_body(email.text_body, email.html_body), owners)
                stats.candidate_contacts += len(candidates)
                for candidate in candidates:
                    db.upsert_contact(candidate)
        except Exception as error:
            stats.errors += 1
            logger.warning("Could not process message %s: %s", email.message_id, error)
        if stats.emails_processed % COMMIT_EVERY == 0:
            db.commit()
            logger.info("processed %s messages", stats.emails_processed)
    # Owner addresses discovered late in the mailbox may have been stored from earlier messages.
    stats.owner_addresses_excluded = db.delete_contacts(owners)
    db.commit()
    stats.contacts_in_database = db.connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    logger.info("processed=%s relevant=%s candidates=%s errors=%s", stats.emails_processed, stats.relevant_emails, stats.candidate_contacts, stats.errors)
    return stats


def analyze(mbox_path: str | Path, threshold: float = 2.0, limit: int | None = None, owner_emails: Iterable[str] = ()) -> dict:
    """Dry run: report what the pipeline would keep, without writing anything."""
    owners = {address.lower() for address in owner_emails}
    processed = relevant = 0
    reasons: Counter[str] = Counter()
    contacts: dict[str, tuple[str | None, float]] = {}
    for email in iter_mbox(mbox_path, limit):
        processed += 1
        owners |= owner_addresses_for(email)
        relevance = score_email(email)
        if relevance.score < threshold:
            continue
        relevant += 1
        reasons.update(reason.split(":", 1)[0] for reason in relevance.reasons)
        for candidate in extract_contacts(email, clean_body(email.text_body, email.html_body), owners):
            previous = contacts.get(candidate.email)
            if not previous or candidate.confidence > previous[1]:
                contacts[candidate.email] = (candidate.name or (previous[0] if previous else None), candidate.confidence)
    for owner in owners:
        contacts.pop(owner, None)
    return {"processed": processed, "relevant": relevant, "relevance_signals": dict(reasons), "contacts": contacts, "owner_addresses": sorted(owners)}
