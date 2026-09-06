"""H5 · SITUATION IMPORTANCE — the gate that matters.

**Gate H5**, invoked by `02-Layer-2-Plan/09-Build-Order-and-Acceptance.md` as::

    pytest tests/context/test_situation_importance.py -q
    python scripts/situation_importance_distribution.py --org <pilot> --since 30d

This file used to be a PLACEHOLDER that skipped. X5 has landed
(`genios_engine/context/importance.py`), so the placeholder is retired and this is the real gate.
The unit suite under it — the six modifiers, the record, the readers — is `test_importance.py`;
what lives HERE is the only thing a per-situation test cannot see: the DISTRIBUTION.

| distinct `importance_bp` values      | > 50    | 5000-for-everything is the defect |
| p90 - p50                            | > 1500  | a flat distribution cannot rank   |
| situations at exactly 5000           | < 5%    | the constant is gone              |
| one critical + four routine signals  | >= 9000 | proves max, not mean              |
| `importance_components` populated    | 100%    | explainability                    |
| identical input twice                | byte-identical | reproducibility            |

**Why a distribution is a different test from a formula.** `reason/reasoners/priority.py:165-197`
recorded 193 of 223 signals scoring an identical 50, and `decision_maker.py:243` recorded that
"the formula has never once decided anything" — while every unit test around both passed. A
composer can be correct per situation and useless in aggregate the moment its inputs collapse, and
no test of one situation can see that.

**This gate and Layer 1's G7 are two halves of ONE fix.** G7 already passes on the production
path: 321 signals scored, 100 distinct values, p50 4480 / p90 6000, spread 1520 bp. So the supply
side is real, and if the distribution below came out flat the cause would be THIS unit.

**What the population here is, honestly.** It is a FIXTURE, not the pilot org: the modifier
availability rates below are stated assumptions, and the real ones are what
`scripts/situation_importance_distribution.py` reports against a tenant. What the fixture cannot
fake, and what the rows after the distribution assert, is that every modifier's threshold is
MEETABLE by the real producers (`test_importance.py` proves that against `compute_trend`,
`detect_anomaly` and `position_from_values`) and that 5000 is reachable ONLY through the
documented fallback with no L2 input — which is the invariant the "< 5%" row is really about.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from genios_engine.capture.esqe.importance import nearest_rank
from genios_engine.context.importance import (
    FLAT_BASE_BP, AnomalyInput, CohortInput, ConflictInput, ConstituentSignal, DependencyInput,
    ImportanceBase, ModifierInputs, ModifierName, ModifierReason, TrendInput,
    UNRESOLVED_RESOLUTION, compose_situation_importance)

#: The size of the population the defect was measured on: 223 situations, 193 of which shared one
#: number. The gate is run at the same scale so its percentiles mean what the incident's did.
POPULATION = 223

#: The gate rows, named so a failure message can quote the threshold it failed.
MIN_DISTINCT = 50
MIN_SPREAD_BP = 1_500
MAX_FLAT_SHARE_BP = 500          # 5% of the population still at exactly 5000
P50_BP, P90_BP = 5_000, 9_000

#: **THE FIXTURE'S STATED ASSUMPTIONS.** Each is "one situation in N has this input available",
#: chosen to be plausible rather than flattering — a modifier that needed a rate nobody's data can
#: reach would be a dead rule, which is why `test_importance.py` proves each threshold against the
#: real producer instead of against these numbers.
_TREND_EVERY = 3          # a third of situations have a trended metric on a subject node
_CONFIDENT_EVERY = 2      # half of those clear the 5000 confidence floor
_COHORT_EVERY = 5         # a fifth sit at the worst expressible band of a real cohort
_ANOMALY_EVERY = 17       # flagged anomalies are rare BY DESIGN (z_like > 30000 AND dev > 2000)
_BLOCKED_EVERY = 7
_CONFLICT_EVERY = 13
_STALE_EVERY = 9
_UNCOVERED_EVERY = 11
#: One situation in twelve has no live qualified signal at all and lands on the documented
#: fallback. That share is what the "< 5% at exactly 5000" row is measuring after composition.
_DEFAULTED_EVERY = 12


def _lcg(seed: int = 20260905):
    """A deterministic integer generator. `random` would also be seedable; this is four lines,
    reads as arithmetic, and cannot pick up a different stream when Python's PRNG changes."""
    state = seed
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state


def _base_bp(draw: int) -> int:
    """A base drawn from the SHAPE Layer 1 actually publishes — G7 measured p50 4480, p90 6000
    over 100 distinct values. Piecewise rather than uniform, because a uniform draw would hand
    this gate a spread the production supply does not have."""
    bucket, offset = draw % 100, draw // 100
    if bucket < 55:
        return 3_000 + offset % 1_500          # the routine middle
    if bucket < 85:
        return 4_500 + offset % 1_600          # the working band around the median
    if bucket < 97:
        return 6_100 + offset % 1_900
    return 8_000 + offset % 1_800              # the genuinely critical tail


def _population(eval_time, size: int = POPULATION):
    """`size` composed situations, deterministic, built from the stated availability rates."""
    draws = _lcg()
    out = []
    for index in range(size):
        draw = next(draws)
        defaulted = index % _DEFAULTED_EVERY == 0
        base = ImportanceBase(
            importance_bp=FLAT_BASE_BP if defaulted else _base_bp(draw),
            source="default" if defaulted else "l1_qualified_signals",
            signal_id=None if defaulted else f"sig_{index}",
            version=None if defaulted else "alg17.v2")
        systems = ("gmail",) if index % 3 else ("gmail", "gcal")
        if index % 8 == 0:
            systems = ("gmail", "gcal", "drive")
        signals = tuple(ConstituentSignal(f"evt_{index}_{s}", s) for s in systems)

        trends = ()
        if index % _TREND_EVERY == 0:
            confident = index % (_TREND_EVERY * _CONFIDENT_EVERY) == 0
            trends = (TrendInput(metric="engagement.touch_count_28d",
                                 subject_node_id=f"node_{index}", direction="declining",
                                 trend_confidence_bp=6_200 if confident else 4_100,
                                 point_count=8, fact_version_id=f"fv_t_{index}"),)
        cohorts = ()
        if index % _COHORT_EVERY == 0:
            worst = index % (_COHORT_EVERY * 2) == 0
            cohorts = (CohortInput(metric="engagement.touch_count_28d",
                                   subject_node_id=f"node_{index}",
                                   percentile_bp=300 if worst else 5_400,
                                   population_size=12 + draw % 40, cohort_id="cohort_plan",
                                   fact_version_id=f"fv_c_{index}"),)
        anomalies = ()
        if index % _ANOMALY_EVERY == 0:
            anomalies = (AnomalyInput(metric="engagement.touch_count_28d",
                                      subject_node_id=f"node_{index}", flagged=True,
                                      periods_used=6, z_like_bp=38_000, direction="below",
                                      fact_version_id=f"fv_a_{index}"),)
        dependencies = ()
        if index % _BLOCKED_EVERY == 0:
            dependencies = (DependencyInput(subject_node_id=f"node_{index}",
                                            blocked_count=1 + draw % 6,
                                            fact_version_id=f"fv_d_{index}"),)
        conflicts = ()
        if index % _CONFLICT_EVERY == 0:
            conflicts = (ConflictInput(conflict_id=f"cf_{index}", field="contract.value",
                                       signal_id=f"sig_{index}",
                                       resolution=UNRESOLVED_RESOLUTION),)
        newest = eval_time - timedelta(days=200 if index % _STALE_EVERY == 0 else 4)

        out.append(compose_situation_importance(
            base=base, signals=signals, eval_time=eval_time,
            modifiers=ModifierInputs(
                trends=trends, cohort_positions=cohorts, anomalies=anomalies,
                dependencies=dependencies, conflicts=conflicts, newest_evidence_at=newest,
                coverage_ready=index % _UNCOVERED_EVERY != 0, coverage_domain="sales")))
    return out


