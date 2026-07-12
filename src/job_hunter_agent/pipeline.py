from __future__ import annotations

from pathlib import Path

from job_hunter_agent.collectors import (
    CollectionError,
    fetch_adzuna_jobs,
    fetch_ashby_jobs,
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_remotive_jobs,
    fetch_themuse_jobs,
)
from job_hunter_agent.enrichment import enrich_jobs, is_job_relevant, load_salary_bands
from job_hunter_agent.io_utils import dataclass_list_to_dicts, dump_json, load_json
from job_hunter_agent.market import merge_job_files
from job_hunter_agent.models import JobOpportunity
from job_hunter_agent.profile import load_profile


def refresh_market_dataset(
    profile_path: str,
    market_config_path: str,
    salary_bands_path: str,
    output_dir: str,
    merged_output_path: str,
) -> dict:
    profile = load_profile(profile_path)
    salary_bands = load_salary_bands(salary_bands_path)
    config = load_json(market_config_path)
    root = Path(market_config_path).resolve().parent.parent
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    relevant_paths: list[str] = []
    results: list[dict] = []

    for company_config in config.get("companies", []):
        company = company_config["company"]
        provider = company_config["provider"]
        location_filter = company_config.get("location_filter")
        try:
            raw_jobs = collect_company_jobs(company_config, root)
        except CollectionError as exc:
            # One flaky or unconfigured source must not kill the whole refresh.
            results.append(
                {
                    "company": company,
                    "provider": provider,
                    "location_filter": location_filter,
                    "raw_jobs": 0,
                    "relevant_jobs": 0,
                    "raw_path": "",
                    "enriched_path": "",
                    "relevant_path": "",
                    "error": str(exc),
                }
            )
            continue
        enriched_jobs = enrich_jobs(raw_jobs, salary_bands, profile)
        relevant_jobs = [job for job in enriched_jobs if is_job_relevant(profile, job)[0]]

        slug = slugify(company)
        raw_path = target_dir / f"{slug}_jobs_raw.json"
        enriched_path = target_dir / f"{slug}_jobs_enriched.json"
        relevant_path = target_dir / f"{slug}_jobs_relevant.json"

        dump_json(raw_path, dataclass_list_to_dicts(raw_jobs))
        dump_json(enriched_path, dataclass_list_to_dicts(enriched_jobs))
        dump_json(relevant_path, dataclass_list_to_dicts(relevant_jobs))
        relevant_paths.append(str(relevant_path))
        results.append(
            {
                "company": company,
                "provider": provider,
                "location_filter": location_filter,
                "raw_jobs": len(raw_jobs),
                "relevant_jobs": len(relevant_jobs),
                "raw_path": str(raw_path),
                "enriched_path": str(enriched_path),
                "relevant_path": str(relevant_path),
                "error": None,
            }
        )

    merged_jobs = merge_job_files(relevant_paths)
    dump_json(merged_output_path, dataclass_list_to_dicts(merged_jobs))
    return {
        "companies": results,
        "merged_output_path": merged_output_path,
        "merged_jobs": len(merged_jobs),
    }


def collect_company_jobs(company_config: dict, repo_root: Path) -> list[JobOpportunity]:
    provider = company_config["provider"]
    token = company_config.get("token", "")
    location_filter = company_config.get("location_filter")
    if provider == "lever":
        return fetch_lever_jobs(token, location_filter=location_filter)
    if provider == "greenhouse":
        return fetch_greenhouse_jobs(token, location_filter=location_filter)
    if provider == "ashby":
        return fetch_ashby_jobs(token, location_filter=location_filter)
    if provider == "remotive":
        # Aggregator: discovers jobs (and companies) dynamically across the whole board.
        categories = company_config.get("categories")
        return fetch_remotive_jobs(
            categories=tuple(categories) if categories else None,
            location_markers=company_config.get("location_markers"),
        )
    if provider == "themuse":
        # Aggregator: discovers jobs (and companies) dynamically for a location.
        return fetch_themuse_jobs(
            location=company_config.get("location", "Madrid, Spain"),
            categories=tuple(company_config.get("categories", ["Software Engineering", "Data and Analytics"])),
            max_pages=int(company_config.get("max_pages", 3)),
        )
    if provider == "adzuna":
        # Aggregator: needs ADZUNA_APP_ID / ADZUNA_APP_KEY in the environment.
        return fetch_adzuna_jobs(
            country=company_config.get("country", "es"),
            where=company_config.get("where", "Madrid"),
            what=company_config.get("what", "engineer"),
            category=company_config.get("category", "it-jobs"),
            max_pages=int(company_config.get("max_pages", 2)),
        )
    if provider == "manual":
        input_path = company_config.get("input_path")
        if not input_path:
            raise ValueError(f"manual provider for {company_config['company']} needs input_path")
        payload = load_json(repo_root / input_path)
        return [JobOpportunity(**item) for item in payload]
    raise ValueError(f"unsupported provider: {provider}")


def slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")
