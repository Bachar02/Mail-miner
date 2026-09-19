from contact_miner.company_normalizer import normalize_email
from contact_miner.database import Database
from contact_miner.deduplicator import deduplicate_database
from contact_miner.models import ContactCandidate


def test_email_normalization_and_upsert(tmp_path):
    assert normalize_email("<JOHN@EXAMPLE.COM>") == "john@example.com"
    db = Database(tmp_path / "test.sqlite3")
    db.upsert_contact(ContactCandidate("John Doe", "JOHN@example.com", "header", "1", confidence=.5))
    db.upsert_contact(ContactCandidate("John", "john@example.com", "signature", "2", confidence=.8))
    assert len(db.rows("contacts")) == 1
    assert db.rows("contacts")[0]["name"] == "John Doe"
    assert deduplicate_database(db) == 0
    db.close()
