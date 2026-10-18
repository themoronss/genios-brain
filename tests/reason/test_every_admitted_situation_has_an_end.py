"""STEP-06 · the compiled lane records what came of every admitted live situation.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_every_admitted_situation_has_an_end.py -q

Tree `yc2_w27_s06 · M24.C2.L-logic.V2.U01`. The admission gate records admit / hold / reject and the
change gate every decided subject; what ended in between — no route, an incomplete slice, a conflict,
a required field missing, an unsupported shape, no tenant pack, today's budget, an error — was a
counter in one log line (`speedrun008/YC-II W27/` STEP-06 §8). Now each admitted live candidate gets
one `situation_outcomes` row: `decided` (with the change gate's word for it), or the stop and its
reason. A second pass with nothing new moves the count, not the rows; a measurement pass writes
nothing. Real Postgres, real Layer 1 ingestion, real corpus — the seeding `test_weld_reaches_a_signal`
uses, imported so the two cannot drift.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.context import situations

from ..l1_supply import attach_l1_signals
from ..test_admin_support_packs import NOW, _run_admin, _seed_org

pytestmark = pytest.mark.pg


def _ready(pg_store, org):
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    _seed_org(pg_store, org)
    # RE-RUNNABLE ON ONE DATABASE: every run publishes at the same `NOW`, so an earlier run's
    # admission decisions would tie with this run's on `decided_at` — the tenant's ledgers go first.
    with pg_store.engine.begin() as conn:
        for table in ("situation_outcomes", "situation_admission_decisions", "signals"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
    _run_admin(pg_store, org)
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    assert attach_l1_signals(pg_store, org, eval_time=NOW) > 0
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    return registry


def _admitted_and_ends(pg_store, org):
    with pg_store.engine.connect() as conn:
        admitted = {r.decision_id: r.situation_id for r in conn.execute(text(
            "select distinct on (situation_id) situation_id, decision_id, outcome "
            "  from situation_admission_decisions where org_id = :o "
            " order by situation_id, decided_at desc, decision_id desc"), {"o": org})
            if r.outcome == "admit"}
        ends = {r.decision_id: (r.outcome, r.reason, r.sweeps) for r in conn.execute(text(
            "select decision_id, outcome, reason, sweeps from situation_outcomes "
            " where org_id = :o"), {"o": org})}
    return admitted, ends


def test_every_admitted_live_candidate_has_its_end(pg_store):
    from genios_engine.reason.domain_shadow import shadow_compile
    org = "so_ends_decided"
    registry = _ready(pg_store, org)
    counts = shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True,
                            registry=registry)
    assert counts.get("emitted", 0) > 0, dict(counts)
    admitted, ends = _admitted_and_ends(pg_store, org)
    assert admitted, "nothing was admitted to assert on"
    assert set(admitted) <= set(ends), sorted(set(admitted) - set(ends))
    assert ("decided", "emitted", 1) in ends.values(), ends


def test_a_second_pass_with_nothing_new_moves_the_count_not_the_rows(pg_store):
    from genios_engine.reason.domain_shadow import shadow_compile
    org = "so_ends_twice"
    registry = _ready(pg_store, org)
    shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True, registry=registry)
    _, first = _admitted_and_ends(pg_store, org)
    shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True, registry=registry)
    _, second = _admitted_and_ends(pg_store, org)
    assert set(second) == set(first)
    for decision_id, (outcome, reason, sweeps) in first.items():
        assert second[decision_id][:2] == (outcome, reason)   # the end it was given stays
        assert second[decision_id][2] == sweeps + 1


@pytest.mark.parametrize("raised, expected", [
    ("no_route", ("no_route", "predicate_rejected")),
    ("incomplete", ("incomplete", None)),
    ("conflict", ("conflict", None)),
    ("required_missing", ("required_missing", None)),
    ("unsupported", ("unsupported", "all_stub")),
    ("error", ("error", "RuntimeError")),
])
def test_a_stop_after_admission_is_recorded_with_its_reason(pg_store, monkeypatch, raised,
                                                            expected):
    from genios_engine.packs.compiler import DomainCompiler
    from genios_engine.packs.compiler import errors as E
    from genios_engine.reason.domain_shadow import shadow_compile

    def _stop(self, *args, **kwargs):
        raise {"no_route": lambda: E.NoExpertiseRoute("planted", reason="predicate_rejected"),
               "incomplete": lambda: E.SituationContextIncomplete("planted"),
               "conflict": lambda: E.SituationContextConflict("planted"),
               "required_missing": lambda: E.RequiredKnowledgeMissing("planted"),
               "unsupported": lambda: E.UnsupportedCoverage("all_stub", "planted"),
               "error": lambda: RuntimeError("planted")}[raised]()

    org = f"so_ends_{raised}"
    registry = _ready(pg_store, org)
    monkeypatch.setattr(DomainCompiler, "compile", _stop)
    shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True, registry=registry)
    admitted, ends = _admitted_and_ends(pg_store, org)
    assert admitted, "nothing was admitted to assert on"
    for decision_id in admitted:
        assert ends[decision_id][:2] == expected, ends


def test_a_measurement_pass_writes_nothing(pg_store):
    from genios_engine.reason.domain_shadow import shadow_compile
    org = "so_ends_measured"
    registry = _ready(pg_store, org)
    shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=False,
                   live_domains=frozenset(), registry=registry)
    with pg_store.engine.connect() as conn:
        n = conn.execute(text("select count(*) from situation_outcomes where org_id = :o"),
                         {"o": org}).scalar()
    assert n == 0
