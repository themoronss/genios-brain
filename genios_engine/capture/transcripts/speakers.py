"""P5 · speaker mapping — a transcript's labels → people, against a CLOSED candidate set.

The candidates are the meeting's attendees plus the uploader, and nobody else (plan §3). The org's
name index is deliberately not consulted: "Priya" in a transcript is one of the four people who
were in the meeting or nobody — an org-wide name lookup would file her promise against whichever
Priya the graph met first, and nothing would record that a guess was made.

Order, first hit wins (§3): manual → email → exact name / alias → unique first name → `Me`/`You`
= the uploader → `unknown`. An ambiguous step (two candidates answer) resolves to nobody and falls
through; `unknown` is a real answer, and the pipeline gives an unknown speaker's claims no owner.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from sqlalchemy import text

_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")
SELF_LABELS = frozenset({"me", "you"})
MATCHES = ("email", "name", "first_name", "self", "manual", "unknown")


def norm_name(value: str | None) -> str:
    """Case-folded, parenthetical-free ("Priya (Acme)" → "priya"), punctuation to spaces."""
    s = _PAREN.sub(" ", str(value or ""))
    s = re.sub(r"[^\w\s'’-]", " ", s.casefold())
    return " ".join(s.replace("’", "'").split())


def _local_part_name(email: str) -> str:
    """"shalini.iyer@voltex.in" → "shalini iyer". A DERIVATION used only as an alias of the
    same candidate — never to find a candidate the meeting did not have."""
    local = email.split("@", 1)[0]
    return " ".join(p for p in re.split(r"[._+\-]+", local.casefold()) if p.isalpha())


@dataclass(frozen=True)
class Candidate:
    """Someone a label may resolve to: an attendee of the linked meeting, or the uploader."""

    email: str | None
    name: str | None = None
    aliases: tuple[str, ...] = ()
    person_node_id: str | None = None
    seat_id: str | None = None
    is_uploader: bool = False

    def names(self) -> set[str]:
        out = {norm_name(n) for n in (self.name, *self.aliases) if n and "@" not in str(n)}
        if self.email:
            derived = _local_part_name(self.email)
            if " " in derived:                      # a single token is a handle, not a name
                out.add(derived)
        return {n for n in out if n}

    def first_names(self) -> set[str]:
        return {n.split()[0] for n in self.names()}

    def view(self) -> dict:
        """The contract's attendee shape: `{name, email|null, person_node_id|null}`."""
        return {"name": self.name or self.email or "", "email": self.email,
                "person_node_id": self.person_node_id}


def _entry(label: str, cand: Candidate | None, match: str) -> dict:
    if cand is None:
        return {"label": label, "email": None, "person_node_id": None, "seat_id": None,
                "match": "unknown" if match != "manual" else "manual"}
    return {"label": label, "email": cand.email, "person_node_id": cand.person_node_id,
            "seat_id": cand.seat_id, "match": match}


def _unique(cands: Iterable[Candidate]) -> Candidate | None:
    found = {(c.email or c.person_node_id or norm_name(c.name)): c for c in cands}
    return next(iter(found.values())) if len(found) == 1 else None


def resolve_label(label: str, candidates: list[Candidate]) -> tuple[Candidate | None, str]:
    """One label → (candidate, match). Pure."""
    n = norm_name(label)
    m = _EMAIL.search(label or "")
    if m:
        hit = _unique(c for c in candidates if c.email and c.email == m.group(0).lower())
        return (hit, "email") if hit else (None, "unknown")
    if not n:
        return None, "unknown"
    hit = _unique(c for c in candidates if n in c.names())
    if hit:
        return hit, "name"
    tokens = n.split()
    if tokens and n not in SELF_LABELS:
        first, rest = tokens[0], tokens[1:]

        def compatible(c: Candidate) -> bool:
            if first not in c.first_names():
                return False
            if not rest:
                return True
            # "Priya S." may be Priya Shah; "Priya Kapoor" is not.
            surnames = {tuple(x.split()[1:]) for x in c.names() if x.split()[0] == first}
            return any(all(s and (w.startswith(r.rstrip(".")) if len(r.rstrip(".")) <= 2 else w == r)
                           for r, w in zip(rest, s)) and len(s) >= len(rest) for s in surnames)
        hit = _unique(c for c in candidates if compatible(c))
        if hit:
            return hit, "first_name"
    if n in SELF_LABELS:
        hit = _unique(c for c in candidates if c.is_uploader)
        if hit:
            return hit, "self"
    return None, "unknown"


