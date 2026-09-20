import csv

from contact_miner.cli import main
from contact_miner.database import Database
from contact_miner.exporter import export_csv
from contact_miner.pipeline import analyze, run_deterministic


def _contacts(db):
    return {row["email"]: dict(row) for row in db.rows("contacts")}


def test_end_to_end_contacts(tmp_path, takeout_mbox):
    db = Database(tmp_path / "db.sqlite3")
    stats = run_deterministic(takeout_mbox, db)
    contacts = _contacts(db)
    assert stats.errors == 0
    assert set(contacts) == {
        "amira.trabelsi@instadeep.com", "recrutement@vermeg.com", "helene@deepsight.ai", "careers@talan.com",
        "karim.mansour@talan.com", "leila.haddad@talan.com", "nour.recruits@gmail.com",
    }
    amira = contacts["amira.trabelsi@instadeep.com"]
    assert (amira["name"], amira["company"], amira["role"], amira["contact_type"]) == ("Amira Trabelsi", "InstaDeep", "Talent Acquisition Specialist", "recruiter")
    assert amira["first_seen"].startswith("2024-03-04") and amira["last_seen"].startswith("2024-03-05")
    assert contacts["helene@deepsight.ai"]["name"] == "Hélène Dupont"
    assert contacts["karim.mansour@talan.com"]["name"] == "Karim Mansour"
    assert contacts["karim.mansour@talan.com"]["company"] == "Talan Tunisie"
    assert contacts["leila.haddad@talan.com"]["name"] == "Leila Haddad"
    assert contacts["nour.recruits@gmail.com"]["name"] == "Nour Gharbi"
    assert contacts["recrutement@vermeg.com"]["name"] is None
    assert contacts["recrutement@vermeg.com"]["contact_type"] == "hr"
    statuses = {row["status"] for row in db.rows("applications")}
    assert {"applied", "interview", "received", "rejected"} <= statuses
    db.close()


def test_rerun_is_idempotent(tmp_path, takeout_mbox):
    db = Database(tmp_path / "db.sqlite3")
    run_deterministic(takeout_mbox, db)
    counts = [len(db.rows(table)) for table in ("emails", "contacts", "applications", "evidence")]
    run_deterministic(takeout_mbox, db)
    assert [len(db.rows(table)) for table in ("emails", "contacts", "applications", "evidence")] == counts
    db.close()


def test_owner_is_never_a_contact(tmp_path, takeout_mbox):
    db = Database(tmp_path / "db.sqlite3")
    run_deterministic(takeout_mbox, db, owner_emails=["bachar@example.org"])
    assert "sami.benali@gmail.com" not in _contacts(db)
    db.close()


def test_analyze_does_not_write(tmp_path, takeout_mbox):
    report = analyze(takeout_mbox)
    assert report["processed"] >= 11
    assert "sami.benali@gmail.com" in report["owner_addresses"]
    assert "amira.trabelsi@instadeep.com" in report["contacts"]
    assert not any(tmp_path.glob("*.sqlite3"))


def test_csv_export_includes_review_status(tmp_path, takeout_mbox):
    db = Database(tmp_path / "db.sqlite3")
    run_deterministic(takeout_mbox, db)
    contact_id = _contacts(db)["careers@talan.com"]["id"]
    db.update_status(contact_id, "do-not-contact")
    path = export_csv(db, tmp_path / "out" / "contacts.csv")
    with path.open(encoding="utf-8-sig") as handle:
        rows = {row["email"]: row for row in csv.DictReader(handle)}
    assert rows["careers@talan.com"]["contact_status"] == "do-not-contact"
    db.close()


def test_cli_run_all(tmp_path, takeout_mbox, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CONTACT_MINER_DB", str(tmp_path / "cli.sqlite3"))
    main(["run-all", "--mbox", str(takeout_mbox), "--no-llm", "--output", str(tmp_path / "out")])
    assert (tmp_path / "out" / "contacts.csv").exists()
    assert (tmp_path / "cli.sqlite3").exists()
