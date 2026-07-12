from __future__ import annotations

import argparse

from job_hunter_agent.collectors import (
    fetch_ashby_jobs,
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_remotive_jobs,
    fetch_themuse_jobs,
)
from job_hunter_agent.contacts import load_contacts, rank_contacts
from job_hunter_agent.emails import build_cold_email, guess_company_domain, guess_email_addresses
from job_hunter_agent.dashboard import resolve_port, serve_dashboard
from job_hunter_agent.enrichment import enrich_jobs, is_job_relevant, load_salary_bands
from job_hunter_agent.io_utils import dataclass_list_to_dicts, dump_json
from job_hunter_agent.jobs import load_jobs, rank_jobs
from job_hunter_agent.market import discover_job_files, merge_job_files
from job_hunter_agent.messages import build_outreach_drafts
from job_hunter_agent.pipeline import refresh_market_dataset
from job_hunter_agent.profile import load_profile
from job_hunter_agent.search_queries import generate_contact_search_queries
from job_hunter_agent.strategy import suggest_outreach


def _print_ranked_jobs(profile_path: str, jobs_path: str, limit: int) -> None:
    profile = load_profile(profile_path)
    jobs = load_jobs(jobs_path)
    ranked = rank_jobs(profile, jobs)
    for index, item in enumerate(ranked[:limit], start=1):
        job = item.job
        avg_salary = "unknown"
        if job.min_salary_eur is not None or job.max_salary_eur is not None:
            low = job.min_salary_eur or job.max_salary_eur or 0
            high = job.max_salary_eur or job.min_salary_eur or 0
            avg_salary = f"EUR {low:,} - {high:,}"
        print(f"{index}. {job.company} | {job.title} | {job.location}")
        print(f"   score={item.score} salary={item.salary_score} fit={item.fit_score} realism={item.realism_score}")
        print(f"   comp={avg_salary} hours_risk={job.hours_risk} url={job.url}")
        print(f"   reasons: {', '.join(item.reasons[:4])}")


def _print_ranked_contacts(profile_path: str, contacts_path: str, limit: int) -> None:
    profile = load_profile(profile_path)
    contacts = load_contacts(contacts_path)
    ranked = rank_contacts(profile, contacts)
    for index, item in enumerate(ranked[:limit], start=1):
        contact = item.contact
        print(f"{index}. {contact.full_name} | {contact.company} | {contact.title}")
        print(f"   score={item.score} location={contact.location} shared_connections={contact.shared_connections}")
        print(f"   linkedin={contact.linkedin_url}")
        print(f"   reasons: {', '.join(item.reasons[:4])}")


def _print_outreach_suggestions(profile_path: str, jobs_path: str, contacts_path: str, limit: int) -> None:
    profile = load_profile(profile_path)
    ranked_jobs = rank_jobs(profile, load_jobs(jobs_path))
    ranked_contacts = rank_contacts(profile, load_contacts(contacts_path))
    suggestions = suggest_outreach(ranked_jobs, ranked_contacts)
    for index, item in enumerate(suggestions[:limit], start=1):
        print(f"{index}. {item.company} | {item.job_title}")
        print(f"   contact={item.contact_name} ({item.contact_title}) score={item.score}")
        print(f"   job={item.job_url}")
        print(f"   linkedin={item.contact_url}")
        print(f"   reasons: {', '.join(item.reasons[:4])}")


def _print_outreach_drafts(profile_path: str, jobs_path: str, contacts_path: str, limit: int) -> None:
    profile = load_profile(profile_path)
    ranked_jobs = rank_jobs(profile, load_jobs(jobs_path))
    ranked_contacts = rank_contacts(profile, load_contacts(contacts_path))
    suggestions = suggest_outreach(ranked_jobs, ranked_contacts)
    drafts = build_outreach_drafts(profile, suggestions, limit=limit)
    for index, item in enumerate(drafts, start=1):
        print(f"{index}. {item.company} | {item.job_title} | {item.contact_name}")
        print(f"   subject={item.subject}")
        print(f"   linkedin={item.contact_url}")
        print("   message:")
        for line in item.message.splitlines():
            print(f"     {line}")


