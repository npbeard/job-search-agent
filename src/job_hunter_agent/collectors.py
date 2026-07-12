from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from job_hunter_agent.models import JobOpportunity


class CollectionError(RuntimeError):
    pass


# Locations a Spain-based candidate can generally work from in remote listings.
SPAIN_ELIGIBLE_MARKERS = ["spain", "madrid", "europe", "emea", "worldwide", "anywhere", "global"]


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


def fetch_ashby_jobs(board_token: str, location_filter: str | None = None) -> list[JobOpportunity]:
    """Fetch jobs from a company's public Ashby job board."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(board_token)}"
    payload = _fetch_json(url)
    jobs: list[JobOpportunity] = []
    for item in payload.get("jobs", []):
        location = item.get("location", "") or "Unknown"
        if item.get("isRemote") and "remote" not in location.lower():
            location = f"Remote - {location}"
        if location_filter and location_filter.lower() not in location.lower():
            continue
        jobs.append(
            JobOpportunity(
                company=_company_from_board_token(board_token),
                title=item.get("title", ""),
                location=location,
                remote_type="remote" if item.get("isRemote") else _infer_remote_type(location),
                employment_type=(item.get("employmentType") or "full-time").lower(),
                skills=[],
                url=item.get("jobUrl", "") or item.get("applyUrl", ""),
                source=f"ashby:{board_token}",
            )
        )
    return jobs


REMOTIVE_TECH_CATEGORIES = {
    "Software Development",
    "DevOps / Sysadmin",
    "Data and Analytics",
    "Artificial Intelligence",
    "Information Technology",
}


def fetch_remotive_jobs(
    categories: tuple[str, ...] | None = None,
    location_markers: list[str] | None = None,
) -> list[JobOpportunity]:
    """Fetch remote jobs across many companies from Remotive's public API.

    The free API serves only the latest postings and ignores server-side category
    filters, so category and Spain-workable location are filtered client-side.
    (Remotive asks for at most ~4 calls/day; callers should cache accordingly.)
    """
    wanted_categories = set(categories or REMOTIVE_TECH_CATEGORIES)
    markers = [marker.lower() for marker in (location_markers or SPAIN_ELIGIBLE_MARKERS)]
    payload = _fetch_json("https://remotive.com/api/remote-jobs")
    jobs: list[JobOpportunity] = []
    for item in payload.get("jobs", []):
        if item.get("category") not in wanted_categories:
            continue
        required_location = item.get("candidate_required_location", "") or ""
        if not any(marker in required_location.lower() for marker in markers):
            continue
        min_salary, max_salary = _parse_salary_text(item.get("salary", ""))
        jobs.append(
            JobOpportunity(
                company=item.get("company_name", "Unknown"),
                title=item.get("title", ""),
                location=f"Remote - {required_location}" if required_location else "Remote",
                remote_type="remote",
                employment_type=(item.get("job_type") or "full_time").replace("_", "-"),
                min_salary_eur=min_salary,
                max_salary_eur=max_salary,
                skills=[],
                url=item.get("url", ""),
                source="remotive",
            )
        )
    return jobs


def fetch_themuse_jobs(
    location: str = "Madrid, Spain",
    categories: tuple[str, ...] = ("Software Engineering", "Data and Analytics"),
    max_pages: int = 3,
) -> list[JobOpportunity]:
    """Fetch jobs across many companies from The Muse public API.

    The API mixes remote listings into location queries, so results are also
    filtered client-side against the requested location.
    """
    wanted = [part.strip().lower() for part in location.split(",") if part.strip()]
    category_params = "".join(f"&category={urllib.parse.quote(cat)}" for cat in categories)
    jobs: list[JobOpportunity] = []
    for page in range(1, max_pages + 1):
        url = f"https://www.themuse.com/api/public/jobs?page={page}&location={urllib.parse.quote(location)}{category_params}"
        payload = _fetch_json(url)
        for item in payload.get("results", []):
            location_names = [loc.get("name", "") for loc in item.get("locations", [])]
            matched = next(
                (name for name in location_names if any(part in name.lower() for part in wanted)),
                None,
            )
            if not matched:
                continue
            jobs.append(
                JobOpportunity(
                    company=item.get("company", {}).get("name", "Unknown"),
                    title=item.get("name", ""),
                    location=matched,
                    remote_type=_infer_remote_type(" ".join(location_names)),
                    employment_type="full-time",
                    skills=[],
                    url=item.get("refs", {}).get("landing_page", ""),
                    source="themuse",
                )
            )
        if page >= int(payload.get("page_count") or 1):
            break
    return jobs


def fetch_adzuna_jobs(
    country: str = "es",
    where: str = "Madrid",
    what: str = "engineer",
    category: str = "it-jobs",
    max_pages: int = 2,
    app_id: str | None = None,
    app_key: str | None = None,
) -> list[JobOpportunity]:
    """Fetch jobs across many companies from the Adzuna API (free key required).

    Credentials come from arguments or the ADZUNA_APP_ID / ADZUNA_APP_KEY
    environment variables (Streamlit secrets are exposed as env vars too).
    """
    app_id = app_id or os.environ.get("ADZUNA_APP_ID", "")
    app_key = app_key or os.environ.get("ADZUNA_APP_KEY", "")
    if not app_id or not app_key:
        raise CollectionError(
            "Adzuna credentials missing: set ADZUNA_APP_ID and ADZUNA_APP_KEY "
            "(free key at https://developer.adzuna.com)"
        )
    jobs: list[JobOpportunity] = []
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode(
            {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": 50,
                "what": what,
                "where": where,
                "category": category,
                "content-type": "application/json",
            }
        )
        url = f"https://api.adzuna.com/v1/api/jobs/{urllib.parse.quote(country)}/search/{page}?{params}"
        payload = _fetch_json(url)
        results = payload.get("results", [])
        for item in results:
            location = item.get("location", {}).get("display_name", "") or "Unknown"
            min_salary = item.get("salary_min")
            max_salary = item.get("salary_max")
            jobs.append(
                JobOpportunity(
                    company=item.get("company", {}).get("display_name", "Unknown"),
                    title=item.get("title", ""),
                    location=location,
                    remote_type=_infer_remote_type(f"{item.get('title', '')} {location}"),
                    employment_type=item.get("contract_time") or "full-time",
                    min_salary_eur=int(min_salary) if min_salary else None,
                    max_salary_eur=int(max_salary) if max_salary else None,
                    skills=[],
                    url=item.get("redirect_url", ""),
                    source="adzuna",
                )
            )
        if len(results) < 50:
            break
    return jobs


_SALARY_RANGE_PATTERN = re.compile(
    r"(?P<currency>[€$£])\s*(?P<low>\d+(?:[.,]\d+)?)\s*(?P<low_k>k?)\s*[-–—]\s*[€$£]?\s*(?P<high>\d+(?:[.,]\d+)?)\s*(?P<high_k>k?)",
    re.IGNORECASE,
)


def _parse_salary_text(text: str) -> tuple[int | None, int | None]:
    """Parse EUR salary ranges like "€60k - €80k" from free text; other currencies are skipped."""
    if not text:
        return None, None
    match = _SALARY_RANGE_PATTERN.search(text)
    if not match or match.group("currency") != "€":
        return None, None

    def to_amount(value: str, has_k: str) -> int:
        if has_k:
            # "60" or "60.5" (decimal comma tolerated) in thousands
            return int(float(value.replace(",", ".")) * 1000)
        # "60000", "60,000", "60.000" — separators are thousands markers
        return int(value.replace(",", "").replace(".", ""))

    low = to_amount(match.group("low"), match.group("low_k"))
    high = to_amount(match.group("high"), match.group("high_k"))
    if low < 1000 or high < low:
        return None, None
    return low, high


def _company_from_board_token(token: str) -> str:
    token_map = {
        "affirm": "Affirm",
        "twilio": "Twilio",
        "grafanalabs": "Grafana Labs",
        "datadog": "Datadog",
        "cabify": "Cabify",
        "typeform": "Typeform",
        "elastic": "Elastic",
    }
    return token_map.get(token.lower(), token.replace("-", " ").title())


def _infer_remote_type(location: str) -> str:
    lower = location.lower()
    if "remote" in lower:
        return "remote"
    if "hybrid" in lower:
        return "hybrid"
    return "onsite"
