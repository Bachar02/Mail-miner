from __future__ import annotations

import re

from .models import ParsedEmail, RelevanceResult

SUBJECT_TERMS = ("internship", "intern", "application", "recruit", "interview", "stage", "candidature", "recrutement", "entretien", "pfe")
BODY_TERMS = ("machine learning", "artificial intelligence", "data science", "software engineer", "research intern", "trainee", "candidate", "hiring", "job", "intelligence artificielle", "apprentissage automatique", "ingénieur ia", "ressources humaines", "offre")
GENERIC_JOB_LOCALPARTS = ("hr", "recruitment", "careers", "jobs", "recruiter")


def score_email(email: ParsedEmail) -> RelevanceResult:
    subject = email.subject.casefold()
    body = f"{email.text_body}\n{email.html_body}".casefold()
    score = 0.0
    reasons: list[str] = []
    subject_hits = [term for term in SUBJECT_TERMS if term in subject]
    body_hits = [term for term in BODY_TERMS if term in body]
    if subject_hits:
        score += 3.0
        reasons.append("job-related subject: " + ", ".join(subject_hits[:3]))
    if body_hits:
        score += min(3.0, 0.75 * len(set(body_hits)))
        reasons.append("job-related body language: " + ", ".join(body_hits[:4]))
    sender_local = email.sender.split("@", 1)[0].casefold() if "@" in email.sender else ""
    if sender_local in GENERIC_JOB_LOCALPARTS:
        score += 1.5
        reasons.append("recruiting mailbox address")
    if re.search(r"\b(20\d{2})\b", body) and (subject_hits or body_hits):
        score += 0.25
        reasons.append("application year present")
    return RelevanceResult(round(score, 2), reasons)


def is_relevant(email: ParsedEmail, threshold: float = 2.0) -> bool:
    return score_email(email).score >= threshold
