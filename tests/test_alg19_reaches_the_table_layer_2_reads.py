"""ALG-19 aged the signal; did Layer 2 ever hear about it?

THE SPLIT. `capture/esqe/lifecycle.sweep_lifecycle` decides that a stored signal is superseded or
expired and `PostgresLifecycleStore.put` writes that to `signal_lifecycle`.
`context/situation_bso.gather_l1_signals` — the one production reader of Layer 1's output —
decides a situation's live importance from `qualified_signals.state = 'active'`. Those are two
different tables, and until this file only ONE of them was ever written by the ageing pass:
`publish_sweep` stores the signals of the CURRENT sweep, and the signals ALG-19 supersedes or
expires are by definition the ones stored by an EARLIER one.

So `signal_lifecycle` said `superseded` while `qualified_signals` still said `active`, and
migration 0093's own stated purpose — *"a renewal signal about a contract that was cancelled is
dead, and must be marked so"* — did not reach the layer that acts on it. A founder kept being
nudged about a renewal that a later, equally-authoritative email had already replaced.

Real Postgres, because the divergence is between two tables and an in-memory pair can be made to
agree by construction.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.capture.esqe import lifecycle as L
from genios_engine.capture.esqe.lifecycle import PostgresLifecycleStore, sweep_lifecycle
from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.capture.esqe.signal_store import PostgresSignalStore
from genios_engine.capture.esqe.source_analyzer import ActorBasis, SourceAttribution
from genios_engine.capture.validate.authority import AuthorityBasis, AuthorityWeight
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.visibility import Visibility

pytestmark = pytest.mark.pg

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
ORG = "org_alg19_reaches_l2"
SUBJECT = "acct:kestrel"
KIND = SignalType.CONTRACT_RENEWAL
STORED = "sig_stored_by_an_earlier_sweep"
VIS = ('{"scope":"org","principals":[],"excluded_subjects":[],'
       '"derived_from":"test:alg19_reach"}')
EVIDENCE = ('[{"source_ref":"prepared_content:old","start_offset":0,"end_offset":3,'
            '"quote":"abc","verified":true}]')


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
                               else "{}" if dt in ("json", "jsonb") else "alg19")
    conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                      "on conflict (id) do nothing"), vals)


def _seed_earlier_sweep(engine) -> None:
    """What last month's sweep left behind: one published signal and its lifecycle row."""
    with engine.begin() as c:
        _seed_org(c)
        for table in ("qualified_signals", "signal_lifecycle"):
            c.execute(text(f"delete from {table} where org_id=:o"), {"o": ORG})
        c.execute(text(
            "insert into qualified_signals (signal_id,org_id,event_id,trace_id,signal_type,"
            "importance_bp,importance_version,confidence_bp,visibility,extraction_ref,"
            "evidence_refs,state,occurred_at) values (:s,:o,'evt_old','tr_old',:k,9000,"
            "'alg17-v1',8000,cast(:v as jsonb),'x_old',cast(:e as jsonb),'active',:at)"),
            {"s": STORED, "o": ORG, "k": KIND.value, "at": NOW - timedelta(days=30),
             "v": VIS, "e": EVIDENCE})
        c.execute(text(
            "insert into signal_lifecycle (org_id,signal_id,subject_key,signal_type,"
            "authority_rank,occurred_at,state,evaluated_at) "
            "values (:o,:s,:sub,:k,2,:at,'active',:ev)"),
            {"o": ORG, "s": STORED, "sub": SUBJECT, "k": KIND.value,
             "at": NOW - timedelta(days=30), "ev": NOW - timedelta(days=30)})


def _todays_sweep():
    """One newer, equally-authoritative signal about the same subject — what replaces the old."""
    signal = NormalizedSignal(
        org_id=ORG, event_id="evt_new", source="gmail", object_type="email_message",
        occurred_at=NOW - timedelta(hours=2),
        visibility=Visibility(scope="org", derived_from="source:gmail"),
        recipients=("ops@genios.ai",), internal_kind=None,
        signal_type=KIND, predicate="renewal_window_open",
        subject_key=SUBJECT, subject_label="Kestrel MSA renewal",
        primary_entity="Kestrel Systems", primary_date=None, primary_amount=None,
        evidence_refs=(EvidenceSpan(source_ref="prepared_content:new", quote="Kestrel",
                                    start_offset=0, end_offset=7, verified=True),),
        attribution=SourceAttribution(
            evidence=AuthorityWeight(authority=Authority.EMAIL_PROSE,
                                     basis=AuthorityBasis.OBJECT_TYPE),
            actor_authority_bp=6000, actor_basis=ActorBasis.ROLE_LADDER,
            actor_email="cfo@kestrel.example"))
    result = SimpleNamespace(
        event=SimpleNamespace(event_id="evt_new", occurred_at=NOW - timedelta(hours=2)),
        esqe=SimpleNamespace(normalized=(signal,), importance=()))
    return SimpleNamespace(org_id=ORG, results=[result], conflicts=None)


