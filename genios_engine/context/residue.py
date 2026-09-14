"""L2 · THE RESIDUE DETECTOR — what this layer looked at and could not explain.

Every pass in `process_pending` reports what it PRODUCED. Nothing reported what it left behind, so
a sweep that explained nothing and a sweep with nothing to explain were indistinguishable in the
report — and "what is happening in my mailbox that this thing never mentioned?" had no answer in
the engine. The only way to find out was to read the graph by hand and compare it against the
cards, which is how every defect on this branch was actually found.

DETERMINISTIC AND CHEAP, on purpose. Four bulk statements over tables the sweep has already
written, no model, no clock of its own, no per-node round trip. It adds no judgement to the layer:
it does not decide that a residue item MATTERS, only that nothing spoke about it. Deciding which
ones are worth a card is a different question with a different budget, and this is the input to it.

FOUR KINDS, EACH A JOIN THAT CAN BE CHECKED. `node_evidence_unread` is evidence held and never
spoken about; `ball_in_court_unreported` is the founder's own case — they replied, we went quiet,
nothing said so; `open_loop_unreported` is an ask still open and attached to nothing; and
`signal_unreached` counts the Layer 1 verdicts no Layer 2 reading consumes.

CURRENT STATE, NOT A LOG. A row means "still unexplained as of the last sweep", and when a reading
finally covers the subject the row is deleted. `first_seen_at` answers "for how long", which is the
number that turns the table into a work queue. It needs no retention because it does not append —
it cannot exceed the size of the graph and it shrinks as coverage improves.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text

#: The two statuses both Layer 3 doors admit — `reason/runner` and `reason/domain_shadow` filter
#: on exactly these. A DORMANT situation does not explain its subject, because a dormant situation
#: cannot reach a card; counting it as coverage would hide the staleness this table exists to find.
_LIVE = "('active', 'partial')"

#: A subject is covered when a live situation ANCHORS on it, or when a live situation's anchor
#: `concerns` it. The second half is not optional: every state reading mints its own anchor node
#: and links the person with one `concerns` hop, so checking `anchor_node_id` alone would report
#: every correctly-served counterparty in the tenant as unexplained.
_COVERED = (
    "(exists (select 1 from context_situations s "
    f"         where s.org_id = :o and s.anchor_node_id = {{ref}} and s.status in {_LIVE}) "
    " or exists (select 1 from graph_edges ce "
    "            join context_situations cs on cs.org_id = ce.org_id "
    "                 and cs.anchor_node_id = ce.from_node_id "
    f"                 and cs.status in {_LIVE} "
    "            where ce.org_id = :o and ce.edge_type = 'concerns' "
    f"              and ce.to_node_id = {{ref}} and ce.valid_to is null))")

RESIDUE_NODE_EVIDENCE = "node_evidence_unread"
RESIDUE_BALL_IN_COURT = "ball_in_court_unreported"
RESIDUE_OPEN_LOOP = "open_loop_unreported"
RESIDUE_SIGNAL = "signal_unreached"

#: One sweep's ceiling per kind. The first run on a tenant whose coverage is poor meets the whole
#: graph at once, and this runs inside the transaction budget of the path that ingests mail. The
#: count is reported so a truncated pass cannot look like a clean one — the same discipline
#: `sampler.budget_exhausted` keeps, and the same failure the `budgets` ledger in `runner.py` was
#: added to end.
DEFAULT_LIMIT = 5_000


@dataclass(frozen=True, slots=True)
class ResidueReport:
    """What one sweep found, per kind, and whether it saw all of it."""

    counts: dict[str, int]
    truncated: frozenset[str]

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def as_record(self) -> dict:
        return {"counts": dict(self.counts), "total": self.total,
                "truncated": sorted(self.truncated)}


def _node_evidence_sql(limit: int) -> str:
    """Nodes carrying active observations that nothing live speaks about."""
    return (
        "select o.subject_node_id as ref, count(*) as n "
        "from graph_observations o "
        "where o.org_id = :o and o.status = 'active' and o.subject_node_id is not null "
        f"  and not {_COVERED.format(ref='o.subject_node_id')} "
        "group by o.subject_node_id "
        f"order by count(*) desc limit {int(limit)}")


def _ball_in_court_sql(limit: int) -> str:
    """The founder's own case: the turn is ours and nothing said so.

    Reads the FACT rather than re-deriving direction, because `waiting.py` and Layer 1's thread
    reconstruction already agree on one answer and a second derivation here would be a second
    opinion about whose turn it is.
    """
    return (
        "select f.subject_node_id as ref, 1 as n "
        "from graph_facts f "
        "where f.org_id = :o and f.field = 'thread.ball_in_court' "
        "  and f.status = 'active' and f.valid_to is null "
        "  and lower(cast(f.value as text)) like '%us%' "
        f"  and not {_COVERED.format(ref='f.subject_node_id')} "
        f"limit {int(limit)}")


def _open_loop_sql(limit: int) -> str:
    """An ask recorded, still open, and attached to nothing anybody can be shown."""
    return (
        "select l.loop_id as ref, l.subject_node_id as subject, l.kind as kind "
        "from open_loops l "
        "where l.org_id = :o and l.status = 'open' "
        f"  and not {_COVERED.format(ref='l.subject_node_id')} "
        f"limit {int(limit)}")


def _signal_sql(limit: int) -> str:
    """Layer 1 verdicts that reached no live situation, grouped by TYPE.

    Grouped because the useful sentence is "deadline: 131 signals, none consumed" rather than 131
    rows saying the same thing, and because a missing PRODUCER is a fact about a type.

    TWO PATHS, and the second is what keeps this honest. `situation_bso._L1_SELECT` joins a signal
    to a situation through `context_correlation_members`, which ONLY `correlation.py` writes — every
    state reading, the period sweep, meeting touch and the document register mint a synthetic
    correlation with no membership rows. Checking that join alone would count a signal whose event
    produced a perfectly good state reading as unreached, and the detector would slander the
    readings that work.
    """
    return (
        "select qs.signal_type as ref, count(*) as n "
        "from qualified_signals qs "
        "where qs.org_id = :o "
        # path 1 — the correlation the composer itself uses
        "  and not exists (select 1 from context_correlation_members m "
        "                  join context_situations s on s.org_id = m.org_id "
        "                       and s.correlation_id = m.correlation_id "
        f"                       and s.status in {_LIVE} "
        "                  where m.org_id = :o and m.event_id = qs.event_id) "
        # path 2 — whatever subject the event actually wrote to
        "  and not exists (select 1 from graph_source_refs r "
        "                  join graph_observations go2 on go2.org_id = r.org_id "
        "                       and go2.observation_id = r.observation_id "
        "                  join context_situations s2 on s2.org_id = r.org_id "
        "                       and s2.anchor_node_id = go2.subject_node_id "
        f"                       and s2.status in {_LIVE} "
        "                  where r.org_id = :o and r.event_id = qs.event_id) "
        "group by qs.signal_type "
        f"order by count(*) desc limit {int(limit)}")


def detect_residue(store, org_id: str, *, eval_time: datetime | None = None,
                   limit: int = DEFAULT_LIMIT) -> ResidueReport:
    """Record what this sweep could not explain. Returns the per-kind counts.

    `eval_time` is a parameter all the way down; the clock is read at the call site, so two runs at
    one instant produce identical rows and the second is an overwrite rather than a second opinion.

    RESOLVED RESIDUE IS DELETED, not marked. Every row this pass finds has `last_seen_at` set to
    the sweep instant, and anything of that kind left behind is by definition no longer residue —
    a reading now covers it. Deleting by `last_seen_at < :now` is the whole reconciliation: no
    second state, and nothing to keep consistent with the first.
    """
    now = eval_time or datetime.now(timezone.utc)
    counts: dict[str, int] = {}
    truncated: set[str] = set()

    def _record(conn, kind: str, rows: list[dict]) -> None:
        for row in rows:
            conn.execute(text(
                "insert into context_residue (org_id, residue_kind, subject_ref, detail, "
                "  first_seen_at, last_seen_at) values (:o, :k, :ref, :d, :now, :now) "
                "on conflict (org_id, residue_kind, subject_ref) do update set "
                # `first_seen_at` is NEVER updated: how long a thing has gone unexplained is the
                # number that makes this a work queue rather than a gauge.
                "  detail = excluded.detail, last_seen_at = excluded.last_seen_at"),
                {"o": org_id, "k": kind, "ref": row["ref"], "now": now,
                 "d": row["detail"]})
        counts[kind] = len(rows)
        if len(rows) >= limit:
            truncated.add(kind)

    with store.engine.begin() as conn:
        _record(conn, RESIDUE_NODE_EVIDENCE, [
            {"ref": str(r.ref), "detail": f'{{"observations": {int(r.n)}}}'}
            for r in conn.execute(text(_node_evidence_sql(limit)), {"o": org_id})])

        _record(conn, RESIDUE_BALL_IN_COURT, [
            {"ref": str(r.ref), "detail": "{}"}
            for r in conn.execute(text(_ball_in_court_sql(limit)), {"o": org_id})])

        _record(conn, RESIDUE_OPEN_LOOP, [
            {"ref": str(r.ref),
             "detail": f'{{"subject": "{r.subject}", "kind": "{r.kind}"}}'}
            for r in conn.execute(text(_open_loop_sql(limit)), {"o": org_id})])

        _record(conn, RESIDUE_SIGNAL, [
            {"ref": str(r.ref), "detail": f'{{"signals": {int(r.n)}}}'}
            for r in conn.execute(text(_signal_sql(limit)), {"o": org_id})])

        # Anything this pass did not re-record is explained now. One statement per sweep.
        conn.execute(text(
            "delete from context_residue where org_id = :o and last_seen_at < :now"),
            {"o": org_id, "now": now})

    return ResidueReport(counts=counts, truncated=frozenset(truncated))


def read_residue(conn, org_id: str, *, kind: str | None = None,
                 limit: int = 100) -> list[dict]:
    """The work queue: what has gone unexplained, longest first."""
    sql = ("select residue_kind, subject_ref, detail, first_seen_at, last_seen_at "
           "from context_residue where org_id = :o "
           + ("" if kind is None else "and residue_kind = :k ")
           + "order by first_seen_at asc limit :lim")
    params: dict = {"o": org_id, "lim": limit}
    if kind is not None:
        params["k"] = kind
    return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


__all__ = ["DEFAULT_LIMIT", "RESIDUE_BALL_IN_COURT", "RESIDUE_NODE_EVIDENCE",
           "RESIDUE_OPEN_LOOP", "RESIDUE_SIGNAL", "ResidueReport", "detect_residue",
           "read_residue"]
