"""H6 · COVERAGE EPOCHS — the window over which `coverage_ready` was true for a source.

**Gate H6** — invoked by `02-Layer-2-Plan/09-Build-Order-and-Acceptance.md` as::

    pytest tests/context/test_convergence.py tests/context/test_coverage_epoch.py \\
           tests/context/analytic/test_gap_reason.py -q

This file used to be a PLACEHOLDER that skipped. X6 has landed
(`genios_engine/context/quality/epoch.py`), so the placeholder is retired and this is the real
gate. Doc 13's loop **L-5** is its subject and its four acceptance lines are the four sections
below.

**THE FAILURE THIS PREVENTS, in one sentence.** L2.5.5 licenses a negative inference on
`GENUINELY_ABSENT` — *"no support tickets, and the desk is connected, therefore this account is
healthy"* — and then the founder connects Intercom. Every inference drawn under the old source
set is now standing on evidence that no longer exists, and `source_coverage` is an UPSERT, so the
record that we ever could not see support has been overwritten in place. There is nothing left to
detect the problem with.

An epoch is the append-only half of that row: one window, one coverage answer, closed rather than
overwritten when the sources move. That is what makes *"was this source reporting when we drew
this conclusion"* a question with an answer.

**Why some of these run against real Postgres.** The window semantics are SQL — one open epoch
per (org, domain) is a partial unique index, and `epoch_at`'s half-open `[opened_at, closed_at)`
is a predicate. A hermetic double would be a second implementation of the thing under test, and
the two would agree until the day they did not.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.coverage.declaration import declare_coverage
from genios_engine.capture.coverage.store import CoverageRow, rows_for
from genios_engine.context.quality.epoch import (EPOCH_TABLE, FIRST_EPOCH, CoverageEpoch,
                                                 advance_epochs, coverage_over, current_epochs,
                                                 epoch_at, epoch_fingerprint, epochs_over,
                                                 scoped_capabilities, stale_coverage)
from genios_engine.contracts.connection import Connection

#: The frozen instant every window in this file is measured from. `tests/context/conftest.py`
#: owns it; imported through the fixture rather than the module for the reason that conftest
#: gives — `tests/capture/conftest.py` is also called `conftest`.
_ORG = "org_x6_epoch"


def _conn(org: str, source_type: str, *, status: str = "connected") -> Connection:
    """One connected source. `status` is the whole point of the parameter: `paused` is the honest
    middle — the tenant HAS the mailbox and it is not flowing — and a paused source withdraws the
    licence to infer silence exactly as a missing one does."""
    return Connection(org_id=org, source_type=source_type, status=status,
                      connection_id=f"con_{source_type}_{status}")


def _rows(org: str, sources, *, at: datetime) -> tuple:
    """The `CoverageRow`s a sweep would file for an org with exactly these sources.

    Built through `declare_coverage` + `rows_for` rather than by hand: the epoch's fingerprint is
    taken over what the SWEEP files, and a fixture that assembled its own rows would let this
    suite stay green against a declaration shape production no longer produces.
    """
    return tuple(rows_for(declare_coverage(
        org_id=org, connections=[_conn(org, s) if isinstance(s, str) else _conn(org, s[0],
                                                                               status=s[1])
                                 for s in sources],
        company_knowledge_count=0, computed_at=at)))


def _domain(rows, domain: str) -> CoverageRow:
    for row in rows:
        if row.domain == domain:
            return row
    raise AssertionError(f"no {domain!r} row in the declaration: {[r.domain for r in rows]}")


# =================================================================================================
# 1 · THE FINGERPRINT — what counts as a change, and what does not
# =================================================================================================

def test_the_same_sources_fingerprint_identically_so_a_sweep_is_not_a_change(eval_time):
    """The idempotence the whole mechanism rests on.

    A sweep runs every ten minutes. If "a sweep ran" were a change, a tenant would mint 144
    epochs a day and every one of them would mark the previous day's inferences stale — the
    revocation machinery would fire constantly and therefore mean nothing.
    """
    first = _rows(_ORG, ("gmail", "hubspot"), at=eval_time)
    later = _rows(_ORG, ("gmail", "hubspot"), at=eval_time + timedelta(hours=6))
    for domain in ("sales", "support", "admin", "fundraising"):
        a, b = _domain(first, domain), _domain(later, domain)
        assert epoch_fingerprint(domain=domain, coverage_ready=a.coverage_ready,
                                 capabilities=scoped_capabilities(
                                     required=a.required, recommended=(),
                                     freshness=a.freshness)) == \
               epoch_fingerprint(domain=domain, coverage_ready=b.coverage_ready,
                                 capabilities=scoped_capabilities(
                                     required=b.required, recommended=(),
                                     freshness=b.freshness)), domain


def test_a_capability_the_domain_does_not_name_is_outside_its_fingerprint():
    """Doc 13's scoping rule, at the level it is actually enforced.

    *"A new billing connector does not invalidate support-absence inferences. The epoch check is
    per-capability, or every connector change re-derives the whole graph."* `source_coverage`
    stores the org's WHOLE connected set on every domain's row, so this is not automatic — it is
    `scoped_capabilities` doing it, and the test is that the extra capability is simply not there.
    """
    support = scoped_capabilities(
        required=("support_desk", "communication"), recommended=("product_usage", "incident"),
        freshness={"communication": "fresh", "support_desk": "fresh", "finance": "fresh"})
    assert "finance" not in support
    assert support["incident"] == "not_connected"   # in scope, and absent — a fixed shape


def test_never_connected_and_lost_hash_the_same_because_they_are_the_same_regime():
    """A capability the org does not have contributes `not_connected` rather than being omitted.

    Two spellings of one state would make the fingerprint depend on whether a key had ever been
    written, so a tenant that connected and revoked Stripe would have a different `admin`
    fingerprint from one that never had it — and would carry a spurious epoch bump for ever.
    """
    never = scoped_capabilities(required=("finance",), recommended=(),
                                freshness={"communication": "fresh"})
    lost = scoped_capabilities(required=("finance",), recommended=(), freshness={})
    assert never == lost


# =================================================================================================
# 2 · CONNECTING A SOURCE BUMPS THE EPOCH — doc 13 acceptance line 1
# =================================================================================================

@pytest.mark.pg
def test_connecting_a_new_source_opens_a_new_epoch_and_closes_the_old_one(pg_store, eval_time):
    """The first acceptance line, against the real table.

    Three things are asserted together because separating them would let two of them pass while
    the third quietly did not happen: the number advances, the OLD window is closed at the same
    instant the new one opens (so no instant belongs to two regimes), and
    `source_coverage.coverage_epoch` — the number a reader has without a window query — moves
    with it.
    """
    from sqlalchemy import text as sql

    org = f"{_ORG}_bump"
    later = eval_time + timedelta(days=7)
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'epoch') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        with pg_store.engine.begin() as conn:
            rows = _rows(org, ("gmail",), at=eval_time)
            for row in rows:
                conn.execute(sql(
                    "insert into source_coverage (org_id, domain, required, connected, "
                    " freshness, coverage_ready, computed_at) "
                    "values (:o, :d, :req, :con, '{}'::jsonb, :r, :at) "
                    "on conflict (org_id, domain) do nothing"),
                    {"o": org, "d": row.domain, "req": list(row.required),
                     "con": list(row.connected), "r": row.coverage_ready, "at": eval_time})
            opened = advance_epochs(conn, org, rows, at=eval_time)
        assert {c.domain for c in opened} == {"sales", "support", "admin", "fundraising"}
        assert all(c.is_first and c.epoch == FIRST_EPOCH for c in opened)

        # A second sweep over the SAME sources: nothing at all.
        with pg_store.engine.begin() as conn:
            assert advance_epochs(conn, org, _rows(org, ("gmail",), at=later), at=later) == ()

        # Now a CRM arrives. `sales` requires it; `support` does not name it at all.
        with pg_store.engine.begin() as conn:
            changed = advance_epochs(conn, org, _rows(org, ("gmail", "hubspot"), at=later),
                                     at=later)
        moved = {c.domain: c for c in changed}
        assert "sales" in moved, "connecting a CRM did not open a new sales epoch"
        assert moved["sales"].epoch == FIRST_EPOCH + 1
        assert moved["sales"].previous_epoch == FIRST_EPOCH
        assert moved["sales"].was_ready is False and moved["sales"].coverage_ready is True

        with pg_store.engine.connect() as conn:
            closed = conn.execute(sql(
                f"select epoch, opened_at, closed_at from {EPOCH_TABLE} "
                "where org_id = :o and domain = 'sales' order by epoch"), {"o": org}).all()
            assert [r.epoch for r in closed] == [1, 2]
            assert closed[0].closed_at == closed[1].opened_at == later, \
                "the old window must close at the instant the new one opens, or one instant " \
                "belongs to two coverage regimes"
            assert closed[1].closed_at is None
            stored = conn.execute(sql(
                "select coverage_epoch from source_coverage where org_id=:o and domain='sales'"),
                {"o": org}).scalar_one()
            assert stored == 2
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


@pytest.mark.pg
def test_a_new_source_does_not_retroactively_make_the_old_period_look_covered(pg_store,
                                                                              eval_time):
    """The placeholder's own second line. An epoch is a window, not a flag.

    Asking what we could see LAST MONTH must return last month's answer, and the whole reason
    the table exists is that `source_coverage` — an upsert — can only ever answer "now".
    """
    from sqlalchemy import text as sql

    org = f"{_ORG}_replay"
    later = eval_time + timedelta(days=30)
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'epoch') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        with pg_store.engine.begin() as conn:
            advance_epochs(conn, org, _rows(org, ("gmail",), at=eval_time), at=eval_time)
            advance_epochs(conn, org, _rows(org, ("gmail", "hubspot"), at=later), at=later)
        with pg_store.engine.connect() as conn:
            then = epoch_at(conn, org, "sales", eval_time + timedelta(days=3))
            now = epoch_at(conn, org, "sales", later + timedelta(days=1))
            before_anything = epoch_at(conn, org, "sales", eval_time - timedelta(days=1))
        assert then is not None and then.epoch == 1 and then.coverage_ready is False
        assert now is not None and now.epoch == 2 and now.coverage_ready is True
        # The half-open boundary: the switching instant belongs to the NEW epoch only.
        assert before_anything is None, \
            "a period before the tenant's first sweep is a period nobody assessed — answering " \
            "it with today's regime is inventing history"
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


# =================================================================================================
# 3 · STALE_COVERAGE, AND ITS SCOPE — doc 13 acceptance lines 2 and 3
# =================================================================================================

def test_an_inference_from_a_superseded_epoch_is_marked_stale():
    """Doc 13's read rule: *"if inference.coverage_epoch < org.coverage_epoch ... mark
    STALE_COVERAGE, re-evaluate before use."*"""
    current = {"sales": 4}
    assert stale_coverage(domain="sales", drawn_under=3, current=current) is True
    assert stale_coverage(domain="sales", drawn_under=4, current=current) is False


