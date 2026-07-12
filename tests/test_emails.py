from __future__ import annotations

from job_hunter_agent.emails import (
    build_cold_email,
    guess_company_domain,
    guess_email_addresses,
    split_name,
)


def test_split_name_handles_middle_names_and_accents():
    assert split_name("Jane Doe") == ("jane", "doe")
    assert split_name("Jane Marie Doe") == ("jane", "doe")
    assert split_name("José García") == ("jose", "garcia")
    assert split_name("Cher") == ("cher", "cher")
    assert split_name("") == ("", "")


def test_guess_email_addresses_ranked_and_deduped():
    guesses = guess_email_addresses("Jane Doe", "acme.com")
    addresses = [guess.address for guess in guesses]
    assert addresses[0] == "jane.doe@acme.com"
    assert "jdoe@acme.com" in addresses
    assert len(addresses) == len(set(addresses))
    confidences = [guess.confidence for guess in guesses]
    assert confidences == sorted(confidences, reverse=True)


def test_guess_email_addresses_strips_url_prefix():
    guesses = guess_email_addresses("Jane Doe", "https://www.acme.com/")
    assert guesses[0].address == "jane.doe@acme.com"


def test_guess_email_addresses_invalid_inputs():
    assert guess_email_addresses("", "acme.com") == []
    assert guess_email_addresses("Jane Doe", "") == []
    assert guess_email_addresses("Jane Doe", "not-a-domain") == []


def test_single_token_name_collapses_duplicates():
    guesses = guess_email_addresses("Cher", "acme.com")
    addresses = [guess.address for guess in guesses]
    # first == last, so first.last / flast / firstlast etc. collapse
    assert len(addresses) == len(set(addresses))
    assert "cher@acme.com" in addresses


def test_guess_company_domain():
    assert guess_company_domain("Acme") == "acme.com"
    assert guess_company_domain("Grafana Labs") == "grafana.com"
    assert guess_company_domain("Clerky, Inc.") == "clerky.com"


def test_build_cold_email_uses_pitch_and_role(profile):
    subject, body = build_cold_email(
        profile,
        company="Acme",
        job_title="Data Engineer",
        contact_name="Jane Doe",
        contact_title="Engineering Manager",
        job_url="https://example.com/job",
    )
    assert subject == "Data Engineer at Acme — quick question"
    assert body.startswith("Hi Jane,")
    assert "Data Engineer opening at Acme" in body
    assert "As Engineering Manager," in body
    assert "https://example.com/job" in body
    assert body.endswith(profile.name)


def test_build_cold_email_without_optionals(profile):
    subject, body = build_cold_email(profile, "Acme", "Data Engineer", contact_name="")
    assert "Hi there," in body
    assert "Role for reference" not in body
