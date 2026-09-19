from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from contact_miner.config import Settings
from contact_miner.database import Database

settings = Settings.from_root(Path(__file__).resolve().parents[1]); settings.ensure_directories()
db = Database(settings.db_path)
contacts = [dict(row) for row in db.rows("contacts")]

st.set_page_config(page_title="Internship Contact Miner", layout="wide")
st.title("Internship Contact Miner")
st.caption("Local-first professional contact review")
cols = st.columns(5)
metrics = [("Emails", len(db.rows("emails"))), ("Contacts", len(contacts)), ("High confidence", sum(row["confidence"] >= 0.8 for row in contacts)), ("Needs review", sum(row["confidence"] < 0.7 for row in contacts)), ("Companies", len({row["company"] for row in contacts if row["company"]}))]
for column, (label, value) in zip(cols, metrics): column.metric(label, value)

search = st.text_input("Search name, email, or company")
company = st.selectbox("Company", ["All"] + sorted({row["company"] for row in contacts if row["company"]}))
filtered = [row for row in contacts if (not search or search.casefold() in " ".join(str(row.get(key) or "") for key in ("name", "email", "company")).casefold()) and (company == "All" or row["company"] == company)]
st.dataframe(filtered, use_container_width=True, hide_index=True)

if filtered:
    selected = st.selectbox("Contact detail", range(len(filtered)), format_func=lambda index: filtered[index].get("name") or filtered[index]["email"])
    contact = filtered[selected]
    st.subheader(contact.get("name") or contact["email"])
    st.write({key: contact.get(key) for key in ("email", "company", "role", "contact_type", "country", "company_domain", "confidence")})
    st.write("Evidence")
    st.dataframe([dict(row) for row in db.connection.execute("SELECT * FROM evidence WHERE contact_id=?", (contact["id"],))], use_container_width=True, hide_index=True)
    status = st.selectbox("Review status", ["review", "approved", "rejected", "do-not-contact"], index=["review", "approved", "rejected", "do-not-contact"].index(contact["contact_status"]))
    if st.button("Save status"):
        db.update_status(contact["id"], status); st.success("Saved")

db.close()
