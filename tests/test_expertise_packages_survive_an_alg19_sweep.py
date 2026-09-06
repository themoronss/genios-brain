"""ALG-19 ageing a tenant's signals must not write a single new `expertise_packages` row.

THE INCIDENT THIS IS THE SECOND ARMING OF. `expertise_packages` is content-addressed and
regenerable, and it reached 4,086 rows / 995 MB on the design partner's database — 67% of the
whole database for 127 distinct situations — because two OBSERVATION fields (`trace_id`, and the
slice's `evaluation_time`) were being hashed as CONTENT. The publisher's
`on conflict (org_id, expertise_id) do nothing` never fired, every sweep wrote a fresh ~238 kB
row per situation, and the project crossed its disk quota into read-only, which stops every
write the product makes.

`tests/test_repeat_compile_does_not_grow_the_database.py` closed that mechanism for the CLOCK.
It cannot see this one. Reading `qualified_signals` gave the BSO a second unstable input — the
LIFECYCLE READING, i.e. which of a situation's signals happen to be `state='active'` at the
instant the sweep looked. ALG-19 expires and supersedes signals on every sync, so on a tenant
with hundreds of situations the reading moves constantly while the knowledge does not, and each
move re-mints the situation hash, the expertise id, and the row. Same mechanism, new input.

WHAT MAY AND MAY NOT MOVE THE ADDRESS. A situation's IMPORTANCE is content: if the score moved,
Layer 3 is looking at a different situation and a new package is correct (asserted below, so this
file is a fix and not a mute button). Which signals are still live, how many there are, and which
disagreements they took part in are a reading of the moment — the same category as `trace_id` and
`eval_time`, both of which this codebase already refuses to hash.

Real Postgres, because a row count is the only thing that says whether the disk grew: an
in-memory publisher keys on the id and so agrees with the bug.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.capture.esqe.lifecycle import (
    ACTIVE,
    EXPIRED,
    SUPERSEDED,
    LifecycleRecord,
    apply_expiries,
    apply_supersessions,
)
from genios_engine.context.domain_spec import spec_for
from genios_engine.context.situation_bso import (
    build_business_situation,
    gather_evidence_and_signals,
    gather_l1_signals,
)
from genios_engine.packs.compiler import (
    DomainCompiler,
    ExpertBrainCatalog,
    InMemoryExpertisePublisher,
    InMemoryRuntimeBrains,
)
from genios_engine.packs.compiler.expertise_publisher import PostgresExpertisePublisher

# `tests/` is not a package and this repo sets no pytest `importmode`, so a plain sibling import
# resolves only when pytest happens to have imported the other module first. Load it explicitly —
# the alternative is a second copy of the authoring corpus that drifts away from the compiler it
# was copied from. Same device, same reason, as `test_repeat_compile_does_not_grow_the_database`.
_SPEC = importlib.util.spec_from_file_location(
    "_compiler_fixtures_alg19",
    pathlib.Path(__file__).with_name("test_domain_expertise_compiler.py"))
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["_compiler_fixtures_alg19"] = _mod
_SPEC.loader.exec_module(_mod)

NOW = _mod.NOW
_authoring_root = _mod._authoring_root
_context = _mod._context

ORG = "org_alg19_amp"
CORRELATION = "corr_alg19_amp"
SITUATION = "sit_alg19_amp"
VISIBILITY = json.dumps({"scope": "org", "principals": [], "excluded_subjects": [],
                         "derived_from": "test:alg19"})

#: The four signals this situation rests on. `sig_top` carries the highest score and neither
#: expires nor is superseded, so the situation's IMPORTANCE is identical either side of the
#: sweep — which is what makes a re-minted package unambiguously write amplification and not a
#: score that legitimately moved.
_SEED = (
    # signal_id,   event,    type,                subject,      importance, occurred, expires
    ("sig_top_00", "evt_top", "contract_renewal",  "acme:renew", 9000, -30, None),
    ("sig_old_00", "evt_old", "deadline_stated",   "acme:date",  4000, -20, -1),
    ("sig_prev_0", "evt_prev", "commitment_made",  "acme:commit", 3000, -10, None),
    ("sig_next_0", "evt_next", "commitment_made",  "acme:commit", 3500, -5, None),
)


def _seed_org(conn) -> None:
    reqd = conn.execute(text(
        "select column_name, data_type from information_schema.columns where table_name='orgs' "
        "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
    cols, ph, vals = ["id"], [":id"], {"id": ORG}
    for r in reqd:
        cols.append(r.column_name)
        ph.append(f":{r.column_name}")
        dt = r.data_type
        vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                               else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                               else False if dt == "boolean"
                               else "{}" if dt in ("json", "jsonb") else "scratch")
    conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                      "on conflict (id) do nothing"), vals)


def _seed(engine) -> None:
    with engine.begin() as c:
        _seed_org(c)
        for table in ("qualified_signals", "context_correlation_members", "expertise_packages"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        for signal_id, event_id, kind, subject, bp, days, expiry in _SEED:
            c.execute(text(
                "insert into context_correlation_members (org_id, correlation_id, event_id) "
                "values (:o,:c,:e) on conflict do nothing"),
                {"o": ORG, "c": CORRELATION, "e": event_id})
            c.execute(text(
                "insert into qualified_signals (signal_id,org_id,event_id,trace_id,signal_type,"
                "importance_bp,importance_components,importance_version,confidence_bp,visibility,"
                "extraction_ref,evidence_refs,conflict_ids,state,expires_at,occurred_at,"
                "authority_rank) values (:s,:o,:e,:t,:k,:i,cast(:comp as jsonb),'alg17-v1',8000,"
                "cast(:v as jsonb),:x,cast(:ev as jsonb),cast(:cf as jsonb),'active',:exp,:at,3)"),
                {"s": signal_id, "o": ORG, "e": event_id, "t": f"trace_{event_id}", "k": kind,
                 "i": bp, "v": VISIBILITY, "x": f"l1x_{signal_id}",
                 # The sweep's frozen instant rides inside the components. It is already excluded
                 # from the address by `_UNSTABLE_COMPONENT`; carrying it here keeps that
                 # exclusion under test rather than assuming it.
                 "comp": json.dumps({"monetary_exposure_bp": bp,
                                     "eval_time": NOW.isoformat()}),
                 "ev": json.dumps([{"source_ref": f"prepared_content:{signal_id}",
                                    "start_offset": 0, "end_offset": 5, "quote": "hello",
                                    "verified": True}]),
                 "cf": json.dumps([f"conflict_{signal_id}"]),
                 "exp": (NOW + timedelta(days=expiry)) if expiry is not None else None,
                 "at": NOW + timedelta(days=days)})


def _situation_row() -> dict:
    return {"situation_id": SITUATION, "situation_type": spec_for("sales").type_for("company"),
            "domain": "sales", "status": "active", "correlation_id": CORRELATION,
            "confidence_overall": 82, "coverage": 70, "first_seen_at": NOW,
            "last_seen_at": NOW, "anchor_node_id": "account_1", "anchor_name": "Acme",
            "anchor_type": "company"}


def _sweep(engine, tmp_path, *, trace: str):
    """One sweep's L2 -> L3 compile, driven the way `domain_shadow.shadow_compile` drives it.

    A FRESH compiler per sweep, deliberately: production runs each sweep in a process holding no
    memory of the last one, so reusing one would prove the in-memory dedup works and nothing
    about the id.
    """
    with engine.connect() as conn:
        signal_ids, evidence = gather_evidence_and_signals(conn, ORG, CORRELATION, SITUATION)
        l1 = gather_l1_signals(conn, ORG, CORRELATION)
        bso = build_business_situation(
            org_id=ORG, situation=_situation_row(), signal_ids=signal_ids, evidence=evidence,
            trace_id=trace, l1=l1)
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path)),
        require_admission=False,
        runtime_brains=InMemoryRuntimeBrains(),
        publisher=InMemoryExpertisePublisher(),
    )
    context = _context(org_id=ORG)
    package = compiler.compile(bso, context=context)
    with engine.begin() as conn:
        PostgresExpertisePublisher(conn).publish(package)
    return bso, package


def _footprint(engine) -> tuple[int, int]:
    """Rows and stored bytes. A row REWRITTEN rather than inserted is the same incident at a
    different scale, so the byte total is asserted beside the count."""
    with engine.connect() as conn:
        return conn.execute(text(
            "select count(*), coalesce(sum(pg_column_size(payload)), 0) "
            "from expertise_packages where org_id = :o"), {"o": ORG}).one()


def _age_the_signals(engine):
    """Run ALG-19 itself over these signals and write back what it decided.

    The states come from `apply_expiries` / `apply_supersessions` rather than from a hand-written
    UPDATE, so the test cannot invent a transition the state machine would refuse.
    """
    records = tuple(
        LifecycleRecord(org_id=ORG, signal_id=signal_id, subject_key=subject, signal_type=kind,
                        authority_rank=3, occurred_at=NOW + timedelta(days=days), state=ACTIVE,
                        supersedes=None,
                        expires_at=(NOW + timedelta(days=expiry)) if expiry is not None else None,
                        evaluated_at=NOW)
        for signal_id, _event, kind, subject, _bp, days, expiry in _SEED)
    expired, aged = apply_expiries(records, eval_time=NOW)
    superseded, final = apply_supersessions(aged, eval_time=NOW)
    with engine.begin() as conn:
        for record in final:
            conn.execute(text(
                "update qualified_signals set state=:s, supersedes=:sup, expires_at=:e "
                "where org_id=:o and signal_id=:id"),
                {"s": record.state, "sup": record.supersedes, "e": record.expires_at,
                 "o": ORG, "id": record.signal_id})
    return expired, superseded, final


@pytest.mark.pg
def test_an_alg19_sweep_writes_no_new_expertise_package(pg_store, tmp_path):
    """THE ASSERTION. A signal expires, another is superseded, and the table does not grow."""
    engine = pg_store.engine
    with engine.connect() as c:
        if not c.execute(text("select to_regclass('public.expertise_packages')")).scalar():
            pytest.skip("expertise_packages migration not applied")
    _seed(engine)

    before_bso, before_pkg = _sweep(engine, tmp_path, trace="trace_sweep_1")
    before = _footprint(engine)
    assert before[0] == 1, f"the first compile did not publish exactly one package: {before}"

    expired, superseded, final = _age_the_signals(engine)

    # The sweep must actually have moved something, or the assertion below is vacuous.
    assert [m.after.signal_id for m in expired] == ["sig_old_00"], (
        f"ALG-19 expired {[m.after.signal_id for m in expired]}, not the dated signal")
    assert [m.after.signal_id for m in superseded] == ["sig_prev_0"], (
        f"ALG-19 superseded {[m.after.signal_id for m in superseded]}")
    states = {r.signal_id: r.state for r in final}
    assert states["sig_old_00"] == EXPIRED and states["sig_prev_0"] == SUPERSEDED
    assert states["sig_top_00"] == ACTIVE, "the scoring signal must survive the sweep"

    after_bso, after_pkg = _sweep(engine, tmp_path, trace="trace_sweep_2")
    after = _footprint(engine)

    # The situation is worth exactly what it was worth: nothing about it CHANGED, ALG-19 merely
    # re-read it. Stated first so a failure below is unambiguously amplification.
    assert after_bso.importance_bp == before_bso.importance_bp == 9000

    # (rows, bytes). The row count is what says whether the disk grew; the byte total is beside
    # it because a row REWRITTEN rather than inserted is the same incident at a different scale.
    assert after == before, (
        f"`expertise_packages` grew across one lifecycle sweep: {before} -> {after}. This is the "
        "995 MB read-only incident's exact mechanism with the lifecycle reading as its input.")
    assert after_pkg.id == before_pkg.id, (
        "an ALG-19 transition minted a new expertise id for unchanged knowledge — "
        f"{before_pkg.id} -> {after_pkg.id}")


@pytest.mark.pg
def test_a_score_that_actually_moved_still_mints_a_new_package(pg_store, tmp_path):
    """The other half, and what makes the fix a fix. If the highest-scoring live signal expires,
    the situation IS worth less and Layer 3 must be told — a content address that ignored that
    would serve last month's ranking for ever."""
    engine = pg_store.engine
    with engine.connect() as c:
        if not c.execute(text("select to_regclass('public.expertise_packages')")).scalar():
            pytest.skip("expertise_packages migration not applied")
    _seed(engine)

    before_bso, before_pkg = _sweep(engine, tmp_path, trace="trace_score_1")
    with engine.begin() as conn:
        conn.execute(text("update qualified_signals set state='expired', expires_at=:e "
                          "where org_id=:o and signal_id='sig_top_00'"),
                     {"o": ORG, "e": NOW - timedelta(days=1)})
    after_bso, after_pkg = _sweep(engine, tmp_path, trace="trace_score_2")

    assert before_bso.importance_bp == 9000
    assert after_bso.importance_bp == 4000, (
        "the situation kept a score its only live signals cannot support")
    assert after_pkg.id != before_pkg.id, "a situation that got cheaper kept its old package"
    assert _footprint(engine)[0] == 2


