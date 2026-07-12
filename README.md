# Job Hunter Agent

A local Python project to help you:

- rank the highest-paying roles you are realistically qualified for
- prioritize non-consulting jobs with saner hours
- rank referral targets and outreach contacts
- keep LinkedIn/contact integrations behind a clean provider interface

## What this project does

The agent takes:

- your profile and constraints
- a list of jobs from company career pages, job boards, or exports
- a list of candidate contacts from LinkedIn or another compliant source

It then scores and ranks:

- jobs by compensation, fit, seniority realism, and work-life preferences
- contacts by alumni overlap, shared connections, role relevance, and company fit

## Important LinkedIn API note

As of April 23, 2026, LinkedIn's official APIs are restricted. In practice, most developers do **not** get open access to general people search, broad profile lookup, or automatic referral-target sourcing across LinkedIn unless they are in approved programs.

Official references:

- https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
- https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/profile-api
- https://www.linkedin.com/help/linkedin/answer/a526048

So this project includes:

- a `LinkedInOfficialProvider` placeholder for OAuth-backed self data and approved scopes
- a generic contact import pipeline for CSV/JSON exports from compliant sources
- careers collectors for common job-board providers: Lever, Greenhouse, and Ashby
- **aggregator collectors** (Remotive, The Muse) that dynamically discover jobs — and
  companies — matching your location, without maintaining a fixed company list
- an email-pattern guesser + cold-email drafter for reaching contacts directly

That gives you something usable right now while staying honest about platform limits.

## How job discovery works

Sources are configured in `config/market_targets.madrid.json` and come in two kinds:

- **Company boards** (`lever`, `greenhouse`, `ashby`, `manual`): a curated list of
  target companies; jobs are fetched live from each board.
