"""Streamlit dashboard for the Job Hunter Agent.

Run locally:
    streamlit run streamlit_app.py

Deploy: push to GitHub and point Streamlit Community Cloud at this file.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd
import streamlit as st

from job_hunter_agent.contacts import load_contacts, rank_contacts
from job_hunter_agent.emails import build_cold_email, guess_company_domain, guess_email_addresses
from job_hunter_agent.enrichment import is_job_relevant, location_parts
from job_hunter_agent.jobs import load_jobs, rank_jobs
from job_hunter_agent.market import discover_job_files, merge_job_files
from job_hunter_agent.messages import build_outreach_drafts
from job_hunter_agent.pipeline import refresh_market_dataset
from job_hunter_agent.profile import load_profile
from job_hunter_agent.search_queries import generate_contact_search_queries
from job_hunter_agent.strategy import suggest_outreach

BAR_COLOR = "#2a78d6"  # single-hue categorical slot 1; jobs-per-company is one series

PROFILE_CANDIDATES = [
    REPO_ROOT / "config" / "profile.local.json",
    REPO_ROOT / "config" / "profile.nicolas.json",
    REPO_ROOT / "config" / "profile.example.json",
]
JOBS_PATH = REPO_ROOT / "data" / "market_jobs.json"
CONTACTS_PATH = REPO_ROOT / "data" / "examples" / "contacts.json"
MARKET_CONFIG = REPO_ROOT / "config" / "market_targets.madrid.json"
SALARY_BANDS = REPO_ROOT / "config" / "salary_bands.example.json"
MARKET_DIR = REPO_ROOT / "data" / "market"

TITLE_OPTIONS = [
    "Software Engineer",
    "Backend Engineer",
    "Platform Engineer",
    "Data Engineer",
    "Site Reliability Engineer",
    "Cloud Engineer",
    "DevOps Engineer",
    "Infrastructure Engineer",
    "Analytics Engineer",
    "Machine Learning Engineer",
]

st.set_page_config(page_title="Job Hunter", page_icon="🎯", layout="wide")


def resolve_profile_path() -> Path:
    return next((path for path in PROFILE_CANDIDATES if path.exists()), PROFILE_CANDIDATES[-1])


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def refresh_live_market(profile_path: str) -> dict:
    """Pull fresh jobs from every configured source (cached for 6 hours)."""
    return refresh_market_dataset(
        profile_path=profile_path,
        market_config_path=str(MARKET_CONFIG),
        salary_bands_path=str(SALARY_BANDS),
        output_dir=str(MARKET_DIR),
        merged_output_path=str(JOBS_PATH),
    )


def load_market_jobs():
    """Prefer the full enriched (unfiltered) datasets so UI tuning can widen the net."""
    enriched_files = discover_job_files(str(MARKET_DIR), suffix="_enriched.json")
    if enriched_files:
        return merge_job_files(enriched_files)
    return load_jobs(str(JOBS_PATH))


def format_salary(job) -> str:
    if job.min_salary_eur is None and job.max_salary_eur is None:
        return "unknown"
    low = job.min_salary_eur or job.max_salary_eur
    high = job.max_salary_eur or job.min_salary_eur
    return f"€{low:,} – €{high:,}"


def balanced_shortlist(items: list, per_company: int = 2) -> list:
    """Round-robin across companies so one board doesn't dominate the list."""
    groups: dict[str, list] = {}
    for item in items:
        groups.setdefault(item.job.company, []).append(item)
    balanced = []
    round_index = 0
    added = True
    while added:
        added = False
        for jobs in groups.values():
            if round_index < min(len(jobs), per_company):
                balanced.append(jobs[round_index])
                added = True
        round_index += 1
    return balanced


