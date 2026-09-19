from __future__ import annotations

import json
import os
from typing import Protocol

from .models import ContactCandidate, ParsedEmail

ALLOWED_TYPES = {"recruiter", "hr", "hiring_manager", "ceo", "founder", "engineer", "researcher", "professor", "manager", "employee", "other"}

class LLMProvider(Protocol):
    def enrich(self, email: ParsedEmail, snippet: str) -> list[dict]: ...

class OpenAIProvider:
    def __init__(self, model: str):
        self.model = model
        from openai import OpenAI
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def enrich(self, email: ParsedEmail, snippet: str) -> list[dict]:
        prompt = "Extract only evidenced professional contacts from this email. Return a JSON array. Null means unknown; never guess. Fields: name,email,company,role,contact_type,country,company_domain,position_applied_for,application_type,application_year,evidence,confidence. Allowed contact_type: " + ",".join(sorted(ALLOWED_TYPES)) + "\nEmail:\n" + snippet[:6000]
        response = self.client.chat.completions.create(model=self.model, temperature=0, response_format={"type": "json_object"}, messages=[{"role": "system", "content": prompt}])
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        return data if isinstance(data, list) else data.get("contacts", [])


def candidates_from_llm(items: list[dict], message_id: str) -> list[ContactCandidate]:
    result = []
    for item in items:
        if not item.get("email"):
            continue
        contact_type = item.get("contact_type") if item.get("contact_type") in ALLOWED_TYPES else None
        result.append(ContactCandidate(name=item.get("name"), email=item["email"], source="llm", source_message_id=message_id, company=item.get("company"), role=item.get("role"), contact_type=contact_type, country=item.get("country"), company_domain=item.get("company_domain"), position_applied_for=item.get("position_applied_for"), application_type=item.get("application_type"), application_year=item.get("application_year"), evidence=item.get("evidence") if isinstance(item.get("evidence"), list) else [str(item.get("evidence"))] if item.get("evidence") else [], confidence=float(item.get("confidence") or 0)))
    return result
