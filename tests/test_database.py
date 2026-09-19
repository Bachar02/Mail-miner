from contact_miner.database import Database
from contact_miner.models import ContactCandidate


def test_database_evidence_and_application(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    contact_id = db.upsert_contact(ContactCandidate("Jane Smith", "jane@startup.ai", "signature", "msg-1", company="Startup AI", role="Founder", position_applied_for="AI Intern", application_year=2024, evidence=["Jane Smith\nFounder"]))
    assert contact_id > 0
    assert len(db.rows("evidence")) == 1
    assert len(db.rows("applications")) == 1
    db.close()
