"""STEP-10 · a sweep says its source and when it finished, so the signals it publishes carry its coverage.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_coverage_is_written_per_signal.py -q

`capture/acquire/sync_runner.SyncSummary` and `api/routes._run_ledger` (tree `yc2_w27_s10 ·
M29.C5.L-data.V0.U01`). Per-signal coverage was NULL on 28 of 28 golden signals (`STEP-18` B5). The
publisher builds the block from the sweep's `source`, `started_at` and `finished_at`
(`capture/esqe/publisher._coverage_of`), and the real summary carried only the start: no source and no
finish, so `_coverage_of` returned None for every sweep `run_sync` ever produced. The publisher's own
test fed it a stand-in that had both names, which is how the gap stayed green. And the
`l1_sync_runs` insert never named `finished_at`: the row took the column default `now()`, the wall
clock, so a replay read its own runs at the hour the suite happened to run (STEP-10 N8). Now the
summary names its source where the run starts and its finish off the clock seam its start came from,
the ledger row records that finish, and a signal published off a real sweep carries the block.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.acquire import sync_runner as S
from genios_engine.capture.acquire.cursor_store import InMemoryCursorStore
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.esqe.publisher import _coverage_of
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

#: The case's instant: in August, so a value off the wall clock (October, when this was written)
#: can never be mistaken for one off the seam.
T0 = datetime(2026, 8, 7, 18, 0, tzinfo=timezone.utc)
ORG = "org_s10_coverage_signal"
CONN = "con_s10_coverage_signal"


class _Clock:
    """The `_now` seam, moving one minute on every read — a start and a finish taken from it are
    equal only if they came from the same read."""

    def __init__(self, at: datetime) -> None:
        self.reads: list[datetime] = []
        self._at = at

    def __call__(self) -> datetime:
        self.reads.append(self._at)
        self._at += timedelta(minutes=1)
        return self.reads[-1]


def _mail(*ids: str) -> list[RawObject]:
    return [RawObject("gmail", "email_message", i, T0 - timedelta(hours=1),
                      actor_email=f"{i}@kestrel.test",
                      raw={"subject": f"Renewal {i}", "snippet": "Can we confirm the renewal?"})
            for i in ids]


class _Mailbox:
    """Three messages and the provider's estimate of them; two pages when asked to backfill."""

    source = "gmail"

    def incremental_changes(self, cursor=None, limit=100, since=None):
        return SourceBatch(objects=_mail("m1", "m2", "m3"), next_cursor=None, claimed_total=3)

    def initial_snapshot(self, cursor=None, limit=100):
        if cursor is None:
            return SourceBatch(objects=_mail("b1", "b2"), next_cursor="page2", claimed_total=3)
        return SourceBatch(objects=_mail("b3"), next_cursor=None, claimed_total=3)

    def validate_connection(self) -> bool:
        return True


def _sync(**kw):
    kw.setdefault("_now", lambda: T0)
    return S.run_sync(_Mailbox(), org_id=ORG, connection_id=CONN,
                      repo=InMemorySourceEventRepository(), **kw)


# =================================================================================================
# The summary says what it read and when — set where the run starts and where it ends
# =================================================================================================

def test_a_sweep_names_the_source_it_read():
    assert _sync().source == "gmail"


def test_a_sweep_says_when_it_finished_off_the_clock_its_start_came_from():
    clock = _Clock(T0)
    summary = _sync(_now=clock)
    assert summary.started_at == T0
    assert summary.finished_at == clock.reads[-1] and summary.finished_at > summary.started_at, (
        "the finish did not come off the run's own clock seam")


def test_a_frozen_replay_stamps_one_instant_for_start_and_finish():
    """N8: a replay frozen at the case's instant records that instant, not the hour it ran."""
    summary = _sync()
    assert (summary.started_at, summary.finished_at) == (T0, T0)


def test_a_poll_the_cadence_declined_names_its_source_and_never_says_it_finished():
    """Nothing was fetched: a skipped poll did not run, so it did not finish either."""
    cursors = InMemoryCursorStore(clock=lambda: T0 - timedelta(minutes=1))
    cursors.save(ORG, CONN, "gmail", cursor=None, watermark=T0 - timedelta(minutes=1))
    with S.scheduled_sweep():
        summary = _sync(cursor_store=cursors)
    assert summary.skipped_not_due is True
    assert (summary.source, summary.finished_at) == ("gmail", None)


