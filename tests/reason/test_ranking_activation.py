"""The `ranking_v2` switch on the LIVE sweep — and what the tenant's own audit rows then hold.

`tests/reason/test_ranking.py` proves the model against a real compiled package in memory. This
proves the last hop: that `domain_shadow` reads the tenant's activation, hands it to the adapter,
and that the six-weight utility, the situation's importance and the computed cost of doing nothing
are in `reasoning_candidates` and `reasoning_run_outputs` afterwards. A model that ranks perfectly
in memory and persists the old five components has changed nothing a human or a replay can see —
which is the exact shape of the three unreached-unit failures Layers 1, 2 and 3 each shipped.

Real Postgres, real Layer 1 ingestion, real corpus, real reasoning, `live=True`. The seeding
helpers are the ones the roster's own live test uses, imported rather than copied.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from genios_engine.context import situations
from genios_engine.contracts.reasoning import (
    RANKING_WEIGHTS_V1,
    RANKING_WEIGHTS_V2,
    RANKING_WEIGHTS_V2_VERSION,
)
from genios_engine.reason.decision_maker import (
    IMPORTANCE_ABSENT_REASON,
    IMPORTANCE_COMPONENT,
    PRIORITY_OVERRIDE_COMPONENT,
    SITUATION_IMPORTANCE_KEY,
)
from scripts.ranking_distribution import measure

from ..l1_supply import attach_l1_signals
from ..test_admin_support_packs import NOW, _run_admin, _seed_org

pytestmark = pytest.mark.pg

_CANDIDATES = (
    "select c.candidate_id, c.run_id, c.final_utility_bp, c.score_components, "
    "       c.disposition, c.rank_position, r.capability_id, r.evaluation_time "
    "from reasoning_candidates c "
    "join reasoning_runs r on r.org_id = c.org_id and r.run_id = c.run_id "
    "where c.org_id = :o and r.capability_id like 'expertise.%' "
    "  and c.disposition = 'eligible' and c.rank_position is not null")

_OUTPUTS = (
    "select o.run_id, o.outcome_kind, o.decision_core, r.capability_id, r.evaluation_time "
    "from reasoning_run_outputs o "
    "join reasoning_runs r on r.org_id = o.org_id and r.run_id = o.run_id "
    "where o.org_id = :o and r.capability_id like 'expertise.%'")

_MANIFESTS = (
    "select distinct s.manifest from reasoning_capability_snapshots s "
    "join reasoning_runs r on r.org_id = s.org_id "
    "     and r.capability_snapshot_id = s.capability_snapshot_id "
    "where s.org_id = :o and r.capability_id like 'expertise.%'")


def _sweep(pg_store, org: str, *, ranking_v2: bool, roster_v2: bool = True,
           l1_scored: bool = True) -> dict:
    """Seed, activate, compile — and hand Layer 1's own supply to Layer 2 before it does.

    `l1_scored` IS THE SUBJECT OF ONE TEST IN THIS FILE and may not be defaulted away. Both values
    give the tenant the verified evidence spans L2's admission gate requires of everyone; they
    differ in whether ALG-17 produced a NUMBER:

      True  — the activated tenant. `importance_source` reads `l1_qualified_signals` and the
              ranker's sixth component is a real measurement with a spread.
      False — Layer 1 qualified these signals and could not score them. Layer 2 reads that as an
              absence, `importance_base` declares the 5,000 fallback, and Layer 4's honesty guard
              reweighs the other five and records `L2_IMPORTANCE_NOT_ACTIVE`. That is what
              `test_this_fixtures_layer_one_never_scored_...` measures, and giving it a score
              would make it pass while proving nothing.
    """
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.platform.l4_activation import activate
    from genios_engine.reason.domain_shadow import shadow_compile

    _seed_org(pg_store, org)
    with pg_store.engine.begin() as conn:
        conn.execute(text("delete from signals where org_id = :o"), {"o": org})
    # THREE EVENTS, AND EVERY EVENT ID CARRIES THE ORG. Two separate reasons, both measured:
    #
    #   * `source_events_pkey` is `(event_id)` — NOT `(org_id, event_id)` — and `_seed_event`
    #     inserts `on conflict do nothing`. `_run_admin`'s default id is the constant `adm_evt`,
    #     so on one database only the FIRST org seeded ever gets a `source_events` row and every
    #     later tenant silently scores `source_count = 0`.
    #   * one email is not enough evidence for this product to speak, and it should not be.
    #     `situations.evidence_score` caps volume at 40 and corroboration at 60; a single event
    #     from a single source scores 8, so `core.confidence` composes 800 bp against a floor of
    #     4500 and the tenant DEFERS — correctly. Three events from one source score 49, which
    #     clears it. The floor is not touched; the tenant is given something to be confident
    #     about.
    for index in range(3):
        _run_admin(pg_store, org, event_id=f"adm_evt_{org}_{index}")
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    assert attach_l1_signals(pg_store, org, eval_time=NOW, scored=l1_scored) > 0
    if roster_v2:
        activate(pg_store.engine, org, feature="roster_v2", by="test")
    if ranking_v2:
        activate(pg_store.engine, org, feature="ranking_v2", by="test")
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    counts = shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True,
                            registry=registry)
    assert counts.get("reasoned", 0) > 0, dict(counts)
    assert counts.get("ranking_v2", 0) == int(ranking_v2), dict(counts)
    # THE SWEEP'S OWN MEASUREMENT OF THE TENANT'S LAYER 1, pinned here because it is what
    # `situation_publisher.decide_publication` conditions its one relaxable hold on. A sweep that
    # stopped measuring it, or measured it per situation instead of per tenant, would still
    # produce decisions — and the absent-importance tenant below would silently go back to being
    # held before the guard it exists to exercise is ever reached.
    assert counts.get("l1_scoring_active") == int(l1_scored), dict(counts)
    return dict(counts)


def _rows(pg_store, org: str, statement: str) -> list[dict]:
    with pg_store.engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(statement), {"o": org}).mappings().all()]


def _json(value):
    return json.loads(value) if isinstance(value, str) else (value or {})


def test_the_activated_sweep_persists_the_six_weight_model(pg_store):
    org = "pk_ranking_live"
    _sweep(pg_store, org, ranking_v2=True)

    manifests = [_json(row["manifest"]) for row in _rows(pg_store, org, _MANIFESTS)]
    assert manifests
    for manifest in manifests:
        assert manifest["ranking_weights"] == dict(RANKING_WEIGHTS_V2)
        carrier = manifest["metadata"][SITUATION_IMPORTANCE_KEY]
        assert set(carrier) == {"importance_bp", "source", "fallback", "version"}


def test_the_persisted_candidates_carry_importance_and_the_demoted_override(pg_store):
    """The whole point, in the tenant's own rows: the sixth component and the prior it replaced."""
    org = "pk_ranking_live_rows"
    _sweep(pg_store, org, ranking_v2=True)

    candidates = _rows(pg_store, org, _CANDIDATES)
    assert candidates
    for row in candidates:
        components = _json(row["score_components"])
        assert "formula_utility" in components
        assert PRIORITY_OVERRIDE_COMPONENT in components
        # The final utility is the 70/30 blend and not the corpus's number verbatim.
        assert row["final_utility_bp"] == min(10_000, (
            components["formula_utility"] * 7 + components[PRIORITY_OVERRIDE_COMPONENT] * 3) // 10)


def test_the_decision_records_its_model_and_its_computed_consequence(pg_store):
    org = "pk_ranking_live_core"
    _sweep(pg_store, org, ranking_v2=True)

    outputs = [row for row in _rows(pg_store, org, _OUTPUTS)
               if str(row["outcome_kind"]) == "decision"]
    assert outputs
    for row in outputs:
        core = _json(row["decision_core"])
        assert core["ranking_weights_version"] == RANKING_WEIGHTS_V2_VERSION
        assert set(core["do_nothing"]) == {"cost_bp", "horizon", "statement", "source"}


def test_an_unactivated_tenant_ranks_exactly_as_it_ranks_today(pg_store):
    """Fail closed, per tenant: nothing about a tenant nobody switched on moves — not the weights,
    not the manifest bytes, not the components its persisted candidates carry."""
    org = "pk_ranking_live_dark"
    _sweep(pg_store, org, ranking_v2=False)

    for manifest in (_json(row["manifest"]) for row in _rows(pg_store, org, _MANIFESTS)):
        assert manifest["ranking_weights"] == dict(RANKING_WEIGHTS_V1)
        assert SITUATION_IMPORTANCE_KEY not in manifest["metadata"]
    for row in _rows(pg_store, org, _CANDIDATES):
        components = _json(row["score_components"])
        assert IMPORTANCE_COMPONENT not in components
        assert PRIORITY_OVERRIDE_COMPONENT not in components
    for row in _rows(pg_store, org, _OUTPUTS):
        core = _json(row["decision_core"])
        assert "ranking_weights_version" not in core
        assert "do_nothing" not in core


def test_the_gate_report_reads_the_rows_the_sweep_actually_wrote(pg_store):
    """`scripts/ranking_distribution.py` against real persisted rows rather than fixtures — the
    query shape and the column names are half of what a gate command has to get right."""
    org = "pk_ranking_live_gate"
    _sweep(pg_store, org, ranking_v2=True)

    report = measure(_rows(pg_store, org, _CANDIDATES), _rows(pg_store, org, _OUTPUTS),
                     org_id=org, since=NOW, until=NOW)

    assert report.candidates > 0
    assert report.with_formula == report.candidates
    assert report.with_override == report.candidates
    assert report.divergence_passed
    assert report.do_nothing_total == report.decisions
    assert report.ranking_versions == (RANKING_WEIGHTS_V2_VERSION,)


def test_this_fixtures_layer_one_never_scored_so_importance_is_absent_and_says_so(pg_store):
    """A MEASUREMENT, not a shortfall to route around — and the reason K1 cannot be read off a
    tenant that has not passed G7.

    This fixture's Layer 1 publishes no scored signal, so `importance_base` answers with the
    neutral 5,000 midpoint and DECLARES the fallback. The ranker therefore refuses the number,
    reweighs the remaining five and names why on every decision. That is the honest behaviour and
    it is what the gate should see: importance coverage 0, plainly reported, rather than a
    tenant ranked on a constant while the report says 25% of the utility came from Layer 2.

    Doc 08: *"G7, H5 and K1 must hold on the same pilot in the same fortnight."* This is what the
    third one looks like when the first has not.
    """
    org = "pk_ranking_live_absent"
    # `scored=False` — Layer 1 QUALIFIED these signals, receipts and all, and could not score
    # them. Not "no Layer 1": a tenant with no `qualified_signals` at all has no verified evidence
    # span either, and L2's admission gate holds it before importance is ever read, so the guard
    # under test would never be reached. This is the absence the guard is for, in the one state
    # that actually reaches it.
    _sweep(pg_store, org, ranking_v2=True, l1_scored=False)

    for manifest in (_json(row["manifest"]) for row in _rows(pg_store, org, _MANIFESTS)):
        assert manifest["metadata"][SITUATION_IMPORTANCE_KEY]["fallback"] is True
    for row in _rows(pg_store, org, _CANDIDATES):
        assert IMPORTANCE_COMPONENT not in _json(row["score_components"])
    for row in _rows(pg_store, org, _OUTPUTS):
        assert any(str(code).startswith(IMPORTANCE_ABSENT_REASON)
                   for code in _json(row["decision_core"]).get("uncertainty") or ())

    report = measure(_rows(pg_store, org, _CANDIDATES), _rows(pg_store, org, _OUTPUTS),
                     org_id=org, since=NOW, until=NOW)
    assert report.with_importance == 0
    assert not report.importance_ranking_passed
    assert not report.passed
