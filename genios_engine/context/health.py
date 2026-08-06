"""L2 · Graph Maintenance — is our picture of the enterprise still trustworthy?

Steps 1–3 build the graph. Nothing until now KEPT it. A graph that is only ever written
to accumulates broken edges, orphan nodes, facts nobody can trace, and duplicates nobody
resolved — and none of that announces itself. It shows up as reasoning that is subtly
wrong for reasons no one can find.

This module answers two questions and refuses to answer a third:

    "What state is each entity in?"        → lifecycle (active / dormant / archived)
    "Is the graph itself healthy?"          → integrity checks and health metrics
    "What should we do about it?"           → NOT THIS LAYER'S JOB

LIFECYCLE LABELS, IT NEVER GATES
This is the same constitutional rule `context_attention` already carries, and it matters
more here because lifecycle is a STATE rather than a score — it looks authoritative.

    A dormant entity is still evaluated. Every sweep. Always.

The trap is a feedback loop that cannot recover: if dormancy narrowed evaluation, a quiet
entity would stop being evaluated, so it would produce no signals, so it would stay quiet,
so it would stay dormant. The customer who went silent — exactly the one worth noticing —
is the one the system would go blind to. `tests/test_graph_health.py` enforces that no
reasoning module reads lifecycle.

NOTHING IS EVER DELETED
The architecture notes ask for a Pruning Engine so the graph "never grows forever". This
implements pruning as ARCHIVAL, not deletion, and that is a deliberate disagreement.

Volume is already controlled where it should be — at Layer 1, where the gate drops noise
before it ever becomes a node. By the time something is in the graph it has passed that
bar, which means deleting it later destroys evidence a human might need to explain a
decision the system already made. Archiving takes it out of the working set and keeps it
answerable. An "old" customer is a dormant relationship, not a mistake to erase.

UNKNOWN IS NOT BAD NEWS
An entity with no dated evidence is not stale — we simply cannot tell. It stays active.
Treating absence as age would archive everything the moment a connector stopped sending
timestamps, which is the same failure this codebase refuses everywhere else: absence of
data must never read as negative evidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

LIFECYCLE_ACTIVE = "active"
LIFECYCLE_DORMANT = "dormant"
LIFECYCLE_ARCHIVED = "archived"

_WRITE_BATCH = 500          # rows per executemany; keeps one pass off the network

DORMANT_AFTER_DAYS = 90     # deliberately longer than a situation's 45: a conversation
                            # ending is normal, a RELATIONSHIP ending takes much longer
ARCHIVE_AFTER_DAYS = 365


def node_lifecycle(*, last_evidence_at: datetime | None, now: datetime) -> str:
    """What state an entity is in, from when we last heard anything about it.

    No evidence date → ACTIVE, not archived. We cannot tell how old it is, and guessing
    "old" would quietly retire every entity the moment a source stopped sending
    timestamps.
    """
    if last_evidence_at is None:
        return LIFECYCLE_ACTIVE
    age = now - last_evidence_at
    if age > timedelta(days=ARCHIVE_AFTER_DAYS):
        return LIFECYCLE_ARCHIVED
    if age > timedelta(days=DORMANT_AFTER_DAYS):
        return LIFECYCLE_DORMANT
    return LIFECYCLE_ACTIVE


# ── integrity: what is structurally broken ───────────────────────────────────────
#
# Every check is READ-ONLY. Automatic repair of a graph is how you turn a small
# inconsistency into a large, silent data loss — the "fix" runs at 3am, deletes the rows
# it decided were wrong, and nobody finds out until a decision cannot be explained.
# Detect, report, let a human choose.

@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    kind: str
    count: int
    detail: str

    @property
    def is_clean(self) -> bool:
        return self.count == 0


_INTEGRITY_CHECKS: tuple[tuple[str, str, str], ...] = (
    (
        "broken_edge",
        "an edge whose other end does not exist or has been closed — usually a merge "
        "that missed a table, and it makes traversal silently incomplete",
        "select count(*) from graph_edges e where e.org_id = :o and e.valid_to is null "
        "and (not exists (select 1 from graph_nodes n where n.org_id = e.org_id "
        "                 and n.node_id = e.from_node_id and n.valid_to is null) "
        "  or not exists (select 1 from graph_nodes n where n.org_id = e.org_id "
        "                 and n.node_id = e.to_node_id and n.valid_to is null))",
    ),
    (
        "self_edge",
        "an entity related to itself ('Acme corresponded_with Acme') — the signature of "
        "a merge that repointed both ends of one edge",
        "select count(*) from graph_edges where org_id = :o and valid_to is null "
        "and from_node_id = to_node_id",
    ),
    (
        "orphan_fact",
        "a fact about an entity that no longer exists — it can never be read, but still "
        "counts toward everything measured about the graph",
        "select count(*) from graph_facts f where f.org_id = :o and f.valid_to is null "
        "and f.status = 'active' and not exists ("
        "  select 1 from graph_nodes n where n.org_id = f.org_id "
        "  and n.node_id = f.subject_node_id and n.valid_to is null)",
    ),
    (
        "duplicate_active_fact",
        "two active values for one (entity, field) — readers take the first row, so "
        "which value is 'true' becomes whichever the planner returns",
        "select coalesce(sum(extra), 0) from ("
        "  select count(*) - 1 as extra from graph_facts "
        "  where org_id = :o and valid_to is null and status = 'active' "
        "  group by subject_node_id, field having count(*) > 1) dupes",
    ),
    (
        "fact_without_evidence",
        "a fact with no source reference — nothing in this system is allowed to be true "
        "just because it is written down",
        "select count(*) from graph_facts f where f.org_id = :o and f.valid_to is null "
        "and f.status = 'active' and not exists ("
        "  select 1 from graph_source_refs r where r.org_id = f.org_id "
        "  and r.fact_version_id = f.fact_version_id)",
    ),
    (
        "orphan_node",
        "an entity with no facts, no edges and no observations — a dead dot that adds "
        "noise to every count and every traversal",
        "select count(*) from graph_nodes n where n.org_id = :o and n.valid_to is null "
        "and not exists (select 1 from graph_facts f where f.org_id = n.org_id "
        "                and f.subject_node_id = n.node_id) "
        "and not exists (select 1 from graph_edges e where e.org_id = n.org_id "
        "                and (e.from_node_id = n.node_id or e.to_node_id = n.node_id)) "
        "and not exists (select 1 from graph_observations g where g.org_id = n.org_id "
        "                and g.subject_node_id = n.node_id)",
    ),
    (
        "alias_to_closed_node",
        "a lookup key pointing at a closed entity — mentions resolve to something that "
        "is no longer there",
        "select count(*) from graph_aliases a where a.org_id = :o and not exists ("
        "  select 1 from graph_nodes n where n.org_id = a.org_id "
        "  and n.node_id = a.node_id and n.valid_to is null)",
    ),
    (
        "correlation_on_closed_node",
        "a situation anchored on a closed entity — it would describe something that no "
        "longer exists",
        "select count(*) from context_correlations c where c.org_id = :o and not exists ("
        "  select 1 from graph_nodes n where n.org_id = c.org_id "
        "  and n.node_id = c.anchor_node_id and n.valid_to is null)",
    ),
)


def check_integrity(store, org_id: str) -> list[IntegrityIssue]:
    """Every structural check, read-only. Returns all of them, clean ones included, so a
    caller can see what WAS verified rather than only what failed."""
    issues: list[IntegrityIssue] = []
    with store.engine.connect() as conn:
        for kind, detail, sql in _INTEGRITY_CHECKS:
            count = conn.execute(text(sql), {"o": org_id}).scalar() or 0
            issues.append(IntegrityIssue(kind=kind, count=int(count), detail=detail))
    return issues


# ── health: is the graph trustworthy enough to reason over ───────────────────────

def _ratio_score(*, bad: int, total: int) -> tuple[int, bool]:
    """A 0–100 score from a defect ratio, and whether there was anything to measure.

    An empty graph returns (100, False) — "nothing measured", never "0% healthy". A new
    tenant with no data has not failed anything, and reporting a fresh account as broken
    is the fastest way to make a health page ignored.
    """
    if total <= 0:
        return 100, False
    return max(0, min(100, round(100 * (1 - bad / total)))), True


@dataclass(frozen=True, slots=True)
class Health:
    overall: int
    dimensions: dict[str, int]
    measured: dict[str, bool]
    metrics: dict[str, int]
    issues: list[dict]


def score_health(*, metrics: dict[str, int], issues: list[IntegrityIssue]) -> Health:
    """The graph's health as a vector, with `overall` as the MINIMUM.

    Minimum for the same reason a situation's confidence uses it: these are failure
    modes, not features. A graph with flawless evidence and 40% broken edges is not
    "70% healthy" — it is a graph you cannot traverse. Averaging would let the parts that
    work conceal the part that does not.
    """
    by_kind = {i.kind: i.count for i in issues}
    nodes = max(0, metrics.get("nodes_total", 0))
    edges = max(0, metrics.get("edges_total", 0))
    facts = max(0, metrics.get("facts_total", 0))
    # Only events that produced facts can meaningfully reach a situation.
    events = max(0, metrics.get("events_with_facts", 0))

    dimensions: dict[str, int] = {}
    measured: dict[str, bool] = {}
    for name, bad, total in (
            ("integrity", by_kind.get("broken_edge", 0) + by_kind.get("self_edge", 0), edges),
            ("evidence", by_kind.get("fact_without_evidence", 0), facts),
            ("coherence", by_kind.get("duplicate_active_fact", 0)
                          + by_kind.get("orphan_fact", 0), facts),
            ("connectivity", by_kind.get("orphan_node", 0), nodes),
            ("identity", metrics.get("open_merge_proposals", 0), nodes),
            ("consistency", metrics.get("open_discrepancies", 0), nodes),
            # What fraction of KNOWLEDGE-BEARING events reached a situation. A low number
            # means correlation is not doing its job — the single most useful signal that
            # Layer 2 has quietly stopped working.
            ("correlation_reach", metrics.get("events_with_facts_uncorrelated", 0),
             events),
    ):
        score, was_measured = _ratio_score(bad=bad, total=total)
        dimensions[name] = score
        measured[name] = was_measured

    # Only dimensions with something behind them count toward the overall score, so a
    # tenant with no edges yet is not marked unhealthy for having no broken ones.
    live = [score for name, score in dimensions.items() if measured[name]]
    return Health(
        overall=min(live) if live else 100,
        dimensions=dimensions, measured=measured, metrics=metrics,
        issues=[{"kind": i.kind, "count": i.count, "detail": i.detail}
                for i in issues if not i.is_clean])


_METRIC_QUERIES: tuple[tuple[str, str], ...] = (
    ("nodes_total",
     "select count(*) from graph_nodes where org_id=:o and valid_to is null"),
    ("edges_total",
     "select count(*) from graph_edges where org_id=:o and valid_to is null"),
    ("facts_total",
     "select count(*) from graph_facts where org_id=:o and valid_to is null "
     "and status='active'"),
    ("events_emitted",
     "select count(*) from source_events where org_id=:o and outcome='emitted'"),
    # The denominator for correlation reach is events that produced KNOWLEDGE, not every
    # event. A newsletter correctly reaches no situation; counting it as a miss would
    # make a healthy tenant with normal marketing volume look broken, and an alarm that
    # fires on healthy systems is an alarm people switch off.
    ("events_with_facts",
     "select count(*) from source_events se where se.org_id=:o and se.outcome='emitted' "
     "and exists (select 1 from graph_facts f where f.org_id=se.org_id "
     "            and f.created_by_event_id=se.event_id)"),
    ("events_with_facts_uncorrelated",
     "select count(*) from source_events se where se.org_id=:o and se.outcome='emitted' "
     "and exists (select 1 from graph_facts f where f.org_id=se.org_id "
     "            and f.created_by_event_id=se.event_id) "
     "and not exists (select 1 from context_correlation_members m "
     "                where m.org_id=se.org_id and m.event_id=se.event_id)"),
    ("open_merge_proposals",
     "select count(*) from merge_proposals where org_id=:o and status='open'"),
    ("open_discrepancies",
     "select count(*) from discrepancies where org_id=:o and status='open'"),
    ("situations_active",
     "select count(*) from context_situations where org_id=:o and status='active'"),
    # Entities that fall through EVERY lens. Queryable via projections, but health.py is
    # where anyone actually looks — uncounted, "nobody classified this" is a fact you can
    # only find if you already suspect it.
    ("nodes_in_no_lens",
     "select count(*) from graph_nodes n where n.org_id=:o and n.valid_to is null "
     "and not exists (select 1 from context_situations s "
     "                where s.org_id=n.org_id and s.anchor_node_id=n.node_id) "
     "and not exists (select 1 from context_situations s "
     "                join context_correlation_members m on m.org_id=s.org_id "
     "                  and m.correlation_id=s.correlation_id "
     "                join graph_facts f on f.org_id=m.org_id "
     "                  and f.created_by_event_id=m.event_id "
     "                 and f.valid_to is null and f.status='active' "
     "                where s.org_id=n.org_id and f.subject_node_id=n.node_id)"),
    ("nodes_dormant",
     "select count(*) from context_node_lifecycle where org_id=:o "
     "and lifecycle <> 'active'"),
)


def compute_health(store, org_id: str, *, persist: bool = True,
                   eval_time: datetime | None = None) -> Health:
    """Measure the graph and, by default, record the measurement.

    History is the point. A single health number says little; the same number falling
    over three weeks says a connector broke, or a merge went wrong, or correlation
    stopped reaching anything.
    """
    now = eval_time or datetime.now(timezone.utc)
    issues = check_integrity(store, org_id)
    with store.engine.connect() as conn:
        metrics = {name: int(conn.execute(text(sql), {"o": org_id}).scalar() or 0)
                   for name, sql in _METRIC_QUERIES}

    health = score_health(metrics=metrics, issues=issues)
    if persist:
        with store.engine.begin() as conn:
            conn.execute(text(
                "insert into graph_health (org_id, computed_at, overall, dimensions, "
                "  measured, metrics, issues) "
                "values (:o, :t, :ov, cast(:dim as jsonb), cast(:meas as jsonb), "
                "  cast(:met as jsonb), cast(:iss as jsonb)) "
                "on conflict (org_id, computed_at) do nothing"),
                {"o": org_id, "t": now, "ov": health.overall,
                 "dim": json.dumps(health.dimensions),
                 "meas": json.dumps(health.measured),
                 "met": json.dumps(health.metrics),
                 "iss": json.dumps(health.issues)})
    return health


def refresh_node_lifecycle(store, org_id: str, *,
                           eval_time: datetime | None = None) -> int:
    """Recompute every entity's lifecycle state from its most recent evidence.

    A LABEL, not a filter. Nothing here removes, hides or excludes an entity — see the
    module docstring for why a state that narrowed evaluation could never recover.
    """
    now = eval_time or datetime.now(timezone.utc)
    with store.engine.connect() as conn:
        # Newest evidence per entity, from every place evidence can land.
        rows = conn.execute(text(
            "select n.node_id, greatest("
            "  coalesce((select max(f.occurred_at) from graph_facts f "
            "            where f.org_id = n.org_id and f.subject_node_id = n.node_id), "
            "           'epoch'::timestamptz), "
            "  coalesce((select max(g.occurred_at) from graph_observations g "
            "            where g.org_id = n.org_id and g.subject_node_id = n.node_id), "
            "           'epoch'::timestamptz), "
            "  coalesce((select max(e.last_seen_at) from graph_edges e "
            "            where e.org_id = n.org_id "
            "            and (e.from_node_id = n.node_id or e.to_node_id = n.node_id)), "
            "           'epoch'::timestamptz)) as last_evidence_at "
            "from graph_nodes n where n.org_id = :o and n.valid_to is null"),
            {"o": org_id}).all()

    params = []
    for row in rows:
        # 'epoch' is the sentinel for "found nothing", not a real date in 1970. Passing
        # it through as a timestamp would archive every entity that has no dated
        # evidence — precisely the unknown-is-not-bad-news rule.
        last = row.last_evidence_at
        if last is not None and last.year <= 1970:
            last = None
        params.append({"o": org_id, "n": row.node_id, "last": last, "t": now,
                       "lc": node_lifecycle(last_evidence_at=last, now=now)})
    if not params:
        return 0

    # The STATE is decided in Python — one tested rule, not a second copy of it in SQL
    # that can drift — but the WRITES go in batches. A row-at-a-time loop is one network
    # round trip per entity; on a tenant with 50k entities that is 50k round trips inside
    # a single transaction, which is how a maintenance pass becomes an outage.
    upsert = text(
        "insert into context_node_lifecycle (org_id, node_id, lifecycle, "
        "  last_evidence_at, computed_at) values (:o, :n, :lc, :last, :t) "
        "on conflict (org_id, node_id) do update set "
        "  lifecycle = excluded.lifecycle, "
        "  last_evidence_at = excluded.last_evidence_at, "
        "  computed_at = excluded.computed_at")
    written = 0
    for start in range(0, len(params), _WRITE_BATCH):
        batch = params[start:start + _WRITE_BATCH]
        with store.engine.begin() as conn:
            conn.execute(upsert, batch)          # executemany
        written += len(batch)
    return written


def purge_old_health(store, org_id: str, *, keep_days: int = 180) -> int:
    """Health history is append-only, and append-only with no clock becomes the largest
    table in the database. The trend is what matters, and six months of it is plenty."""
    with store.engine.begin() as conn:
        return conn.execute(text(
            "delete from graph_health where org_id = :o "
            "and computed_at < now() - make_interval(days => :days)"),
            {"o": org_id, "days": keep_days}).rowcount
