from __future__ import annotations

import csv
import json
from pathlib import Path

from .database import Database

CONTACT_COLUMNS = ["name", "email", "company", "role", "contact_type", "country", "company_domain", "confidence", "confidence_reasons", "contact_status", "first_seen", "last_seen", "notes"]
REVIEW_THRESHOLD = 0.7


def _contact_rows(db: Database) -> list[dict]:
    rows = []
    for row in db.connection.execute("SELECT * FROM contacts ORDER BY confidence DESC, company, email"):
        data = dict(row)
        data["confidence_reasons"] = "; ".join(json.loads(data["confidence_reasons"] or "[]"))
        rows.append({key: data.get(key) for key in CONTACT_COLUMNS})
    return rows


def export_csv(db: Database, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel on Windows shows accented names correctly
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONTACT_COLUMNS)
        writer.writeheader()
        writer.writerows(_contact_rows(db))
    return path


def export_excel(db: Database, output: str | Path) -> Path:
    import pandas as pd

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    contacts = pd.DataFrame(_contact_rows(db), columns=CONTACT_COLUMNS)
    applications = pd.read_sql_query("SELECT c.email, c.name, a.company, a.position, a.application_type, a.application_year, a.status, a.source_message_id FROM applications a JOIN contacts c ON c.id = a.contact_id ORDER BY a.application_year, a.company", db.connection)
    evidence = pd.read_sql_query("SELECT c.email, e.message_id, e.evidence_type, e.evidence_text FROM evidence e JOIN contacts c ON c.id = e.contact_id ORDER BY c.email", db.connection)
    review = contacts[(contacts["confidence"] < REVIEW_THRESHOLD) & (contacts["contact_status"] == "review")]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet, frame in (("Contacts", contacts), ("Applications", applications), ("Evidence", evidence), ("Review", review)):
            frame.to_excel(writer, sheet_name=sheet, index=False)
    return path