def _collect_jobs(provider: str, token: str, location: str | None, output: str) -> None:
    if provider == "lever":
        jobs = fetch_lever_jobs(token, location_filter=location)
    elif provider == "greenhouse":
        jobs = fetch_greenhouse_jobs(token, location_filter=location)
    elif provider == "ashby":
        jobs = fetch_ashby_jobs(token, location_filter=location)
    elif provider == "remotive":
        jobs = fetch_remotive_jobs()
    elif provider == "themuse":
        jobs = fetch_themuse_jobs(location=location or "Madrid, Spain")
    else:
        raise ValueError(f"unsupported provider: {provider}")
    dump_json(output, dataclass_list_to_dicts(jobs))
    print(f"saved {len(jobs)} jobs to {output}")


def _enrich_jobs(
    profile_path: str,
    jobs_path: str,
    salary_bands_path: str,
    output: str,
    filtered_output: str | None,
) -> None:
    profile = load_profile(profile_path)
    jobs = load_jobs(jobs_path)
    salary_bands = load_salary_bands(salary_bands_path)
    enriched_jobs = enrich_jobs(jobs, salary_bands, profile)
    dump_json(output, dataclass_list_to_dicts(enriched_jobs))
    print(f"saved {len(enriched_jobs)} enriched jobs to {output}")
    if filtered_output:
        filtered_jobs = [job for job in enriched_jobs if is_job_relevant(profile, job)[0]]
        dump_json(filtered_output, dataclass_list_to_dicts(filtered_jobs))
        print(f"saved {len(filtered_jobs)} filtered jobs to {filtered_output}")


def _print_job_relevance(profile_path: str, jobs_path: str, limit: int) -> None:
    profile = load_profile(profile_path)
    jobs = load_jobs(jobs_path)
    scored: list[tuple[bool, list[str], object]] = []
    for job in jobs:
        relevant, reasons = is_job_relevant(profile, job)
        scored.append((relevant, reasons, job))
    for index, (relevant, reasons, job) in enumerate(scored[:limit], start=1):
        verdict = "keep" if relevant else "skip"
        print(f"{index}. {job.company} | {job.title} | {job.location} -> {verdict}")
        print(f"   reasons: {', '.join(reasons) if reasons else 'looks relevant'}")


def _serve_ui(host: str, port: int) -> None:
    resolved_port = resolve_port(port)
    serve_dashboard(host=host, port=resolved_port)


def _merge_jobs(inputs: list[str], output: str, discover_dir: str | None, suffix: str) -> None:
    paths = list(inputs)
    if discover_dir:
        paths.extend(discover_job_files(discover_dir, suffix=suffix))
    merged = merge_job_files(paths)
    dump_json(output, dataclass_list_to_dicts(merged))
    print(f"saved {len(merged)} merged jobs to {output}")


def _refresh_market(
    profile_path: str,
    market_config_path: str,
    salary_bands_path: str,
    output_dir: str,
    merged_output: str,
) -> None:
    report = refresh_market_dataset(
        profile_path=profile_path,
        market_config_path=market_config_path,
        salary_bands_path=salary_bands_path,
        output_dir=output_dir,
        merged_output_path=merged_output,
    )
    for item in report["companies"]:
        if item.get("error"):
            print(f"{item['company']}: SKIPPED ({item['error']})")
            continue
        print(
            f"{item['company']}: raw={item['raw_jobs']} relevant={item['relevant_jobs']} "
            f"provider={item['provider']} file={item['relevant_path']}"
        )
    print(f"merged {report['merged_jobs']} jobs into {report['merged_output_path']}")