def test_a_billing_connector_does_not_stale_a_support_inference():
    """The scoping acceptance line, at the level a caller sees it.

    Epochs are per domain and the fingerprint is per domain's own capabilities, so the scoping is
    STRUCTURAL rather than a second condition somebody has to remember to write — which is what
    the line "the epoch check is per-capability" is really asking for.
    """
    current = {"admin": 7, "support": 2}
    assert stale_coverage(domain="support", drawn_under=2, current=current) is False
    assert stale_coverage(domain="admin", drawn_under=2, current=current) is True


def test_an_inference_with_no_epoch_recorded_is_not_stale_it_is_unverifiable():
    """`None` is the third state here too. Marking every pre-migration row stale would drown the
    rows that genuinely are, which is the same as not marking anything."""
    assert stale_coverage(domain="sales", drawn_under=None, current={"sales": 9}) is False
    #: and a domain with no regime on record has nothing to be behind
    assert stale_coverage(domain="sales", drawn_under=1, current={}) is False


@pytest.mark.pg
def test_a_superseded_epoch_is_closed_and_never_deleted(pg_store, eval_time):
    """*"Marked, not trusted and not deleted — deleting it would lose the audit trail of what the
    system believed and why."* The old row is still there, with its window and its receipt."""
    from sqlalchemy import text as sql

    org = f"{_ORG}_audit"
    later = eval_time + timedelta(days=2)
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'epoch') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        with pg_store.engine.begin() as conn:
            advance_epochs(conn, org, _rows(org, ("gmail",), at=eval_time), at=eval_time)
            advance_epochs(conn, org, _rows(org, ("gmail", "zendesk"), at=later), at=later)
        with pg_store.engine.connect() as conn:
            rows = conn.execute(sql(
                f"select epoch, coverage_ready, capabilities from {EPOCH_TABLE} "
                "where org_id=:o and domain='support' order by epoch"), {"o": org}).all()
            live = current_epochs(conn, org)
        assert len(rows) == 2, "the superseded epoch was deleted rather than closed"
        assert rows[0].coverage_ready is False and rows[1].coverage_ready is True
        assert "support_desk=not_connected" in list(rows[0].capabilities), \
            "the receipt for the bump — which capability moved — is not on the row"
        assert "support_desk=fresh" in list(rows[1].capabilities)
        assert live["support"].epoch == 2 and live["support"].is_open
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


