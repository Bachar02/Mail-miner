from __future__ import annotations

import re
from email.utils import parseaddr

from .company_normalizer import is_generic_job_mailbox
from .email_cleaner import html_to_text
from .models import ParsedEmail, RelevanceResult

SUBJECT_TERMS = ("internship", "intern", "interns", "application", "applying", "recruitment", "recruiting", "recruiter",
                 "interview", "stage", "stagiaire", "candidature", "recrutement", "entretien", "pfe", "job", "hiring",
                 "alternance")
BODY_TERMS = ("machine learning", "artificial intelligence", "data science", "software engineer", "research intern",
              "internship", "trainee", "candidate", "candidat", "hiring", "job", "resume", "cv", "interview",
              "intelligence artificielle", "apprentissage automatique", "ingénieur", "ressources humaines", "offre",
              "stage", "candidature", "recrutement")
_SUBJECT_RE = re.compile(r"(?i)\b(" + "|".join(re.escape(term) for term in SUBJECT_TERMS) + r")\b")
_BODY_RE = re.compile(r"(?i)\b(" + "|".join(re.escape(term) for term in BODY_TERMS) + r")\b")


def score_email(email: ParsedEmail) -> RelevanceResult:
    subject_hits = sorted({hit.casefold() for hit in _SUBJECT_RE.findall(email.subject)})
    body = email.text_body or html_to_text(email.html_body)
    body_hits = sorted({hit.casefold() for hit in _BODY_RE.findall(body)})
    score = 0.0
    reasons: list[str] = []
    if subject_hits:
        score += 3.0
        reasons.append("job-related subject: " + ", ".join(subject_hits[:3]))
    if body_hits:
        score += min(3.0, 0.75 * len(body_hits))
        reasons.append("job-related body language: " + ", ".join(body_hits[:4]))
    sender_address = parseaddr(email.sender)[1]
    if sender_address and is_generic_job_mailbox(sender_address):
        score += 1.5
        reasons.append("recruiting mailbox address")
    if re.search(r"\b20\d{2}\b", f"{email.subject}\n{body}") and (subject_hits or body_hits):
        score += 0.25
        reasons.append("application year present")
    return RelevanceResult(round(score, 2), reasons)


def is_relevant(email: ParsedEmail, threshold: float = 2.0) -> bool:
    return score_email(email).score >= threshold