def map_speakers(labels: Iterable[str], candidates: list[Candidate], *,
                 manual: Mapping[str, Candidate | None] | None = None) -> list[dict]:
    """Every label → the §3 speaker entry. `manual` (label → candidate or None) wins outright:
    a person's explicit mapping is the one assignment that is not a derivation."""
    out = []
    for label in dict.fromkeys(labels):
        if manual is not None and label in manual:
            out.append(_entry(label, manual[label], "manual"))
            continue
        cand, match = resolve_label(label, candidates)
        out.append(_entry(label, cand, match))
    return out


# ── database side ──────────────────────────────────────────────────────────────────────────────
def load_candidates(conn, org_id: str, emails: Iterable[str], *,
                    uploader_email: str | None) -> list[Candidate]:
    """The attendees' and the uploader's person nodes, name aliases and seats. An address with no
    person node is still a candidate (mapped by email / local-part name, node filled in by L2)."""
    wanted = sorted({str(e).strip().lower() for e in [*emails, uploader_email or ""]
                     if e and "@" in str(e)})
    up = (uploader_email or "").strip().lower()
    if not wanted:
        return []
    nodes = conn.execute(text(
        "select node_id, lower(canonical_key) as email, display_name from graph_nodes "
        "where org_id=:o and node_type='person' and valid_to is null "
        "and lower(canonical_key) = any(:e)"), {"o": org_id, "e": wanted}).fetchall()
    by_email = {r.email: r for r in nodes}
    aliases: dict[str, list[str]] = {}
    if nodes:
        for r in conn.execute(text(
                "select node_id, alias_key from graph_aliases where org_id=:o "
                "and alias_type='person_name' and node_id = any(:n)"),
                {"o": org_id, "n": [r.node_id for r in nodes]}).fetchall():
            aliases.setdefault(r.node_id, []).append(r.alias_key)
    seats = {r.email: r.seat_id for r in conn.execute(text(
        "select seat_id, lower(email) as email from org_seats where org_id=:o and active "
        "and lower(email) = any(:e)"), {"o": org_id, "e": wanted}).fetchall()}
    out = []
    for e in wanted:
        node = by_email.get(e)
        name = node.display_name if node is not None and node.display_name \
            and "@" not in node.display_name else None
        out.append(Candidate(email=e, name=name,
                             aliases=tuple(aliases.get(node.node_id, ())) if node else (),
                             person_node_id=node.node_id if node is not None else None,
                             seat_id=seats.get(e), is_uploader=(e == up)))
    return out


def manual_candidate(conn, org_id: str, value: str | None) -> Candidate | None:
    """A PUT /speakers value → a candidate: a person node id of this org, or an email (its node
    when one exists). None/"" clears the label to `unknown`. Raises ValueError for a node id that
    is not a live person of this org."""
    v = (value or "").strip()
    if not v:
        return None
    if "@" in v:
        email = v.lower()
        row = conn.execute(text(
            "select node_id, display_name from graph_nodes where org_id=:o and node_type='person' "
            "and valid_to is null and lower(canonical_key)=:e limit 1"),
            {"o": org_id, "e": email}).first()
        seat = conn.execute(text("select seat_id from org_seats where org_id=:o and active "
                                 "and lower(email)=:e limit 1"), {"o": org_id, "e": email}).scalar()
        return Candidate(email=email, name=(row.display_name if row else None),
                         person_node_id=row.node_id if row else None, seat_id=seat)
    row = conn.execute(text(
        "select node_id, lower(canonical_key) as email, display_name from graph_nodes "
        "where org_id=:o and node_id=:n and node_type='person' and valid_to is null"),
        {"o": org_id, "n": v}).first()
    if row is None:
        raise ValueError(f"{v!r} is not a person in this workspace")
    email = row.email if row.email and "@" in row.email else None
    seat = conn.execute(text("select seat_id from org_seats where org_id=:o and active "
                             "and lower(email)=:e limit 1"), {"o": org_id, "e": email}).scalar() \
        if email else None
    return Candidate(email=email, name=row.display_name, person_node_id=row.node_id, seat_id=seat)


def candidate_from_entry(entry: Mapping) -> Candidate | None:
    """A stored §3 speaker entry back into a candidate (to carry manual mappings forward)."""
    if not entry.get("email") and not entry.get("person_node_id"):
        return None
    return Candidate(email=entry.get("email"), person_node_id=entry.get("person_node_id"),
                     seat_id=entry.get("seat_id"))


__all__ = ["Candidate", "MATCHES", "SELF_LABELS", "candidate_from_entry", "load_candidates",
           "manual_candidate", "map_speakers", "norm_name", "resolve_label"]
