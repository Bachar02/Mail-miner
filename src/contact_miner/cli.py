from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import Settings
from .database import Database
from .deduplicator import deduplicate_database
from .exporter import export_csv, export_excel
from .pipeline import run_deterministic


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract professional contacts from an MBOX")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("ingest", "analyze", "run-all"):
        command = sub.add_parser(name); command.add_argument("--mbox", type=Path, default=Path("data/raw/mail.mbox")); command.add_argument("--limit", type=int); command.add_argument("--no-llm", action="store_true")
    sub.add_parser("deduplicate")
    export = sub.add_parser("export"); export.add_argument("--output", type=Path, default=Path("data/output"))
    args = parser.parse_args(); logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_root(); settings.ensure_directories(); db = Database(settings.db_path)
    try:
        if args.command in {"ingest", "analyze", "run-all"}:
            if not args.mbox.exists(): parser.error(f"MBOX not found: {args.mbox}")
            stats = run_deterministic(args.mbox, db, settings.relevance_threshold, args.limit); print(stats)
            if args.command == "run-all":
                print(f"Merged duplicates: {deduplicate_database(db)}")
                export_csv(db, settings.output_dir / "contacts.csv")
                try: export_excel(db, settings.output_dir / "contacts.xlsx")
                except ImportError: logging.warning("Install pandas and openpyxl for Excel export")
        elif args.command == "deduplicate": print(f"Merged duplicates: {deduplicate_database(db)}")
        elif args.command == "export": export_csv(db, args.output / "contacts.csv"); export_excel(db, args.output / "contacts.xlsx"); print(f"Exports written to {args.output}")
    finally: db.close()

if __name__ == "__main__": main()
