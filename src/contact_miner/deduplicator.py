from __future__ import annotations

from .database import Database

_FILLABLE = ("name", "company", "role", "contact_type", "country", "company_domain", "notes")


def deduplicate_database(db: Database) -> int:
    """Merge contacts whose addresses differ only by case/whitespace. Names alone never merge contacts."""
    duplicates = 0
    groups = db.connection.execute("SELECT LOWER(TRIM(email)) AS key FROM contacts GROUP BY key HAVING COUNT(*) > 1").fetchall()
    for group in groups:
        rows = db.connection.execute("SELECT * FROM contacts WHERE LOWER(TRIM(email)) = ? ORDER BY confidence DESC, id", (group["key"],)).fetchall()
        keeper, others = rows[0], rows[1:]
        first_seen = min((row["first_seen"] for row in rows if row["first_seen"]), default=None)
        last_seen = max((row["last_seen"] for row in rows if row["last_seen"]), default=None)
        for duplicate in others:
            for field in _FILLABLE:
                if not keeper[field] and duplicate[field]:
                    db.connection.execute(f"UPDATE contacts SET {field} = ? WHERE id = ?", (duplicate[field], keeper["id"]))
            db.connection.execute("UPDATE OR IGNORE evidence SET contact_id=? WHERE contact_id=?", (keeper["id"], duplicate["id"]))
            db.connection.execute("UPDATE OR IGNORE applications SET contact_id=? WHERE contact_id=?", (keeper["id"], duplicate["id"]))
            db.connection.execute("DELETE FROM contacts WHERE id=?", (duplicate["id"],))
            duplicates += 1
        db.connection.execute("UPDATE contacts SET email=?, first_seen=?, last_seen=? WHERE id=?", (group["key"], first_seen, last_seen, keeper["id"]))
    db.commit()
    return duplicates
