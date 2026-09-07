"""Law 2, under the Y3 inputs: same situation + same brain snapshot = BYTE-IDENTICAL package.

This is the invariant every change in this wave sits inside. The compile is content-addressed, so
a set iterated in nondeterministic order, a dict that serialises differently or a clock that leaks
in does not produce a wrong answer — it produces a NEW package id for unchanged knowledge, the
publisher's `on conflict do nothing` never fires, and the table grows a ~238 kB row per situation
per sweep. That is not hypothetical: it reached 4,086 rows and 995 MB on the design partner's
database, 67% of the whole thing, and took the project read-only.

So byte-identity is asserted on the BYTES the publisher actually writes — `canonical_dumps` over
`to_semantic_dict()` — not on the id alone, and it is asserted with every one of this wave's new
inputs present: analytic facts on the slice, an activated pattern fire on the BSO, and typed
absences in the slice metadata.
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from l3_inputs import (NOW, anomaly_fact, build_situation, build_slice, cohort_fact,
                       trend_fact)
from sqlalchemy import text

from genios_engine.context.quality.inference import absence_metadata
from genios_engine.packs.compiler import (DomainCompiler, ExpertBrainCatalog,
                                          InMemoryRuntimeBrains)
from genios_engine.packs.compiler.context_adapter import (ANOMALY_FACT_PREFIX,
                                                          COHORT_POSITION_FACT_PREFIX,
                                                          TREND_FACT_PREFIX)
from genios_engine.packs.compiler.expertise_publisher import PostgresExpertisePublisher
from genios_engine.platform.canonical import canonicalize

WHEN = ("[{kind: trend, metric: engagement, direction: DECLINING, min_confidence_bp: 5000},"
        " {kind: cohort, metric: spend_growth, band: D1, min_population: 5},"
        " {kind: anomaly, metric: support_tickets},"
        " {kind: absence, fact: decision.scheduled, type: GENUINELY_ABSENT}]")

PATTERN = "pattern.renewal_at_risk"


def _analytic_facts():
    return {f"{TREND_FACT_PREFIX}engagement": {"value": trend_fact()},
            f"{COHORT_POSITION_FACT_PREFIX}spend_growth": {"value": cohort_fact()},
            f"{ANOMALY_FACT_PREFIX}support_tickets": {"value": anomaly_fact()}}


def _fire():
    return {"pattern_id": PATTERN, "pattern_version": "1.0.0", "pattern_activated": True,
            "pattern_match_strength_bp": 8_800,
            "matched_conditions": [{"condition": "auto_renew", "fact": "contract.auto_renew"}]}


def _bytes(package) -> str:
    """Exactly what `PostgresExpertisePublisher` stores in the jsonb column."""
    return json.dumps(canonicalize(package.to_semantic_dict()), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def _compiler(root, publisher=None):
    return DomainCompiler(catalog=ExpertBrainCatalog(root),
                          runtime_brains=InMemoryRuntimeBrains(),
                          publisher=publisher, require_admission=False)


def _sweep(compiler, *, trace: str, at, pattern: bool = True):
    """One sweep's compile, varying only what a real sweep varies: the trace id it mints per
    situation and the clock it reads once."""
    situation = build_situation(
        trace_id=trace,
        metadata=({**_fire(), "domain_ids": ["sales"]} if pattern else None))
    context = build_slice(facts=_analytic_facts(),
                          metadata=absence_metadata(absent=["decision.scheduled"],
                                                    unknowable=["contract.amendment"]),
                          trace_id=f"{trace}_ctx", evaluation_time=at)
    return compiler.compile(situation, context)


def test_two_compiles_of_one_situation_are_byte_identical(authoring_root):
    root = authoring_root(when=WHEN, pattern_when=WHEN, pattern_id=PATTERN)
    compiler = _compiler(root)
    first = _sweep(compiler, trace="trace_sweep_1", at=NOW)
    second = _sweep(compiler, trace="trace_sweep_2", at=NOW + timedelta(hours=6))

    assert _bytes(first) == _bytes(second), "the compile is not byte-stable across sweeps"
    assert first.id == second.id
    assert first.semantic_hash == second.semantic_hash
    assert first.brain_snapshot_id == second.brain_snapshot_id


def test_a_fresh_process_compiles_the_same_bytes(authoring_root):
    """A SECOND CATALOG AND A SECOND COMPILER, because production runs each sweep in a process
    that holds no memory of the last one. Dict insertion order, `frozenset` iteration and any
    per-process hash seed are the failure modes this catches and the single-compiler test cannot.
    """
    root = authoring_root(when=WHEN, pattern_when=WHEN, pattern_id=PATTERN)
    first = _sweep(_compiler(root), trace="trace_a", at=NOW)
    second = _sweep(_compiler(root), trace="trace_b", at=NOW + timedelta(days=2))
    assert _bytes(first) == _bytes(second)


def test_the_new_inputs_still_move_the_address_when_they_change(authoring_root):
    """The other half, and the one that makes byte-identity a property rather than a mute button.
    A package whose analytic inputs changed MUST mint a new id, or the compiled brain would serve
    a stale reading for ever."""
    root = authoring_root(when=WHEN, pattern_when=WHEN, pattern_id=PATTERN)
    compiler = _compiler(root)
    baseline = _sweep(compiler, trace="trace_a", at=NOW)

    situation = build_situation(trace_id="trace_c",
                               metadata={**_fire(), "domain_ids": ["sales"]})
    moved = build_slice(
        facts={**_analytic_facts(),
               f"{TREND_FACT_PREFIX}engagement": {"value": trend_fact(confidence_bp=9_100)}},
        metadata=absence_metadata(absent=["decision.scheduled"],
                                  unknowable=["contract.amendment"]),
        trace_id="trace_c_ctx", evaluation_time=NOW)
    after = compiler.compile(situation, moved)

    assert after.id != baseline.id
    assert _bytes(after) != _bytes(baseline)


def test_a_situation_with_no_pattern_fire_is_unchanged_by_this_wave(authoring_root):
    """The migration property, expressed as bytes: the routing receipt keys are written ONLY when
    a fire reached the compile, so every tenant without X6 — which is all of them today —
    compiles the package it compiled before this wave landed."""
    root = authoring_root(when="[]", pattern_when="[]", pattern_id=PATTERN)
    package = _compiler(root).compile(build_situation(), build_slice())
    body = json.loads(_bytes(package))
    assert "pattern_route_id" not in body["metadata"]
    assert "pattern_route_state" not in body["metadata"]


@pytest.fixture
def scratch_org(pg_store):
    """A tenant row `expertise_packages` can reference, built from the live column list so the
    fixture cannot drift from the schema."""
    org = "org_l3_y3_churn"
    with pg_store.engine.begin() as conn:
        required = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        columns, placeholders, values = ["id"], [":id"], {"id": org}
        for row in required:
            columns.append(row.column_name)
            placeholders.append(f":{row.column_name}")
            kind = row.data_type
            values[row.column_name] = (
                "2026-01-01T00:00:00Z" if ("time" in kind or "date" in kind)
                else 0 if ("int" in kind or "numeric" in kind or "double" in kind)
                else False if kind == "boolean"
                else "{}" if kind in ("json", "jsonb") else "scratch")
        conn.execute(text(f"insert into orgs ({', '.join(columns)}) "
                          f"values ({', '.join(placeholders)}) on conflict (id) do nothing"),
                     values)
        conn.execute(text("delete from expertise_packages where org_id = :o"), {"o": org})
    return org


def test_many_sweeps_over_an_unchanged_graph_write_one_row(pg_store, scratch_org, authoring_root):
    """MUST-NOT-REGRESS #10, measured on real Postgres, with the Y3 inputs live.

    Ten sweeps, each in a FRESH compiler (production holds no memory between sweeps), each with a
    new trace id and a later clock. One row. The row count is the only thing that says whether the
    disk grew — the in-memory publisher keys on the id and so agreed with the bug that filled it.
    """
    root = authoring_root(when=WHEN, pattern_when=WHEN, pattern_id=PATTERN)
    payloads = set()
    for index in range(10):
        package = _sweep(_compiler(root), trace=f"trace_run_{index}",
                         at=NOW + timedelta(hours=index))
        payloads.add(_bytes(package))
        with pg_store.engine.begin() as conn:
            object.__setattr__(package, "org_id", scratch_org)
            PostgresExpertisePublisher(conn).publish(package)

    assert len(payloads) == 1, "ten sweeps produced more than one payload for one situation"
    with pg_store.engine.connect() as conn:
        rows = conn.execute(text("select count(*) from expertise_packages where org_id=:o"),
                            {"o": scratch_org}).scalar()
    assert rows == 1, f"ten sweeps over an unchanged graph wrote {rows} packages"


def test_the_stored_payload_is_the_bytes_the_compiler_produced(pg_store, scratch_org,
                                                               authoring_root):
    """`PostgresExpertisePublisher` re-reads the row and refuses a mismatch, so a compile whose
    bytes differed from what Postgres holds raises rather than silently diverging. Driven here
    with the analytic facts and the pattern receipt on board — the fields this wave added."""
    root = authoring_root(when=WHEN, pattern_when=WHEN, pattern_id=PATTERN)
    package = _sweep(_compiler(root), trace="trace_stored", at=NOW)
    object.__setattr__(package, "org_id", scratch_org)
    with pg_store.engine.begin() as conn:
        PostgresExpertisePublisher(conn).publish(package)
    with pg_store.engine.connect() as conn:
        stored = conn.execute(text(
            "select payload from expertise_packages where org_id=:o and expertise_id=:i"),
            {"o": scratch_org, "i": package.id}).scalar()
    if isinstance(stored, str):
        stored = json.loads(stored)
    assert json.dumps(stored, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False) == _bytes(package)
    assert stored["metadata"]["pattern_route_id"] == PATTERN
    assert stored["metadata"]["matched_situation_ids"] == ["sales.sit.pattern"]
