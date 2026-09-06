"""G2 · L1.3.8-U1 — the SQL the ladder rides on, against a real PostgreSQL.

`test_refetch_drain.py` proves the state machine; this file proves the four things about it that
only a server can answer, and each one is a way the component could be silently wrong:

  * the CLAIM is a lease under concurrency — `for update … skip locked` means a cron and an
    operator's manual run cannot both fetch the same attachment, and the attempt is burned before
    the network call so a killed drain still terminates;
  * the RECOVERY is one transaction across four tables — payload, seam, ledger and park — because
    a crash between them leaves an event marked `emitted` whose body is still an empty stub, which
    is the original silent loss wearing a different hat;
  * the recovered event is then VISIBLE to L2 — asserted through the actual `context/runner.py`
    pull shape, not through a table we hope it reads;
  * the aging query is the G2 number, computed by the database.

Marked `pg`: without GENIOS_TEST_DATABASE_URL these skip, and the hermetic lane still refuses
sockets for everything else in this tree.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.documents.base import DocumentResult, DocumentStatus
from genios_engine.capture.parked.refetch import (PostgresRefetchQueue, read_aging,
                                                  refetch_parked_attachments)
from genios_engine.capture.parked.refetch_policy import DEFAULT_POLICY, ParkStatus
from genios_engine.platform.crypto import decrypt
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

ORG = "org_l1_refetch_pg"
KEY = "sxpepd0Y2jFCXW0Vjbb-EK_dQ9Yv9keeVdOOoNTk0eE="       # the test-only key tests/conftest pins
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
CONTRACT = "Master Services Agreement. Total contract value $84,000 payable annually."

_TABLES = ("prepared_content", "document_jobs", "raw_payloads", "parked_events", "source_events")


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres refetch tests skipped")
    eng = get_engine(live_db_url)
    _reset(eng)
    _seed_org(eng)
    yield eng
    _reset(eng)


def _reset(eng) -> None:
    """Data first, then the org row itself.

    Leaving the org behind would be a slow-acting bug in somebody else's file: several fixtures in
    this suite start with `select id from orgs limit 1`, and an empty org that outlives its test is
    a plausible answer to that query — the next module then seeds nothing, asserts on nothing, and
    passes for a reason its author never wrote down."""
    with eng.begin() as c:
        for table in _TABLES:
            c.execute(text(f"delete from {table} where org_id=:o"), {"o": ORG})
        c.execute(text("delete from orgs where id=:o"), {"o": ORG})


def _seed_org(eng) -> None:
    """An `orgs` row is required: migration 0033 puts an org FK on parked_events, and `not valid`
    skips the backfill check while still enforcing every INSERT. Required columns are discovered
    rather than listed so a later migration adding one does not turn this file into a skip."""
    with eng.begin() as c:
        if c.execute(text("select 1 from orgs where id=:o"), {"o": ORG}).scalar():
            return
        required = c.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, placeholders, values = ["id"], [":id"], {"id": ORG}
        for row in required:
            cols.append(row.column_name)
            placeholders.append(f":{row.column_name}")
            kind = row.data_type
            values[row.column_name] = ("2026-01-01T00:00:00Z" if ("time" in kind or "date" in kind)
                                       else 0 if ("int" in kind or "numeric" in kind)
                                       else False if kind == "boolean"
                                       else "{}" if kind in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                       f"({', '.join(placeholders)}) on conflict (id) do nothing"), values)


def _park_attachment(eng, *, event_id: str, reason: str = "DOC-05",
                     parked_at: datetime | None = None, attachment_id: str = "att456",
                     with_payload: bool = True) -> None:
    """One parked attachment stub, exactly as the connector + pipeline would have written it."""
    parked_at = parked_at or (NOW - timedelta(hours=3))
    payload = {"subject": "MSA-signed.pdf", "body": "", "mime": "application/pdf",
               "has_attachment": True, "to": ["founder@genios.ai"], "cc": [],
               "document": {"status": DocumentStatus.FETCH_FAILED.value}}
    from genios_engine.platform.crypto import encrypt
    with eng.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, parent_object_id, dedup_key, actor, occurred_at, captured_at, "
            "outcome, payload_ref) values (:e, :o, 'conn_1', 'gmail', 'email_attachment', "
            ":soid, 'm123', :dedup, cast('{}' as jsonb), :at, :at, 'parked', :pay)"),
            {"e": event_id, "o": ORG, "soid": f"m123::{attachment_id}",
             "dedup": f"dedup_{event_id}", "at": parked_at, "pay": f"pay_{event_id}"})
        if with_payload:
            c.execute(text(
                "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
                "expires_at) values (:id, :o, :e, 'application/json', :enc, :exp)"),
                {"id": f"pay_{event_id}", "o": ORG, "e": event_id,
                 "enc": encrypt(json.dumps(payload), KEY), "exp": NOW + timedelta(days=90)})
        c.execute(text(
            "insert into parked_events (event_id, org_id, source, reason_code, stage, status, "
            "created_at) values (:e, :o, 'gmail', :r, 'gate', 'pending', :at)"),
            {"e": event_id, "o": ORG, "r": reason, "at": parked_at})


class _Fetcher:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def fetch_attachment(self, message_id, attachment_id):
        self.calls.append((message_id, attachment_id))
        answer = self.answers.pop(0) if self.answers else b"%PDF bytes"
        if isinstance(answer, BaseException):
            raise answer
        return answer


def _accepted(*, mime=None, data=None, filename=None, ocr=None) -> DocumentResult:
    return DocumentResult(text=CONTRACT, native_parse_used=True, ocr_used=False, ocr_engine=None,
                          ocr_pages=2, confidence_bp=9_100,
                          status=DocumentStatus.ACCEPTED.value)


def _queue(live_db_url) -> PostgresRefetchQueue:
    return PostgresRefetchQueue(live_db_url, KEY)


def _drain(live_db_url, *, fetcher=None, now=NOW, extract=_accepted, org_id=ORG):
    return refetch_parked_attachments(
        _queue(live_db_url), connector_for=lambda _c: fetcher or _Fetcher(), eval_time=now,
        org_id=org_id, extract=extract)


# ── the claim ────────────────────────────────────────────────────────────────────────────────

def test_the_claim_selects_only_due_refetchable_attachments(engine, live_db_url):
    _park_attachment(engine, event_id="evt_due")
    _park_attachment(engine, event_id="evt_young", parked_at=NOW - timedelta(minutes=2))
    _park_attachment(engine, event_id="evt_wrong_reason", reason="low_relevance")
    with engine.begin() as c:
        c.execute(text("update source_events set object_type='email_message' "
                       "where event_id='evt_wrong_reason'"))
        c.execute(text("update parked_events set refetch_attempts=5 where event_id='evt_young'"))

    claimed = _queue(live_db_url).claim_due(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG)
    assert [c.event_id for c in claimed] == ["evt_due"]
    assert claimed[0].attempts == 0, "the row as it was when we decided to claim it"
    assert claimed[0].source_object_id == "m123::att456"


def test_the_claim_burns_the_attempt_and_hides_the_row_before_any_fetch(engine, live_db_url):
    _park_attachment(engine, event_id="evt_lease")
    queue = _queue(live_db_url)
    queue.claim_due(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG)

    with engine.connect() as c:
        row = c.execute(text("select refetch_attempts, refetch_next_attempt_at, "
                             "refetch_first_attempt_at from parked_events "
                             "where event_id='evt_lease'")).one()
    assert row.refetch_attempts == 1
    assert row.refetch_next_attempt_at == NOW + DEFAULT_POLICY.lease
    assert row.refetch_first_attempt_at == NOW
    # and it is invisible to the next claim until the lease expires
    assert queue.claim_due(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG) == ()
    assert len(queue.claim_due(eval_time=NOW + DEFAULT_POLICY.lease + timedelta(seconds=1),
                               policy=DEFAULT_POLICY, org_id=ORG)) == 1


def test_two_concurrent_drains_never_claim_the_same_attachment(engine, live_db_url):
    """`skip locked` is the whole reason a cron and a manual run are safe to overlap."""
    for i in range(4):
        _park_attachment(engine, event_id=f"evt_c{i}", attachment_id=f"att{i}")
    first = _queue(live_db_url).claim_due(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG,
                                          limit=2)
    second = _queue(live_db_url).claim_due(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG,
                                           limit=4)
    ids_first = {c.event_id for c in first}
    ids_second = {c.event_id for c in second}
    assert len(ids_first) == 2 and len(ids_second) == 2
    assert ids_first.isdisjoint(ids_second)


def test_the_claim_ignores_other_tenants(engine, live_db_url):
    _park_attachment(engine, event_id="evt_mine")
    claimed = _queue(live_db_url).claim_due(eval_time=NOW, policy=DEFAULT_POLICY,
                                            org_id="org_someone_else")
    assert claimed == ()


# ── the recovery ─────────────────────────────────────────────────────────────────────────────

def test_a_recovered_attachment_reaches_every_table_L2_reads(engine, live_db_url):
    _park_attachment(engine, event_id="evt_recover")
    report = _drain(live_db_url, fetcher=_Fetcher(b"%PDF real bytes"))
    assert report.recovered == 1

    with engine.connect() as c:
        park = c.execute(text("select status, refetch_attempts, refetch_next_attempt_at, "
                              "refetch_last_error from parked_events "
                              "where event_id='evt_recover'")).one()
        # the exact shape context/runner.py::_pull uses
        pulled = c.execute(text(
            "select se.event_id, rp.enc_content, pc.clean_text as prepared_text "
            "  from source_events se "
            "  join raw_payloads rp on rp.event_id = se.event_id "
            "  left join prepared_content pc on pc.event_id = se.event_id "
            " where se.org_id=:o and se.outcome='emitted'"), {"o": ORG}).all()
        job = c.execute(text("select status, avg_confidence, ocr_pages, format "
                             "from document_jobs where event_id='evt_recover'")).one()

    assert (park.status, park.refetch_attempts) == (ParkStatus.RECOVERED.value, 1)
    assert park.refetch_next_attempt_at is None and park.refetch_last_error is None
    assert len(pulled) == 1, "exactly one row, so the payload was UPDATED not duplicated"
    body = json.loads(decrypt(bytes(pulled[0].enc_content), KEY))
    assert "84,000" in body["body"] and body["to"] == ["founder@genios.ai"]
    assert "Master Services Agreement" in pulled[0].prepared_text
    assert job.status == DocumentStatus.ACCEPTED.value
    assert str(job.avg_confidence) == "0.910", "9100 bp stored exactly, no float rounding"
    assert job.ocr_pages == 2 and job.format == "application/pdf"


def test_recovering_twice_does_not_double_anything(engine, live_db_url):
    _park_attachment(engine, event_id="evt_idem")
    _drain(live_db_url, fetcher=_Fetcher(b"%PDF bytes"))
    # force it back onto the ladder and recover again — the guarded transition must be a no-op
    with engine.begin() as c:
        c.execute(text("update parked_events set status='pending', refetch_attempts=0, "
                       "refetch_next_attempt_at=null where event_id='evt_idem'"))
    _drain(live_db_url, fetcher=_Fetcher(b"%PDF bytes"), now=NOW + timedelta(hours=1))

    with engine.connect() as c:
        assert c.execute(text("select count(*) from raw_payloads where event_id='evt_idem'")
                         ).scalar() == 1
        assert c.execute(text("select count(*) from prepared_content where event_id='evt_idem'")
                         ).scalar() == 1
        assert c.execute(text("select outcome from source_events where event_id='evt_idem'")
                         ).scalar() == "emitted"


def test_a_recovery_whose_payload_expired_writes_a_new_one_and_repoints_the_ledger(engine,
                                                                                   live_db_url):
    """The raw payload has a TTL; the park can outlive it. Losing the recipients is a cost, but
    losing the CONTRACT because a blob expired is not one the ladder is allowed to pay."""
    _park_attachment(engine, event_id="evt_no_payload", with_payload=False)
    assert _drain(live_db_url, fetcher=_Fetcher(b"%PDF bytes")).recovered == 1

    with engine.connect() as c:
        row = c.execute(text(
            "select se.payload_ref, rp.id from source_events se "
            "join raw_payloads rp on rp.event_id = se.event_id "
            "where se.event_id='evt_no_payload'")).one()
    assert row.payload_ref == row.id, "the ledger points at the payload that now exists"


# ── failure, aging, the admin surface ────────────────────────────────────────────────────────

def test_a_transient_failure_persists_the_ladder_state(engine, live_db_url):
    _park_attachment(engine, event_id="evt_retry")
    _drain(live_db_url, fetcher=_Fetcher(RuntimeError("ReadTimeout: upstream")))

    with engine.connect() as c:
        row = c.execute(text("select status, refetch_attempts, refetch_next_attempt_at, "
                             "refetch_last_error from parked_events "
                             "where event_id='evt_retry'")).one()
    assert row.status == ParkStatus.PENDING.value and row.refetch_attempts == 1
    assert row.refetch_next_attempt_at == NOW + timedelta(seconds=600)
    assert "ReadTimeout" in row.refetch_last_error
    with engine.connect() as c:
        assert c.execute(text("select outcome from source_events where event_id='evt_retry'")
                         ).scalar() == "parked"


def test_the_aging_query_is_the_gate_number(engine, live_db_url):
    _park_attachment(engine, event_id="evt_old", parked_at=NOW - timedelta(hours=9))
    _park_attachment(engine, event_id="evt_fresh", parked_at=NOW - timedelta(minutes=20),
                     attachment_id="att2")
    aging = _queue(live_db_url).aging(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG)

    assert aging.pending == 2
    assert aging.stuck == 1 and aging.stuck_attachments == 1
    assert aging.stuck_after_seconds == 3_600
    row = next(r for r in aging.rows if r.reason_code == "DOC-05")
    assert row.object_type == "email_attachment"
    assert row.oldest_age_seconds == 9 * 3_600, "whole seconds, computed by the database"


def test_dead_letters_are_a_queryable_console_and_can_be_requeued(engine, live_db_url):
    _park_attachment(engine, event_id="evt_dead")
    _drain(live_db_url, fetcher=_Fetcher(RuntimeError("HTTP 404: message not found")))

    queue = _queue(live_db_url)
    dead = queue.dead_letters(org_id=ORG)
    assert [d.event_id for d in dead] == ["evt_dead"]
    assert dead[0].attempts == 1 and "404" in (dead[0].last_error or "")
    assert dead[0].source_object_id == "m123::att456"
    # a dead letter is out of the backlog, not hiding in it
    assert queue.aging(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG).pending == 0

    assert queue.requeue_dead_letters(eval_time=NOW, org_id=ORG) == 1
    with engine.connect() as c:
        row = c.execute(text("select status, refetch_attempts, refetch_last_error "
                             "from parked_events where event_id='evt_dead'")).one()
    assert (row.status, row.refetch_attempts, row.refetch_last_error) == ("pending", 0, None)


def test_the_full_ladder_terminates_against_a_real_row(engine, live_db_url):
    """Five cycles, five attempts, one dead letter — the same acceptance the hermetic test states,
    proven against the columns that actually persist it."""
    _park_attachment(engine, event_id="evt_ladder")
    fetcher = _Fetcher(*[RuntimeError("ReadTimeout")] * 6)
    clock = NOW
    for _ in range(6):
        _drain(live_db_url, fetcher=fetcher, now=clock)
        with engine.connect() as c:
            nxt = c.execute(text("select refetch_next_attempt_at from parked_events "
                                 "where event_id='evt_ladder'")).scalar()
        clock = (nxt or clock) + timedelta(seconds=1)

    assert len(fetcher.calls) == 5, "bounded at max_attempts, whatever the caller does"
    with engine.connect() as c:
        assert c.execute(text("select status from parked_events where event_id='evt_ladder'")
                         ).scalar() == ParkStatus.DEAD_LETTER.value


# ── D1/D2 · the state and its age, against the columns that hold them ────────────────────────

def test_a_transient_failure_is_still_claimable_after_the_first_heartbeat(engine, live_db_url):
    """D1, on the row rather than on the report. The failure text is what a Composio call answers
    while a Gmail grant is being refreshed — it carries `not found`, and the permanent-first
    classifier read that as "the attachment is gone" and dead-lettered the park on tick one. The
    assertion is deliberately about STATE and AGE: after a heartbeat the row is pending, its park
    age is untouched, and the next heartbeat past its backoff claims it again."""
    _park_attachment(engine, event_id="evt_reauth")
    _drain(live_db_url, fetcher=_Fetcher(RuntimeError(
        "HTTPStatusError: 401 Unauthorized — connected account not found, refreshing token")))

    with engine.connect() as c:
        row = c.execute(text(
            "select status, refetch_attempts, refetch_next_attempt_at, refetch_failure_kind, "
            "       created_at from parked_events where event_id='evt_reauth'")).one()
    assert row.status == ParkStatus.PENDING.value
    assert row.refetch_attempts == 1
    assert row.refetch_next_attempt_at == NOW + timedelta(seconds=600)
    assert row.refetch_failure_kind == "transient"
    assert row.created_at == NOW - timedelta(hours=3), "an attempt does not reset the park's age"

    aging = _queue(live_db_url).aging(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG)
    assert aging.pending == 1, "still in the backlog the gate reads, not hidden as dead"

    later = NOW + timedelta(seconds=601)
    report = _drain(live_db_url, now=later)
    assert report.claimed == 1 and report.recovered == 1


def test_a_dead_letter_records_which_kind_of_failure_ended_it(engine, live_db_url):
    """The console column that used to be free text alone. `transient` here means "we tried five
    times"; the same column says `permanent` for a 404 and `capability` for bytes no engine could
    read, and those three have three different fixes."""
    _park_attachment(engine, event_id="evt_kind_gone")
    _drain(live_db_url, fetcher=_Fetcher(RuntimeError("HTTP 404: message not found")))

    _park_attachment(engine, event_id="evt_kind_slow", attachment_id="att9")
    clock = NOW
    for _ in range(DEFAULT_POLICY.max_attempts):
        _drain(live_db_url, fetcher=_Fetcher(RuntimeError("ReadTimeout: upstream")), now=clock)
        clock += timedelta(hours=12)

    kinds = {d.event_id: d.failure_kind for d in _queue(live_db_url).dead_letters(org_id=ORG)}
    assert kinds == {"evt_kind_gone": "permanent", "evt_kind_slow": "transient"}


def test_a_requeue_clears_the_kind_with_the_ladder(engine, live_db_url):
    """A requeued row has no verdict yet. Leaving the old stamp on it would report a conclusion
    about a run that is being thrown away."""
    _park_attachment(engine, event_id="evt_kind_requeue")
    _drain(live_db_url, fetcher=_Fetcher(RuntimeError("HTTP 404: not found")))
    assert _queue(live_db_url).requeue_dead_letters(eval_time=NOW, org_id=ORG) == 1
    with engine.connect() as c:
        assert c.execute(text("select refetch_failure_kind from parked_events "
                              "where event_id='evt_kind_requeue'")).scalar() is None


@pytest.mark.parametrize("reason_code", ["DOC-02", "DOC-04", "DOC-05", "DOC-06",
                                         "DOC-07", "DOC-08", "DOC-09"])
def test_every_refetch_park_code_is_claimed_by_the_drain(engine, live_db_url, reason_code):
    """D2. The claim filters on `reason_code = any(:reasons)`, so a park code missing from
    `NEEDS_REFETCH` is never selected by any query in the engine — it simply sits. One row per
    code so a future orphan names itself."""
    _park_attachment(engine, event_id=f"evt_{reason_code}", reason=reason_code)
    report = _drain(live_db_url)
    assert report.claimed == 1 and report.recovered == 1
    with engine.connect() as c:
        assert c.execute(text("select outcome from source_events where event_id=:e"),
                         {"e": f"evt_{reason_code}"}).scalar() == "emitted"


@pytest.mark.parametrize("reason_code", ["DOC-02", "DOC-04", "DOC-05", "DOC-06",
                                         "DOC-07", "DOC-08", "DOC-09"])
def test_every_refetch_park_code_is_counted_by_the_s1_report(engine, live_db_url, reason_code):
    """D2's other half: `scripts/l1_s1_report.py`'s first metric IS `read_aging`, which filters on
    the same set. An orphaned code was not merely undrained, it was UNCOUNTED — the G2 number read
    clean while the documents sat there."""
    from scripts.l1_s1_report import stuck_refetch_metric

    _park_attachment(engine, event_id=f"evt_count_{reason_code}", reason=reason_code,
                     parked_at=NOW - timedelta(hours=9))
    with engine.connect() as c:
        metric = stuck_refetch_metric(c, org_id=ORG, now=NOW)
    assert metric.observed == 1, "one stuck attachment, seen by the gate"
    assert any(reason_code in line for line in metric.sample)


# ── the black hole at the last rung, against the real claim ──────────────────────────────────

def test_a_park_leased_on_its_final_attempt_and_never_settled_is_still_claimable(engine,
                                                                                live_db_url):
    """`_CLAIM_SQL` used to carry `pe.refetch_attempts < :max_attempts`, which duplicated the
    terminal condition `plan_refetch` owns and thereby made it unreachable.

    The state below is exactly what a drain killed mid-fetch on the FINAL rung leaves: pending,
    `refetch_attempts = max_attempts`, lease expired. No later heartbeat could claim it, so it
    sat at `status='pending'` forever — and `read_aging`, which IS the G2 metric, counts pending
    parks by reason code without ever looking at the attempt count. A permanently stuck row in
    the number the gate asserts is zero, with nothing in the system able to clear it.
    """
    _park_attachment(engine, event_id="evt_crashed")
    with engine.begin() as c:
        c.execute(text(
            "update parked_events set refetch_attempts = :n, refetch_last_attempt_at = :at, "
            "refetch_next_attempt_at = :lease where event_id = 'evt_crashed'"),
            {"n": DEFAULT_POLICY.max_attempts, "at": NOW,
             "lease": NOW + DEFAULT_POLICY.lease})

    later = NOW + DEFAULT_POLICY.lease + timedelta(hours=1)
    claimed = _queue(live_db_url).claim_due(eval_time=later, policy=DEFAULT_POLICY, org_id=ORG)
    assert [c.event_id for c in claimed] == ["evt_crashed"], (
        "the crashed final lease is unclaimable — it can never leave status='pending'")
    assert claimed[0].attempts == DEFAULT_POLICY.max_attempts, (
        "the claim must hand `plan_refetch` the PRE-lease count, or the terminal branch reads "
        "the wrong number")


def test_the_crashed_park_reaches_a_dead_letter_and_leaves_the_gate_number(engine, live_db_url):
    """End to end on real rows: one heartbeat settles it, no provider call is made, and
    `read_aging` — the G2 query — then reports nothing stuck."""
    _park_attachment(engine, event_id="evt_crashed2")
    with engine.begin() as c:
        c.execute(text(
            "update parked_events set refetch_attempts = :n, refetch_next_attempt_at = :lease "
            "where event_id = 'evt_crashed2'"),
            {"n": DEFAULT_POLICY.max_attempts, "lease": NOW + DEFAULT_POLICY.lease})

    class _NeverAsked:
        source = "gmail"

        def __init__(self) -> None:
            self.calls = 0

        def fetch_attachment(self, message_id, attachment_id):   # pragma: no cover — must not run
            self.calls += 1
            return b"bytes"

    connector = _NeverAsked()
    later = NOW + DEFAULT_POLICY.lease + timedelta(hours=1)
    report = refetch_parked_attachments(_queue(live_db_url),
                                        connector_for=lambda *_a, **_k: connector,
                                        eval_time=later)
    assert report.dead_lettered == 1, report
    assert connector.calls == 0, "a bounded-out row was fetched again"

    with engine.connect() as c:
        row = c.execute(text(
            "select status, refetch_attempts, refetch_failure_kind from parked_events "
            "where event_id='evt_crashed2'")).one()
        aging = read_aging(c, eval_time=later, policy=DEFAULT_POLICY, org_id=ORG)
    assert row.status == ParkStatus.DEAD_LETTER.value
    assert row.refetch_attempts == DEFAULT_POLICY.max_attempts, (
        "the terminal settlement inflated the attempt count past the ladder")
    assert row.refetch_failure_kind == "transient", (
        "five failures we caused were recorded as a claim that the attachment is gone")
    assert aging.stuck_attachments == 0, aging
