from __future__ import annotations

from urllib.parse import quote_plus

from job_hunter_agent.models import CandidateProfile, ContactSearchQuery, RankedJob


PERSONA_TEMPLATES = [
    {
        "persona": "recruiter",
        "parts": ["{company}", "{location}", "technical recruiter"],
        "score": 0.72,
        "reason": "direct path to recruiting team",
    },
    {
        "persona": "hiring manager",
        "parts": ["{company}", "{location}", "engineering manager", "{role_family}"],
        "score": 0.78,
        "reason": "likely hiring influence",
    },
    {
        "persona": "peer engineer",
        "parts": ["{company}", "{location}", "{job_title}"],
        "score": 0.76,
        "reason": "peer referral target for the exact role family",
    },
    {
        "persona": "alumni",
        "parts": ["{company}", "{location}", "{role_family}", "{university}"],
        "score": 0.86,
        "reason": "shared school background improves response odds",
    },
    {
        "persona": "second degree style",
        "parts": ["{company}", "{location}", "{role_family}", "shared connections"],
        "score": 0.67,
        "reason": "good fallback when direct alumni matches are thin",
    },
]


def generate_contact_search_queries(
    profile: CandidateProfile,
    ranked_jobs: list[RankedJob],
    limit_jobs: int = 10,
) -> list[ContactSearchQuery]:
    queries: list[ContactSearchQuery] = []
    for ranked_job in ranked_jobs[:limit_jobs]:
        job = ranked_job.job
        role_family = infer_role_family(job.title)
        universities = profile.universities[:2] or [""]
        for template in PERSONA_TEMPLATES:
            schools = universities if "{university}" in " ".join(template["parts"]) else [""]
            for university in schools:
                parts = [
                    part.format(
                        company=job.company,
                        location=normalize_search_location(job.location),
                        job_title=job.title,
                        role_family=role_family,
                        university=university,
                    ).strip()
                    for part in template["parts"]
                ]
                query = " ".join(part for part in parts if part)
                score = min(1.0, template["score"] + (ranked_job.score * 0.2))
                reasons = [template["reason"], f"built from ranked role score {ranked_job.score:.2f}"]
                if university:
                    reasons.append(f"targets {university} alumni")
                queries.append(
                    ContactSearchQuery(
                        company=job.company,
                        job_title=job.title,
                        persona=template["persona"],
                        query=query,
                        linkedin_url=f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}",
                        score=round(score, 4),
                        reasons=reasons,
                    )
                )
    deduped: list[ContactSearchQuery] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(queries, key=lambda query: query.score, reverse=True):
        key = (item.company.lower(), item.query.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def infer_role_family(job_title: str) -> str:
    lowered = job_title.lower()
    if "data" in lowered:
        return "data engineer"
    if "site reliability" in lowered or "sre" in lowered:
        return "site reliability engineer"
    if "platform" in lowered:
        return "platform engineer"
    if "cloud" in lowered:
        return "cloud engineer"
    if "backend" in lowered:
        return "backend engineer"
    if "software" in lowered:
        return "software engineer"
    if "infrastructure" in lowered:
        return "infrastructure engineer"
    return "engineer"


def normalize_search_location(location: str) -> str:
    lowered = location.lower()
    if "remote" in lowered and "spain" in lowered:
        return "Spain"
    if "madrid" in lowered:
        return "Madrid"
    return location
