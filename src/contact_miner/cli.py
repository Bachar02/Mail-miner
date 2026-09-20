from __future__ import annotations

import argparse
import logging
import os
from dataclasses import asdict
from pathlib import Path

from .config import Settings
from .contact_extractor import owner_addresses_for
from .database import Database
from .deduplicator import deduplicate_database
from .email_cleaner import clean_body
from .exporter import export_csv, export_excel
from .mailbox_reader import iter_mbox
from .pipeline import analyze, run_deterministic
from .relevance import score_email

DEFAULT_MBOX = Path("data/raw/mail.mbox")


def _export(db: Database, output: Path) -> None:
    print(f"CSV written to {export_csv(db, output / 'contacts.csv')}")
    try:
        print(f"Excel written to {export_excel(db, output / 'contacts.xlsx')}")
    except ImportError:
        logging.warning("Install pandas and openpyxl for Excel export (pip install -e \".[app]\"); CSV and SQLite are available")


def _print_stats(stats: object) -> None:
    for key, value in asdict(stats).items():
        print(f"  {key.replace('_', ' ')}: {value}")


def _enrich(args: argparse.Namespace, settings: Settings, owners: set[str], db: Database) -> None:
    from .llm_extractor import MAX_SNIPPET_CHARS, OpenAIProvider, candidates_from_llm

    provider = OpenAIProvider(args.model or settings.llm_model)
    calls = stored = 0
    for email in iter_mbox(args.mbox, args.limit):
        owners |= owner_addresses_for(email)
        if email.is_bulk or score_email(email).score < settings.relevance_threshold:
            continue
        snippet = f"Subject: {email.subject}\nFrom: {email.sender}\nTo: {', '.join(email.to)}\nCc: {', '.join(email.cc)}\n\n{clean_body(email.text_body, email.html_body)}"[:MAX_SNIPPET_CHARS]
        try:
            items = provider.enrich(email, snippet)
            calls += 1
        except Exception as error:
            logging.warning("LLM enrichment failed for %s: %s", email.message_id, error)
            continue
        for candidate in candidates_from_llm(items, email.message_id, snippet, owners, email.date):
            db.upsert_contact(candidate)
            stored += 1
        db.commit()
    db.delete_contacts(owners)
    print(f"LLM calls: {calls}, contacts stored or updated: {stored}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contact-miner", description="Extract professional contacts from a Gmail Takeout MBOX")
    sub = parser.add_subparsers(dest="command", required=True)
    specs = {
        "ingest": "parse the MBOX and store relevant emails and contacts in SQLite",
        "analyze": "dry run: show relevance and contacts that would be extracted, without writing",
        "run-all": "ingest, deduplicate and export CSV/Excel",
    }
    for name, help_text in specs.items():
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--mbox", type=Path, default=DEFAULT_MBOX)
        command.add_argument("--limit", type=int, help="process only the first N messages")
        command.add_argument("--owner", action="append", default=[], help="your own address (repeatable); also OWNER_EMAILS in .env")
        command.add_argument("--no-llm", action="store_true", help="accepted for clarity; these commands never call an LLM")
        command.add_argument("--output", type=Path, default=Path("data/output"))
    sub.add_parser("deduplicate", help="merge contacts whose addresses differ only by case")
    enrich = sub.add_parser("enrich", help="optional: send bounded snippets of relevant emails to OpenAI")
    enrich.add_argument("--mbox", type=Path, default=DEFAULT_MBOX)
    enrich.add_argument("--limit", type=int)
    enrich.add_argument("--owner", action="append", default=[])
    enrich.add_argument("--model")
    export = sub.add_parser("export", help="write contacts.csv and contacts.xlsx")
    export.add_argument("--output", type=Path, default=Path("data/output"))
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_root()
    owners = set(settings.owner_emails) | {address.strip().lower() for address in getattr(args, "owner", [])}
    mbox = getattr(args, "mbox", None)
    if mbox is not None and not mbox.exists():
        parser.error(f"MBOX not found: {mbox}. Export Gmail with Google Takeout and place the .mbox file there, or pass --mbox.")
    if args.command == "enrich" and not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required for enrich (set it in .env); deterministic commands do not call an LLM")

    if args.command == "analyze":
        report = analyze(args.mbox, settings.relevance_threshold, args.limit, owners)
        print(f"Messages processed: {report['processed']}, relevant: {report['relevant']}")
        print(f"Owner addresses excluded: {', '.join(report['owner_addresses']) or 'none detected'}")
        print(f"Relevance signals: {report['relevance_signals']}")
        print(f"Contacts that would be stored ({len(report['contacts'])}):")
        for email, (name, confidence) in sorted(report["contacts"].items(), key=lambda item: -item[1][1]):
            print(f"  {confidence:.2f}  {email}  {name or ''}")
        return

    settings.ensure_directories()
    db = Database(settings.db_path)
    try:
        if args.command in {"ingest", "run-all"}:
            stats = run_deterministic(args.mbox, db, settings.relevance_threshold, args.limit, owners)
            print(f"Database: {settings.db_path}")
            if args.command == "run-all":
                stats.duplicates_merged = deduplicate_database(db)
                _export(db, args.output)
            _print_stats(stats)
        elif args.command == "enrich":
            _enrich(args, settings, owners, db)
        elif args.command == "deduplicate":
            print(f"Merged duplicates: {deduplicate_database(db)}")
        elif args.command == "export":
            _export(db, args.output)
    finally:
        db.close()


if __name__ == "__main__":
    main()