# =================================================================================================
# 4 · A REVOKED CONNECTOR — doc 13 acceptance line 4
# =================================================================================================

@pytest.mark.pg
def test_a_revoked_connector_opens_an_epoch_that_withdraws_the_licence(pg_store, eval_time):
    """*"a revoked connector turns future absences UNKNOWABLE, not GENUINELY_ABSENT."*

    The epoch's job is to make that visible and revocable: `withdraws_licence` names the
    direction, and the new regime's `coverage_ready=False` is what the classifier reads.
    """
    from sqlalchemy import text as sql

    org = f"{_ORG}_revoked"
    later = eval_time + timedelta(days=5)
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'epoch') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        with pg_store.engine.begin() as conn:
            advance_epochs(conn, org, _rows(org, ("gmail", "zendesk"), at=eval_time),
                           at=eval_time)
            # The desk is paused, not deleted — the honest middle, and it withdraws the licence
            # for the same reason a missing one does: a paused connector produces the same empty
            # result set as a connected one with nothing in it.
            changes = advance_epochs(conn, org,
                                     _rows(org, ("gmail", ("zendesk", "paused")), at=later),
                                     at=later)
        support = {c.domain: c for c in changes}["support"]
        assert support.withdraws_licence is True
        assert support.was_ready is True and support.coverage_ready is False
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


