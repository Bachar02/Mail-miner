from contact_miner.contact_extractor import extract_contacts
from contact_miner.email_cleaner import clean_body, signature_block
from contact_miner.models import ParsedEmail


def test_header_and_signature_extraction():
    email = ParsedEmail("<1>", "2024-01-01", "AI Internship Application", "John Doe <john.doe@acme.com>", [], [], [], "Hello\n--\nJohn Doe\nTalent Acquisition Manager\nACME Technologies\njohn.doe@acme.com", "")
    contacts = extract_contacts(email, clean_body(email.text_body))
    assert any(contact.email == "john.doe@acme.com" for contact in contacts)
    assert signature_block(email.text_body).startswith("John Doe")
