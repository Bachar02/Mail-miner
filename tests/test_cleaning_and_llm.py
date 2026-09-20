import os
import sqlite3

from contact_miner.company_normalizer import company_from_domain, is_noise_address
from contact_miner.config import Settings
from contact_miner.database import Database
from contact_miner.email_cleaner import clean_body
from contact_miner.llm_extractor import candidates_from_llm
from contact_miner.models import ParsedEmail
from contact_miner.relevance import score_email


def test_clean_body_cuts_outlook_and_french_replies():
    outlook = "Merci pour votre retour.\n\nFrom: Jane <jane@acme.com>\nSent: Monday\nSubject: x\n\nold text"
    assert clean_body(outlook) == "Merci pour votre retour."
    french = "Bonjour,\nOui.\nLe lun. 4 mars 2024 à 09:00, Sami <\nsami@gmail.com> a écrit :\n> ancien"
    assert clean_body(french) == "Bonjour,\nOui."
    assert clean_body("From: the start of our partnership, we grew.") == "From: the start of our partnership, we grew."


def test_relevance_uses_sender_address_and_word_boundaries():
    email = ParsedEmail("<1>", None, "Hello", "Careers Team <careers@acme.com>", [], [], [], "", "")
    assert "recruiting mailbox address" in score_email(email).reasons
    unrelated = ParsedEmail("<2>", None, "International internal memo", "a@b.com", [], [], [], "", "")
    assert score_email(unrelated).score == 0


def test_noise_and_domains():
    assert is_noise_address("jobalerts-noreply@linkedin.com")
    assert is_noise_address("mailer-daemon@googlemail.com")
    assert not is_noise_address("hr@company.com")
    assert company_from_domain("mail.instadeep.com") == "Instadeep"
    assert company_from_domain("company.co.uk") == "Company"
    assert company_from_domain("gmail.com") is None


def test_llm_output_is_validated_against_snippet():
    snippet = "From: Jane Smith <jane@startup.ai>\nJane Smith, CTO\nMy colleague bob@startup.ai"
    items = [
        {"name": "Jane Smith", "email": "JANE@startup.ai", "role": "CTO", "contact_type": "wizard", "confidence": 3},
        {"name": "Invented", "email": "ghost@startup.ai"},
        {"name": "Owner", "email": "me@gmail.com"},
        {"name": None, "email": "bob@startup.ai", "application_year": "not a year"},
        {"name": "No email"},
    ]
    result = candidates_from_llm(items, "m1", snippet + "\nme@gmail.com", owner_emails=["me@gmail.com"])
    assert [candidate.email for candidate in result] == ["jane@startup.ai", "bob@startup.ai"]
    assert result[0].contact_type is None and result[0].confidence == 0.95
    assert result[1].application_year is None


def test_dotenv_is_loaded(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTACT_MINER_DB", raising=False)
    monkeypatch.delenv("OWNER_EMAILS", raising=False)
    (tmp_path / ".env").write_text("CONTACT_MINER_DB=custom/db.sqlite3\nOWNER_EMAILS=Me@Example.com, other@example.com\n", encoding="utf-8")
    settings = Settings.from_root(tmp_path)
    assert settings.db_path == tmp_path.resolve() / "custom" / "db.sqlite3"
    assert settings.owner_emails == {"me@example.com", "other@example.com"}
    os.environ.pop("CONTACT_MINER_DB", None)
    os.environ.pop("OWNER_EMAILS", None)


def test_migration_removes_legacy_duplicates(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    Database(path).close()
    connection = sqlite3.connect(path)
    connection.execute("DROP INDEX idx_evidence_unique")
    connection.execute("DROP INDEX idx_applications_unique")
    connection.execute("INSERT INTO contacts(id,email,created_at,updated_at) VALUES(1,'a@b.com','x','x')")
    for _ in range(3):
        connection.execute("INSERT INTO evidence(contact_id,message_id,evidence_type,evidence_text) VALUES(1,'m','header','t')")
        connection.execute("INSERT INTO applications(contact_id,company,source_message_id) VALUES(1,NULL,'m')")
    connection.commit()
    connection.close()
    db = Database(path)
    assert len(db.rows("evidence")) == 1 and len(db.rows("applications")) == 1
    db.close()
