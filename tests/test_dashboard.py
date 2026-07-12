from __future__ import annotations

from pathlib import Path

from job_hunter_agent.dashboard import REPO_ROOT, WEB_DIR, build_dashboard_payload, default_data_sources


def test_default_data_sources_exist():
    sources = default_data_sources()
    for key in ("profile", "jobs", "contacts"):
        assert Path(sources[key]).is_file(), f"{key} default missing: {sources[key]}"


def test_build_dashboard_payload_from_examples():
    payload = build_dashboard_payload(
        str(REPO_ROOT / "config" / "profile.example.json"),
        str(REPO_ROOT / "data" / "examples" / "jobs.json"),
        str(REPO_ROOT / "data" / "examples" / "contacts.json"),
    )
    assert payload["summary"]["job_count"] > 0
    assert payload["ranked_jobs"]
    assert payload["companies"] == sorted(payload["companies"])
    assert isinstance(payload["outreach_drafts"], list)


def test_web_assets_exist():
    for name in ("index.html", "app.js", "styles.css"):
        assert (WEB_DIR / name).is_file()
