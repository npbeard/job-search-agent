from __future__ import annotations

from job_hunter_agent.models import CandidateProfile, OutreachDraft
from job_hunter_agent.strategy import OutreachSuggestion


def _default_pitch(profile: CandidateProfile) -> str:
    top_skills = ", ".join(profile.skills[:4]) if profile.skills else "software engineering"
    return (
        f"I'm a {profile.location.split(',')[0]}-based engineer with about "
        f"{profile.years_experience:g} years of experience, focused on {top_skills}"
    )


def build_outreach_drafts(
    profile: CandidateProfile,
    suggestions: list[OutreachSuggestion],
    limit: int = 10,
) -> list[OutreachDraft]:
    pitch = profile.pitch.strip().rstrip(".") or _default_pitch(profile)
    drafts: list[OutreachDraft] = []
    for suggestion in suggestions[:limit]:
        bridge = ""
        if "shared university" in suggestion.reasons:
            bridge = "We also seem to have a shared university connection, which made this feel a bit less out of the blue. "
        message = (
            f"Hi {suggestion.contact_name},\n\n"
            f"{pitch}. I came across the {suggestion.job_title} role at {suggestion.company} and it looks "
            f"like a strong fit for my background. "
            f"{bridge}If you're open to it, I'd really appreciate a quick perspective on the team and whether you think the role "
            f"is worth pursuing. If after that it feels appropriate, I'd be grateful for a referral.\n\n"
            f"Thanks,\n{profile.name}"
        )
        drafts.append(
            OutreachDraft(
                company=suggestion.company,
                job_title=suggestion.job_title,
                contact_name=suggestion.contact_name,
                contact_title=suggestion.contact_title,
                score=suggestion.score,
                subject=f"{suggestion.company} {suggestion.job_title} - quick question",
                message=message,
                contact_url=suggestion.contact_url,
                job_url=suggestion.job_url,
            )
        )
    return drafts
