from __future__ import annotations

import pytest

from job_hunter_agent import collectors
from job_hunter_agent.collectors import (
    CollectionError,
    _parse_salary_text,
    fetch_adzuna_jobs,
    fetch_ashby_jobs,
    fetch_remotive_jobs,
    fetch_themuse_jobs,
)


def _patch_fetch(monkeypatch, responses):
    """Replace the HTTP fetch with canned responses, keyed by URL substring."""
    calls = []

    def fake_fetch(url: str):
        calls.append(url)
        for needle, payload in responses.items():
            if needle in url:
                return payload
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(collectors, "_fetch_json", fake_fetch)
    return calls


def test_fetch_remotive_filters_by_candidate_location(monkeypatch):
    _patch_fetch(
        monkeypatch,
        {
            "remotive.com": {
                "jobs": [
                    {
                        "company_name": "EuroCo",
                        "title": "Data Engineer",
                        "category": "Software Development",
                        "candidate_required_location": "Europe",
                        "salary": "€60k - €80k",
                        "job_type": "full_time",
                        "url": "https://remotive.com/j/1",
                    },
                    {
                        "company_name": "BrazilCo",
                        "title": "Data Engineer",
                        "category": "Software Development",
                        "candidate_required_location": "Brazil",
                        "url": "https://remotive.com/j/2",
                    },
                    {
                        "company_name": "SalesCo",
                        "title": "Inside Sales Contractor",
                        "category": "Sales",
                        "candidate_required_location": "Worldwide",
                        "url": "https://remotive.com/j/3",
                    },
                ]
            }
        },
    )
    jobs = fetch_remotive_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "EuroCo"
    assert job.location == "Remote - Europe"
    assert job.remote_type == "remote"
    assert (job.min_salary_eur, job.max_salary_eur) == (60000, 80000)
    assert job.source == "remotive"


def test_fetch_themuse_filters_location_and_paginates(monkeypatch):
    page = {
        "page_count": 2,
        "results": [
            {
                "name": "Platform Engineer",
                "company": {"name": "MuseCo"},
                "locations": [{"name": "Madrid, Spain"}, {"name": "Flexible / Remote"}],
                "refs": {"landing_page": "https://themuse.com/j/1"},
            },
            {
                "name": "Platform Engineer II",
                "company": {"name": "RemoteOnlyCo"},
                "locations": [{"name": "Flexible / Remote"}],
                "refs": {"landing_page": "https://themuse.com/j/2"},
            },
        ],
    }
    calls = _patch_fetch(monkeypatch, {"themuse.com": page})
    jobs = fetch_themuse_jobs(location="Madrid, Spain", max_pages=5)
    # page_count=2 stops pagination early even though max_pages=5
    assert len(calls) == 2
    # remote-only listing without a Madrid/Spain location is dropped
    assert {job.company for job in jobs} == {"MuseCo"}
    assert jobs[0].location == "Madrid, Spain"
    assert jobs[0].source == "themuse"


def test_fetch_ashby_jobs(monkeypatch):
    _patch_fetch(
        monkeypatch,
        {
            "ashbyhq.com": {
                "jobs": [
                    {
                        "title": "Cloud Engineer",
                        "location": "Madrid",
                        "isRemote": False,
                        "employmentType": "FullTime",
                        "jobUrl": "https://jobs.ashbyhq.com/x/1",
                    },
                    {
                        "title": "Cloud Engineer (EU)",
                        "location": "Europe",
                        "isRemote": True,
                        "jobUrl": "https://jobs.ashbyhq.com/x/2",
                    },
                ]
            }
        },
    )
    jobs = fetch_ashby_jobs("acme", location_filter="Madrid")
    assert len(jobs) == 1
    assert jobs[0].title == "Cloud Engineer"
    assert jobs[0].source == "ashby:acme"

    all_jobs = fetch_ashby_jobs("acme")
    assert len(all_jobs) == 2
    assert all_jobs[1].location == "Remote - Europe"
    assert all_jobs[1].remote_type == "remote"


def test_fetch_adzuna_requires_credentials(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    with pytest.raises(CollectionError, match="credentials missing"):
        fetch_adzuna_jobs()


def test_fetch_adzuna_jobs(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    _patch_fetch(
        monkeypatch,
        {
            "adzuna.com": {
                "results": [
                    {
                        "title": "Data Engineer",
                        "company": {"display_name": "AdzunaCo"},
                        "location": {"display_name": "Madrid, Comunidad de Madrid"},
                        "salary_min": 55000.0,
                        "salary_max": 70000.0,
                        "contract_time": "full_time",
                        "redirect_url": "https://adzuna.com/j/1",
                    }
                ]
            }
        },
    )
    jobs = fetch_adzuna_jobs(max_pages=3)
    # fewer than 50 results on page 1 stops pagination
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "AdzunaCo"
    assert (job.min_salary_eur, job.max_salary_eur) == (55000, 70000)
    assert job.source == "adzuna"


def test_parse_salary_text():
    assert _parse_salary_text("€60k - €80k") == (60000, 80000)
    assert _parse_salary_text("€60,000 - €80,000") == (60000, 80000)
    assert _parse_salary_text("€60.000 - €80.000") == (60000, 80000)
    # non-EUR currencies are skipped rather than mis-recorded
    assert _parse_salary_text("$80k - $100k") == (None, None)
    assert _parse_salary_text("") == (None, None)
    assert _parse_salary_text("competitive") == (None, None)
    # inverted ranges are rejected
    assert _parse_salary_text("€80k - €60k") == (None, None)
