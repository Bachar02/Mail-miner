from __future__ import annotations

from .company_normalizer import normalize_email
from .database import Database


def deduplicate_database(db: Database) -> int:
    duplicates = 0
    groups = db.connection.execute("SELECT email, COUNT(*) AS count FROM contacts GROUP BY email HAVING count > 1").fetchall()
    for group in groups:
        ids = [row[0] for row in db.connection.execute("SELECT id FROM contacts WHERE email=? ORDER BY confidence DESC, id", (normalize_email(group[0]),))]
        keeper = ids[0]
        for duplicate in ids[1:]:
            db.connection.execute("UPDATE evidence SET contact_id=? WHERE contact_id=?", (keeper, duplicate))
            db.connection.execute("UPDATE applications SET contact_id=? WHERE contact_id=?", (keeper, duplicate))
            db.connection.execute("DELETE FROM contacts WHERE id=?", (duplicate,))
            duplicates += 1
    db.connection.commit()
    return duplicates
