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
