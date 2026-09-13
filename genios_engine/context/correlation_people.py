"""G-08 · PERSON-TO-PERSON CORRELATION — who depends on whom inside the tenant, read off the graph.

Correlation until now grouped around COUNTERPARTIES (`correlation.py`, `correlation_organization.py`):
a situation is "everything about Acme". The P4 team questions are about the people INSIDE the
tenant — Anisha's absence matters to Emru because Anisha owes Emru something due on the 18th. This
module reads those links; it writes nothing and calls no model.

    commitments       owner (`commitment.owner` fact, else the `owns` edge) ↔ beneficiary
                      (`commitment.owed_to`)
    responsibilities  who answers for a slice (`seat_responsibilities`) — cover candidates
    availability      org-visible absence windows, mapped to people and seats

ORG-VISIBLE ONLY. Every fact read here drops `visibility_scope='private'` rows: a team situation is
shown to a seat other than the one whose screen may have produced a private overlay (P2,
`context/fact_visibility.py`), so a private fact never reaches it — not even for its own principal.

A FALSE LINK IS WORSE THAN A MISSING ONE (the dependency lane's rule, for the same reason): a name
resolves to a person only on an exact email, an exact display name / `person_name` alias, or a
single-word first name unique among the org's SEATS. Anything else is no link.

NOT READ, stated rather than guessed: blocker ↔ blocked. `correlation_dependency.py` publishes chains
as derived counts, not person edges, so there is no person link to read yet.

LAYER NOTE. Responsibility routing lives in `executive/assignment.py` (layer 5); this is layer 2 and
may not import it. `answering_for` is the same half-open-window read as
`PgSeatDirectory.answerable_for`, and `COUNTERPARTY_WORDS` are its alias words for
`commitment.owed_to` — `tests/test_team_unit.py` pins that parity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from sqlalchemy import text

from genios_engine.context.availability import AvailabilityWindow, org_availability

DONE_STATUSES: frozenset[str] = frozenset({"done", "delivered", "completed", "complete",
                                           "fulfilled", "closed", "resolved"})
DROPPED_STATUSES: frozenset[str] = frozenset({"cancelled", "canceled", "dropped", "void",
                                              "withdrawn"})
#: `executive.assignment.SCOPE_ALIASES` words whose paths include `commitment.owed_to`.
COUNTERPARTY_WORDS: tuple[str, ...] = ("account", "client", "company", "counterparty", "customer",
                                       "firm", "organisation", "organization")
#: The longest value that can still be a NAME (same bound as assignment._SCOPE_VALUE_MAX).
_SCOPE_VALUE_MAX = 120
_ORG_VISIBLE = "f.visibility_scope is distinct from 'private'"


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


@dataclass(frozen=True, slots=True)
class Person:
    node_id: str | None = None
    email: str | None = None
    name: str | None = None
    seat_id: str | None = None

    @property
    def label(self) -> str:
        if self.name:
            return self.name
        if self.email:
            return self.email.split("@", 1)[0]
        return self.seat_id or "someone"


@dataclass(frozen=True)
class CommitmentLink:
    node_id: str
    text: str
    due: date | None
    status: str
    owner: Person | None
    beneficiary: Person | None
    owed_to: str | None
    facts: Mapping[str, Any]

    @property
    def done(self) -> bool:
        return self.status in DONE_STATUSES

    @property
    def dropped(self) -> bool:
        return self.status in DROPPED_STATUSES

    @property
    def open(self) -> bool:
        return not self.done and not self.dropped


class PeopleDirectory:
    """Person nodes + active seats, joined on the email (`graph_nodes.canonical_key` of a person
    is its address — `context/pipeline.py`; `org_seats.email` — the seat). Pure once built."""

    def __init__(self, persons: Iterable[tuple[str, str | None, str | None]],
                 aliases: Iterable[tuple[str, str]], seats: Iterable[tuple[str, str | None]]):
        self._node: dict[str, tuple[str | None, str | None]] = {}
        self._by_email: dict[str, str] = {}
        self._by_name: dict[str, set[str]] = {}
        for node_id, key, name in persons:
            email = key.strip().lower() if isinstance(key, str) and "@" in key else None
            label = name.strip() if isinstance(name, str) and name.strip() else None
            self._node[node_id] = (email, label)
            if email:
                self._by_email.setdefault(email, node_id)
            if label:
                self._by_name.setdefault(label.casefold(), set()).add(node_id)
        for alias, node_id in aliases:
            if node_id in self._node and _text(alias):
                self._by_name.setdefault(alias.strip().casefold(), set()).add(node_id)
        self._seat_email: dict[str, str | None] = {}
        self._seat_by_email: dict[str, str] = {}
        for seat_id, email in seats:
            e = email.strip().lower() if isinstance(email, str) and email.strip() else None
            self._seat_email[seat_id] = e
            if e:
                self._seat_by_email.setdefault(e, seat_id)

    @property
    def seat_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._seat_email))

    def for_node(self, node_id: str | None) -> Person | None:
        if not node_id or node_id not in self._node:
            return None
        email, name = self._node[node_id]
        return Person(node_id, email, name, self._seat_by_email.get(email) if email else None)

    def for_seat(self, seat_id: str | None) -> Person | None:
        if not seat_id or seat_id not in self._seat_email:
            return None
        email = self._seat_email[seat_id]
        node = self._by_email.get(email) if email else None
        return Person(node, email, self._node[node][1] if node else None, seat_id)

    def for_email(self, email: str) -> Person:
        e = email.strip().lower()
        node = self._by_email.get(e)
        return Person(node, e, self._node[node][1] if node else None, self._seat_by_email.get(e))

    def resolve(self, ref: Any) -> Person | None:
        """A seat id, an email or a name → a Person, or None when it does not resolve to exactly
        one (see the module note: a false link is worse than none)."""
        s = _text(ref)
        if s is None:
            return None
        if s in self._seat_email:
            return self.for_seat(s)
        if "@" in s:
            return self.for_email(s)
        name = s.casefold()
        hits = self._by_name.get(name, set())
        if len(hits) == 1:
            return self.for_node(next(iter(hits)))
        if hits or " " in name:
            return None
        seat_hits = {n for n, (email, label) in self._node.items()
                     if email in self._seat_by_email and label
                     and label.split()[0].casefold() == name}
        return self.for_node(next(iter(seat_hits))) if len(seat_hits) == 1 else None

    def windows_of(self, person: Person | None,
                   windows: Iterable[AvailabilityWindow]) -> list[AvailabilityWindow]:
        if person is None:
            return []
        return [w for w in windows
                if (person.node_id and w.person_node_id == person.node_id)
                or (person.email and (w.person_key or "").strip().lower() == person.email)]


def load_directory(conn, org_id: str) -> PeopleDirectory:
    persons = conn.execute(text(
        "select node_id, canonical_key, display_name from graph_nodes where org_id = :o "
        "and node_type = 'person' and valid_to is null"), {"o": org_id}).all()
    aliases = conn.execute(text(
        "select alias_key, node_id from graph_aliases where org_id = :o "
        "and alias_type = 'person_name'"), {"o": org_id}).all()
    seats = conn.execute(text(
        "select seat_id, email from org_seats where org_id = :o and active"), {"o": org_id}).all()
    return PeopleDirectory([tuple(r) for r in persons], [tuple(r) for r in aliases],
                           [tuple(r) for r in seats])


def commitment_links(conn, org_id: str, directory: PeopleDirectory | None = None
                     ) -> list[CommitmentLink]:
    """Every commitment node with its org-visible facts, owner and beneficiary. Two statements."""
    directory = directory or load_directory(conn, org_id)
    rows = conn.execute(text(
        "select n.node_id, n.display_name, f.field, f.value from graph_nodes n "
        "join graph_facts f on f.org_id = n.org_id and f.subject_node_id = n.node_id "
        "and f.valid_to is null and f.status = 'active' and " + _ORG_VISIBLE + " "
        "where n.org_id = :o and n.node_type = 'commitment' and n.valid_to is null "
        "and left(f.field, 11) = 'commitment.'"), {"o": org_id}).all()
    facts: dict[str, dict[str, Any]] = {}
    names: dict[str, str | None] = {}
    for r in rows:
        facts.setdefault(r.node_id, {})[r.field] = r.value
        names[r.node_id] = r.display_name
    if not facts:
        return []
    owners = {r.to_node_id: r.from_node_id for r in conn.execute(text(
        "select from_node_id, to_node_id from graph_edges where org_id = :o "
        "and edge_type = 'owns' and valid_to is null and to_node_id = any(:ids) "
        "order by edge_version_id"), {"o": org_id, "ids": sorted(facts)})}
    out: list[CommitmentLink] = []
    for node_id in sorted(facts):
        f = facts[node_id]
        owner = directory.resolve(f.get("commitment.owner")) or directory.for_node(
            owners.get(node_id))
        owed = _text(f.get("commitment.owed_to"))
        out.append(CommitmentLink(
            node_id=node_id,
            text=_text(f.get("commitment.text")) or _text(names.get(node_id)) or "commitment",
            due=_as_date(f.get("commitment.due_at")),
            status=(_text(f.get("commitment.status")) or "open").lower(),
            owner=owner, beneficiary=directory.resolve(owed), owed_to=owed, facts=dict(f)))
    return out


def same_beneficiary(a: CommitmentLink, b: CommitmentLink) -> bool:
    if a.beneficiary and b.beneficiary and a.beneficiary.node_id \
            and a.beneficiary.node_id == b.beneficiary.node_id:
        return True
    return bool(a.owed_to and b.owed_to and a.owed_to.casefold() == b.owed_to.casefold())


# ── responsibilities ─────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class Answering:
    seat_id: str
    scope_kind: str
    scope_key: str
    accountability: str
    source: str


def scope_pairs_for(link: CommitmentLink) -> tuple[tuple[str, str], ...]:
    """Every `(scope_kind, scope_key)` a responsibility could name this commitment by: its raw fact
    paths, the counterparty words for whom it is owed to, and its owner (`seat` / `person`) — the
    last is how "Shalini covers Anisha" is declared."""
    pairs: set[tuple[str, str]] = set()
    for field, value in link.facts.items():
        s = _text(value)
        if s and len(s) <= _SCOPE_VALUE_MAX:
            pairs.add((field.lower(), s.lower()))
    owed = _text(link.owed_to)
    if owed and len(owed) <= _SCOPE_VALUE_MAX:
        pairs.update((word, owed.lower()) for word in COUNTERPARTY_WORDS)
    o = link.owner
    if o is not None:
        if o.seat_id:
            pairs.add(("seat", o.seat_id.lower()))
        if o.email:
            pairs.update({("person", o.email), ("seat", o.email)})
        if o.name:
            pairs.add(("person", o.name.lower()))
    return tuple(sorted(pairs))


def answering_for(conn, org_id: str, pairs: Iterable[tuple[str, str]], at: datetime
                  ) -> tuple[Answering, ...]:
    """Responsibilities in force at `at` over any of `pairs`, active seats only. One statement;
    `()` when nothing is declared — which is every tenant on day one."""
    wanted = sorted({(str(k).strip().lower(), str(v).strip().lower()) for k, v in pairs
                     if str(k).strip() and str(v).strip()})
    if not wanted:
        return ()
    clauses, params = [], {"o": org_id, "at": at}
    for i, (kind, key) in enumerate(wanted):
        clauses.append(f"(lower(r.scope_kind) = :k{i} and lower(r.scope_key) = :v{i})")
        params[f"k{i}"], params[f"v{i}"] = kind, key
    rows = conn.execute(text(
        "select r.seat_id, r.scope_kind, r.scope_key, r.accountability, r.source "
        "from seat_responsibilities r join org_seats s on s.org_id = r.org_id "
        "and s.seat_id = r.seat_id and s.active where r.org_id = :o and (" +
        " or ".join(clauses) + ") and r.valid_from <= :at "
        "and (r.valid_until is null or r.valid_until > :at) "
        "order by r.seat_id, r.scope_kind, r.scope_key, r.valid_from"), params).all()
    return tuple(Answering(r.seat_id, r.scope_kind, r.scope_key, r.accountability, r.source)
                 for r in rows)


# ── availability ─────────────────────────────────────────────────────────────────────────────
def org_visible_windows(conn, org_id: str, start: date, end: date, *,
                        absent_only: bool = True) -> list[AvailabilityWindow]:
    """`availability.org_availability` minus any window held only as a private overlay. Absence
    windows are work facts (org-visible by the P2 rule), so this normally drops nothing."""
    windows = org_availability(conn, org_id=org_id, start=start, end=end)
    private = {r.fact_version_id for r in conn.execute(text(
        "select fact_version_id from graph_facts where org_id = :o "
        "and field = 'person.availability' and valid_to is null "
        "and visibility_scope = 'private'"), {"o": org_id})}
    return [w for w in windows if w.fact_version_id not in private
            and (w.absent or not absent_only)]


__all__ = ["Answering", "COUNTERPARTY_WORDS", "CommitmentLink", "DONE_STATUSES",
           "DROPPED_STATUSES", "PeopleDirectory", "Person", "answering_for", "commitment_links",
           "load_directory", "org_visible_windows", "same_beneficiary", "scope_pairs_for"]
