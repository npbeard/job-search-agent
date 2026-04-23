from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from job_hunter_agent.io_utils import load_csv, load_json
from job_hunter_agent.models import CandidateProfile, RankedContact, ReferralContact


def load_contacts(path: str) -> list[ReferralContact]:
    source = Path(path)
    if source.suffix.lower() == ".csv":
        rows = load_csv(source)
    else:
        rows = load_json(source)
    contacts: list[ReferralContact] = []
    for row in rows:
        normalized = dict(row)
        for key in ("shared_connections",):
            if key in normalized and normalized[key] != "":
                normalized[key] = int(normalized[key])
        for key in ("same_university", "recruiter", "hiring_manager", "works_in_target_role"):
            value = normalized.get(key, False)
            if isinstance(value, str):
                normalized[key] = value.strip().lower() in {"1", "true", "yes", "y"}
        normalized["linkedin_url"] = resolve_contact_url(
            normalized.get("linkedin_url", ""),
            normalized.get("full_name", ""),
            normalized.get("company", ""),
            normalized.get("location", ""),
            normalized.get("title", ""),
        )
        contacts.append(ReferralContact(**normalized))
    return contacts


def resolve_contact_url(linkedin_url: str, full_name: str, company: str, location: str, title: str) -> str:
    if linkedin_url and "example-" not in linkedin_url and "/404" not in linkedin_url:
        return linkedin_url
    query = " ".join(part for part in [full_name, company, title, location] if part).strip()
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"


def rank_contacts(profile: CandidateProfile, contacts: list[ReferralContact]) -> list[RankedContact]:
    ranked: list[RankedContact] = []
    target_titles = {title.lower() for title in profile.target_titles}
    for contact in contacts:
        reasons: list[str] = []
        score = 0.0
        if contact.same_university or contact.university in profile.universities:
            score += 0.35
            reasons.append("shared university background")
        if contact.shared_connections:
            score += min(contact.shared_connections / 20.0, 0.25)
            reasons.append(f"{contact.shared_connections} shared connections")
        if contact.recruiter:
            score += 0.2
            reasons.append("recruiter access")
        if contact.hiring_manager:
            score += 0.25
            reasons.append("likely hiring influence")
        if contact.works_in_target_role or any(title.lower() in contact.title.lower() for title in target_titles):
            score += 0.2
            reasons.append("works close to target role")
        if any(pref.lower() in contact.location.lower() for pref in profile.preferred_locations):
            score += 0.05
            reasons.append("good location match")
        ranked.append(RankedContact(contact=contact, score=round(min(score, 1.0), 4), reasons=reasons))
    return sorted(ranked, key=lambda item: item.score, reverse=True)
