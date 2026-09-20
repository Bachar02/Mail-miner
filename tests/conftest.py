"""Shared test configuration: a synthetic Gmail-Takeout-style mailbox (no real data)."""
from email.header import Header
from email.message import EmailMessage
from mailbox import mbox

import pytest

OWNER = "Sami Ben Ali <sami.benali@gmail.com>"


def _message(mid, date, sender, to, subject, body, html=None, labels="Inbox", cc=None, extra=None):
    message = EmailMessage()
    message["X-Gmail-Labels"] = labels
    if labels != "Sent":
        message["Delivered-To"] = "sami.benali@gmail.com"
    message["Message-ID"] = f"<{mid}@example.test>"
    message["Date"] = date
    message["From"] = sender
    message["To"] = to
    if cc:
        message["Cc"] = cc
    message["Subject"] = subject
    for key, value in (extra or {}).items():
        message[key] = value
    if body is None:
        message.set_content(html, subtype="html")
    else:
        message.set_content(body)
        if html:
            message.add_alternative(html, subtype="html")
    return message


MESSAGES = [
    _message("m1", "Mon, 04 Mar 2024 09:00:00 +0100", OWNER, "Amira Trabelsi <amira.trabelsi@instadeep.com>",
             "Application - AI Research Internship 2024",
             "Dear Ms. Trabelsi,\n\nPlease find attached my application for the AI Research Internship.\n\nBest regards,\nSami Ben Ali\nsami.benali@gmail.com\n", labels="Sent"),
    _message("m2", "Tue, 05 Mar 2024 14:30:00 +0100", "Amira Trabelsi <amira.trabelsi@instadeep.com>", OWNER,
             "Re: Application - AI Research Internship 2024",
             "Hi Sami,\n\nThanks for your interest. We would like to schedule an interview next week.\n\nBest regards,\nAmira Trabelsi\nTalent Acquisition Specialist\nInstaDeep\namira.trabelsi@instadeep.com\n\nOn Mon, Mar 4, 2024 at 9:00 AM Sami Ben Ali <sami.benali@gmail.com> wrote:\n> Dear Ms. Trabelsi,\n"),
    _message("m3", "Wed, 10 Apr 2024 10:00:00 +0100", "Recrutement Vermeg <recrutement@vermeg.com>", OWNER,
             "Votre candidature - Stage PFE Intelligence Artificielle",
             "Bonjour,\n\nNous avons bien reçu votre candidature pour le stage PFE en intelligence artificielle.\n\nCordialement,\nL'équipe Recrutement\nVermeg\n"),
    _message("m4", "Thu, 11 Apr 2024 08:00:00 +0000", "Workday <no-reply@myworkday.com>", OWNER,
             "Your application for Software Engineer Intern was received", "Thank you for applying. Please do not reply."),
    _message("m5", "Fri, 12 Apr 2024 07:00:00 +0000", "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>", OWNER,
             "30 new jobs for 'machine learning intern'", "New jobs match your preferences. Contact talent@companyx.com. Unsubscribe.",
             extra={"List-Unsubscribe": "<https://linkedin.com/unsub>"}),
    _message("m6", "Sat, 13 Apr 2024 12:00:00 +0000", "Mom <mom.family@gmail.com>", OWNER, "Dinner on Sunday", "Don't forget dinner!"),
    _message("m7", "Mon, 06 May 2024 16:00:00 +0200", f"{Header('Hélène Dupont', 'utf-8').encode()} <helene@deepsight.ai>", OWNER,
             "Internship opportunity at DeepSight", None,
             html="<p>Hi Sami,</p><p>I'm the founder of DeepSight, we are hiring a machine learning intern.</p><p>Best regards,<br>Hélène Dupont<br>Founder &amp; CEO<br>DeepSight<br>helene@deepsight.ai</p>"),
    _message("m8", "Tue, 07 May 2024 09:00:00 +0000", "Mail Delivery Subsystem <mailer-daemon@googlemail.com>", OWNER,
             "Delivery Status Notification (Failure) - internship application", "Your message to jobs@nonexistent.com couldn't be delivered."),
    _message("m9", "Wed, 08 May 2024 11:00:00 +0100", OWNER, "careers@talan.com", "Candidature spontanée - Stage Data Science 2024",
             "Bonjour,\n\nJe vous adresse ma candidature.\n\nCordialement,\nSami Ben Ali\n\nFrom: Karim Mansour <karim.mansour@talan.com>\nSent: Tuesday, May 7, 2024\nSubject: stage\n\nEnvoie ton CV\n",
             labels="Sent", cc="Karim Mansour <karim.mansour@talan.com>"),
    _message("m10", "Thu, 09 May 2024 15:00:00 +0100", "Karim Mansour <karim.mansour@talan.com>", OWNER,
             "Re: Candidature spontanée - Stage Data Science 2024",
             "Salut Sami,\n\nTu peux aussi contacter notre responsable recrutement Leila Haddad (leila.haddad@talan.com).\n\n--\nKarim Mansour\nSenior Data Engineer | Talan Tunisie\n"),
    _message("m11", "Fri, 10 May 2024 10:00:00 +0000", "Nour Recruiter <nour.recruits@gmail.com>", OWNER, "Update on your internship application",
             "Hi Sami,\nUnfortunately we will not move forward with your candidacy.\nKind regards,\nNour Gharbi\nIndependent Recruiter\n"),
]


@pytest.fixture
def takeout_mbox(tmp_path):
    path = tmp_path / "mail.mbox"
    box = mbox(path)
    for message in MESSAGES:
        box.add(message)
    box.flush()
    box.close()
    with open(path, "ab") as handle:  # a malformed trailing message must be skipped, not crash the run
        handle.write(b"From MAILER-DAEMON Thu Jan  1 00:00:00 1970\nContent-Type: multipart/mixed; boundary=\"broken\n\n--broken\ngarbage\n\n")
    return path
