from __future__ import annotations

import re

FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "outlook.fr", "hotmail.com", "hotmail.fr", "live.com", "live.fr",
    "msn.com", "yahoo.com", "yahoo.fr", "ymail.com", "icloud.com", "me.com", "aol.com", "gmx.com", "gmx.fr",
    "protonmail.com", "proton.me", "mail.com", "laposte.net", "orange.fr", "free.fr",
}
# Second-level labels used under country TLDs, e.g. company.co.uk or company.com.tn
_SECOND_LEVEL = {"co", "com", "org", "net", "ac", "edu", "gov", "gouv", "ens", "nat"}

NOISE_LOCAL_PATTERN = re.compile(
    r"(?i)(^|[._+-])(no-?reply|do-?not-?reply|notifications?|notify|mailer-daemon|postmaster|bounces?|"
    r"newsletters?|marketing|alerts?|jobalerts|digest|updates|news|info-?mail|automated|system)([._+-]|$)"
)
GENERIC_JOB_LOCALPARTS = {
    "hr", "rh", "recruitment", "recrutement", "recruiting", "recruiter", "careers", "career", "jobs", "job",
    "talent", "talents", "hiring", "internships", "internship", "stage", "stages", "candidature", "candidatures",
}


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    return value[1:-1] if value.startswith("<") and value.endswith(">") else value


def local_part(email: str) -> str:
    return normalize_email(email).split("@", 1)[0]


def domain_from_email(email: str) -> str | None:
    normalized = normalize_email(email)
    return normalized.split("@", 1)[1] if "@" in normalized else None


def is_free_email_domain(domain: str | None) -> bool:
    return bool(domain) and domain.casefold() in FREE_EMAIL_DOMAINS


def is_noise_address(email: str) -> bool:
    """Automated senders (no-reply, notifications, bounces, newsletters) are never contacts."""
    return bool(NOISE_LOCAL_PATTERN.search(local_part(email)))


def is_generic_job_mailbox(email: str) -> bool:
    return local_part(email) in GENERIC_JOB_LOCALPARTS


def registrable_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    labels = domain.casefold().strip(".").split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def normalize_company(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" .,-|")
    return cleaned or None


def company_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def company_from_domain(domain: str | None) -> str | None:
    if not domain or is_free_email_domain(domain):
        return None
    registrable = registrable_domain(domain)
    if not registrable:
        return None
    return registrable.split(".")[0].replace("-", " ").title()