def parse_csv_field(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


# ---------------------------------------------------------------- data loading
profile_path = resolve_profile_path()
base_profile = load_profile(str(profile_path))

with st.sidebar:
    st.title("🎯 Job Hunter")
    st.caption(f"Profile: `{profile_path.name}`")

    auto_refresh = st.toggle(
        "Auto-refresh live data",
        value=True,
        help="Pulls fresh jobs from company boards and aggregators. Cached for 6 hours.",
    )
    if st.button("Force refresh now", width="stretch"):
        refresh_live_market.clear()

    refresh_report = None
    if auto_refresh:
        try:
            with st.spinner("Fetching live jobs from all sources…"):
                refresh_report = refresh_live_market(str(profile_path))
        except Exception as exc:  # noqa: BLE001 - fall back to the committed dataset
            st.warning(f"Live refresh failed ({exc}); using the last saved dataset.")
    if refresh_report:
        skipped = [item for item in refresh_report["companies"] if item.get("error")]
        for item in skipped:
            st.caption(f"⚠️ {item['company']} skipped: {item['error']}")

    st.divider()
    with st.expander("🎛 Tune profile", expanded=True):
        salary_floor = st.number_input(
            "Salary floor (EUR)", min_value=0, max_value=200_000,
            value=base_profile.salary_floor_eur, step=5_000,
            help="Salaries are scored relative to this floor.",
        )
        years_experience = st.number_input(
            "Your years of experience", min_value=0.0, max_value=30.0,
            value=float(base_profile.years_experience), step=0.5,
        )
        title_options = sorted(set(TITLE_OPTIONS) | set(base_profile.target_titles))
        target_titles = st.multiselect("Target roles", title_options, default=base_profile.target_titles)
        stretch_options = sorted({f"Senior {title}" for title in title_options} | set(base_profile.stretch_level_titles))
        stretch_titles = st.multiselect(
            "Stretch roles (scored favorably despite seniority)",
            stretch_options, default=base_profile.stretch_level_titles,
        )
        max_required_years = st.slider(
            "Max required experience you'd apply to", 1, 15,
            value=base_profile.max_reasonable_required_years,
        )
        avoid_keywords_text = st.text_input(
            "Avoid keywords (comma-separated)", value=", ".join(base_profile.avoid_keywords),
        )
        skills_text = st.text_area(
            "Your skills (comma-separated)", value=", ".join(base_profile.skills), height=100,
        )
        only_relevant = st.toggle(
            "Only relevant roles", value=True,
            help="Hide roles that fail the relevance screen (wrong role family, too senior, leadership, avoid keywords).",
        )

    st.divider()
    st.subheader("Filters")
    min_score = st.slider("Minimum score", 0.0, 1.0, 0.6, 0.05)
    view_mode = st.radio("View", ["Balanced shortlist", "Best overall"], horizontal=True)

profile = replace(
    base_profile,
    salary_floor_eur=int(salary_floor),
    years_experience=float(years_experience),
    target_titles=target_titles or base_profile.target_titles,
    stretch_level_titles=stretch_titles,
    max_reasonable_required_years=int(max_required_years),
    avoid_keywords=parse_csv_field(avoid_keywords_text),
    skills=parse_csv_field(skills_text) or base_profile.skills,
)

all_jobs = load_market_jobs()
if only_relevant:
    screened_jobs = [job for job in all_jobs if is_job_relevant(profile, job)[0]]
else:
    screened_jobs = all_jobs
ranked_jobs = rank_jobs(profile, screened_jobs)
contacts = load_contacts(str(CONTACTS_PATH))
ranked_contacts = rank_contacts(profile, contacts)
suggestions = suggest_outreach(ranked_jobs, ranked_contacts)
drafts = build_outreach_drafts(profile, suggestions, limit=10)
search_queries = generate_contact_search_queries(profile, ranked_jobs, limit_jobs=10)

companies = sorted({item.job.company for item in ranked_jobs})
countries = sorted({location_parts(item.job.location)[1] for item in ranked_jobs})
cities = sorted({location_parts(item.job.location)[0] for item in ranked_jobs})
with st.sidebar:
    company_filter = st.selectbox("Company", ["All companies", *companies])
    country_filter = st.selectbox("Country / region", ["All countries", *countries])
    city_filter = st.selectbox("City", ["All cities", *cities], help="Remote roles are grouped under the city “Remote”.")

filtered = [item for item in ranked_jobs if item.score >= min_score]
if company_filter != "All companies":
    filtered = [item for item in filtered if item.job.company == company_filter]
if country_filter != "All countries":
    filtered = [item for item in filtered if location_parts(item.job.location)[1] == country_filter]
if city_filter != "All cities":
    filtered = [item for item in filtered if location_parts(item.job.location)[0] == city_filter]
if company_filter == "All companies" and view_mode == "Balanced shortlist":
    filtered = balanced_shortlist(filtered)

# ---------------------------------------------------------------------- header
st.title("Ranked roles, referral targets, and outreach")
if refresh_report:
    st.caption(
        f"Live data: {refresh_report['merged_jobs']} pre-screened jobs from "
        f"{len(refresh_report['companies'])} sources (boards + aggregators, cached ≤ 6 h)."
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("Matching roles", len(ranked_jobs), help=f"Out of {len(all_jobs)} collected jobs, given your tuned profile.")
m2.metric("Companies", len(companies))
m3.metric("LinkedIn searches", len(search_queries))
m4.metric("Outreach pairings", len(suggestions))

# ------------------------------------------------------------------------ tabs
jobs_tab, searches_tab, drafts_tab, email_tab, profile_tab = st.tabs(
    ["🏆 Jobs", "🔎 Referral searches", "✉️ Outreach drafts", "📧 Email finder", "👤 Profile"]
)

with jobs_tab:
    chart_col, table_col = st.columns([1, 2])
    with chart_col:
        st.subheader("Jobs per company")
        if ranked_jobs:
            counts = pd.DataFrame(
                [(item.job.company, 1) for item in ranked_jobs], columns=["Company", "Jobs"]
            ).groupby("Company", as_index=False).sum().sort_values("Jobs", ascending=False)
            if len(counts) > 12:
                st.caption(f"Top 12 of {len(counts)} companies")
                counts = counts.head(12)
            st.bar_chart(counts, x="Company", y="Jobs", color=BAR_COLOR, horizontal=True, height=300)
        else:
            st.info("No matching roles — widen the target roles or lower the relevance bar.")
    with table_col:
        st.subheader(f"{'All' if company_filter == 'All companies' else company_filter} roles ≥ {min_score:.2f}")
        if not filtered:
            st.info("No jobs match the current filters — lower the minimum score or tune the profile.")
        else:
            table = pd.DataFrame(
                {
                    "Score": item.score,
                    "Company": item.job.company,
                    "Title": item.job.title.strip(),
                    "Location": item.job.location,
                    "Salary": format_salary(item.job),
                    "Level": item.job.level,
                    "Hours": item.job.hours_risk,
                    "Link": item.job.url,
                }
                for item in filtered
            )
            st.dataframe(
                table,
                hide_index=True,
                width="stretch",
                column_config={
                    "Score": st.column_config.NumberColumn(format="%.2f"),
                    "Link": st.column_config.LinkColumn(display_text="Open role"),
                },
            )

    st.subheader("Why the top matches rank high")
    for item in filtered[:5]:
        with st.expander(f"{item.score:.2f} · {item.job.company} — {item.job.title.strip()}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Salary", f"{item.salary_score:.2f}")
            c2.metric("Fit", f"{item.fit_score:.2f}")
            c3.metric("Realism", f"{item.realism_score:.2f}")
            c4.metric("Lifestyle", f"{item.lifestyle_score:.2f}")
            st.write(" · ".join(item.reasons))
            st.write(f"[Open role]({item.job.url}) — {format_salary(item.job)}")

with searches_tab:
    st.caption("Pre-built LinkedIn people searches for referral hunting, ranked by persona strength × job score.")
    active = [q for q in search_queries if company_filter in ("All companies", q.company)]
    if not active:
        st.info("No searches for this company filter.")
    else:
        searches_table = pd.DataFrame(
            {
                "Score": item.score,
                "Persona": item.persona,
                "Company": item.company,
                "Role": item.job_title.strip(),
                "Query": item.query,
                "Search": item.linkedin_url,
            }
            for item in active[:25]
        )
        st.dataframe(
            searches_table,
            hide_index=True,
            width="stretch",
            column_config={
                "Score": st.column_config.NumberColumn(format="%.2f"),
                "Search": st.column_config.LinkColumn(display_text="Open on LinkedIn"),
            },
        )

with drafts_tab:
    st.caption(f"First-pass LinkedIn messages pairing top jobs with the strongest contacts (from `{CONTACTS_PATH.name}` — swap in your own contact export).")
    active_drafts = [d for d in drafts if company_filter in ("All companies", d.company)]
    if not active_drafts:
        st.info("No drafts for this company filter — add contacts at these companies.")
    for draft in active_drafts:
        with st.expander(f"{draft.score:.2f} · {draft.contact_name} — {draft.company} / {draft.job_title.strip()}"):
            st.write(f"**Subject:** {draft.subject}")
            st.code(draft.message, language=None)
            st.write(f"[Open contact]({draft.contact_url}) · [Open role]({draft.job_url})")

with email_tab:
    st.caption(
        "Guess a contact's likely work email from common corporate patterns and draft a first-touch "
        "email for a specific role. Guesses are **unverified** — confirm with a verification service "
        "or a mutual contact, and reach out to one person at a time."
    )
    left, right = st.columns(2)
    with left:
        contact_name = st.text_input("Contact name", placeholder="e.g. Jane Doe")
        contact_title = st.text_input("Contact title (optional)", placeholder="e.g. Engineering Manager")
        email_company = st.selectbox("Company", [*companies, "Other…"], key="email-company")
        if email_company == "Other…":
            email_company = st.text_input("Company name", key="email-company-custom")
        domain_default = guess_company_domain(email_company) if email_company else ""
        domain = st.text_input("Email domain", value=domain_default, help="Auto-guessed from the company name — fix it if you know the real domain.")
        company_roles = [item.job.title.strip() for item in ranked_jobs if item.job.company == email_company]
        role_pick = st.selectbox("Role to reference", [*company_roles, "Custom…"] if company_roles else ["Custom…"])
        if role_pick == "Custom…":
            role_pick = st.text_input("Role title", key="email-role-custom")
        role_url = next(
            (item.job.url for item in ranked_jobs if item.job.company == email_company and item.job.title.strip() == role_pick),
            "",
        )
    with right:
        if contact_name and domain:
            guesses = guess_email_addresses(contact_name, domain)
            if guesses:
                st.subheader("Likely addresses")
                guess_table = pd.DataFrame(
                    {"Address": g.address, "Pattern": g.pattern, "Likelihood": g.confidence} for g in guesses
                )
                st.dataframe(
                    guess_table,
                    hide_index=True,
                    width="stretch",
                    column_config={"Likelihood": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=0.5)},
                )
            else:
                st.warning("Couldn't build guesses — check the name and that the domain looks like `company.com`.")
        else:
            st.info("Enter a contact name and domain to see likely addresses.")

    if contact_name and email_company and role_pick:
        subject, body = build_cold_email(
            profile,
            company=email_company,
            job_title=role_pick,
            contact_name=contact_name,
            contact_title=contact_title,
            job_url=role_url,
        )
        st.subheader("Draft email")
        st.write(f"**Subject:** {subject}")
        st.code(body, language=None)

with profile_tab:
    st.subheader(profile.name)
    st.write(profile.pitch or profile.notes)
    st.caption("Values below reflect the live tuning in the sidebar, not the saved file.")
    p1, p2 = st.columns(2)
    with p1:
        st.metric("Experience", f"{profile.years_experience:g} yrs")
        st.write("**Target titles:** " + ", ".join(profile.target_titles))
        st.write("**Preferred locations:** " + ", ".join(profile.preferred_locations))
        st.write("**Salary floor:** " + f"€{profile.salary_floor_eur:,}")
    with p2:
        st.write("**Skills:** " + ", ".join(profile.skills))
        st.write("**Stretch titles:** " + ", ".join(profile.stretch_level_titles))
        st.write("**Avoiding:** " + ", ".join(profile.avoid_keywords))