@pytest.mark.pg
def test_a_situations_provenance_does_not_decay_as_its_signals_age(pg_store, tmp_path):
    """The other thing the state filter was doing, and the reason the fix is not just a hash
    tweak. `signal_ids` and `evidence` are the situation's account of what it was built from. A
    receipt does not stop being a receipt when its clock runs out — filtered by state, an old
    situation ended up able to name none of the signals that produced it."""
    engine = pg_store.engine
    with engine.connect() as c:
        if not c.execute(text("select to_regclass('public.expertise_packages')")).scalar():
            pytest.skip("expertise_packages migration not applied")
    _seed(engine)

    before_bso, _ = _sweep(engine, tmp_path, trace="trace_prov_1")
    _age_the_signals(engine)
    after_bso, _ = _sweep(engine, tmp_path, trace="trace_prov_2")

    every = tuple(sorted(row[0] for row in _SEED))
    assert before_bso.signal_ids == every
    assert after_bso.signal_ids == every, (
        "the situation forgot the signals ALG-19 retired — "
        f"{after_bso.signal_ids} instead of {every}")
    refs = {e.get("source_ref") for e in after_bso.evidence}
    assert "prepared_content:sig_old_00" in refs, "the expired signal's receipt was dropped"
    assert "prepared_content:sig_prev_0" in refs, "the superseded signal's receipt was dropped"
    # …and the LIVE reading still reads live, because that is what sets the score.
    with engine.connect() as conn:
        l1 = gather_l1_signals(conn, ORG, CORRELATION)
    assert l1.signal_count == 2, "the state filter stopped applying to the score"
    assert l1.importance_bp == 9000


