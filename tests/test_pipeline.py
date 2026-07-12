from __future__ import annotations

from pathlib import Path

import pytest

from job_hunter_agent import pipeline
from job_hunter_agent.pipeline import collect_company_jobs

from tests.conftest import make_job


def test_collect_company_jobs_dispatches_aggregators(monkeypatch):
    captured = {}

    def fake_remotive(categories, location_markers):
        captured["remotive"] = (categories, location_markers)
        return [make_job(source="remotive")]

    def fake_themuse(location, categories, max_pages):
        captured["themuse"] = (location, categories, max_pages)
        return [make_job(source="themuse")]

    monkeypatch.setattr(pipeline, "fetch_remotive_jobs", fake_remotive)
    monkeypatch.setattr(pipeline, "fetch_themuse_jobs", fake_themuse)

    remotive_config = {
        "company": "Remotive (remote aggregator)",
        "provider": "remotive",
        "categories": ["Software Development"],
        "location_markers": ["spain"],
    }
    assert len(collect_company_jobs(remotive_config, Path("."))) == 1
    assert captured["remotive"] == (("Software Development",), ["spain"])

    themuse_config = {
        "company": "The Muse (Madrid aggregator)",
        "provider": "themuse",
        "location": "Madrid, Spain",
        "categories": ["Software Engineering"],
        "max_pages": 2,
    }
    assert len(collect_company_jobs(themuse_config, Path("."))) == 1
    assert captured["themuse"] == ("Madrid, Spain", ("Software Engineering",), 2)


def test_collect_company_jobs_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unsupported provider"):
        collect_company_jobs({"company": "X", "provider": "workday", "token": "x"}, Path("."))


def test_market_config_providers_are_supported():
    """Every provider in the shipped market config must have a dispatch branch."""
    import json

    config = json.loads(
        (Path(__file__).resolve().parent.parent / "config" / "market_targets.madrid.json").read_text()
    )
    supported = {"lever", "greenhouse", "ashby", "remotive", "themuse", "manual"}
    for entry in config["companies"]:
        assert entry["provider"] in supported, f"{entry['company']} uses unsupported provider {entry['provider']}"
