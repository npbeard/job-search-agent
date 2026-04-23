from __future__ import annotations

from pathlib import Path

from job_hunter_agent.io_utils import load_json
from job_hunter_agent.models import JobOpportunity


def merge_job_files(paths: list[str]) -> list[JobOpportunity]:
    merged: list[JobOpportunity] = []
    seen: set[tuple[str, str, str]] = set()
    for path in paths:
        payload = load_json(path)
        for item in payload:
            job = JobOpportunity(**item)
            key = (job.company.strip().lower(), job.title.strip().lower(), job.url.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(job)
    return merged


def discover_job_files(directory: str, suffix: str = "_relevant.json") -> list[str]:
    root = Path(directory)
    return sorted(str(path) for path in root.glob(f"*{suffix}") if path.is_file())
