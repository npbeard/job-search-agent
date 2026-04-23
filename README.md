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
- careers collectors for common job-board providers like Lever and Greenhouse

That gives you something usable right now while staying honest about platform limits.

## Project layout

```text
job-hunter-agent/
  config/
    profile.example.json
  data/examples/
    jobs.json
    contacts.json
  config/
    salary_bands.example.json
    market_targets.madrid.json
  src/job_hunter_agent/
    __main__.py
    cli.py
    collectors.py
    contacts.py
    enrichment.py
    io_utils.py
    jobs.py
    linkedin.py
    messages.py
    models.py
    profile.py
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

2. Install in editable mode:

```bash
pip install -e .
```

3. Copy the sample profile and edit it:

```bash
cp config/profile.example.json config/profile.json
```

4. Run the demo job ranking:

```bash
python3 -m job_hunter_agent rank-jobs \
  --profile config/profile.json \
  --jobs data/examples/jobs.json
```

5. Run the demo contact ranking:

```bash
python3 -m job_hunter_agent rank-contacts \
  --profile config/profile.json \
  --contacts data/examples/contacts.json
```

6. Generate combined outreach suggestions:

```bash
python3 -m job_hunter_agent suggest-outreach \
  --profile config/profile.json \
  --jobs data/examples/jobs.json \
  --contacts data/examples/contacts.json
```

7. Generate outreach drafts:

```bash
python3 -m job_hunter_agent draft-messages \
  --profile config/profile.json \
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
  --profile config/profile.json \
  --jobs data/aircall_jobs.json \
  --salary-bands config/salary_bands.example.json \
  --output data/aircall_jobs_enriched.json \
  --filtered-output data/aircall_jobs_relevant.json
```

10. Review which jobs are worth ranking:

```bash
python3 -m job_hunter_agent review-jobs \
  --profile config/profile.json \
  --jobs data/aircall_jobs_enriched.json
```

11. Launch the local dashboard:

```bash
python3 -m job_hunter_agent serve-ui --port 8765
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