@pytest.fixture
def population(eval_time):
    return _population(eval_time)


# =================================================================================================
# THE FOUR DISTRIBUTION ROWS
# =================================================================================================

def test_the_distribution_has_more_than_fifty_distinct_values(population) -> None:
    """Row 1. "A handful of values means it is not deciding." 193 of 223 sharing one number is the
    defect; the composer must carry Layer 1's spread through and add to it."""
    values = [c.importance_bp for c in population]
    distinct = len(set(values))

    assert distinct > MIN_DISTINCT, (
        f"{distinct} distinct values across {len(values)} situations — the gate is "
        f"> {MIN_DISTINCT}. A composer that collapses its inputs cannot rank anything.")


def test_the_spread_between_the_median_and_the_top_decile_can_rank(population) -> None:
    """Row 2. A distribution can have many distinct values and still be useless if they are all
    within a whisker of each other — p90 minus p50 is what a ranker actually has to work with.
    Measured with L1's own `nearest_rank`, so this gate and G7 cannot disagree about a median."""
    ordered = sorted(c.importance_bp for c in population)
    p50, p90 = nearest_rank(ordered, P50_BP), nearest_rank(ordered, P90_BP)

    assert p90 - p50 > MIN_SPREAD_BP, (
        f"p50={p50} p90={p90} spread={p90 - p50} — the gate is > {MIN_SPREAD_BP} bp")


def test_almost_nothing_is_left_at_exactly_five_thousand(population) -> None:
    """Row 3, and its meaning has MOVED. `DEFAULT_IMPORTANCE_BP` is no longer stamped on every
    situation — `situation_bso` branches across four sources and records which fired — so this row
    now measures the share still landing on the documented FALLBACK with nothing to move it.

    One situation in twelve here starts on that fallback; the L2 modifiers must carry most of them
    off it, because a situation with a declining trend and three blocked items is not a 5000
    whatever Layer 1 could or could not say about it."""
    values = [c.importance_bp for c in population]
    flat = sum(1 for v in values if v == FLAT_BASE_BP)
    share_bp = flat * 10_000 // len(values)

    assert share_bp < MAX_FLAT_SHARE_BP, (
        f"{flat}/{len(values)} ({share_bp} bp) still sit at exactly {FLAT_BASE_BP} — the gate is "
        f"< {MAX_FLAT_SHARE_BP} bp")


def test_a_composed_five_thousand_is_never_a_stamp(population) -> None:
    """**The invariant the row above is really about**, and the one a fixture cannot flatter.

    A 5000 is now allowed to arise two ways, and both are STATED on the record:

    * the documented fallback — `base_source == 'default'` with nothing to move it. That is an
      honest "we have no live signal here and no L2 fact about it either";
    * arithmetic that happens to land there — a defaulted base plus a corroborating second source
      minus a staleness discount, say. The terms are in the record, so it is explainable rather
      than identical-looking.

    What must never happen is the third case: a number that equals the fallback with a record
    that cannot account for it. That is the state that made 193 of 223 signals unrankable, because
    a stamped 5000 and a computed one were indistinguishable in the column.
    """
    for composed in population:
        if composed.importance_bp != FLAT_BASE_BP:
            continue
        moved = composed.corroboration_bp != 0 or composed.modifier_total_bp != 0
        if moved:
            # Arrived by arithmetic: every term is on the record and they close.
            deltas = sum(t.delta_bp for t in composed.modifiers)
            assert (composed.base_bp + composed.corroboration_bp + deltas
                    - composed.modifier_cap_removed_bp == composed.subtotal_bp)
            assert any(t.fired for t in composed.modifiers) or composed.corroboration_bp
        else:
            assert composed.base_source == "default", (
                f"a {composed.base_source} situation sits at exactly {FLAT_BASE_BP} with nothing "
                "in its record to explain it — that is the constant wearing a new coat")


def test_the_untouched_fallback_is_a_small_minority(population) -> None:
    """The share this gate's "< 5%" row is really measuring, now that the constant is gone: how
    many situations reach Layer 3 on the neutral fallback with NO L2 fact about them at all. Those
    are the ones a ranker still cannot separate, and the modifiers exist to shrink the set."""
    untouched = [c for c in population if c.base_source == "default"
                 and c.modifier_total_bp == 0 and c.corroboration_bp == 0]
    share_bp = len(untouched) * 10_000 // len(population)

    assert share_bp < MAX_FLAT_SHARE_BP, (
        f"{len(untouched)}/{len(population)} ({share_bp} bp) situations carry the fallback with "
        f"nothing else known about them — the gate is < {MAX_FLAT_SHARE_BP} bp")


def test_one_critical_signal_and_four_routine_ones_stay_critical(eval_time) -> None:
    """Row 4, the max-not-mean pair. The base is `gather_l1_signals`' max (9000); the mean of the
    same five is 4200. Any averaging anywhere on the path shows up as a factor of two here."""
    composed = compose_situation_importance(
        base=ImportanceBase(importance_bp=9_000, source="l1_qualified_signals",
                            signal_id="sig_critical", version="alg17.v2"),
        signals=(ConstituentSignal("evt_1", "gmail"),),
        modifiers=ModifierInputs(coverage_ready=True, newest_evidence_at=eval_time),
        eval_time=eval_time)

    assert composed.importance_bp >= 9_000
    assert (9_000 + 3_000 * 4) // 5 == 4_200 < composed.importance_bp


