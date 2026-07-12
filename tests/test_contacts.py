from __future__ import annotations

import json

from job_hunter_agent.contacts import load_contacts, rank_contacts, resolve_contact_url
from job_hunter_agent.models import ReferralContact


def make_contact(**overrides) -> ReferralContact:
    defaults = dict(
        full_name="Jane Doe",
        company="Acme",
        title="Data Engineer",
        location="Madrid, Spain",
        linkedin_url="https://www.linkedin.com/in/janedoe",
    )
    defaults.update(overrides)
    return ReferralContact(**defaults)


def test_load_contacts_csv_coerces_types(tmp_path):
    csv_path = tmp_path / "contacts.csv"
    csv_path.write_text(
        "full_name,company,title,location,linkedin_url,university,shared_connections,"
        "same_university,recruiter,hiring_manager,works_in_target_role\n"
        "Jane Doe,Acme,Data Engineer,Madrid,https://www.linkedin.com/in/janedoe,IE University,7,true,false,yes,no\n",
        encoding="utf-8",
    )
    contacts = load_contacts(str(csv_path))
    assert len(contacts) == 1
    contact = contacts[0]
    assert contact.shared_connections == 7
    assert contact.same_university is True
    assert contact.recruiter is False
    assert contact.hiring_manager is True
    assert contact.works_in_target_role is False


def test_load_contacts_json(tmp_path):
    json_path = tmp_path / "contacts.json"
    json_path.write_text(
        json.dumps([{"full_name": "Jane Doe", "company": "Acme", "title": "Engineer",
                     "location": "Madrid", "linkedin_url": ""}]),
        encoding="utf-8",
    )
    contacts = load_contacts(str(json_path))
    assert contacts[0].linkedin_url.startswith("https://www.linkedin.com/search/")


def test_resolve_contact_url_keeps_real_urls():
    url = "https://www.linkedin.com/in/janedoe"
    assert resolve_contact_url(url, "Jane", "Acme", "Madrid", "Engineer") == url


def test_resolve_contact_url_builds_search_for_placeholders():
    resolved = resolve_contact_url("https://linkedin.com/in/example-abc", "Jane Doe", "Acme", "Madrid", "Engineer")
    assert "search/results/people" in resolved
    assert "Jane+Doe" in resolved


def test_rank_contacts_prioritizes_strong_signals(profile):
    strong = make_contact(full_name="Strong", same_university=True, hiring_manager=True, shared_connections=10)
    weak = make_contact(full_name="Weak", company="Elsewhere", title="Accountant", location="Berlin")
    ranked = rank_contacts(profile, [weak, strong])
    assert ranked[0].contact.full_name == "Strong"
    assert ranked[0].score > ranked[1].score
    assert all(0.0 <= item.score <= 1.0 for item in ranked)
