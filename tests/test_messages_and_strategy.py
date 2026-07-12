from __future__ import annotations

from dataclasses import replace

from job_hunter_agent.messages import build_outreach_drafts
from job_hunter_agent.search_queries import generate_contact_search_queries, infer_role_family
from job_hunter_agent.strategy import OutreachSuggestion, suggest_outreach
from job_hunter_agent.contacts import rank_contacts
from job_hunter_agent.jobs import rank_jobs

from tests.conftest import make_job
from tests.test_contacts import make_contact


def _suggestion(**overrides) -> OutreachSuggestion:
    defaults = dict(
        company="Acme",
        job_title="Data Engineer",
        contact_name="Jane Doe",
        contact_title="Engineer",
        score=0.9,
        reasons=["same company"],
        job_url="https://example.com/job",
        contact_url="https://linkedin.com/in/janedoe",
    )
    defaults.update(overrides)
    return OutreachSuggestion(**defaults)


def test_drafts_use_profile_pitch(profile):
    custom = replace(profile, pitch="I'm a test engineer who ships things")
    drafts = build_outreach_drafts(custom, [_suggestion()])
    assert "I'm a test engineer who ships things" in drafts[0].message
    assert drafts[0].message.startswith("Hi Jane Doe")
    assert drafts[0].message.endswith(custom.name)


def test_drafts_fall_back_to_generated_pitch(profile):
    drafts = build_outreach_drafts(profile, [_suggestion()])
    assert "Madrid-based" in drafts[0].message
    assert "4.5 years" in drafts[0].message


def test_drafts_mention_shared_university(profile):
    drafts = build_outreach_drafts(profile, [_suggestion(reasons=["shared university"])])
    assert "shared university connection" in drafts[0].message


def test_suggest_outreach_boosts_same_company(profile):
    jobs = rank_jobs(profile, [make_job(company="Acme", min_salary_eur=90000, max_salary_eur=110000, hours_risk="low")])
    contacts = rank_contacts(
        profile,
        [
            make_contact(full_name="Insider", company="Acme", same_university=True, hiring_manager=True),
            make_contact(full_name="Outsider", company="Elsewhere", same_university=True, hiring_manager=True),
        ],
    )
    suggestions = suggest_outreach(jobs, contacts)
    assert suggestions
    assert suggestions[0].contact_name == "Insider"
    assert "same company" in suggestions[0].reasons


def test_generate_contact_search_queries(profile):
    ranked = rank_jobs(profile, [make_job()])
    queries = generate_contact_search_queries(profile, ranked)
    assert queries
    personas = {query.persona for query in queries}
    assert "recruiter" in personas
    assert "alumni" in personas
    assert all(query.linkedin_url.startswith("https://www.linkedin.com/search/") for query in queries)
    # deduped: no repeated (company, query) pairs
    keys = [(query.company, query.query) for query in queries]
    assert len(keys) == len(set(keys))


def test_infer_role_family():
    assert infer_role_family("Senior Data Platform Engineer") == "data engineer"
    assert infer_role_family("Cloud Infrastructure Engineer") == "cloud engineer"
    assert infer_role_family("Widget Specialist") == "engineer"
