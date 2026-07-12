from __future__ import annotations

from dataclasses import replace

from job_hunter_agent.io_utils import load_json
from job_hunter_agent.models import CandidateProfile, JobOpportunity


LEVEL_KEYWORDS = [
    ("principal", "principal"),
    ("staff", "staff"),
    ("senior", "senior"),
    ("lead", "senior"),
    ("manager", "senior"),
    ("junior", "entry"),
    ("graduate", "entry"),
    ("intern", "entry"),
]

ROLE_SKILL_HINTS = {
    "data": ["SQL", "ETL", "ELT", "Spark", "dbt", "Warehouse"],
    "backend": ["Python", "Java", "APIs", "Microservices", "Backend Systems"],
    "platform": ["AWS", "Terraform", "Linux", "Kubernetes", "Reliability"],
    "sre": ["Linux", "Terraform", "AWS", "Reliability", "Incident Response"],
}

TITLE_SKILL_HINTS = {
    "data engineer": ["SQL", "ETL", "ELT", "Spark", "Python"],
    "backend engineer": ["Python", "Java", "APIs", "Backend Systems", "AWS"],
    "software engineer": ["Python", "Java", "AWS", "Linux"],
    "platform engineer": ["AWS", "Terraform", "Linux"],
    "infrastructure engineer": ["AWS", "Terraform", "Linux"],
    "site reliability engineer": ["AWS", "Terraform", "Linux"],
}

TARGET_TITLE_ALIASES = {
    "software engineer": {"software engineer", "backend engineer", "backend developer"},
    "backend engineer": {"backend engineer", "software engineer", "backend developer"},
    "platform engineer": {"platform engineer", "infrastructure engineer", "site reliability engineer"},
    "data engineer": {"data engineer", "analytics engineer", "data platform engineer"},
    "site reliability engineer": {"site reliability engineer", "platform engineer", "infrastructure engineer"},
    "cloud engineer": {"cloud engineer", "platform engineer", "infrastructure engineer"},
}

LEADERSHIP_KEYWORDS = {
    "manager",
    "management",
    "director",
    "vp",
    "vice president",
    "head of",
}

ARCHITECT_KEYWORDS = {
    "architect",
}


def load_salary_bands(path: str) -> dict:
    return load_json(path)


def enrich_jobs(
    jobs: list[JobOpportunity],
    salary_bands: dict,
    profile: CandidateProfile | None = None,
) -> list[JobOpportunity]:
    enriched: list[JobOpportunity] = []
    for job in jobs:
        level = infer_level(job.title, job.level)
        required_years = infer_required_years(level, job.required_years_experience)
        skills = infer_skills(job.title, job.skills)
        min_salary, max_salary = infer_salary(job.company, level, salary_bands, job.min_salary_eur, job.max_salary_eur)
        hours_risk = infer_hours_risk(job.title, job.hours_risk)
        normalized_location = normalize_location(job.location)
        enriched.append(
            replace(
                job,
                level=level,
                required_years_experience=required_years,
                skills=skills,
                min_salary_eur=min_salary,
                max_salary_eur=max_salary,
                hours_risk=hours_risk,
                location=normalized_location,
            )
        )
    return enriched


def infer_level(title: str, current_level: str) -> str:
    if current_level and current_level != "unknown":
        return current_level
    lowered = title.lower()
    for needle, level in LEVEL_KEYWORDS:
        if needle in lowered:
            return level
    return "mid"


def infer_required_years(level: str, current_value: float | None) -> float:
    if current_value is not None:
        return current_value
    defaults = {
        "entry": 0.0,
        "mid": 3.0,
        "senior": 5.0,
        "staff": 7.0,
        "principal": 9.0,
        "unknown": 3.0,
    }
    return defaults.get(level, 3.0)


