from email.message import EmailMessage
from mailbox import mbox

from contact_miner.mailbox_reader import iter_mbox


def test_multipart_mbox_parsing(tmp_path):
    path = tmp_path / "mail.mbox"
    message = EmailMessage()
    message["Message-ID"] = "<abc@example.com>"
    message["From"] = "John Doe <john@example.com>"
    message["Subject"] = "AI Internship"
    message.set_content("Plain body")
    message.add_alternative("<p>HTML body</p>", subtype="html")
    box = mbox(path); box.add(message); box.flush(); box.close()
    emails = list(iter_mbox(path))
    assert len(emails) == 1
    assert emails[0].message_id == "<abc@example.com>"
    assert "Plain body" in emails[0].text_body
    assert "HTML body" in emails[0].html_body