@pytest.mark.pg
def test_a_situation_whose_signals_have_all_retired_says_so(pg_store, tmp_path):
    """`importance_source` must not call this `l1_unscored`. Live-but-unmeasured and
    nothing-live-left are different facts, and a reader deciding whether to trust the neutral
    default needs to know which one produced it."""
    from genios_engine.context.situation_bso import DEFAULT_IMPORTANCE_BP

    engine = pg_store.engine
    _seed(engine)
    with engine.begin() as conn:
        conn.execute(text("update qualified_signals set state='expired', expires_at=:e "
                          "where org_id=:o"), {"o": ORG, "e": NOW - timedelta(days=1)})

    with engine.connect() as conn:
        signal_ids, evidence = gather_evidence_and_signals(conn, ORG, CORRELATION, SITUATION)
        l1 = gather_l1_signals(conn, ORG, CORRELATION)
        bso = build_business_situation(
            org_id=ORG, situation=_situation_row(), signal_ids=signal_ids, evidence=evidence,
            trace_id="trace_retired", l1=l1)

    assert bso.metadata["importance_source"] == "l1_all_retired"
    assert bso.importance_bp == DEFAULT_IMPORTANCE_BP
    assert bso.metadata["l1_signal_count"] == len(_SEED), (
        "the provenance count followed the lifecycle instead of the signal set")
    assert l1.signal_count == 0 and l1.scored_count == 0
