from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.models import RankedContact, RankedJob


@dataclass
class OutreachSuggestion:
    company: str
    job_title: str
    contact_name: str
    contact_title: str
    score: float
    reasons: list[str]
    job_url: str
    contact_url: str


def suggest_outreach(ranked_jobs: list[RankedJob], ranked_contacts: list[RankedContact]) -> list[OutreachSuggestion]:
    suggestions: list[OutreachSuggestion] = []
    for ranked_job in ranked_jobs:
        for ranked_contact in ranked_contacts:
            score = (ranked_job.score * 0.6) + (ranked_contact.score * 0.4)
            reasons: list[str] = []
            if ranked_job.job.company.lower() == ranked_contact.contact.company.lower():
                score += 0.2
                reasons.append("same company")
            if ranked_contact.contact.recruiter:
                reasons.append("recruiter contact")
            if ranked_contact.contact.hiring_manager:
                reasons.append("hiring manager signal")
            if ranked_contact.contact.same_university:
                reasons.append("shared university")
            if ranked_contact.contact.works_in_target_role:
                reasons.append("close to target role")
            if score >= 0.7:
                suggestions.append(
                    OutreachSuggestion(
                        company=ranked_job.job.company,
                        job_title=ranked_job.job.title,
                        contact_name=ranked_contact.contact.full_name,
                        contact_title=ranked_contact.contact.title,
                        score=round(min(score, 1.0), 4),
                        reasons=reasons,
                        job_url=ranked_job.job.url,
                        contact_url=ranked_contact.contact.linkedin_url,
                    )
                )
    return sorted(suggestions, key=lambda item: item.score, reverse=True)