# =================================================================================================
# 5 · A WINDOW, NOT AN INSTANT — "no trend may cross an epoch boundary without saying so"
# =================================================================================================

def _epoch(number: int, ready: bool, opened: datetime,
           closed: datetime | None = None) -> CoverageEpoch:
    return CoverageEpoch(org_id=_ORG, domain="sales", epoch=number, coverage_ready=ready,
                         fingerprint=f"fp{number}", capabilities=(),
                         opened_at=opened, closed_at=closed)


def test_a_window_inside_one_covered_epoch_licenses_a_negative_inference(eval_time):
    start, end = eval_time - timedelta(days=28), eval_time
    window = coverage_over("sales", (_epoch(1, True, eval_time - timedelta(days=90)),),
                           start=start, end=end)
    assert window.ready is True and window.crossed is False
    assert window.licenses_negative_inference is True


def test_a_window_that_crosses_a_boundary_says_so_and_licenses_nothing(eval_time):
    """The decisive row. Both halves of this window were COVERED, and it still licenses nothing:
    *"engagement fell"* and *"we started being able to see engagement"* are the same series and
    two different sentences, and only the epochs can tell a reader which one they are looking at.
    """
    boundary = eval_time - timedelta(days=14)
    window = coverage_over("sales", (
        _epoch(1, True, eval_time - timedelta(days=90), boundary),
        _epoch(2, True, boundary)), start=eval_time - timedelta(days=28), end=eval_time)
    assert window.ready is True
    assert window.crossed is True
    assert window.licenses_negative_inference is False
    assert window.epochs == (1, 2)


def test_disagreeing_epochs_make_the_window_unknown_never_false(eval_time):
    boundary = eval_time - timedelta(days=10)
    window = coverage_over("sales", (
        _epoch(1, False, eval_time - timedelta(days=90), boundary),
        _epoch(2, True, boundary)), start=eval_time - timedelta(days=28), end=eval_time)
    assert window.ready is None, "a window whose regimes disagree has no single honest answer"
    assert window.crossed is True


def test_a_window_no_epoch_describes_is_unknown_never_false(eval_time):
    """The state that must never be `False`. A period before the tenant's first sweep is a period
    nobody assessed, and `False` there is a claim we invented — the same distinction
    `analytic/history.gap_point` keeps when it returns `coverage_ready=None` for a gap."""
    assert coverage_over("sales", (), start=eval_time - timedelta(days=7),
                         end=eval_time).ready is None
    # Half-described is also unknown: the epoch opened INSIDE the window.
    partial = coverage_over("sales", (_epoch(1, True, eval_time - timedelta(days=3)),),
                            start=eval_time - timedelta(days=28), end=eval_time)
    assert partial.ready is None and partial.crossed is True