def test_every_situation_carries_a_populated_component_record(population) -> None:
    """Row 5, at 100%. "Why is this a 7400?" must be answerable from stored data for EVERY
    situation, not for the interesting ones — and populated means all six modifier terms, because
    a term that is absent when it did not fire cannot be told from a term nobody computed."""
    for composed in population:
        record = json.loads(json.dumps(composed.as_record()))
        assert record["version"] and record["base_source"]
        assert [t["name"] for t in record["modifiers"]] == [m.value for m in ModifierName]
        assert all(t["reason"] for t in record["modifiers"])
        deltas = sum(t["delta_bp"] for t in record["modifiers"])
        assert (record["base_bp"] + record["corroboration_bp"] + deltas
                - record["modifier_cap_removed_bp"] == record["subtotal_bp"])


def test_the_whole_population_replays_byte_identically(eval_time) -> None:
    """Row 6. Two runs over the same inputs, one JSON blob — the property that lets a composed
    importance be content-addressed, and the one a stray clock or a set iteration would break."""
    first = json.dumps([c.as_record() for c in _population(eval_time)], sort_keys=True)
    second = json.dumps([c.as_record() for c in _population(eval_time)], sort_keys=True)

    assert first == second


# =================================================================================================
# THE FIRING TABLE — six modifiers that never fire reproduce the flat distribution with more code
# =================================================================================================

def test_every_modifier_actually_fires_on_the_population(population, capsys) -> None:
    """**The dead-rule check, and it is the reason this file is not just four percentile asserts.**

    Fifteen of Layer 1's twenty-one deep sales rules were dead because they gated on a field only
    9% of records carried, and every unit test around them passed. A modifier that cannot fire is
    the same failure: the code reads correct, the distribution stays flat, and nothing says which
    of the six did nothing.

    So the firing SHARE of each modifier is measured and printed. The assertion is deliberately
    weak (> 0) because these are fixture rates; the printed table is the artefact a reviewer reads
    against `scripts/situation_importance_distribution.py`'s real-tenant version of it.
    """
    table = {}
    for name in ModifierName:
        fired = sum(1 for c in population if c.term(name).fired)
        table[name.value] = (fired, fired * 10_000 // len(population))

    with capsys.disabled():
        print("\n  modifier firing rates over "
              f"{len(population)} composed situations (fixture, not a tenant):")
        for name, (fired, share_bp) in table.items():
            print(f"    {name:<16} {fired:>4} / {len(population)}  = {share_bp / 100:>5.1f}%")

    dead = [name for name, (fired, _) in table.items() if fired == 0]
    assert not dead, (
        f"{dead} fired on no situation in a population built to contain their inputs — a modifier "
        "that cannot fire reproduces the flat distribution with more code")


def test_the_reasons_are_recorded_for_the_ones_that_did_not_fire(population) -> None:
    """The other half of the table. A modifier that did not fire says WHY, so "no trend on this
    subject" is distinguishable from "a decline we were not confident enough in" — and a threshold
    that turns out to be unmeetable is visible in the reasons rather than in a silence."""
    reasons = {name: set() for name in ModifierName}
    for composed in population:
        for name in ModifierName:
            term = composed.term(name)
            if not term.fired:
                reasons[name].add(term.reason)

    assert ModifierReason.TREND_CONFIDENCE_BELOW_FLOOR in reasons[ModifierName.TREND]
    assert ModifierReason.NO_INPUT in reasons[ModifierName.ANOMALY]
    assert ModifierReason.COHORT_NOT_AT_WORST_EXTREME in reasons[ModifierName.COHORT_POSITION]
    assert all(ModifierReason.FIRED not in rs for rs in reasons.values())


def test_a_flat_layer_one_supply_is_reported_and_not_papered_over(eval_time) -> None:
    """Doc 07's refusal, at the gate. If more than 90% of incoming signals still carry exactly
    5000, this unit must NOT synthesize a spread: the guard suppresses the modifiers, the base
    passes through, and `L1_IMPORTANCE_NOT_ACTIVE` is logged. A fake distribution is worse than a
    flat one because it looks like it works."""
    composed = [compose_situation_importance(
        base=ImportanceBase(importance_bp=FLAT_BASE_BP, source="l1_qualified_signals"),
        signals=(ConstituentSignal(f"evt_{i}", "gmail"),),
        modifiers=ModifierInputs(dependencies=(DependencyInput(f"node_{i}", 4),)),
        eval_time=eval_time, l1_active=False) for i in range(50)]

    assert {c.importance_bp for c in composed} == {FLAT_BASE_BP}
    assert all(c.l1_importance_not_active for c in composed)


# =================================================================================================
# THE L1 -> L2 SEAM, on a real database
# =================================================================================================

@pytest.mark.pg
def test_the_max_not_mean_pair_survives_the_real_layer_one_read(pg_store, eval_time) -> None:
    """**The gate row that cannot be faked in memory.** One critical signal (9000) and four
    routine ones (3000) are written into `qualified_signals` exactly as Layer 1's publisher writes
    them, read back through the PRODUCTION function (`situation_bso.gather_l1_signals`), and
    composed. The whole H5/G7 pair lives or dies on this: G7 proves signals CARRY real importance,
    this proves the situation COMPOSES from the strongest of them instead of averaging them into a
    scheduling note."""
    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import gather_l1_signals

    org, correlation = "org_l2_h5_seam", "corr_h5"
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'h5 seam') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        with pg_store.engine.begin() as conn:
            for index, importance in enumerate((9_000, 3_000, 3_000, 3_000, 3_000)):
                event_id = f"evt_h5_{index}"
                conn.execute(sql(
                    "insert into source_events (event_id, org_id, connection_id, source, "
                    " object_type, source_object_id, dedup_key, actor, occurred_at) values "
                    "(:e, :o, 'conn', :s, 'email_message', :e, :e, '{}'::jsonb, :t)"),
                    {"e": event_id, "o": org, "s": "gmail" if index else "drive",
                     "t": eval_time - timedelta(days=2)})
                conn.execute(sql(
                    "insert into context_correlation_members (org_id, correlation_id, event_id) "
                    "values (:o, :c, :e)"), {"o": org, "c": correlation, "e": event_id})
                conn.execute(sql(
                    "insert into qualified_signals (signal_id, org_id, event_id, trace_id, "
                    " signal_type, importance_bp, importance_version, confidence_bp, visibility, "
                    " extraction_ref, evidence_refs, state, occurred_at) values "
                    "(:s, :o, :e, :tr, 'commitment_made', :i, 'alg17.v2', 6200, "
                    " '{\"scope\": \"org\"}'::jsonb, :x, "
                    " '[{\"source_ref\": \"prepared_content:e\", \"quote\": \"q\"}]'::jsonb, "
                    " 'active', :t)"),
                    {"s": f"sig_h5_{index}", "o": org, "e": event_id, "tr": f"trace_{index}",
                     "i": importance, "x": f"extraction_{index}",
                     "t": eval_time - timedelta(days=2)})

        with pg_store.engine.connect() as conn:
            l1 = gather_l1_signals(conn, org, correlation)

        assert l1 is not None and l1.importance_bp == 9_000, (
            f"gather_l1_signals returned {l1 and l1.importance_bp} — the base is the MAX of the "
            "live scored signals, and the mean of these five is 4200")

        composed = compose_situation_importance(
            base=ImportanceBase(importance_bp=l1.importance_bp, source="l1_qualified_signals",
                                signal_id=l1.signal_ids[0], version=l1.importance_version),
            signals=(ConstituentSignal("evt_h5_0", "drive"),
                     ConstituentSignal("evt_h5_1", "gmail")),
            modifiers=ModifierInputs(coverage_ready=True,
                                     newest_evidence_at=eval_time - timedelta(days=2)),
            eval_time=eval_time)

        assert composed.importance_bp >= 9_000
        assert composed.corroboration_bp == 500, "two independent source systems"
        assert composed.as_record()["base_source"] == "l1_qualified_signals"
    finally:
        with pg_store.engine.begin() as conn:
            for table in ("qualified_signals", "context_correlation_members", "source_events"):
                conn.execute(sql(f"delete from {table} where org_id = :o"), {"o": org})
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