- **Aggregators** (`remotive`, `themuse`): discover jobs across *any* company matching
  your location and category filters — new companies appear automatically. Note that
  Remotive's free API serves only its latest postings and asks for ≤ ~4 calls/day
  (the app's 6-hour cache respects that).

Duplicate roles found via both a company board and an aggregator are merged
(board version wins).

## Project layout

```text
job-hunter-agent/
  config/
    profile.example.json        # template profile (copy to profile.local.json)
    salary_bands.example.json   # per-company/level salary bands
    market_targets.madrid.json  # target companies for refresh-market
  data/
    examples/                   # demo jobs + contacts
    market/                     # per-company raw/enriched/relevant datasets
    seeds/                      # manually curated job inputs
    market_jobs.json            # merged market dataset (dashboard default)
  scripts/
    ui.sh                       # start/stop/status for the dashboard
  src/job_hunter_agent/
    cli.py                      # argparse entry point
    collectors.py               # Lever / Greenhouse careers API clients
    contacts.py                 # contact loading + ranking
    dashboard.py                # local web dashboard server
    enrichment.py               # level/salary/skill/location inference
    jobs.py                     # job ranking (salary/fit/realism/lifestyle)
    market.py                   # dataset merge + discovery
    messages.py                 # outreach draft generation
    models.py                   # dataclasses shared across modules
    pipeline.py                 # end-to-end refresh-market pipeline
    profile.py                  # profile loading
    search_queries.py           # LinkedIn referral search generation
    strategy.py                 # job x contact outreach pairing
    web/                        # dashboard static assets
  tests/                        # pytest suite
  .env.example
  pyproject.toml
  README.md
```

## Quick start

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install in editable mode (add `[dev]` for the test suite):

```bash
pip install -e ".[dev]"
```

3. Copy the sample profile and edit it (the `.local` name is gitignored and the dashboard picks it up automatically):

```bash
cp config/profile.example.json config/profile.local.json
```

4. Run the demo job ranking:

```bash
python3 -m job_hunter_agent rank-jobs \
  --profile config/profile.local.json \
  --jobs data/examples/jobs.json
```

5. Run the demo contact ranking:

```bash
python3 -m job_hunter_agent rank-contacts \
  --profile config/profile.local.json \
  --contacts data/examples/contacts.json
```

6. Generate combined outreach suggestions:

```bash
python3 -m job_hunter_agent suggest-outreach \
  --profile config/profile.local.json \
  --jobs data/examples/jobs.json \
  --contacts data/examples/contacts.json
```

7. Generate outreach drafts:

```bash
python3 -m job_hunter_agent draft-messages \
  --profile config/profile.local.json \
  --jobs data/examples/jobs.json \
  --contacts data/examples/contacts.json
```

8. Collect live jobs from common careers APIs:

```bash
python3 -m job_hunter_agent collect-jobs \
  --provider lever \
  --token aircall \
  --location Madrid \
  --output data/aircall_jobs.json

python3 -m job_hunter_agent collect-jobs \
  --provider greenhouse \
  --token twilio \
  --location Spain \
  --output data/twilio_jobs.json
```

9. Enrich raw collected jobs with inferred level and salary:

```bash
python3 -m job_hunter_agent enrich-jobs \
  --profile config/profile.local.json \
  --jobs data/aircall_jobs.json \
  --salary-bands config/salary_bands.example.json \
  --output data/aircall_jobs_enriched.json \
  --filtered-output data/aircall_jobs_relevant.json
```

10. Review which jobs are worth ranking:

```bash
python3 -m job_hunter_agent review-jobs \
  --profile config/profile.local.json \
  --jobs data/aircall_jobs_enriched.json
```

11. Launch the local dashboard:

```bash
python3 -m job_hunter_agent serve-ui --port 8765
# or, in the background:
scripts/ui.sh start
```

12. Merge multiple company datasets into one market file:

```bash
python3 -m job_hunter_agent merge-jobs \
  --input data/examples/jobs.json \
  --discover-dir data \
  --suffix _relevant.json \
  --output data/market_jobs.json
```

13. Refresh the full Madrid / Spain-remote market dataset:

```bash
python3 -m job_hunter_agent refresh-market \
  --profile config/profile.example.json \
  --market-config config/market_targets.madrid.json \
  --salary-bands config/salary_bands.example.json \
  --output-dir data/market \
  --merged-output data/market_jobs.json
```

14. Generate LinkedIn referral searches from the ranked jobs:

```bash
python3 -m job_hunter_agent contact-searches \
  --profile config/profile.example.json \
  --jobs data/market_jobs.json
```

15. Guess likely email addresses for a contact (and draft a cold email):

```bash
python3 -m job_hunter_agent guess-emails \
  --name "Jane Doe" \
  --company "Acme" \
  --job-title "Data Engineer" \
  --profile config/profile.local.json
```

## Streamlit app (local or hosted)

A Streamlit version of the dashboard lives in `streamlit_app.py`. It reuses the same
ranking modules and auto-refreshes live market data on load (cached for 6 hours), so a
hosted deployment always shows fresh jobs. It also supports:

- **Live profile tuning** — adjust salary floor, target/stretch roles, skills, avoid
  keywords, and experience in the sidebar; rankings and relevance re-compute instantly
  against the full collected dataset (not just the pre-filtered shortlist).
- **Email finder** — guess a contact's likely work email from common corporate
  patterns and draft a role-specific first-touch email from your profile. Guesses are
  unverified; confirm before relying on them.

Run it locally:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Deploy to Streamlit Community Cloud (free):

1. Push this repo to GitHub.
2. Go to https://share.streamlit.io, sign in with GitHub, and click **Create app**.
3. Pick the repo, branch `main`, and main file `streamlit_app.py`.
4. Deploy — every git push redeploys automatically.

Note: the app URL is publicly reachable, and the committed profile (name, pitch,
salary floor) is visible to anyone with the link. Keep `config/profile.local.json`
for anything you don't want published — it stays gitignored and takes precedence
when present locally.

## Testing

```bash
python3 -m pytest
```

## Profile fields worth knowing

- `pitch`: a one-or-two-sentence intro used verbatim in outreach drafts. If empty, a generic pitch is built from your location, experience, and top skills.
- `stretch_level_titles`: titles slightly above your level that you still want scored favorably.
- `avoid_keywords`: any job whose title/company/location contains one of these gets its lifestyle score capped.

## Expected job input

Jobs are JSON objects with fields like:

- `company`
- `title`
- `location`
- `remote_type`
- `employment_type`
- `min_salary_eur`
- `max_salary_eur`
- `hours_risk`
- `required_years_experience`
- `level`
- `skills`
- `url`
- `source`

## Expected contact input

Contacts are JSON objects with fields like:

- `full_name`
- `company`
- `title`
- `location`
- `linkedin_url`
- `university`
- `shared_connections`
- `same_university`
- `recruiter`
- `hiring_manager`
- `works_in_target_role`

## Suggested workflow

1. Save live jobs from target career pages into a JSON file.
2. Or use `collect-jobs` for companies on Lever or Greenhouse.
3. Run `enrich-jobs` to infer level, salary, skills, and a filtered shortlist.
4. Run `review-jobs` to sanity check the shortlist.
5. Run `rank-jobs` to identify the best realistic opportunities.
6. Export or manually gather potential contacts into JSON or CSV.
7. Run `rank-contacts` to prioritize who to message first.
8. Run `suggest-outreach` to pair top jobs with the best referral targets.
9. Run `draft-messages` to generate customized first-pass outreach text.
10. Run `merge-jobs` so the dashboard sees a market-wide dataset instead of one company file.
11. Run `serve-ui` to inspect the shortlist and outreach drafts visually.
12. Use the generated ranking and drafts to drive outreach and applications.

## Next improvements

- add salary enrichment from public compensation sources
- add OAuth flow if you receive approved LinkedIn access
