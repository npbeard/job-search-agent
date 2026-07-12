from __future__ import annotations

import json

from job_hunter_agent.market import discover_job_files, merge_job_files
from job_hunter_agent.pipeline import slugify

from tests.conftest import make_job


def _write_jobs(path, jobs):
    path.write_text(json.dumps([job.__dict__ for job in jobs]), encoding="utf-8")


def test_merge_job_files_dedupes(tmp_path):
    job = make_job()
    file_a = tmp_path / "a_relevant.json"
    file_b = tmp_path / "b_relevant.json"
    _write_jobs(file_a, [job, make_job(title="Other Role")])
    _write_jobs(file_b, [job])
    merged = merge_job_files([str(file_a), str(file_b)])
    assert len(merged) == 2


def test_discover_job_files_filters_suffix(tmp_path):
    (tmp_path / "acme_jobs_relevant.json").write_text("[]", encoding="utf-8")
    (tmp_path / "acme_jobs_raw.json").write_text("[]", encoding="utf-8")
    found = discover_job_files(str(tmp_path))
    assert len(found) == 1
    assert found[0].endswith("_relevant.json")


def test_slugify():
    assert slugify("Grafana Labs") == "grafana_labs"
    assert slugify("A--B  C") == "a_b_c"
