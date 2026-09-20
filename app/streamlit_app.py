from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # works without `pip install -e .`
    sys.path.insert(0, str(ROOT / "src"))

from contact_miner.config import Settings  # noqa: E402
from contact_miner.database import REVIEW_STATUSES, Database  # noqa: E402
from contact_miner.exporter import REVIEW_THRESHOLD  # noqa: E402

TABLE_COLUMNS = ["name", "email", "company", "role", "contact_type", "confidence", "contact_status", "first_seen", "last_seen"]

st.set_page_config(page_title="Internship Contact Miner", layout="wide")
settings = Settings.from_root(ROOT)
settings.ensure_directories()
db = Database(settings.db_path)
try:
    contacts = [dict(row) for row in db.connection.execute("SELECT * FROM contacts ORDER BY confidence DESC, company, email")]
    email_count = db.connection.execute("SELECT COUNT(*) FROM emails").fetchone()[0]

    st.title("Internship Contact Miner")
    st.caption(f"Local-first professional contact review · database: {settings.db_path}")
    if not contacts:
        st.info("No contacts yet. Run `python -m contact_miner run-all --mbox data\\raw\\mail.mbox --no-llm` first.")
        st.stop()

    metrics = [
        ("Emails scanned", email_count), ("Contacts", len(contacts)),
        ("High confidence", sum(row["confidence"] >= 0.8 for row in contacts)),
        ("Needs review", sum(row["confidence"] < REVIEW_THRESHOLD and row["contact_status"] == "review" for row in contacts)),
        ("Companies", len({row["company"] for row in contacts if row["company"]})),
    ]
    for column, (label, value) in zip(st.columns(len(metrics)), metrics):
        column.metric(label, value)

    search_col, company_col, type_col, status_col, confidence_col = st.columns([3, 2, 2, 2, 2])
    search = search_col.text_input("Search name, email, company or role")
    company = company_col.selectbox("Company", ["All"] + sorted({row["company"] for row in contacts if row["company"]}, key=str.casefold))
    contact_type = type_col.selectbox("Contact type", ["All"] + sorted({row["contact_type"] for row in contacts if row["contact_type"]}))
    statuses = status_col.multiselect("Review status", REVIEW_STATUSES, default=[status for status in REVIEW_STATUSES if status != "rejected"])
    min_confidence = confidence_col.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)

    def matches(row: dict) -> bool:
        haystack = " ".join(str(row.get(key) or "") for key in ("name", "email", "company", "role")).casefold()
        return (
            (not search or search.casefold() in haystack)
            and (company == "All" or row["company"] == company)
            and (contact_type == "All" or row["contact_type"] == contact_type)
            and row["contact_status"] in statuses
            and row["confidence"] >= min_confidence
        )

    filtered = [row for row in contacts if matches(row)]
    st.dataframe([{key: row[key] for key in TABLE_COLUMNS} for row in filtered], width="stretch", hide_index=True)
    st.caption(f"{len(filtered)} of {len(contacts)} contacts")

    if filtered:
        selected = st.selectbox("Contact detail", range(len(filtered)), format_func=lambda index: f"{filtered[index].get('name') or '(no name)'} · {filtered[index]['email']}")
        contact = filtered[selected]
        st.subheader(contact.get("name") or contact["email"])
        details, review = st.columns([3, 2])
        with details:
            st.json({key: contact.get(key) for key in ("email", "company", "role", "contact_type", "country", "company_domain", "confidence")})
            st.write("Why this confidence: " + "; ".join(json.loads(contact["confidence_reasons"] or "[]")))
        with review:
            current = contact["contact_status"] if contact["contact_status"] in REVIEW_STATUSES else "review"
            status = st.selectbox("Review status", REVIEW_STATUSES, index=REVIEW_STATUSES.index(current), key=f"status-{contact['id']}")
            notes = st.text_area("Notes", contact.get("notes") or "", key=f"notes-{contact['id']}")
            if st.button("Save review"):
                db.update_status(contact["id"], status)
                db.update_notes(contact["id"], notes)
                st.toast("Saved")
                st.rerun()
        st.write("Applications")
        st.dataframe([dict(row) for row in db.connection.execute("SELECT company, position, application_type, application_year, status, source_message_id FROM applications WHERE contact_id=? ORDER BY application_year", (contact["id"],))], width="stretch", hide_index=True)
        st.write("Evidence")
        st.dataframe([dict(row) for row in db.connection.execute("SELECT evidence_type, evidence_text, message_id FROM evidence WHERE contact_id=?", (contact["id"],))], width="stretch", hide_index=True)
finally:
    db.close()
