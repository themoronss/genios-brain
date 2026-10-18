"""Layer 5.2 · Phase 3 — the outbox spine, proven against real PostgreSQL.

The spine's SQL (partial-index ON CONFLICT, FOR UPDATE SKIP LOCKED, fencing) is exactly the kind a
fake cannot model, so this exercises it against a live database — inside ONE transaction that is
rolled back, leaving the DB byte-identical. Skips cleanly when no database is configured, so the
rest of the suite never depends on it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.delivery import DeliveryFormat, DeliveryObject, DeliveryPriority
from genios_engine.contracts.execution import AudienceClass, ChannelClass
from genios_engine.deliver import spine

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def conn(live_db_url):
    """A live connection in a rolled-back transaction, or skip if no DB / schema is reachable."""
    try:
        from genios_engine.platform.db import get_engine
        from sqlalchemy import text
        # The scratch database when one is set — never the configured (production) one.
        # See tests/conftest.py::live_test_database_url for why that ordering matters.
        url = live_db_url
        if not url:
            pytest.skip("no database configured")
        engine = get_engine(url)
        c = engine.connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no live database: {exc}")
    tx = c.begin()
    # require the 0043 control-plane schema + at least one org for FK satisfaction
    from sqlalchemy import text
    if not c.execute(text("select to_regclass('public.delivery_events')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0043 control plane not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org to satisfy cascade FKs")
    try:
        yield c, org
    finally:
        tx.rollback()
        c.close()


def _obj(org: str, dedupe: str) -> DeliveryObject:
    return DeliveryObject(
        org_id=org, delivery_id="del_spine_t", execution_id="exec_spine_t", execution_hash="h",
        audience=AudienceClass.OWNER, channel="slack", channel_class=ChannelClass.CHAT,
        fmt=DeliveryFormat.CHAT_MESSAGE, priority=DeliveryPriority.CRITICAL, band="critical",
        dedupe_key=dedupe, route_ladder=("slack", "in_app"), recipient="seat_spine_t")


def test_materialize_is_atomic_and_deduped(conn):
    from sqlalchemy import text
    c, org = conn
    dk = spine.logical_dedupe_key(org, "exec_spine_t", "initial")
    assert spine.materialize(c, _obj(org, dk), at=NOW) is True
    assert spine.materialize(c, _obj(org, dk), at=NOW) is False, "one logical delivery per key"
    rows = c.execute(text("select count(*) from delivery_outbox where org_id=:o and dedupe_key=:d"),
                     {"o": org, "d": dk}).scalar()
    events = c.execute(text("select count(*) from delivery_events "
                            "where org_id=:o and delivery_id='del_spine_t' and kind='queued'"),
                       {"o": org}).scalar()
    assert rows == 1 and events == 1, "the row and its queued event are written together"


def test_claim_is_fenced_against_a_second_worker(conn):
    c, org = conn
    dk = spine.logical_dedupe_key(org, "exec_spine_t", "initial")
    spine.materialize(c, _obj(org, dk), at=NOW)
    at = NOW + timedelta(minutes=1)
    claimed = spine.claim_due(c, org_id=org, worker_id="worker_A", at=at)
    assert any(r["delivery_id"] == "del_spine_t" for r in claimed)
    assert all(r["fence_token"] for r in claimed), "a claim carries a fencing token"
    # the lease is live, so a second worker at the same instant cannot re-claim it
    again = spine.claim_due(c, org_id=org, worker_id="worker_B", at=at)
    assert not any(r["delivery_id"] == "del_spine_t" for r in again)


def test_materialization_failure_is_visible(conn):
    from sqlalchemy import text
    c, org = conn
    fid = spine.record_materialization_failure(
        c, org_id=org, execution_id="exec_bad", reason_code="unparseable_object", at=NOW)
    n = c.execute(text("select count(*) from delivery_materialization_failures where id=:i"),
                  {"i": fid}).scalar()
    assert n == 1, "a corrupt source object is recorded for operations, never silently dropped"


# ── ⛔ the recovery's FIRST tests — it had none at all until 2026-10-01 ────────────────────────
#
# `spine.recover_expired_claims` was the one component of the whole v2 control plane exercised by
# NOTHING: not production, not a test. Its docstring states the harm it prevents — *"An expired
# worker may have POSTed to a provider before dying; we must never silently retry over that
# ambiguity"* — and nothing had ever run it. ⛔ An unguarded cutover, not a bug: `claim_due` is
# uncalled too, so the ambiguity cannot arise until the cutover is taken. These tests are what makes
# taking it safe, and `tests/deliver/test_the_spine_cutover_cannot_be_taken_unguarded.py` is what
# makes taking it without them loud.

def _seed_started_attempt(c, org: str, *, claim_token: str, settled: bool = False) -> str:
    """One physical `started` attempt under a claim — the row the recovery is written for."""
    from sqlalchemy import text
    from genios_engine.platform.ids import new_id
    aid = new_id("att")
    c.execute(text(
        "insert into delivery_attempts (id, org_id, delivery_id, retry_generation, channel, "
        "attempt_no, claim_token, started_at, settled_at, outcome) "
        "values (:i, :o, 'del_spine_t', 0, 'slack', 1, :t, :s, :st, 'started')"),
        {"i": aid, "o": org, "t": claim_token, "s": NOW,
         "st": NOW + timedelta(seconds=1) if settled else None})
    return aid


def _outcome(c, aid: str) -> tuple[str, object]:
    from sqlalchemy import text
    row = c.execute(text("select outcome, settled_at from delivery_attempts where id=:i"),
                    {"i": aid}).one()
    return row[0], row[1]


def _claim(c, org: str, *, lease: int = 300):
    """Materialise one delivery and claim it, returning its fence token."""
    dk = spine.logical_dedupe_key(org, "exec_spine_t", "initial")
    spine.materialize(c, _obj(org, dk), at=NOW)
    rows = spine.claim_due(c, org_id=org, worker_id="worker_A", at=NOW + timedelta(seconds=1),
                           lease_seconds=lease)
    fence = next(r["fence_token"] for r in rows if r["delivery_id"] == "del_spine_t")
    return fence


def test_an_expired_claims_unsettled_attempt_becomes_unknown(conn):
    """⛔ THE POINT. The attempt is marked before anyone reclaims the row, so the next worker can
    see that an ambiguity happened rather than retrying over it."""
    c, org = conn
    fence = _claim(c, org, lease=60)
    aid = _seed_started_attempt(c, org, claim_token=fence)

    # a minute past the lease: the worker that owned this attempt is gone
    changed = spine.recover_expired_claims(c, at=NOW + timedelta(seconds=180))
    assert changed >= 1, "the expired claim's unsettled attempt was not recovered"
    outcome, settled_at = _outcome(c, aid)
    assert outcome == "unknown", "an attempt that may have reached a provider must not read failed"
    assert settled_at is not None, "a recovered attempt is settled, so it cannot be recovered twice"


def test_a_live_claims_attempt_is_untouched(conn):
    """The lease is the whole boundary: a worker still inside it owns its attempt."""
    c, org = conn
    fence = _claim(c, org, lease=3600)
    aid = _seed_started_attempt(c, org, claim_token=fence)

    spine.recover_expired_claims(c, at=NOW + timedelta(seconds=120))
    assert _outcome(c, aid)[0] == "started", "a live worker's attempt was stolen from under it"


def test_a_settled_attempt_is_never_rewritten(conn):
    """⛔ `delivered` must never become `unknown`. The recovery is about ABSENCE of an outcome, and
    overwriting a known one would turn a successful send into an ambiguity."""
    c, org = conn
    fence = _claim(c, org, lease=60)
    aid = _seed_started_attempt(c, org, claim_token=fence, settled=True)

    spine.recover_expired_claims(c, at=NOW + timedelta(seconds=180))
    outcome, _ = _outcome(c, aid)
    assert outcome == "started", (
        "an attempt with a settle time was rewritten -- the predicate must be `settled_at is null`")


def test_an_attempt_under_a_different_fence_is_not_recovered(conn):
    """⛔ THE RECOVERY'S OWN BLIND SPOT, PINNED RATHER THAN FIXED.

    The recovery joins `a.claim_token = d.fence_token`, and `claim_due` writes a NEW fence when it
    reclaims. So once a row has been handed to a fresh worker, the previous worker's orphaned
    attempt can never match again — it stays `started` forever.

    ⛔ That is **recorded, not corrected here**: changing the join is a behaviour change on a path
    nobody runs yet, and the honest response is a receipt that does not share the blind spot.
    `platform/receipts.py`'s unsettled-attempt receipt is deliberately fence-independent, and
    `tests/deliver/test_the_spine_cutover_cannot_be_taken_unguarded.py` asserts that it is.
    **A guard must not inherit the blind spot of the thing it guards.**
    """
    c, org = conn
    _claim(c, org, lease=60)
    aid = _seed_started_attempt(c, org, claim_token="fence_from_a_previous_generation")

    spine.recover_expired_claims(c, at=NOW + timedelta(seconds=180))
    assert _outcome(c, aid)[0] == "started", (
        "if this now reads `unknown`, the fence join was changed -- which is a real improvement, "
        "and the receipt's fence-independence test and this docstring both need rewriting")
