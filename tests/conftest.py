from __future__ import annotations

import pytest

from job_hunter_agent.models import CandidateProfile, JobOpportunity


@pytest.fixture
def profile() -> CandidateProfile:
    return CandidateProfile(
        name="Test Candidate",
        location="Madrid, Spain",
        citizenships=["Spain"],
        languages=["English", "Spanish"],
        universities=["IE University"],
        years_experience=4.5,
        target_titles=["Software Engineer", "Data Engineer", "Cloud Engineer"],
        skills=["Python", "SQL", "AWS", "Terraform", "Spark", "Linux"],
        preferred_locations=["Madrid, Spain", "Remote - Spain", "Spain"],
        avoid_keywords=["consulting"],
        avoid_hours_risk=["high"],
        preferred_hours_risk=["low", "medium"],
        salary_floor_eur=55000,
        stretch_level_titles=["Senior Data Engineer"],
        max_reasonable_required_years=6,
    )


def make_job(**overrides) -> JobOpportunity:
    defaults = dict(
        company="Acme",
        title="Data Engineer",
        location="Madrid, Spain",
        remote_type="hybrid",
        employment_type="full-time",
        min_salary_eur=60000,
        max_salary_eur=80000,
        hours_risk="medium",
        required_years_experience=3.0,
        level="mid",
        skills=["Python", "SQL", "AWS"],
        url="https://example.com/job",
        source="test",
    )
    defaults.update(overrides)
    return JobOpportunity(**defaults)
