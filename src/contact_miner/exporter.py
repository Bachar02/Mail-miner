from __future__ import annotations

import csv
import json
from pathlib import Path

from .database import Database

CONTACT_COLUMNS = ["name", "email", "company", "role", "contact_type", "country", "company_domain", "confidence", "confidence_reasons", "first_seen", "last_seen", "notes"]


def export_csv(db: Database, output: str | Path) -> Path:
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    rows = db.rows("contacts")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONTACT_COLUMNS); writer.writeheader()
        for row in rows:
            data = dict(row); data["confidence_reasons"] = "; ".join(json.loads(data["confidence_reasons"]))
            writer.writerow({key: data.get(key, "") for key in CONTACT_COLUMNS})
    return path


def export_excel(db: Database, output: str | Path) -> Path:
    import pandas as pd
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet, table in (("Contacts", "contacts"), ("Applications", "applications"), ("Evidence", "evidence")):
            frame = pd.DataFrame([dict(row) for row in db.rows(table)])
            frame.to_excel(writer, sheet_name=sheet, index=False)
        contacts = pd.DataFrame([dict(row) for row in db.rows("contacts")])
        review = contacts[contacts["confidence"] < 0.7] if not contacts.empty else contacts
        review.to_excel(writer, sheet_name="Review", index=False)
    return path
