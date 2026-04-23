from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from job_hunter_agent.models import JobOpportunity


class CollectionError(RuntimeError):
    pass


def _fetch_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "job-hunter-agent/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise CollectionError(f"failed to fetch {url}: {exc}") from exc


def fetch_lever_jobs(company: str, location_filter: str | None = None) -> list[JobOpportunity]:
    url = f"https://api.lever.co/v0/postings/{urllib.parse.quote(company)}?mode=json"
    payload = _fetch_json(url)
    jobs: list[JobOpportunity] = []
    for item in payload:
        categories = item.get("categories", {})
        location = categories.get("location", "") or item.get("workplaceType", "Unknown")
        if location_filter and location_filter.lower() not in location.lower():
            continue
        jobs.append(
            JobOpportunity(
                company=item.get("company", company.title()),
                title=item.get("text", ""),
                location=location or "Unknown",
                remote_type=_infer_remote_type(location),
                employment_type=categories.get("commitment", "full-time"),
                skills=[],
                url=item.get("hostedUrl", ""),
                source=f"lever:{company}",
            )
        )
    return jobs


def fetch_greenhouse_jobs(board_token: str, location_filter: str | None = None) -> list[JobOpportunity]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(board_token)}/jobs"
    payload = _fetch_json(url)
    jobs: list[JobOpportunity] = []
    for item in payload.get("jobs", []):
        location = item.get("location", {}).get("name", "Unknown")
        if location_filter and location_filter.lower() not in location.lower():
            continue
        jobs.append(
            JobOpportunity(
                company=_company_from_board_token(board_token),
                title=item.get("title", ""),
                location=location,
                remote_type=_infer_remote_type(location),
                employment_type="full-time",
                skills=[],
                url=item.get("absolute_url", ""),
                source=f"greenhouse:{board_token}",
            )
        )
    return jobs


def _company_from_board_token(token: str) -> str:
    token_map = {
        "affirm": "Affirm",
        "twilio": "Twilio",
        "grafanalabs": "Grafana Labs",
        "datadog": "Datadog",
    }
    return token_map.get(token.lower(), token.replace("-", " ").title())


def _infer_remote_type(location: str) -> str:
    lower = location.lower()
    if "remote" in lower:
        return "remote"
    if "hybrid" in lower:
        return "hybrid"
    return "onsite"
