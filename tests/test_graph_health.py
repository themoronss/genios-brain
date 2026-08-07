"""L2 · Graph Maintenance — lifecycle, integrity, and whether the graph can be trusted.

Two failures here are far worse than a wrong number:

  * LIFECYCLE THAT GATES. If dormancy narrowed what gets evaluated, a quiet entity would
    produce no signals, so it would stay quiet, so it would stay dormant. The customer
    who went silent — exactly the one worth noticing — is the one the system would go
    blind to, permanently, with nothing in the logs.
  * A HEALTH PAGE THAT LIES ABOUT EMPTY. A brand-new tenant with no data has not failed
    anything. Scoring it 0% is the fastest way to make the whole page ignored.

Most of these tests are about those two.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genios_engine.context.health import (ARCHIVE_AFTER_DAYS, DORMANT_AFTER_DAYS,
                                          LIFECYCLE_ACTIVE, LIFECYCLE_ARCHIVED,
                                          LIFECYCLE_DORMANT, IntegrityIssue,
                                          _INTEGRITY_CHECKS, _ratio_score,
                                          node_lifecycle, score_health)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1] / "genios_engine"


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def _issues(**counts) -> list[IntegrityIssue]:
    return [IntegrityIssue(kind=k, count=v, detail="") for k, v in counts.items()]


# ── lifecycle ────────────────────────────────────────────────────────────────────

def test_a_recently_active_entity_is_active() -> None:
    assert node_lifecycle(last_evidence_at=_ago(3), now=NOW) == LIFECYCLE_ACTIVE


def test_a_long_quiet_entity_goes_dormant() -> None:
    assert node_lifecycle(last_evidence_at=_ago(DORMANT_AFTER_DAYS + 10),
                          now=NOW) == LIFECYCLE_DORMANT


def test_a_very_old_entity_is_archived() -> None:
    assert node_lifecycle(last_evidence_at=_ago(ARCHIVE_AFTER_DAYS + 10),
                          now=NOW) == LIFECYCLE_ARCHIVED


def test_an_entity_with_no_dated_evidence_stays_active() -> None:
    """Unknown is not old. Treating absence as age would retire every entity the moment
    a source stopped sending timestamps — absence read as negative evidence, which this
    codebase refuses everywhere else."""
    assert node_lifecycle(last_evidence_at=None, now=NOW) == LIFECYCLE_ACTIVE


def test_a_relationship_outlives_a_conversation() -> None:
    """A situation goes quiet after 45 days; a RELATIONSHIP takes far longer to end.
    Using one threshold for both would archive customers who are merely between deals."""
    from genios_engine.context.situations import DORMANT_AFTER_DAYS as SITUATION_WINDOW
    assert DORMANT_AFTER_DAYS > SITUATION_WINDOW


def test_lifecycle_is_pure_and_repeatable() -> None:
    args = dict(last_evidence_at=_ago(100), now=NOW)
    assert node_lifecycle(**args) == node_lifecycle(**args)


# ── the constitutional rule ──────────────────────────────────────────────────────

def test_lifecycle_never_gates_evaluation() -> None:
    """The starvation loop, one level up from attention. A dormant entity must still be
    evaluated every sweep — otherwise a quiet customer can never become loud again."""
    offenders = [str(py.relative_to(ROOT)) for py in (ROOT / "reason").rglob("*.py")
                 if "context_node_lifecycle" in py.read_text()]
    assert not offenders, f"reason/ must not read lifecycle: {offenders}"


def test_context_is_the_sole_writer_of_lifecycle() -> None:
    offenders = []
    for package in ("deliver", "feedback", "capture", "packs", "executive"):
        for py in (ROOT / package).rglob("*.py"):
            source = py.read_text()
            if any(w in source for w in ("insert into context_node_lifecycle",
                                         "update context_node_lifecycle",
                                         "delete from context_node_lifecycle")):
                offenders.append(str(py.relative_to(ROOT)))
    assert not offenders, f"only context/ writes lifecycle: {offenders}"


def test_nothing_in_maintenance_deletes_graph_data() -> None:
    """Pruning here is ARCHIVAL. Volume is controlled at Layer 1, where the gate drops
    noise before it becomes a node — so anything in the graph has already passed that
    bar, and deleting it later destroys evidence a human may need to explain a decision
    the system already made."""
    source = (ROOT / "context" / "health.py").read_text().lower()
    for forbidden in ("delete from graph_nodes", "delete from graph_facts",
                      "delete from graph_edges", "delete from graph_observations",
                      "drop table"):
        assert forbidden not in source


def test_integrity_checks_never_repair() -> None:
    """An auto-fix that runs unattended turns a small inconsistency into a large, silent
    data loss: it deletes the rows it decided were wrong, and nobody finds out until a
    decision cannot be explained."""
    for _kind, _detail, sql in _INTEGRITY_CHECKS:
        lowered = sql.lower()
        assert lowered.strip().startswith("select"), sql
        for mutation in ("update ", "delete ", "insert "):
            assert mutation not in lowered, sql


# ── integrity coverage ───────────────────────────────────────────────────────────

def test_the_checks_cover_the_ways_this_graph_actually_breaks() -> None:
    """Each of these has a specific cause in this codebase, not a textbook one."""
    kinds = {kind for kind, _, _ in _INTEGRITY_CHECKS}
    assert {
        "broken_edge",              # a merge that missed a table
        "self_edge",                # a merge that repointed both ends of one edge
        "duplicate_active_fact",    # the invariant apply_merge repairs, checked globally
        "fact_without_evidence",    # nothing is true just because it is written down
        "orphan_node",              # the dead dots the P1 anchor rule exists to prevent
        "alias_to_closed_node",     # Step 1 leaving a key pointing at nothing
        "correlation_on_closed_node",   # Step 2 anchored on an entity that is gone
    } <= kinds


def test_every_check_explains_why_it_matters() -> None:
    """A monitor that reports 'orphan_fact: 412' and nothing else gets ignored."""
    for kind, detail, _ in _INTEGRITY_CHECKS:
        assert len(detail) > 40, kind


# ── health scoring ───────────────────────────────────────────────────────────────

def test_an_empty_graph_is_not_unhealthy() -> None:
    """A new tenant has not failed anything. Reporting a fresh account as broken is the
    fastest way to make a health page nobody reads."""
    health = score_health(metrics={}, issues=[])
    assert health.overall == 100
    assert not any(health.measured.values())


def test_nothing_to_measure_is_marked_as_such() -> None:
    score, measured = _ratio_score(bad=0, total=0)
    assert (score, measured) == (100, False)


def test_overall_is_the_minimum_not_the_average() -> None:
    """A graph with flawless evidence and 40% broken edges is not '70% healthy' — it is
    a graph you cannot traverse. Same rule as situation confidence, for the same reason."""
    health = score_health(
        metrics={"edges_total": 100, "facts_total": 100, "nodes_total": 100,
                 "events_emitted": 100},
        issues=_issues(broken_edge=40))
    assert health.dimensions["evidence"] == 100
    assert health.dimensions["integrity"] == 60
    assert health.overall == 60


def test_an_unmeasured_dimension_cannot_drag_the_score_down() -> None:
    """A tenant with facts but no edges yet must not be marked unhealthy for having no
    broken ones."""
    health = score_health(metrics={"facts_total": 50, "nodes_total": 10},
                          issues=_issues(fact_without_evidence=0))
    assert health.measured["integrity"] is False
    assert health.overall == 100


def test_untraceable_facts_lower_the_evidence_score() -> None:
    health = score_health(metrics={"facts_total": 100, "nodes_total": 10},
                          issues=_issues(fact_without_evidence=25))
    assert health.dimensions["evidence"] == 75


def test_events_reaching_no_situation_are_the_layer2_alarm() -> None:
    """The single most useful signal that Layer 2 has quietly stopped working: material
    arriving and landing in no situation at all."""
    health = score_health(
        metrics={"events_with_facts": 100, "events_with_facts_uncorrelated": 90,
                 "nodes_total": 10},
        issues=[])
    assert health.dimensions["correlation_reach"] == 10
    assert health.overall == 10


def test_newsletters_do_not_trip_the_correlation_alarm() -> None:
    """A newsletter correctly reaches no situation. Measuring reach against EVERY event
    would make a healthy tenant with normal marketing volume look broken — and an alarm
    that fires on healthy systems is an alarm people switch off.

    Here 1000 events arrived, only 100 produced any knowledge, and all 100 correlated.
    That is a perfect score, not 10%.
    """
    health = score_health(
        metrics={"events_emitted": 1000, "events_with_facts": 100,
                 "events_with_facts_uncorrelated": 0, "nodes_total": 10},
        issues=[])
    assert health.dimensions["correlation_reach"] == 100


def test_the_reach_metric_measures_knowledge_bearing_events() -> None:
    from genios_engine.context.health import _METRIC_QUERIES
    queries = dict(_METRIC_QUERIES)
    assert "events_with_facts_uncorrelated" in queries
    # The denominator must be restricted the same way, or the ratio is meaningless.
    assert "graph_facts" in queries["events_with_facts"]


def test_lifecycle_writes_are_batched() -> None:
    """A row-at-a-time loop is one network round trip per entity. On a 50k-entity tenant
    that is 50k round trips inside one transaction — how a maintenance pass becomes an
    outage."""
    from genios_engine.context.health import _WRITE_BATCH, refresh_node_lifecycle
    source = inspect.getsource(refresh_node_lifecycle)
    assert "_WRITE_BATCH" in source
    assert _WRITE_BATCH > 1
    # The rule itself stays in Python — one tested definition, not a second copy in SQL
    # that can drift away from it.
    assert "node_lifecycle(last_evidence_at=" in source


def test_health_history_has_a_retention_clock() -> None:
    """Append-only with no clock becomes the largest table in the database."""
    from genios_engine.context.health import purge_old_health
    assert "delete from graph_health" in inspect.getsource(purge_old_health)


def test_unresolved_duplicates_show_up_as_an_identity_problem() -> None:
    """It ties back to Step 1: proposals nobody acts on are a measurable defect, not a
    quiet queue."""
    health = score_health(metrics={"nodes_total": 100, "open_merge_proposals": 30},
                          issues=[])
    assert health.dimensions["identity"] == 70


def test_only_real_problems_are_reported_as_issues() -> None:
    """check_integrity returns clean checks too, so a caller can see what WAS verified —
    but the health report must not list them as findings."""
    health = score_health(metrics={"edges_total": 10},
                          issues=_issues(broken_edge=0, self_edge=2))
    assert [i["kind"] for i in health.issues] == ["self_edge"]


def test_scores_stay_inside_their_bounds() -> None:
    health = score_health(metrics={"facts_total": 10}, issues=_issues(orphan_fact=999))
    assert health.dimensions["coherence"] == 0
    assert health.overall >= 0


def test_health_scoring_is_pure_and_repeatable() -> None:
    args = dict(metrics={"nodes_total": 10, "edges_total": 5}, issues=_issues(self_edge=1))
    assert score_health(**args) == score_health(**args)


# ── the epoch sentinel ───────────────────────────────────────────────────────────

def test_the_no_evidence_sentinel_is_not_mistaken_for_a_real_date() -> None:
    """`greatest(...)` needs a floor, and 'epoch' is it. Passing that through as a real
    timestamp would archive every entity with no dated evidence — the exact rule the
    lifecycle function exists to protect."""
    from genios_engine.context.health import refresh_node_lifecycle
    source = inspect.getsource(refresh_node_lifecycle)
    assert "year <= 1970" in source
    assert "last = None" in source