def _states(engine) -> tuple[dict, dict]:
    with engine.connect() as c:
        published = dict(c.execute(text(
            "select signal_id, state from qualified_signals where org_id=:o"), {"o": ORG}).all())
        lifecycle = dict(c.execute(text(
            "select signal_id, state from signal_lifecycle where org_id=:o"), {"o": ORG}).all())
    return published, lifecycle


def test_a_supersession_reaches_qualified_signals_not_just_signal_lifecycle(pg_store, monkeypatch):
    """THE ASSERTION. One ageing sweep, and BOTH tables agree about what is still live."""
    url = pg_store.engine.url.render_as_string(hide_password=False)
    engine = pg_store.engine
    _seed_earlier_sweep(engine)

    signals = PostgresSignalStore(url)
    outcome = sweep_lifecycle(_todays_sweep(), org_id=ORG, store=PostgresLifecycleStore(url))
    moved = [t.after.signal_id for t in outcome.superseded]
    assert moved == [STORED], (
        f"ALG-19 superseded {moved}; without a real transition this test proves nothing")

    signals.apply_lifecycle(outcome.records)

    published, lifecycle = _states(engine)
    assert lifecycle[STORED] == L.SUPERSEDED, "signal_lifecycle lost the supersession"
    assert published[STORED] == L.SUPERSEDED, (
        "`signal_lifecycle` says superseded and `qualified_signals` still says "
        f"{published[STORED]!r} — Layer 2 filters on the SECOND, so a replaced signal keeps "
        "setting a live situation's importance for ever")


def test_the_pass_never_invents_a_row_for_a_signal_that_never_published(pg_store):
    """A lifecycle row exists for every signal the sweep normalized; a `qualified_signals` row
    exists only for the ones the gate EMITTED. Propagation must update what is there and never
    insert — a signal V-1 refused must not reappear as published because it aged."""
    url = pg_store.engine.url.render_as_string(hide_password=False)
    engine = pg_store.engine
    _seed_earlier_sweep(engine)
    with engine.begin() as c:
        c.execute(text("delete from qualified_signals where org_id=:o"), {"o": ORG})

    outcome = sweep_lifecycle(_todays_sweep(), org_id=ORG, store=PostgresLifecycleStore(url))
    written = PostgresSignalStore(url).apply_lifecycle(outcome.records)

    with engine.connect() as c:
        rows = c.execute(text("select count(*) from qualified_signals where org_id=:o"),
                         {"o": ORG}).scalar()
    assert written == 0 and rows == 0, (
        "the lifecycle pass created a published signal out of a lifecycle row")


def test_an_active_record_never_reopens_a_signal_the_gate_retired(pg_store):
    """The propagation carries ALG-19's verdict; it is not a second opinion about `active`.
    A record that is still live must leave a row that some other pass closed exactly as it is."""
    url = pg_store.engine.url.render_as_string(hide_password=False)
    engine = pg_store.engine
    _seed_earlier_sweep(engine)
    with engine.begin() as c:
        c.execute(text("update qualified_signals set state='resolved' where org_id=:o "
                       "and signal_id=:s"), {"o": ORG, "s": STORED})

    record = L.LifecycleRecord(
        org_id=ORG, signal_id=STORED, subject_key=SUBJECT, signal_type=KIND.value,
        authority_rank=2, occurred_at=NOW - timedelta(days=30), state=L.ACTIVE,
        supersedes=None, expires_at=None, evaluated_at=NOW)
    assert PostgresSignalStore(url).apply_lifecycle((record,)) == 0

    with engine.connect() as c:
        state = c.execute(text("select state from qualified_signals where org_id=:o "
                               "and signal_id=:s"), {"o": ORG, "s": STORED}).scalar()
    assert state == "resolved", "an 'active' lifecycle record reopened a retired signal"


def test_the_sync_door_carries_the_lifecycle_onto_the_published_rows():
    """The store method is not the fix; the CALL is — and the ORDER of the calls.

    The sequence moved out of `api/routes._run_ledger` into `capture/esqe/finalize.finalize_l1`
    when the upload door needed to reach it too (a `run_sync` hook covers exactly the callers of
    `run_sync`, and an uploaded contract is not one). Both halves are still asserted, because
    both can break independently: the sync door must REACH the sequence, and the sequence must
    keep its order."""
    import inspect

    from genios_engine.api import routes
    from genios_engine.capture.esqe import finalize

    door = inspect.getsource(routes._run_ledger)
    assert "finalize_l1(" in door, (
        "the sync door no longer reaches L1's finalizer — nothing qualifies, ages or publishes")

    source = inspect.getsource(finalize.finalize_l1)
    assert "apply_lifecycle" in source, (
        "the finalizer computes the lifecycle and never carries it onto `qualified_signals`")
    assert source.index("sweep_lifecycle(") < source.index("apply_lifecycle"), (
        "the verdict is applied before it is decided")
    assert source.index("apply_lifecycle") < source.index("publish_sweep("), (
        "this sweep's own signals must be published AFTER the retirement pass, or a signal "
        "published and retired in one sweep is written back as active")