def test_a_backfill_says_its_source_its_first_start_and_its_last_finish():
    clock = _Clock(T0)
    total = S.backfill_drain(_Mailbox(), org_id=ORG, connection_id=CONN,
                             repo=InMemorySourceEventRepository(), source="gmail",
                             pages_per_round=1, _now=clock)
    assert len(clock.reads) == 4, "two rounds, each read for its start and for its finish"
    assert (total.source, total.started_at, total.finished_at) == ("gmail", T0, clock.reads[-1])


def test_a_real_sweep_gives_the_publisher_a_coverage_block():
    """B5 at the producer, on a summary `run_sync` built — not on a stand-in that has the names."""
    block = _coverage_of(_sync())
    assert block is not None, "a real sweep still gives the publisher no window or no source"
    assert (block.window_from, block.window_to) == (T0, T0)
    (gmail,) = block.sources
    assert (gmail.source, gmail.indexed, gmail.claimed_total, gmail.is_estimate,
            gmail.cursor_exhausted, gmail.completeness_bp) == ("gmail", 3, 3, True, True, 10_000)


# =================================================================================================
# The ledger row says when the run finished — through the hook every sync caller passes
# =================================================================================================

@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the ledger and the signal store need Postgres")
    return live_db_url


@pytest.fixture
def tenant(pg_url):
    from genios_engine.platform.db import get_engine

    engine = get_engine(pg_url)

    def _drop():
        with engine.begin() as conn:      # `l1_sync_runs` and `qualified_signals` cascade from it
            conn.execute(text("delete from orgs where id = :o"), {"o": ORG})

    _drop()
    with engine.begin() as conn:
        cols = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        names, params = ["id"], {"id": ORG}
        for col in cols:
            names.append(col.column_name)
            params[col.column_name] = (0 if "int" in col.data_type or "numeric" in col.data_type
                                       else T0 if "timestamp" in col.data_type else ORG)
        conn.execute(text(f"insert into orgs ({', '.join(names)}) values "
                          f"({', '.join(':' + n for n in names)})"), params)
    yield engine
    _drop()


def _runs(engine) -> list:
    with engine.connect() as conn:
        return conn.execute(text(
            "select started_at, finished_at, scanned, claimed_total, cursor_exhausted, error "
            "from l1_sync_runs where org_id = :o order by finished_at"), {"o": ORG}).all()


@pytest.mark.pg
def test_the_ledger_row_records_when_the_run_finished_not_when_it_was_filed(tenant, monkeypatch):
    from genios_engine.api import routes

    monkeypatch.setattr(routes, "_l1_stores", lambda: routes.L1Stores())
    clock = _Clock(T0)
    _sync(_now=clock, run_ledger=routes._run_ledger)
    (row,) = _runs(tenant)
    assert row.started_at == T0
    assert row.finished_at == clock.reads[-1], (
        "the row took the database's clock — a replay would read its runs at the hour it ran")
    assert (row.scanned, row.claimed_total, row.cursor_exhausted) == (3, 3, True)


@pytest.mark.pg
def test_a_total_failure_still_files_a_row_and_its_finish_is_when_it_was_recorded(tenant,
                                                                                  monkeypatch):
    """No summary, no clock of its own: the failure is recorded when it is noticed. The column is
    NOT NULL, so a finish named without a fallback would cost the failure its row."""
    from genios_engine.api import routes

    monkeypatch.setattr(routes, "_l1_stores", lambda: routes.L1Stores())
    before = datetime.now(timezone.utc) - timedelta(minutes=5)
    routes._run_ledger(org_id=ORG, connection_id=CONN, source="gmail", mode="incremental",
                       error="401 credentials revoked")
    (row,) = _runs(tenant)
    assert row.error == "401 credentials revoked" and row.started_at is None
    assert row.finished_at is not None and row.finished_at > before


# =================================================================================================
# The signal carries the block — a real sweep, the production hook, the Postgres signal store
# =================================================================================================

@dataclass
class _Intent:
    observed_anything: bool = True


@dataclass
class _Esqe:
    normalized: tuple
    intent: _Intent = field(default_factory=_Intent)
    intent_disagreements: tuple = ()
    classification: object = None
    domains: object = None


@dataclass
class _Gated:
    triage_lane: str = "P1"
    coverage_ready: bool | None = True
    versions: dict = field(default_factory=lambda: {"preprocessor": "pp-2", "gate_rules": "gate-1"})
    domain_hints: list = field(default_factory=list)


@dataclass
class _Captured:
    """What `capture_event` returns for an emitted message, reduced to what the sweep and the four
    L1 seams read. Stood in for the pipeline because the qualifier needs a model's extraction; the
    event, the sweep, the hook, the floor, the gate and the store are the real ones."""

    event: object
    esqe: _Esqe
    gated: _Gated = field(default_factory=_Gated)
    outcome: str = "emitted"
    extraction: object = None
    extraction_ref: str | None = "l1x_s10_coverage"
    extraction_parked: object = None
    prepared: object = None