def _print_contact_searches(profile_path: str, jobs_path: str, limit: int) -> None:
    profile = load_profile(profile_path)
    ranked_jobs = rank_jobs(profile, load_jobs(jobs_path))
    queries = generate_contact_search_queries(profile, ranked_jobs, limit_jobs=10)
    for index, item in enumerate(queries[:limit], start=1):
        print(f"{index}. {item.company} | {item.persona} | {item.job_title}")
        print(f"   score={item.score} query={item.query}")
        print(f"   linkedin={item.linkedin_url}")
        print(f"   reasons: {', '.join(item.reasons)}")


def _print_email_guesses(
    name: str,
    domain: str | None,
    company: str | None,
    job_title: str | None,
    profile_path: str | None,
) -> None:
    resolved_domain = domain or (guess_company_domain(company) if company else "")
    if not resolved_domain:
        raise ValueError("provide --domain or --company to guess against")
    guesses = guess_email_addresses(name, resolved_domain)
    print(f"Likely addresses for {name} @ {resolved_domain} (unverified):")
    for index, guess in enumerate(guesses, start=1):
        print(f"{index:>2}. {guess.address:<40} pattern={guess.pattern} confidence={guess.confidence:.2f}")
    if profile_path and company and job_title:
        profile = load_profile(profile_path)
        subject, body = build_cold_email(profile, company, job_title, contact_name=name)
        print(f"\nsubject: {subject}\n")
        print(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-hunter-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    jobs_parser = subparsers.add_parser("rank-jobs", help="Rank jobs for fit and compensation.")
    jobs_parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    jobs_parser.add_argument("--jobs", required=True, help="Path to jobs JSON.")
    jobs_parser.add_argument("--limit", type=int, default=10, help="Number of jobs to print.")

    contacts_parser = subparsers.add_parser("rank-contacts", help="Rank referral contacts.")
    contacts_parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    contacts_parser.add_argument("--contacts", required=True, help="Path to contacts JSON or CSV.")
    contacts_parser.add_argument("--limit", type=int, default=10, help="Number of contacts to print.")

    outreach_parser = subparsers.add_parser("suggest-outreach", help="Pair strong jobs with strong contacts.")
    outreach_parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    outreach_parser.add_argument("--jobs", required=True, help="Path to jobs JSON.")
    outreach_parser.add_argument("--contacts", required=True, help="Path to contacts JSON or CSV.")
    outreach_parser.add_argument("--limit", type=int, default=10, help="Number of suggestions to print.")

    drafts_parser = subparsers.add_parser("draft-messages", help="Generate outreach drafts for top suggestions.")
    drafts_parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    drafts_parser.add_argument("--jobs", required=True, help="Path to jobs JSON.")
    drafts_parser.add_argument("--contacts", required=True, help="Path to contacts JSON or CSV.")
    drafts_parser.add_argument("--limit", type=int, default=5, help="Number of drafts to print.")

    collect_parser = subparsers.add_parser("collect-jobs", help="Collect jobs from common careers APIs.")
    collect_parser.add_argument(
        "--provider",
        choices=["lever", "greenhouse", "ashby", "remotive", "themuse"],
        required=True,
        help="Careers platform or aggregator.",
    )
    collect_parser.add_argument("--token", default="", help="Company slug or board token (unused for aggregators).")
    collect_parser.add_argument("--location", help="Optional location substring filter.")
    collect_parser.add_argument("--output", required=True, help="Path to output JSON.")

    enrich_parser = subparsers.add_parser("enrich-jobs", help="Infer level, salary, skills, and filtered outputs.")
    enrich_parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    enrich_parser.add_argument("--jobs", required=True, help="Path to raw jobs JSON.")
    enrich_parser.add_argument("--salary-bands", required=True, help="Path to salary bands JSON.")
    enrich_parser.add_argument("--output", required=True, help="Path to enriched jobs JSON.")
    enrich_parser.add_argument("--filtered-output", help="Optional path for filtered relevant jobs JSON.")

    relevance_parser = subparsers.add_parser("review-jobs", help="Review which jobs look relevant before ranking.")
    relevance_parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    relevance_parser.add_argument("--jobs", required=True, help="Path to jobs JSON.")
    relevance_parser.add_argument("--limit", type=int, default=20, help="Number of jobs to print.")

    ui_parser = subparsers.add_parser("serve-ui", help="Run the local web dashboard.")
    ui_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    ui_parser.add_argument("--port", type=int, default=8765, help="Preferred port.")

    merge_parser = subparsers.add_parser("merge-jobs", help="Merge multiple job datasets into one market view.")
    merge_parser.add_argument("--input", action="append", default=[], help="Path to a jobs JSON file. Repeatable.")
    merge_parser.add_argument("--discover-dir", help="Optional directory to scan for job files.")
    merge_parser.add_argument("--suffix", default="_relevant.json", help="Suffix used when discovering files.")
    merge_parser.add_argument("--output", required=True, help="Path to merged jobs JSON.")

    refresh_parser = subparsers.add_parser("refresh-market", help="Collect, enrich, filter, and merge target companies.")
    refresh_parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    refresh_parser.add_argument("--market-config", required=True, help="Path to market targets JSON.")
    refresh_parser.add_argument("--salary-bands", required=True, help="Path to salary bands JSON.")
    refresh_parser.add_argument("--output-dir", required=True, help="Directory for per-company datasets.")
    refresh_parser.add_argument("--merged-output", required=True, help="Path to merged market jobs JSON.")

    searches_parser = subparsers.add_parser("contact-searches", help="Generate LinkedIn search queries for referral hunting.")
    searches_parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    searches_parser.add_argument("--jobs", required=True, help="Path to jobs JSON.")
    searches_parser.add_argument("--limit", type=int, default=20, help="Number of searches to print.")

    emails_parser = subparsers.add_parser("guess-emails", help="Guess likely email addresses for a contact.")
    emails_parser.add_argument("--name", required=True, help="Contact full name.")
    emails_parser.add_argument("--domain", help="Company email domain, e.g. acme.com.")
    emails_parser.add_argument("--company", help="Company name (used to guess domain if --domain omitted).")
    emails_parser.add_argument("--job-title", help="Role to reference in a drafted email.")
    emails_parser.add_argument("--profile", help="Profile JSON; with --company and --job-title, drafts an email.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "rank-jobs":
        _print_ranked_jobs(args.profile, args.jobs, args.limit)
    elif args.command == "rank-contacts":
        _print_ranked_contacts(args.profile, args.contacts, args.limit)
    elif args.command == "suggest-outreach":
        _print_outreach_suggestions(args.profile, args.jobs, args.contacts, args.limit)
    elif args.command == "draft-messages":
        _print_outreach_drafts(args.profile, args.jobs, args.contacts, args.limit)
    elif args.command == "collect-jobs":
        _collect_jobs(args.provider, args.token, args.location, args.output)
    elif args.command == "enrich-jobs":
        _enrich_jobs(args.profile, args.jobs, args.salary_bands, args.output, args.filtered_output)
    elif args.command == "review-jobs":
        _print_job_relevance(args.profile, args.jobs, args.limit)
    elif args.command == "serve-ui":
        _serve_ui(args.host, args.port)
    elif args.command == "merge-jobs":
        _merge_jobs(args.input, args.output, args.discover_dir, args.suffix)
    elif args.command == "refresh-market":
        _refresh_market(
            args.profile,
            args.market_config,
            args.salary_bands,
            args.output_dir,
            args.merged_output,
        )
    elif args.command == "contact-searches":
        _print_contact_searches(args.profile, args.jobs, args.limit)
    elif args.command == "guess-emails":
        _print_email_guesses(args.name, args.domain, args.company, args.job_title, args.profile)
