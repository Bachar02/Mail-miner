from __future__ import annotations

from .company_normalizer import company_from_domain, company_key, is_free_email_domain, is_generic_job_mailbox
from .models import ContactCandidate


def score_candidate(candidate: ContactCandidate) -> ContactCandidate:
    """Explainable confidence: every point added comes with a human-readable reason."""
    score = 0.25
    reasons: list[str] = []
    if candidate.name:
        score += 0.2
        reasons.append("name available")
    if candidate.source == "signature":
        score += 0.25
        reasons.append("details found in sender signature")
    elif candidate.source == "header":
        score += 0.12
        reasons.append("address found in email header")
    elif candidate.source == "body":
        reasons.append("address mentioned in body")
    domain_company = company_from_domain(candidate.company_domain)
    if candidate.company and domain_company and candidate.company == domain_company:
        score += 0.06
        reasons.append("company inferred from email domain")
    elif candidate.company:
        score += 0.12
        reasons.append("company explicitly stated")
        if domain_company and company_key(candidate.company).startswith(company_key(domain_company)):
            score += 0.06
            reasons.append("company domain supports company")
    if candidate.role:
        score += 0.12
        reasons.append("role explicitly stated")
    if candidate.company_domain and not is_free_email_domain(candidate.company_domain):
        score += 0.08
        reasons.append("professional company email")
    if is_generic_job_mailbox(candidate.email):
        reasons.append("generic recruiting mailbox")
    candidate.confidence = round(min(score, 0.99), 2)
    candidate.confidence_reasons = reasons
    return candidate
