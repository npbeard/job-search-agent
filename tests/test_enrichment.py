from __future__ import annotations

from job_hunter_agent.enrichment import (
    infer_level,
    infer_required_years,
    infer_salary,
    infer_skills,
    is_job_relevant,
    location_parts,
    normalize_location,
    normalize_target_titles,
)

from tests.conftest import make_job


def test_infer_level_from_title():
    assert infer_level("Senior Data Engineer", "unknown") == "senior"
    assert infer_level("Staff Engineer", "unknown") == "staff"
    assert infer_level("Junior Developer", "unknown") == "entry"
    assert infer_level("Data Engineer", "unknown") == "mid"


def test_infer_level_keeps_existing_value():
    assert infer_level("Senior Data Engineer", "mid") == "mid"


def test_infer_required_years_defaults():
    assert infer_required_years("senior", None) == 5.0
    assert infer_required_years("entry", None) == 0.0
    assert infer_required_years("mid", 2.0) == 2.0


def test_infer_salary_prefers_company_band():
    bands = {
        "global_defaults": {"mid": [60000, 85000]},
        "companies": {"Acme": {"mid": [70000, 90000]}},
    }
    assert infer_salary("Acme", "mid", bands, None, None) == (70000, 90000)
    assert infer_salary("Other", "mid", bands, None, None) == (60000, 85000)
    assert infer_salary("Acme", "mid", bands, 50000, 55000) == (50000, 55000)


def test_infer_skills_casing_is_clean():
    skills = infer_skills("Data Engineer", [])
    assert "SQL" in skills
    assert "Sql" not in skills
    assert "Aws" not in " ".join(skills)


def test_infer_skills_keeps_existing():
    assert infer_skills("Data Engineer", ["Rust"]) == ["Rust"]


def test_normalize_location_madrid_and_remote():
    assert normalize_location("Madrid") == "Madrid, Spain"
    assert normalize_location("Remote - Spain") == "Remote - Spain"
    assert normalize_location("Spain (Remote)") == "Remote - Spain"
    assert normalize_location("Germany (Remote) ; Spain (Remote)") == "Remote - Spain"


def test_normalize_location_keeps_spanish_cities():
    assert normalize_location("Barcelona, Spain") == "Barcelona, Spain"
    assert normalize_location("Valencia, Spain") == "Valencia, Spain"


def test_normalize_location_passthrough():
    assert normalize_location("Berlin, Germany") == "Berlin, Germany"


def test_location_parts():
    assert location_parts("Madrid, Spain") == ("Madrid", "Spain")
    assert location_parts("Barcelona, Spain") == ("Barcelona", "Spain")
    assert location_parts("Remote - Spain") == ("Remote", "Spain")
    assert location_parts("Remote - Europe") == ("Remote", "Europe")
    assert location_parts("Remote") == ("Remote", "Anywhere")
    assert location_parts("Madrid, Comunidad de Madrid") == ("Madrid", "Spain")
    assert location_parts("Berlin, Germany") == ("Berlin", "Germany")
    assert location_parts("Paris") == ("Paris", "Unknown")
    assert location_parts("") == ("Unknown", "Unknown")


def test_is_job_relevant_accepts_target_title(profile):
    job = make_job(title="Data Engineer")
    relevant, reasons = is_job_relevant(profile, job)
    assert relevant, reasons


def test_is_job_relevant_rejects_leadership(profile):
    job = make_job(title="Engineering Manager, Data")
    relevant, reasons = is_job_relevant(profile, job)
    assert not relevant
    assert any("leadership" in reason for reason in reasons)


def test_is_job_relevant_rejects_too_senior(profile):
    job = make_job(title="Principal Data Engineer", level="principal", required_years_experience=10)
    relevant, reasons = is_job_relevant(profile, job)
    assert not relevant


def test_normalize_target_titles_expands_aliases():
    expanded = normalize_target_titles(["Cloud Engineer"])
    assert "cloud engineer" in expanded
    assert "platform engineer" in expanded
