"""Canonical identity keys — ONE definition, imported downward by every layer.

Identity is the substrate of cross-intelligence: the same human arriving via gmail
(sender), calendar (attendee), CRM (contact) and a typed note must converge on ONE
node, or every cross-tool rule reasons about strangers. That only holds if every
writer computes the SAME canonical key — and it didn't: the structured lane
lowercased only, while the extraction pipeline also stripped +tags, so
priya+cal@x.com (calendar) and priya@x.com (email) became two people.

Deterministic, no fuzz: exact key equality is the ONLY auto-merge (D8 — name
similarity is a candidate finder, never a merge authority)."""
from __future__ import annotations

import re

# Legal-form tokens carried by a company's registered name but never by how people
# refer to it. "Acme, Inc." / "Acme Technologies Pvt Ltd" / "ACME" are one company in
# conversation and three strings in the data.
_LEGAL_SUFFIXES: frozenset[str] = frozenset({
    "inc", "incorporated", "llc", "llp", "ltd", "limited", "pvt", "private",
    "corp", "corporation", "co", "company", "gmbh", "ag", "sa", "sas", "bv", "nv",
    "plc", "pte", "pty", "srl", "spa", "oy", "ab", "as", "kk", "kft",
})

# Two-part public suffixes we see in practice. Not a full public-suffix list — a
# missing entry only makes domain_root SHORTER than ideal ("acme" → "co"), which is
# why the caller never auto-merges on it. Extend as real domains show up.
_COMPOUND_TLDS: frozenset[str] = frozenset({
    "co.uk", "co.in", "co.jp", "co.nz", "co.za", "com.au", "com.br", "com.sg",
    "com.mx", "org.uk", "net.au", "ac.uk", "gov.uk", "co.il", "co.kr",
})


def norm_email(email: str | None) -> str | None:
    """Canonical email key: lowercase + trim + strip a +tag suffix from the local
    part. None for malformed input. THE person-identity function — every layer that
    mints a person canonical_key must use exactly this."""
    if not email or "@" not in str(email):
        return None
    local, _, dom = str(email).strip().lower().partition("@")
    local = local.split("+", 1)[0]
    return f"{local}@{dom}" if local and dom else None


#: The handle prefix a person known only by a LinkedIn profile carries as `actor_email` and as
#: their node's canonical key (SCREEN_INTEL_P2_BUILD §3.2). An email can never start with it.
LINKEDIN_PREFIX = "li:"

_LINKEDIN_PROFILE = re.compile(
    r"^(?:https?://)?(?:[a-z0-9-]+\.)*linkedin\.com/in/([^/?#\s]+)", re.IGNORECASE)


def norm_linkedin_url(url: str | None) -> str | None:
    """A LinkedIn PROFILE url → `https://www.linkedin.com/in/<slug>`, lower-cased. None otherwise.

    One person, many spellings: `http://in.linkedin.com/in/Priya-S/`, `linkedin.com/in/priya-s`,
    `https://www.linkedin.com/in/priya-s?trk=…#about` and `…/in/priya-s/details/experience` are
    one profile. Scheme, subdomain (country / mobile), query, fragment, trailing slash and any
    sub-page are dropped; the slug is kept as written (lower-cased). An already-prefixed handle
    (`li:https://…`) is accepted, so normalising twice is a no-op.

    Only `/in/` profiles: a `/company/` page or a post is not a person and returns None.
    Derivation, never comparison — the result is matched by string equality like every key here.
    """
    raw = str(url or "").strip()
    if raw.lower().startswith(LINKEDIN_PREFIX):
        raw = raw[len(LINKEDIN_PREFIX):].strip()
    match = _LINKEDIN_PROFILE.match(raw)
    if not match:
        return None
    slug = match.group(1).strip().lower()
    return f"https://www.linkedin.com/in/{slug}" if slug else None


def linkedin_handle(url: str | None) -> str | None:
    """`li:` + the normalised profile url — the identity a LinkedIn-only person is keyed on."""
    norm = norm_linkedin_url(url)
    return f"{LINKEDIN_PREFIX}{norm}" if norm else None


def person_key(value: str | None) -> str | None:
    """The canonical key for a person arriving as `actor_email`: an email, or an `li:` handle.

    Emails go through `norm_email`; an `li:` handle through `linkedin_handle`, so two spellings of
    one profile URL mint ONE node. Anything else is returned trimmed and lower-cased, which is what
    the context pipeline did for every non-email key before this existed.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.lower().startswith(LINKEDIN_PREFIX):
        return linkedin_handle(raw) or raw.lower()
    return norm_email(raw) or raw.lower()


def company_slug(name: str | None) -> str | None:
    """Company NAME → a comparison key. 'Acme, Inc.' / 'ACME' / 'Acme  Inc' → 'acme'.

    A CANDIDATE key, never an identity. Two real companies can share a slug ('Apex
    Legal' and 'Apex Logistics' both shorten to nothing useful if you over-trim), so a
    collision here raises a merge PROPOSAL for a human — it never merges anything.

    Only legal-form tokens are stripped, and never all of them: 'Co' alone stays 'co',
    because trimming a one-word name to nothing would make every such company collide.
    """
    if not name:
        return None
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", str(name).strip().lower())
    words = [w for w in cleaned.split() if w]
    if not words:
        return None
    kept = [w for w in words if w not in _LEGAL_SUFFIXES]
    return " ".join(kept or words)


def domain_root(domain: str | None) -> str | None:
    """Email/web domain → the company label. 'mail.acme.io' → 'acme', 'acme.co.uk' → 'acme'.

    Also a candidate key only. Sub-brands share a root, unrelated companies can share a
    label across TLDs (acme.io vs acme.com may be one company or two), and the compound
    TLD list is incomplete by design. Never auto-merge on this.
    """
    if not domain or "." not in str(domain):
        return None
    parts = [p for p in str(domain).strip().lower().strip(".").split(".") if p]
    if len(parts) < 2:
        return None
    if len(parts) >= 3 and ".".join(parts[-2:]) in _COMPOUND_TLDS:
        return parts[-3]
    return parts[-2]


def person_name_key(name: str | None) -> str | None:
    """Person NAME → a comparison key. 'Rohit  S.' → 'rohit s'.

    The weakest key in the file. Two colleagues genuinely share a name; an email
    signature and a calendar invite spell the same person three ways. Used ONLY to
    surface a proposal alongside other evidence — on its own it proves nothing.
    """
    if not name:
        return None
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", str(name).strip().lower())
    return " ".join(cleaned.split()) or None
