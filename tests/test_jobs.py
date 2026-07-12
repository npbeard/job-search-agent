from __future__ import annotations

from job_hunter_agent.jobs import rank_jobs

from tests.conftest import make_job


def test_rank_jobs_orders_by_score(profile):
    strong = make_job(title="Data Engineer", min_salary_eur=80000, max_salary_eur=100000, hours_risk="low")
    weak = make_job(
        company="GrindCo",
        title="Principal Consultant",
        level="principal",
        min_salary_eur=None,
        max_salary_eur=None,
        hours_risk="high",
        required_years_experience=12,
        skills=[],
    )
    ranked = rank_jobs(profile, [weak, strong])
    assert ranked[0].job.title == "Data Engineer"
    assert ranked[0].score > ranked[1].score


def test_rank_jobs_scores_are_bounded(profile):
    ranked = rank_jobs(profile, [make_job()])
    item = ranked[0]
    for value in (item.score, item.salary_score, item.fit_score, item.realism_score, item.lifestyle_score):
        assert 0.0 <= value <= 1.0


def test_stretch_title_boosts_realism(profile):
    plain_senior = make_job(title="Senior Platform Engineer", level="senior")
    stretch_senior = make_job(title="Senior Data Engineer", level="senior")
    ranked = {item.job.title: item for item in rank_jobs(profile, [plain_senior, stretch_senior])}
    assert ranked["Senior Data Engineer"].realism_score > ranked["Senior Platform Engineer"].realism_score


def test_avoid_keyword_tanks_lifestyle(profile):
    job = make_job(title="Data Engineer, Consulting Services")
    ranked = rank_jobs(profile, [job])
    assert ranked[0].lifestyle_score <= 0.1
    assert "contains avoid keyword" in ranked[0].reasons
