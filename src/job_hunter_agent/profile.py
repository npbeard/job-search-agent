from __future__ import annotations

from job_hunter_agent.io_utils import load_json
from job_hunter_agent.models import CandidateProfile


def load_profile(path: str) -> CandidateProfile:
    payload = load_json(path)
    return CandidateProfile(**payload)

