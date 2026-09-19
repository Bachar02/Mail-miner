from __future__ import annotations

from .models import ContactCandidate


def score_candidate(candidate: ContactCandidate) -> ContactCandidate:
    score = 0.25
    reasons: list[str] = []
    if candidate.name:
        score += 0.2
        reasons.append("name available")
    if candidate.source == "signature":
        score += 0.25
        reasons.append("name found in signature")
    elif candidate.source == "header":
        score += 0.12
        reasons.append("name found in email header")
    elif candidate.source == "body":
        reasons.append("person mentioned in body")
    if candidate.company:
        score += 0.12
        reasons.append("company explicitly stated")
    if candidate.role:
        score += 0.12
        reasons.append("role explicitly stated")
    if candidate.company_domain and candidate.company:
        score += 0.06
        reasons.append("company domain supports company")
    if candidate.email and "@" in candidate.email and candidate.email.split("@", 1)[1] not in {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com"}:
        score += 0.08
        reasons.append("professional company email")
    candidate.confidence = round(min(score, 0.99), 2)
    candidate.confidence_reasons = reasons
    return candidate
