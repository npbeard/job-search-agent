from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CandidateProfile:
    name: str
    location: str
    citizenships: list[str]
    languages: list[str]
    universities: list[str]
    years_experience: float
    target_titles: list[str]
    skills: list[str]
    preferred_locations: list[str]
    avoid_keywords: list[str]
    avoid_hours_risk: list[str]
    preferred_hours_risk: list[str]
    salary_floor_eur: int
    stretch_level_titles: list[str]
    max_reasonable_required_years: int
    notes: str = ""


@dataclass
class JobOpportunity:
    company: str
    title: str
    location: str
    remote_type: str
    employment_type: str
    min_salary_eur: int | None = None
    max_salary_eur: int | None = None
    hours_risk: str = "unknown"
    required_years_experience: float | None = None
    level: str = "unknown"
    skills: list[str] = field(default_factory=list)
    url: str = ""
    source: str = ""


@dataclass
class RankedJob:
    job: JobOpportunity
    score: float
    salary_score: float
    fit_score: float
    realism_score: float
    lifestyle_score: float
    reasons: list[str]


@dataclass
class ReferralContact:
    full_name: str
    company: str
    title: str
    location: str
    linkedin_url: str
    university: str = ""
    shared_connections: int = 0
    same_university: bool = False
    recruiter: bool = False
    hiring_manager: bool = False
    works_in_target_role: bool = False


@dataclass
class RankedContact:
    contact: ReferralContact
    score: float
    reasons: list[str]


@dataclass
class OutreachDraft:
    company: str
    job_title: str
    contact_name: str
    contact_title: str
    score: float
    subject: str
    message: str
    contact_url: str
    job_url: str


@dataclass
class ContactSearchQuery:
    company: str
    job_title: str
    persona: str
    query: str
    linkedin_url: str
    score: float
    reasons: list[str]
