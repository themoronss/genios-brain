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


def norm_email(email: str | None) -> str | None:
    """Canonical email key: lowercase + trim + strip a +tag suffix from the local
    part. None for malformed input. THE person-identity function — every layer that
    mints a person canonical_key must use exactly this."""
    if not email or "@" not in str(email):
        return None
    local, _, dom = str(email).strip().lower().partition("@")
    local = local.split("+", 1)[0]
    return f"{local}@{dom}" if local and dom else None