@pytest.mark.pg
def test_epochs_over_finds_a_regime_that_opened_before_the_window(pg_store, eval_time):
    """Overlap, not containment. A stable tenant's only epoch opened long before every window it
    will ever ask about, and a containment test would find nothing and answer "unknown" for the
    one tenant whose coverage never moved."""
    from sqlalchemy import text as sql

    org = f"{_ORG}_over"
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'epoch') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        with pg_store.engine.begin() as conn:
            advance_epochs(conn, org, _rows(org, ("gmail", "hubspot"), at=eval_time),
                           at=eval_time - timedelta(days=200))
        with pg_store.engine.connect() as conn:
            found = epochs_over(conn, org, "sales", eval_time - timedelta(days=28), eval_time)
            window = coverage_over("sales", found, start=eval_time - timedelta(days=28),
                                   end=eval_time)
        assert [e.epoch for e in found] == [1]
        assert window.ready is True and window.crossed is False
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


def test_a_window_that_ends_before_it_starts_is_refused_not_answered():
    """A silently empty result for a reversed window would read as `ready=None` — "we could not
    see" — for what is in fact a caller bug."""
    class _Refuse:
        def execute(self, *_a, **_k):        # pragma: no cover — must never be reached
            raise AssertionError("a reversed window must be refused before any query")

    with pytest.raises(ValueError, match="ends before it starts"):
        epochs_over(_Refuse(), _ORG, "sales", datetime(2026, 3, 1, tzinfo=timezone.utc),
                    datetime(2026, 2, 1, tzinfo=timezone.utc))


# =================================================================================================
# 6 · THE WIRING — the epoch advances on a REAL capture path, not only in this file
# =================================================================================================

@pytest.mark.pg
def test_the_coverage_factory_every_capture_door_shares_advances_the_epoch(pg_store, eval_time):
    """*"Green and called by nothing"* is the defect Layer 1 shipped six times, and an epoch that
    only ever advances from a test is exactly that.

    `platform.wiring.make_coverage_fn` is the ONE factory the sweep, the Composio webhook, the
    manual door and the dev sample all go through — the same seam that fixed `coverage_ready=None
    on 100% of events`. This drives THAT function, with a real database behind it, and asserts the
    rows exist afterwards: a source-level grep would stay green against a call somebody commented
    out, which is precisely the shape of a wiring regression.
    """
    from sqlalchemy import text as sql

    from genios_engine.capture.coverage.store import InMemoryCoverageStore
    from genios_engine.platform.wiring import make_coverage_fn

    org = f"{_ORG}_factory"
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'epoch') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        verdict = make_coverage_fn(org, connections=[_conn(org, "gmail")],
                                   engine=pg_store.engine, store=InMemoryCoverageStore(),
                                   now=eval_time)
        assert verdict("sales")["coverage_ready"] is False     # the factory still does its job
        with pg_store.engine.connect() as conn:
            opened = current_epochs(conn, org)
        assert set(opened) == {"sales", "support", "admin", "fundraising"}, \
            "the shared coverage factory did not advance the epoch — every capture door files a " \
            "declaration and none of them record that the source set moved"
        assert all(e.epoch == FIRST_EPOCH for e in opened.values())

        # A second call over the SAME sources, through the same production factory: still one.
        make_coverage_fn(org, connections=[_conn(org, "gmail")], engine=pg_store.engine,
                         store=InMemoryCoverageStore(), now=eval_time + timedelta(hours=1))
        with pg_store.engine.connect() as conn:
            assert conn.execute(sql(f"select count(*) from {EPOCH_TABLE} where org_id=:o"),
                                {"o": org}).scalar_one() == 4
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


def test_the_epoch_advance_never_kills_a_sweep():
    """A coverage row is a hint; a sweep is the tenant's mail. `save` already logs and returns 0
    on a database error, and the epoch advance must hold the same line — a history row that could
    not be opened must not cost the ingestion it was describing."""
    from genios_engine.platform.wiring import _advance_coverage_epochs

    class _Exploding:
        def begin(self):
            raise RuntimeError("database is on fire")

    declaration = declare_coverage(org_id=_ORG, connections=[_conn(_ORG, "gmail")],
                                   company_knowledge_count=0,
                                   computed_at=datetime(2026, 3, 1, tzinfo=timezone.utc))
    _advance_coverage_epochs(declaration, engine=_Exploding())      # must not raise
    _advance_coverage_epochs(declaration, engine=None)              # nor with no database at all