# =================================================================================================
# THE WIRING — the half of this gate that Layer 1 shipped six units without
# =================================================================================================
#
# Layer 1 shipped SIX units that were green and called by nothing, each found only in review. A
# composer with no production caller is not a smaller version of a working feature; it is the
# same state the constant was in, with more code. The two tests below are the ratchet: they read
# the SOURCE of every publish path in the tree, and they name the file and the line when one of
# them stops composing.

import ast          # noqa: E402 - the wiring section's own imports, kept beside their use
from collections.abc import Mapping   # noqa: E402
import pathlib      # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Where a BSO can be published from. `tests/` is deliberately absent: a test that builds a BSO
#: without a composition is usually testing exactly the pre-composition fallback, which must stay
#: reachable (A-1 — `DEFAULT_IMPORTANCE_BP` is the documented answer for a situation Layer 1 never
#: scored, not a defect). Production code has no such excuse.
_PUBLISH_ROOTS = ("genios_engine", "scripts")

#: The builder every publish path calls, and the keyword that carries BLG-18 steps 2..6.
_BUILDER = "build_business_situation"
_COMPOSED_KEYWORD = "composed"


def _call_sites(name: str) -> list[tuple[pathlib.Path, ast.Call]]:
    """Every call to `name` in production code, as (file, node). AST, never a substring search:
    a `grep` for the builder's name matches its own definition, its import, and every mention of
    it in a docstring — three false positives that would make this ratchet unmaintainable and
    therefore, eventually, deleted."""
    out: list[tuple[pathlib.Path, ast.Call]] = []
    for root in _PUBLISH_ROOTS:
        for path in sorted((_ROOT / root).rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                called = (func.id if isinstance(func, ast.Name)
                          else func.attr if isinstance(func, ast.Attribute) else None)
                if called == name:
                    out.append((path, node))
    return out


def test_no_business_situation_is_published_without_a_composed_importance() -> None:
    """**THE CHECK THAT CATCHES A WHOLE CLASS.** A new publish path that forgets `composed=`
    publishes a BSO carrying Layer 1's base alone — no corroboration, no modifiers, no coverage
    penalty and, decisively, an EMPTY `importance_components`. Nothing fails: the object is valid,
    the compile runs, a card appears, and the only symptom is that H5's distribution goes flat
    again on the tenant that added the path. That is precisely how `coverage_ready` shipped four
    times at Layer 1 before an identical source test was written for it.

    Naming the FILE AND LINE is the point: "something does not compose" is not actionable, and a
    reviewer who has to go looking will approve the change.
    """
    offenders = [f"{path.relative_to(_ROOT)}:{node.lineno}"
                 for path, node in _call_sites(_BUILDER)
                 if not any(kw.arg == _COMPOSED_KEYWORD for kw in node.keywords)]
    assert not offenders, (
        f"these publish paths build a BusinessSituationObject without composing its importance "
        f"(BLG-18 steps 2..6): {', '.join(offenders)}. Pass `composed=stored_importance(row)` — "
        "the composition is already on the `context_situations` row the sweep wrote, so reading "
        "it costs no query and recomputing it would cost five per situation.")


def test_the_wiring_check_is_actually_looking_at_the_publish_paths() -> None:
    """A source ratchet that matches nothing passes for ever. Both known publish paths — the
    live Layer 3 compile and the corpus route probe — must be in the set the test above walks, so
    a rename or a move that hides them from the walker fails HERE rather than silently disarming
    the guard."""
    found = {str(path.relative_to(_ROOT)) for path, _ in _call_sites(_BUILDER)}
    assert "genios_engine/reason/domain_shadow.py" in found, (
        "the live Layer 3 publish path is no longer visible to the wiring check")
    assert "scripts/corpus_route_probe.py" in found
    assert len(found) >= 2


#: EVERY module that inserts a `context_situations` row. Six writers, five modules — `outreach_
#: situations` writes through `support_situations._upsert`. They are listed rather than counted
#: because the composition pass is a SWEEP over the table, not a line in each writer: it covers
#: any writer that already exists, and a NEW one is only covered if `refresh_situation_importance`
#: still runs after it. That is a scheduling fact no source test can check, so this list is the
#: tripwire that sends a reviewer to look.
_KNOWN_SITUATION_WRITERS = frozenset({
    "genios_engine/context/situations.py",            # the correlation-driven refresh
    "genios_engine/context/periodic.py",              # tenant window aggregates
    "genios_engine/context/support_situations.py",    # support readings (+ outreach, via _upsert)
    "genios_engine/context/meeting_touch.py",         # the calendar channel
    "genios_engine/context/document_register.py",     # records control gaps
})


def test_a_new_writer_of_context_situations_has_to_be_ranked_too() -> None:
    """The sibling class, one table down, and the one that nearly shipped unnoticed here.

    `refresh_situations` is NOT the only writer of `context_situations` — there are six, five of
    which mint synthetic correlation ids and never call `score_situation`. A composition welded
    to one writer leaves the other five carrying a NULL `importance_bp`, and a null is invisible
    to the H5 gate rather than failing it: the situations nobody ranks would be exactly the ones
    nobody notices. `refresh_situation_importance` therefore sweeps the TABLE, and this test fails
    by file and line when a sixth module starts writing to it — the reviewer's job is then to
    confirm the new writer runs BEFORE that pass in `reason/runner`, which is a scheduling fact no
    source test can see.
    """
    found: dict[str, int] = {}
    for root in _PUBLISH_ROOTS:
        for path in sorted((_ROOT / root).rglob("*.py")):
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if "insert into context_situations" in line:
                    found.setdefault(str(path.relative_to(_ROOT)), number)
    unknown = [f"{path}:{line}" for path, line in sorted(found.items())
               if path not in _KNOWN_SITUATION_WRITERS]
    assert not unknown, (
        f"a new writer of context_situations: {', '.join(unknown)}. Its rows are ranked only if "
        "`situation_bso.refresh_situation_importance` still runs AFTER it in the sweep — check "
        "`context/runner.py`, then add the module here.")
    assert set(found) == _KNOWN_SITUATION_WRITERS, (
        f"a declared writer no longer writes situations: "
        f"{sorted(_KNOWN_SITUATION_WRITERS - set(found))}")


def test_the_ranking_pass_runs_behind_every_analytic_pass_that_feeds_it() -> None:
    """**THE ORDERING BUG THIS UNIT ALMOST SHIPPED WITH.** The six modifiers read
    `derived.trend.*`, `derived.cohort_position.*`, `derived.anomaly.*` and
    `derived.dependency.blocked_count`. Every one of those families is written by a pass in the L2
    drain, and `refresh_situations` runs BEFORE all of them. Composing inside that function reads
    last sweep's analytic stratum — and on a tenant's FIRST sweep, an empty one: every modifier
    silent, the distribution flat, and the cause nothing whatever to do with the composer. That is
    the failure mode doc 09 warns about in the same breath as tuning a threshold, because from the
    gate it looks identical.

    Asserted on the source order of the calls in `context/runner.py`, which is the only place the
    schedule is written down.
    """
    body = (_ROOT / "genios_engine" / "context" / "runner.py").read_text()
    ranked = body.index("refresh_situation_importance(store, org_id")
    for feeder in ("refresh_trend_facts(", "refresh_anomaly_facts(", "refresh_comparison_facts(",
                   "refresh_dependency_chains(", "refresh_situations(store"):
        assert body.index(feeder) < ranked, (
            f"{feeder} runs AFTER the importance pass — its facts would be composed one sweep "
            "late, and not at all on a tenant's first sweep")


# =================================================================================================
# THE GATE, ON A REAL DATABASE, THROUGH THE PRODUCTION SWEEP
# =================================================================================================
#
# Everything above this line composes in memory. This section seeds a tenant, runs the two
# functions `reason/runner` runs — `situations.refresh_situations` and
# `situation_bso.refresh_situation_importance` — and then measures the five H5 rows with the GATE
# SCRIPT's own arithmetic (`scripts/situation_importance_distribution.distribution`), off the
# stored columns. Nothing here calls the composer.
#
# WHAT IS SEEDED AND WHAT IS NOT. The `derived.*` bodies are written as literal JSON rather than
# through `compute_trend` / `detect_anomaly` / `position_from_values`, because those producers are
# already driven against the readers in `test_importance.py` and a second copy of that proof here
# would be slower and no stronger. What THIS file proves instead is that the bodies are READ: if a
# seeded shape were wrong, its modifier's fire count would be zero, and the per-modifier assertion
# below fails on the modifier's own name rather than on a distribution that mysteriously flattened.

_ORG = "h5_prod_path"
#: 90 situations. The incident's population was 223; the gate's percentile rows need enough rows
#: for a p90 to mean something and enough distinct scores to clear 50, and 90 does both while
#: keeping the seed under a second.
_SITUATIONS = 90


def _seed_h5_org(conn, sql, eval_time) -> None:
    """One tenant with a realistic spread: Layer 1 scores, several source systems, four families
    of derived fact, unresolved conflicts, silent situations and one uncovered domain."""
    conn.execute(sql("insert into orgs (id, name) values (:o, 'h5') "
                     "on conflict (id) do nothing"), {"o": _ORG})
    # Step 4's input. `sales` is covered; `support` is NOT, and the situations filed under it take
    # the *8//10 discount. Two domains rather than one because the penalty is per-domain, and a
    # single-domain fixture would make step 4 either universal or dead.
    for domain, ready in (("sales", True), ("support", False)):
        conn.execute(sql("insert into source_coverage (org_id, domain, coverage_ready) "
                         "values (:o, :d, :r) on conflict (org_id, domain) do update set "
                         "coverage_ready = excluded.coverage_ready"),
                     {"o": _ORG, "d": domain, "r": ready})

    for index in range(_SITUATIONS):
        anchor, deal = f"nd_h5_a{index}", f"nd_h5_d{index}"
        correlation = f"corr_h5_{index}"
        # One situation in 17 is filed under the uncovered domain.
        domain = "support" if index % 17 == 0 else "sales"
        # One in 13 has gone silent for longer than the 90-day staleness window.
        last_seen = eval_time - timedelta(days=200 if index % 13 == 0 else 3)
        for node, node_type in ((anchor, "company"), (deal, "deal")):
            conn.execute(sql(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name, "
                " valid_from) values (:n, 1, :o, :t, :n, :f) on conflict do nothing"),
                {"n": node, "o": _ORG, "t": node_type, "f": eval_time - timedelta(days=300)})
        conn.execute(sql(
            "insert into context_correlations (correlation_id, org_id, anchor_node_id, "
            " anchor_type, domain, generation, first_event_at, last_event_at, event_count) "
            "values (:c, :o, :a, 'company', :d, 1, :f, :l, :n) "
            "on conflict (correlation_id) do nothing"),
            {"c": correlation, "o": _ORG, "a": anchor, "d": domain,
             "f": eval_time - timedelta(days=300), "l": last_seen, "n": 1 + index % 3})

        # STEP 2's input: 1..3 DISTINCT source systems per situation, so corroboration spans its
        # whole 0..1500 range rather than sitting at one value.
        first_signal = None
        for slot, source in enumerate(("gmail", "gcal", "gdrive")[:1 + index % 3]):
            event = f"evt_h5_{index}_{slot}"
            conn.execute(sql(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                " source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, 'conn', :s, 'email_message', :e, :e, "
                " cast(:actor as jsonb), :t)"),
                {"e": event, "o": _ORG, "s": source, "t": last_seen,
                 "actor": json.dumps({"email": f"p{index}@peer.example",
                                      "type": "external_contact"})})
            conn.execute(sql("insert into context_correlation_members (org_id, correlation_id, "
                             "event_id) values (:o, :c, :e)"),
                         {"o": _ORG, "c": correlation, "e": event})
            # STEP 1's base. One situation in 29 publishes NO qualified signal at all and lands on
            # the documented fallback — the `importance_source='default'` share the "< 5%" row is
            # really measuring now that the constant is gone.
            if index % 29 == 0:
                continue
            signal = f"sig_h5_{index}_{slot}"
            first_signal = first_signal or signal
            conn.execute(sql(
                "insert into qualified_signals (signal_id, org_id, event_id, trace_id, "
                " signal_type, importance_bp, importance_version, confidence_bp, visibility, "
                " extraction_ref, evidence_refs, importance_components, state, occurred_at) "
                "values (:s, :o, :e, :tr, 'commitment_made', :i, 'alg17-v1', 6200, "
                " cast('{\"scope\": \"org\"}' as jsonb), :x, "
                " cast('[{\"source_ref\": \"prepared_content:e\", \"quote\": \"q\"}]' as jsonb), "
                " cast('{\"base_bp\": 4000}' as jsonb), 'active', :t)"),
                # A wide, non-repeating spread: the base is what the distribution is mostly made
                # of, and a base with six values could not clear "distinct > 50" whatever the
                # modifiers did.
                {"s": signal, "o": _ORG, "e": event, "tr": f"tr_{index}_{slot}",
                 "i": 1500 + (index * 79 + slot * 11) % 7000, "x": f"ex_{index}_{slot}",
                 "t": last_seen})

        # The plain fact that makes the DEAL node one of this situation's subject nodes: it was
        # written by one of the correlation's own events. Every derived fact below hangs off it.
        conn.execute(sql(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            " value, value_type, status, created_by_event_id, valid_from) values "
            "(:v, :f, :o, :n, 'deal.stage', cast(:val as jsonb), 'string', 'active', :e, :t)"),
            {"v": f"fv_stage_{index}", "f": f"f_stage_{index}", "o": _ORG, "n": deal,
             "val": json.dumps("negotiation"), "e": f"evt_h5_{index}_0",
             "t": eval_time - timedelta(days=30)})

        def _derived(field: str, body: dict) -> None:
            conn.execute(sql(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                " field, value, value_type, status, valid_from) values "
                "(:v, :f, :o, :n, :field, cast(:val as jsonb), 'json', 'active', :t)"),
                {"v": f"fv_{field}_{index}", "f": f"f_{field}_{index}", "o": _ORG, "n": deal,
                 "field": field, "val": json.dumps(body),
                 "t": eval_time - timedelta(days=7)})

        if index % 3 == 0:
            _derived("derived.trend.engagement.touch_count_28d",
                     {"metric": "engagement.touch_count_28d", "direction": "declining",
                      "trend_confidence_bp": 6_000, "point_count": 8})
        elif index % 3 == 1:
            # A COMPARISON THAT EXISTS AND DOES NOT QUALIFY — the case that separates "the
            # importance leaned on this" from "the org happens to hold this". Rising engagement is
            # a real trend on a subject node of this situation, and modifier 3a must not fire on
            # it; nor may the sixth axis score it, or the axis would report the certainty of a
            # comparison that moved nothing.
            _derived("derived.trend.engagement.touch_count_28d",
                     {"metric": "engagement.touch_count_28d", "direction": "rising",
                      "trend_confidence_bp": 7_500, "point_count": 9})
        if index % 5 == 0:
            # HIGHER_IS_WORSE, at the top of a cohort of twelve — deciles are expressible at
            # n >= 11, so the worst band here really is D10.
            _derived("derived.cohort_position.engagement.days_since_contact",
                     {"metric": "engagement.days_since_contact", "percentile_bp": 9_600,
                      "population_size": 12, "cohort_id": "co_h5", "band": "D10"})
        elif index % 5 == 2:
            # Mid-cohort on the same risk metric: a position, correctly measured, that says this
            # subject is unremarkable. Same non-qualifying role as the rising trend above.
            _derived("derived.cohort_position.engagement.days_since_contact",
                     {"metric": "engagement.days_since_contact", "percentile_bp": 5_100,
                      "population_size": 12, "cohort_id": "co_h5", "band": "D6"})
        if index % 7 == 0:
            _derived("derived.anomaly.support.ticket_count_28d",
                     {"metric": "support.ticket_count_28d", "flagged": True,
                      "periods_used": 6, "z_like_bp": 40_000})
        elif index % 7 == 3:
            # The detector looked and found nothing unusual. `flagged` is False, not absent —
            # "we checked" is a different fact from "we never checked", and neither raises
            # importance nor counts as a comparison the number leaned on.
            _derived("derived.anomaly.support.ticket_count_28d",
                     {"metric": "support.ticket_count_28d", "flagged": False,
                      "periods_used": 6, "z_like_bp": 400})
        if index % 4 == 0:
            _derived("derived.dependency.blocked_count", {"count": 1 + index % 5})
        if index % 11 == 0 and first_signal:
            conn.execute(sql(
                "insert into signal_conflicts (conflict_id, org_id, signal_id, field, "
                " subject_key, claims, resolution) values "
                "(:c, :o, :s, 'contract.value', :k, cast('[]' as jsonb), :r)"),
                {"c": f"cf_h5_{index}", "o": _ORG, "s": first_signal,
                 "k": f"peer{index}", "r": UNRESOLVED_RESOLUTION})


def _drop_h5_org(conn, sql) -> None:
    for table in ("signal_conflicts", "qualified_signals", "context_correlation_members",
                  "source_events", "graph_facts", "graph_nodes", "context_situations",
                  "context_correlations", "source_coverage"):
        conn.execute(sql(f"delete from {table} where org_id = :o"), {"o": _ORG})
    conn.execute(sql("delete from orgs where id = :o"), {"o": _ORG})


@pytest.fixture
def h5_org(pg_store, eval_time):
    """The tenant, seeded and swept through the PRODUCTION functions, then torn down.

    `refresh_situations` writes the rows; `refresh_situation_importance` composes and stores their
    importance. These are the two calls `context/runner` makes, in the order it makes them — and
    that the ordering in the runner is this one is asserted separately, on the runner's source, by
    `test_the_ranking_pass_runs_behind_every_analytic_pass_that_feeds_it`.
    """
    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import refresh_situation_importance
    from genios_engine.context.situations import refresh_situations

    with pg_store.engine.begin() as conn:
        _drop_h5_org(conn, sql)
        _seed_h5_org(conn, sql, eval_time)
    try:
        written = refresh_situations(pg_store, _ORG, eval_time=eval_time)
        assert written == _SITUATIONS, f"the sweep wrote {written} situations, not {_SITUATIONS}"
        ranked = refresh_situation_importance(pg_store, _ORG, eval_time=eval_time)
        assert ranked == _SITUATIONS, f"the sweep ranked {ranked} situations, not {written}"
        yield pg_store
    finally:
        with pg_store.engine.begin() as conn:
            _drop_h5_org(conn, sql)


def _report(pg_store, eval_time):
    """The GATE SCRIPT's own report, over the stored columns. Not a re-implementation: the same
    functions `scripts/situation_importance_distribution.py --org … --since 30d` runs."""
    from scripts.situation_importance_distribution import build_report
    with pg_store.engine.connect() as conn:
        return build_report(conn, org_id=_ORG, since=eval_time - timedelta(days=30),
                            until=eval_time + timedelta(minutes=1))


@pytest.mark.pg
def test_the_production_sweep_produces_a_rankable_distribution(h5_org, eval_time) -> None:
    """**H5, END TO END.** Five rows, measured off `context_situations` after the real sweep.

    If this comes out flat the fix is NOT to move a threshold: the per-modifier assertion below
    and the report's own `modifier_fires` table say which input stopped arriving, and a gate
    passed by tuning is the same failure as the constant it replaced.
    """
    report = _report(h5_org, eval_time)

    assert report.composed == _SITUATIONS, (
        f"only {report.composed} of {report.situations} situations carry a composed importance — "
        "a null is invisible to this gate rather than failing it, which is why it is checked "
        "first")
    assert report.distinct > MIN_DISTINCT, (
        f"{report.distinct} distinct scores over {report.composed} situations "
        f"(gate > {MIN_DISTINCT}); most common: {report.top_scores}")
    assert report.spread_bp > MIN_SPREAD_BP, (
        f"p90 {report.p90_bp} - p50 {report.p50_bp} = {report.spread_bp} "
        f"(gate > {MIN_SPREAD_BP}) — a flat distribution cannot rank")
    assert report.default_share_bp < MAX_FLAT_SHARE_BP, (
        f"{report.at_default} of {report.composed} situations sit at exactly {FLAT_BASE_BP} "
        f"({report.default_share_bp} bp, gate < {MAX_FLAT_SHARE_BP}); base sources: "
        f"{report.sources}")
    assert report.components_bp == 10_000, (
        f"{report.with_components}/{report.composed} carry importance_components — "
        "'why is this a 7400' must be answerable from stored data")
    assert report.passed, report.as_dict()
    assert report.versions == ("l2-situation-importance.v1",)
    # The supply guard did NOT fire: this tenant's Layer 1 scores are a real spread, so a flat
    # result here could only have been the composer's fault.
    assert report.suppressed == 0


@pytest.mark.pg
def test_every_modifier_fires_on_the_production_path(h5_org, eval_time) -> None:
    """**THE DIAGNOSTIC ROW, and the reason a flat gate is never fixed by tuning.** Six modifiers,
    six independent reads — a derived fact family, a conflict table, the situation's own last
    evidence date. A modifier that never fires is a dead rule, and 15 of Layer 1's 21 deep sales
    rules were dead for exactly this reason: their input existed, and the join to it did not.

    Named individually so a failure says WHICH read stopped working rather than "the distribution
    went flat".
    """
    report = _report(h5_org, eval_time)
    fires = dict(report.modifier_fires)
    for name in ModifierName:
        assert fires.get(name.value, 0) > 0, (
            f"the {name.value} modifier fired on none of {report.composed} situations — its "
            f"input is seeded, so the join that reads it is broken. All fires: {fires}")
    print(f"\n  H5, production path — {report.composed} situations, {report.distinct} distinct, "
          f"p50 {report.p50_bp} / p90 {report.p90_bp} (spread {report.spread_bp})")
    for name, count in report.modifier_fires:
        print(f"    {name:<18} {count:>3} / {report.composed}")


@pytest.mark.pg
def test_the_stored_record_explains_the_number_without_recomputing_it(h5_org) -> None:
    """H5's explainability row, as a PROPERTY rather than a count. Every stored record is read
    back through `stored_importance` — a parse, no facts, no cohorts, no clock — and its own terms
    must re-derive the stored number exactly."""
    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import stored_importance

    with h5_org.engine.connect() as conn:
        rows = conn.execute(sql(
            "select situation_id, importance_bp, importance_components, confidence_analytic "
            "from context_situations where org_id = :o"), {"o": _ORG}).mappings().all()
    assert len(rows) == _SITUATIONS
    for row in rows:
        composed = stored_importance(row)
        assert composed is not None, f"{row['situation_id']} stored an unreadable record"
        assert composed.importance_bp == row["importance_bp"]
        # The arithmetic, re-derived from the stored terms alone.
        modifiers = sum(term.delta_bp for term in composed.modifiers)
        assert composed.subtotal_bp == (composed.base_bp + composed.corroboration_bp
                                        + composed.modifier_total_bp)
        assert composed.modifier_total_bp == modifiers - composed.modifier_cap_removed_bp
        assert composed.importance_bp == (composed.subtotal_bp + composed.coverage_penalty_bp
                                          + composed.clamp_delta_bp)
        assert len(composed.modifiers) == len(ModifierName), "a term went missing from the record"


@pytest.mark.pg
def test_the_sixth_axis_reaches_the_row_and_only_when_a_comparison_was_used(h5_org) -> None:
    """L2.5.1's analytic axis, ADOPTED. It existed as a scored field that nothing ever passed an
    input to, so every situation ever written reported it not-applicable — a dimension that cannot
    fail is not a dimension.

    The axis is scored from the comparisons the IMPORTANCE LEANED ON, so the two must agree row by
    row: a situation whose trend, cohort and anomaly modifiers were all silent used no comparison
    and keeps the sentinel; one where any of the three fired carries a real 0..100 score."""
    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import stored_importance
    from genios_engine.context.situations import COVERAGE_UNKNOWN, SCORE_MAX

    comparative = {ModifierName.TREND, ModifierName.COHORT_POSITION, ModifierName.ANOMALY}
    with h5_org.engine.connect() as conn:
        rows = conn.execute(sql(
            "select situation_id, importance_components, confidence_analytic, inputs "
            "from context_situations where org_id = :o"), {"o": _ORG}).mappings().all()
    scored = 0
    #: Situations that HOLD a comparison which did not qualify — a rising trend, a mid-cohort
    #: position, an unflagged anomaly. These are the rows that separate "leaned on" from
    #: "available", and without at least one of them the assertion below would pass against an
    #: axis scored from everything the org happens to hold.
    held_but_unused = 0
    for row in rows:
        composed = stored_importance(row)
        assert composed is not None
        leaned = any(composed.term(name).fired for name in comparative)
        analytic = row["confidence_analytic"]
        inputs = row["inputs"] if isinstance(row["inputs"], dict) else json.loads(row["inputs"])
        if leaned:
            scored += 1
            assert 0 <= analytic <= SCORE_MAX, (
                f"{row['situation_id']} leaned on a comparison and scored {analytic}")
            assert inputs["analytic_known"] is True
            assert inputs["analytic_weakest"] != "no comparative input"
        else:
            if any(composed.term(name).reason not in
                   (ModifierReason.NO_INPUT, ModifierReason.SUPPRESSED) for name in comparative):
                held_but_unused += 1
            assert analytic == COVERAGE_UNKNOWN, (
                f"{row['situation_id']} used no comparison and still scored {analytic} — "
                "absence of a comparison is not bad comparative evidence")
            assert inputs["analytic_known"] is False
    assert scored, "no situation in the fixture leaned on a comparison"
    assert held_but_unused, (
        "no situation in the fixture HOLDS a comparison that did not qualify, so this test "
        "cannot tell an axis scored from what the importance leaned on apart from one scored "
        "from everything the org has")


@pytest.mark.pg
def test_a_second_sweep_over_an_unchanged_graph_rewrites_an_identical_record(h5_org,
                                                                            eval_time) -> None:
    """**THE WRITE-AMPLIFICATION GUARD, on the production path.** The stored record reaches
    `BusinessSituationObject.metadata`, `to_semantic_dict` hashes that into the expertise package's
    content address, and anything derived from the clock there mints a fresh ~238 kB package row
    per situation per sweep. That mechanism put 995 MB on one tenant's database — 67% of the whole
    database — and took the project read-only, which stops every write the product makes.

    So the pass is run a SECOND time, at a DIFFERENT instant, over an unchanged graph, and every
    stored body must come back byte-identical."""
    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import refresh_situation_importance

    def _bodies() -> dict[str, str]:
        with h5_org.engine.connect() as conn:
            return {str(row["situation_id"]): json.dumps(
                row["importance_components"] if isinstance(row["importance_components"], dict)
                else json.loads(row["importance_components"]), sort_keys=True)
                for row in conn.execute(sql(
                    "select situation_id, importance_components from context_situations "
                    "where org_id = :o"), {"o": _ORG}).mappings()}

    before = _bodies()
    refresh_situation_importance(h5_org, _ORG, eval_time=eval_time + timedelta(days=1))
    after = _bodies()
    changed = [sid for sid in before if before[sid] != after[sid]]
    assert not changed, (
        f"{len(changed)} records changed when only the clock did, e.g. {changed[:3]} — a "
        "per-sweep value in this body re-mints one expertise package per situation per sweep")


def _plain(value):
    """A frozen contract value as plain dicts and lists. `BusinessSituationObject` deep-freezes
    metadata into mappingproxies and tuples, and `json.dumps(..., default=str)` would stringify a
    mappingproxy whole rather than descend into it — comparing two such strings passes for the
    wrong reason."""
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


@pytest.mark.pg
def test_the_layer_three_object_carries_the_composed_number_not_the_base(h5_org) -> None:
    """**THE HALF-WIRED STATE THIS CATCHES.** A BSO can carry the composed RECORD and still
    publish Layer 1's base as its `importance_bp` — the record explains 7400 while the object
    ranks at 6000, and every assertion about explainability passes. Layer 3 then reasons, and
    Layer 4 ranks, on the number BLG-18 exists to replace.

    Read through the live compile's own query (`domain_shadow._ACTIVE_SITUATIONS`) and built with
    the builder it uses, on the situations where the two numbers actually DIFFER — a fixture where
    every modifier happened to be silent would prove nothing.
    """
    from sqlalchemy import text as sql

    from genios_engine.contracts.visibility import Visibility
    from genios_engine.context.situation_bso import (
        build_business_situation, stored_importance,
    )
    from genios_engine.reason.domain_shadow import _ACTIVE_SITUATIONS

    with h5_org.engine.connect() as conn:
        rows = conn.execute(sql(_ACTIVE_SITUATIONS), {"o": _ORG, "lim": _SITUATIONS}).mappings()
        rows = list(rows)
    assert rows, "the live compile's own query returned nothing to publish"

    moved = 0
    for row in rows:
        composed = stored_importance(row)
        assert composed is not None
        bso = build_business_situation(
            org_id=_ORG, situation=row, signal_ids=["sig"], evidence=[{"event_id": "e"}],
            trace_id="tr", visibility=Visibility(scope="org", derived_from="test"),
            composed=composed)
        assert bso.importance_bp == composed.importance_bp, (
            f"{row['situation_id']} publishes {bso.importance_bp} while its stored composition "
            f"says {composed.importance_bp}")
        # Normalised, because the contract freezes metadata into mappingproxies and tuples on
        # the way in. What must match is the CONTENT — the record a reader gets back.
        assert _plain(bso.metadata["importance_components"]) == _plain(composed.as_record())
        if composed.importance_bp != composed.base_bp:
            moved += 1
            assert bso.importance_bp != composed.base_bp, (
                f"{row['situation_id']} published Layer 1's base ({composed.base_bp}) although "
                f"steps 2..6 moved it to {composed.importance_bp}")
    assert moved > _SITUATIONS // 4, (
        f"only {moved} of {len(rows)} situations had their base moved by steps 2..6 — this test "
        "cannot see the defect on a fixture where the composition is a no-op")