def _captured(raw: RawObject, **_kw) -> _Captured:
    """One emitted message carrying one renewal signal, its claim resting on the signal's span."""
    from genios_engine.capture.esqe.normalize import NormalizedSignal
    from genios_engine.capture.esqe.source_analyzer import ActorBasis, SourceAttribution
    from genios_engine.capture.validate.authority import AuthorityBasis, AuthorityWeight
    from genios_engine.contracts.conflict import Authority
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.contracts.extraction import Commitment, ExtractionResult
    from genios_engine.contracts.signal import SignalType
    from genios_engine.contracts.source_event import Actor, SourceEvent
    from genios_engine.contracts.visibility import Visibility

    quote, body = "confirm the renewal", "Can we confirm the renewal?"
    start = body.index(quote)
    span = EvidenceSpan(source_ref=f"prepared_content:pc_{raw.source_object_id}", quote=quote,
                        start_offset=start, end_offset=start + len(quote), verified=True)
    signal = NormalizedSignal(
        org_id=ORG, event_id=f"evt_{raw.source_object_id}", source="gmail",
        object_type="email_message", occurred_at=raw.occurred_at,
        visibility=Visibility(scope="org", derived_from="source:gmail"),
        recipients=("ops@genios.test", raw.actor_email), internal_kind=None,
        signal_type=SignalType.CONTRACT_RENEWAL, predicate="renewal_window_open",
        subject_key=f"thread:{raw.source_object_id}", subject_label="Kestrel renewal",
        primary_entity="Kestrel", primary_date=None, primary_amount=None,
        evidence_refs=(span,),
        attribution=SourceAttribution(
            evidence=AuthorityWeight(authority=Authority.SIGNED_DOCUMENT,
                                     basis=AuthorityBasis.EXECUTED),
            actor_authority_bp=8000, actor_basis=ActorBasis.ROLE_LADDER,
            actor_email=raw.actor_email))
    extraction = ExtractionResult(
        intent="inform", stance="neutral",
        commitments=[Commitment(actor="Kestrel", action="confirm", is_conditional=False,
                                evidence=[span], confidence_bp=8000)],
        model_snapshot="fake-model-1", prompt_version="p1", schema_version="1",
        extraction_profile="email", input_tokens=1000, output_tokens=200)
    event = SourceEvent(event_id=signal.event_id, org_id=ORG, connection_id=CONN, source="gmail",
                        source_family="communication", object_type="email_message",
                        source_object_id=raw.source_object_id,
                        dedup_key=f"gmail:{raw.source_object_id}",
                        actor=Actor(type="external_contact", email=raw.actor_email),
                        occurred_at=raw.occurred_at, captured_at=T0)
    return _Captured(event=event, esqe=_Esqe(normalized=(signal,)), extraction=extraction)


@pytest.mark.pg
def test_a_signal_published_off_a_real_sweep_carries_the_sweeps_coverage(tenant, pg_url,
                                                                          monkeypatch):
    """Nothing here calls the publisher: three messages go into `run_sync` with the production
    ledger hook, and `qualified_signals` rows come out — each with the sweep's block."""
    from genios_engine.api import routes
    from genios_engine.capture.esqe import qualification as Q
    from genios_engine.capture.esqe.signal_store import PostgresSignalStore

    monkeypatch.setattr(S, "capture_event", _captured)
    monkeypatch.setattr(routes, "_l1_stores", lambda: routes.L1Stores(
        floors=Q.InMemoryFloorStore({ORG: 1}), drops=Q.InMemoryDropLedger(),
        signals=PostgresSignalStore(pg_url)))

    _sync(run_ledger=routes._run_ledger)

    with tenant.connect() as conn:
        blocks = [r.coverage for r in conn.execute(text(
            "select coverage from qualified_signals where org_id = :o"), {"o": ORG})]
    assert len(blocks) == 3, "the sweep published nothing — the test proves no coverage"
    assert all(b is not None for b in blocks), "a published signal still carries no coverage"
    for block in blocks:
        (gmail,) = block["sources"]
        assert gmail == {"source": "gmail", "indexed": 3, "claimed_total": 3, "is_estimate": True,
                         "cursor_exhausted": True, "completeness_bp": 10_000}
        assert block["window_from"] == block["window_to"], "a frozen replay has a one-instant window"
        assert block["window_from"].startswith("2026-08-07"), block["window_from"]
