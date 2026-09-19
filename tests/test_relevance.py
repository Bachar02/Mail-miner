from contact_miner.models import ParsedEmail
from contact_miner.relevance import is_relevant, score_email


def test_bilingual_relevance():
    email = ParsedEmail("<1>", "2024-01-01", "Candidature stage IA", "hr@company.com", [], [], [], "Votre candidature pour un stage sera étudiée", "")
    result = score_email(email)
    assert is_relevant(email)
    assert result.score >= 4
