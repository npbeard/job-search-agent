"""Guess likely corporate email addresses and draft cold outreach emails.

Guesses are built from the handful of patterns that cover the vast majority of
company email schemes. They are *unverified* — treat them as best-effort leads,
send politely, and prefer a verification service (e.g. Hunter, NeverBounce) or a
mutual contact when accuracy matters.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from job_hunter_agent.models import CandidateProfile


@dataclass
class EmailGuess:
    address: str
    pattern: str
    confidence: float


# (pattern name, share of companies using it — rough industry priors)
EMAIL_PATTERNS: list[tuple[str, float]] = [
    ("first.last", 0.40),
    ("first", 0.15),
    ("flast", 0.14),
    ("firstlast", 0.08),
    ("first_last", 0.06),
    ("f.last", 0.05),
    ("last.first", 0.04),
    ("firstl", 0.03),
    ("first-last", 0.03),
    ("last", 0.02),
]


def _ascii_token(text: str) -> str:
    """Lowercase, strip accents, and drop anything that isn't a letter."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if char.isascii() and char.isalpha()).lower()


def split_name(full_name: str) -> tuple[str, str]:
    """Return (first, last) tokens, ignoring middle names/initials."""
    tokens = [_ascii_token(part) for part in full_name.strip().split()]
    tokens = [token for token in tokens if token]
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return tokens[0], tokens[0]
    return tokens[0], tokens[-1]


def _build_local_part(pattern: str, first: str, last: str) -> str:
    mapping = {
        "first.last": f"{first}.{last}",
        "first": first,
        "flast": f"{first[:1]}{last}",
        "firstlast": f"{first}{last}",
        "first_last": f"{first}_{last}",
        "f.last": f"{first[:1]}.{last}",
        "last.first": f"{last}.{first}",
        "firstl": f"{first}{last[:1]}",
        "first-last": f"{first}-{last}",
        "last": last,
    }
    return mapping[pattern]


def guess_email_addresses(full_name: str, domain: str) -> list[EmailGuess]:
    """Rank likely addresses for a person at a company domain."""
    first, last = split_name(full_name)
    domain = domain.strip().lower().removeprefix("http://").removeprefix("https://").removeprefix("www.").strip("/")
    if not first or not domain or "." not in domain:
        return []
    guesses: list[EmailGuess] = []
    seen: set[str] = set()
    for pattern, confidence in EMAIL_PATTERNS:
        local = _build_local_part(pattern, first, last)
        address = f"{local}@{domain}"
        if address in seen:
            continue
        seen.add(address)
        guesses.append(EmailGuess(address=address, pattern=pattern, confidence=confidence))
    return guesses


def guess_company_domain(company: str) -> str:
    """Best-effort default domain from a company name (always verify)."""
    cleaned = re.sub(r"\b(inc|llc|ltd|gmbh|sl|sa|corp|co|labs)\b\.?", "", company.lower())
    slug = "".join(char for char in cleaned if char.isalnum())
    return f"{slug}.com" if slug else ""


def build_cold_email(
    profile: CandidateProfile,
    company: str,
    job_title: str,
    contact_name: str,
    contact_title: str = "",
    job_url: str = "",
) -> tuple[str, str]:
    """Return (subject, body) for a first-touch email about a specific role."""
    first_name = contact_name.strip().split()[0] if contact_name.strip() else "there"
    pitch = profile.pitch.strip().rstrip(".")
    if not pitch:
        top_skills = ", ".join(profile.skills[:4]) if profile.skills else "software engineering"
        pitch = (
            f"I'm a {profile.location.split(',')[0]}-based engineer with about "
            f"{profile.years_experience:g} years of experience, focused on {top_skills}"
        )
    role_line = f"the {job_title} opening at {company}"
    link_line = f"\n\nRole for reference: {job_url}" if job_url else ""
    who = f" As {contact_title}," if contact_title else ""
    subject = f"{job_title} at {company} — quick question"
    body = (
        f"Hi {first_name},\n\n"
        f"{pitch}. I'm reaching out because I'm very interested in {role_line}, and I'd rather "
        f"talk to someone on the inside than send a resume into the void.{who} I'd hugely "
        f"appreciate 10 minutes of your perspective on the team and what makes candidates "
        f"successful there. If the conversation goes well and it feels appropriate, a referral "
        f"would mean a lot — but no pressure either way."
        f"{link_line}\n\n"
        f"Thanks for your time,\n"
        f"{profile.name}"
    )
    return subject, body
