from __future__ import annotations

from job_hunter_agent.enrichment import normalize_target_titles
from job_hunter_agent.io_utils import load_json
from job_hunter_agent.models import CandidateProfile, JobOpportunity, RankedJob


HOURS_WEIGHT = {"low": 1.0, "medium": 0.65, "high": 0.1, "unknown": 0.5}
LEVEL_MATCH = {
    "entry": 0.7,
    "mid": 1.0,
    "senior": 0.7,
    "staff": 0.2,
    "principal": 0.1,
    "unknown": 0.6,
}


def load_jobs(path: str) -> list[JobOpportunity]:
    payload = load_json(path)
    return [JobOpportunity(**item) for item in payload]


def _normalize(text: str) -> str:
    return text.strip().lower()


def _average_salary(job: JobOpportunity) -> float:
    if job.min_salary_eur is not None and job.max_salary_eur is not None:
        return (job.min_salary_eur + job.max_salary_eur) / 2
    if job.max_salary_eur is not None:
        return float(job.max_salary_eur)
    if job.min_salary_eur is not None:
        return float(job.min_salary_eur)
    return 0.0


def _salary_score(profile: CandidateProfile, job: JobOpportunity) -> float:
    avg_salary = _average_salary(job)
    if avg_salary <= 0:
        return 0.35
    floor = max(profile.salary_floor_eur, 1)
    return min(avg_salary / floor, 2.0) / 2.0


def _fit_score(profile: CandidateProfile, job: JobOpportunity) -> tuple[float, list[str]]:
    reasons: list[str] = []
    profile_skills = {_normalize(skill) for skill in profile.skills}
    job_skills = {_normalize(skill) for skill in job.skills}
    skill_overlap = len(profile_skills & job_skills)
    expanded_titles = normalize_target_titles(profile.target_titles)
    title_lower = _normalize(job.title)
    exact_title_match = any(
        _normalize(target) in title_lower or title_lower in _normalize(target)
        for target in profile.target_titles
    )
    alias_title_match = any(alias in title_lower for alias in expanded_titles)
    if exact_title_match:
        title_bonus = 0.3
        reasons.append("title aligns with target roles")
    elif alias_title_match:
        title_bonus = 0.2
        reasons.append("title is a close match for target role family")
    else:
        title_bonus = 0.0
    score = min(skill_overlap / 5.0, 1.0) * 0.7 + title_bonus
    if skill_overlap:
        reasons.append(f"{skill_overlap} matching core skills")
    return min(score, 1.0), reasons


def _realism_score(profile: CandidateProfile, job: JobOpportunity) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = LEVEL_MATCH.get(_normalize(job.level), 0.6)
    required_years = job.required_years_experience or profile.years_experience
    gap = required_years - profile.years_experience
    if gap <= 0:
        score += 0.2
        reasons.append("experience level is within reach")
    elif gap <= 1.5:
        score += 0.05
        reasons.append("slight stretch but still plausible")
    else:
        score -= min(gap * 0.15, 0.6)
        reasons.append("experience requirement is a meaningful stretch")
    if job.title in profile.stretch_level_titles:
        reasons.append("title is in your accepted stretch range")
    if required_years > profile.max_reasonable_required_years:
        score -= 0.2
        reasons.append("required experience may be too high")
    return max(min(score, 1.0), 0.0), reasons


def _lifestyle_score(profile: CandidateProfile, job: JobOpportunity) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = HOURS_WEIGHT.get(_normalize(job.hours_risk), 0.5)
    text = f"{job.company} {job.title} {job.location}".lower()
    if any(keyword.lower() in text for keyword in profile.avoid_keywords):
        score = min(score, 0.1)
        reasons.append("contains avoid keyword")
    if job.hours_risk in profile.avoid_hours_risk:
        reasons.append("hours risk is higher than preferred")
    else:
        reasons.append("hours risk is within preferred range")
    if any(pref.lower() in job.location.lower() for pref in profile.preferred_locations):
        score += 0.1
        reasons.append("preferred location")
    return min(score, 1.0), reasons


def rank_jobs(profile: CandidateProfile, jobs: list[JobOpportunity]) -> list[RankedJob]:
    ranked: list[RankedJob] = []
    for job in jobs:
        salary = _salary_score(profile, job)
        fit, fit_reasons = _fit_score(profile, job)
        realism, realism_reasons = _realism_score(profile, job)
        lifestyle, lifestyle_reasons = _lifestyle_score(profile, job)
        total = (salary * 0.35) + (fit * 0.3) + (realism * 0.25) + (lifestyle * 0.1)
        ranked.append(
            RankedJob(
                job=job,
                score=round(total, 4),
                salary_score=round(salary, 4),
                fit_score=round(fit, 4),
                realism_score=round(realism, 4),
                lifestyle_score=round(lifestyle, 4),
                reasons=fit_reasons + realism_reasons + lifestyle_reasons,
            )
        )
    return sorted(ranked, key=lambda item: item.score, reverse=True)