def infer_skills(title: str, existing_skills: list[str]) -> list[str]:
    if existing_skills:
        return existing_skills
    lowered = title.lower()
    collected: list[str] = []
    for keyword, skills in TITLE_SKILL_HINTS.items():
        if keyword in lowered:
            collected.extend(skills)
    for keyword, skills in ROLE_SKILL_HINTS.items():
        if keyword in lowered:
            collected.extend(skills)
    deduped: list[str] = []
    seen: set[str] = set()
    for skill in collected:
        marker = skill.lower()
        if marker not in seen:
            deduped.append(skill)
            seen.add(marker)
    return deduped


def infer_salary(
    company: str,
    level: str,
    salary_bands: dict,
    min_salary: int | None,
    max_salary: int | None,
) -> tuple[int | None, int | None]:
    if min_salary is not None or max_salary is not None:
        return min_salary, max_salary
    company_bands = salary_bands.get("companies", {}).get(company, {})
    band = company_bands.get(level) or salary_bands.get("global_defaults", {}).get(level)
    if not band:
        return min_salary, max_salary
    return int(band[0]), int(band[1])


def infer_hours_risk(title: str, current_hours_risk: str) -> str:
    if current_hours_risk != "unknown":
        return current_hours_risk
    lowered = title.lower()
    if "consult" in lowered or "architect" in lowered:
        return "high"
    if "staff" in lowered or "principal" in lowered:
        return "high"
    if "senior" in lowered or "manager" in lowered:
        return "medium"
    return "medium"


SPAIN_CITIES = ["barcelona", "valencia", "seville", "sevilla", "bilbao", "malaga", "zaragoza"]


def normalize_location(location: str) -> str:
    lowered = location.lower()
    if "madrid" in lowered:
        return "Madrid, Spain"
    if "spain" in lowered and "remote" in lowered:
        return "Remote - Spain"
    # Multi-country remote strings (e.g. Typeform: "Germany (Remote) ; Spain (Remote) ; ...")
    # If Spain appears in a multi-location string, treat as Spain-remote
    if "spain" in lowered and (";" in location or "|" in location):
        return "Remote - Spain"
    # Keep specific Spanish cities as-is instead of mislabeling them remote
    for city in SPAIN_CITIES:
        if city in lowered:
            return f"{city.title()}, Spain"
    if "spain" in lowered:
        return "Remote - Spain"
    return location


SPAIN_REGION_MARKERS = ["spain", "comunidad de madrid", "cataluña", "catalonia", "andaluc", "país vasco", "basque"]


def location_parts(location: str) -> tuple[str, str]:
    """Split a free-form job location into (city, country) for filtering.

    Remote listings report city "Remote" and their eligible region as country.
    """
    text = location.strip()
    lowered = text.lower()
    if lowered.startswith("remote"):
        region = text.split("-", 1)[1].strip() if "-" in text else "Anywhere"
        return "Remote", region or "Anywhere"
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        return "Unknown", "Unknown"
    city = parts[0]
    country = parts[-1] if len(parts) > 1 else ""
    if any(marker in lowered for marker in SPAIN_REGION_MARKERS):
        country = "Spain"
    return city, country or "Unknown"


def is_job_relevant(profile: CandidateProfile, job: JobOpportunity) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    title = job.title.lower()
    if any(keyword.lower() in title for keyword in profile.avoid_keywords):
        reasons.append("title contains avoid keyword")
    if any(keyword in title for keyword in LEADERSHIP_KEYWORDS):
        reasons.append("leadership role is outside target scope")
    if any(keyword in title for keyword in ARCHITECT_KEYWORDS):
        reasons.append("architect role is outside target scope")
    if job.level in {"staff", "principal"}:
        reasons.append("level is likely too senior")
    if job.required_years_experience and job.required_years_experience > profile.max_reasonable_required_years + 1:
        reasons.append("experience requirement is too high")
    normalized_targets = normalize_target_titles(profile.target_titles)
    if not any(alias in title for alias in normalized_targets):
        reasons.append("title is outside target role families")
    return len(reasons) == 0, reasons


def normalize_target_titles(titles: list[str]) -> set[str]:
    normalized: set[str] = set()
    for title in titles:
        lowered = title.lower()
        normalized.add(lowered)
        normalized.update(TARGET_TITLE_ALIASES.get(lowered, set()))
    return normalized