def test_the_base_still_names_its_four_sources_apart() -> None:
    """**A-1's invariant, pinned where the branch now lives.** Step 1 was already built when this
    unit started, and lifting its four-way branch out of `build_business_situation` into
    `importance_base` is exactly the kind of refactor that silently merges two arms: `l1_unscored`
    (live signals the floor could not measure) and `l1_all_retired` (ALG-19 has retired every one)
    both land on `DEFAULT_IMPORTANCE_BP`, so collapsing them changes no number and destroys the
    only field that says WHY a situation sits at the fallback.

    The fallback itself is asserted REACHABLE, not absent: `DEFAULT_IMPORTANCE_BP` is the correct
    answer for a situation whose events published no live score, and deleting it would replace a
    documented neutral with a zero that ranks unmeasured situations below every measured one.
    """
    from genios_engine.context.situation_bso import (
        DEFAULT_IMPORTANCE_BP, L1Signals, importance_base,
    )

    scored = importance_base(L1Signals(signal_ids=("s1",), scored_signal_ids=("s1",),
                                       importance_bp=8_100, importance_version="alg17-v1",
                                       signal_count=1, scored_count=1))
    assert (scored.importance_bp, scored.source) == (8_100, "l1_qualified_signals")
    assert scored.signal_id == "s1" and scored.version == "alg17-v1"

    unscored = importance_base(L1Signals(signal_ids=("s2",), importance_bp=None,
                                         importance_version="unscored", signal_count=1,
                                         scored_count=0))
    assert (unscored.importance_bp, unscored.source) == (DEFAULT_IMPORTANCE_BP, "l1_unscored")

    retired = importance_base(L1Signals(signal_ids=("s3",), importance_bp=None,
                                        importance_version="unscored", signal_count=0))
    assert (retired.importance_bp, retired.source) == (DEFAULT_IMPORTANCE_BP, "l1_all_retired")

    absent = importance_base(None)
    assert (absent.importance_bp, absent.source) == (DEFAULT_IMPORTANCE_BP, "default")
    assert absent.signal_id is None and absent.version is None

    assert len({scored.source, unscored.source, retired.source, absent.source}) == 4, (
        "two of the four sources now report the same word — a situation on the fallback can no "
        "longer say which of the four reasons put it there")
