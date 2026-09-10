"""CL-03, CL-06 and the four ways a stale situation outlived every mechanism meant to end it.

    pytest tests/context/test_lifecycle_survives_the_drain.py -q

Four separate defects, one shape: **the thing that ends a situation never ran, or ran and was
overwritten.** All four are what a user actually sees — a card that will not go away.

1. WAITING FACTS NEVER RETIRED. `waiting._state` writes `thread.days_waiting` only while the
   last message in the exchange is ours. When a reply lands it stops being WRITTEN — and a fact
   that stops being written is not a fact that ended. The row stayed `status='active'`,
   `valid_to is null`, holding whatever number the last waiting sweep computed, so
   `read_awaiting_response` kept minting `awaiting_response` for an ANSWERED conversation at a
   frozen day count. Its own docstring claims "it closes itself the moment they do", and
   `_reconcile` could never fire because the finding never stopped being produced.

2. A HUMAN'S 'HANDLED' WAS DESTROYED BY THE NEXT DRAIN. `POST /situations/{id}/resolve` sets
   `resolved_by='human'`; `_upsert` then ran within six hours and reset status, resolved_by and
   resolved_at. `situations.decide_lifecycle`'s rule — "a human resolution sticks until new
   evidence" — could never see that a human had closed anything, because the provenance was
   erased rather than overridden.

3 & 4. DORMANCY AND ARCHIVAL WERE GATED ON NEW MAIL. `refresh_situations` and `refresh_attention`
   sat behind `if done or affected:` in `runner.process_pending`. Every quantity they recompute —
   freshness, active→dormant at 45 days, resolved→archived at 180, attention decay — is derived
   from the CLOCK, so on a quiet tenant nothing aged. Dormancy is the only mechanism that stops a
   stale situation compiling into a card, and the org whose quiet IS the finding was the one org
   where it never ran. `detect_resolutions` cannot cover the gap: it `continue`s on
   STATEMENT_NONE, which is every situation on a quiet org.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context import runner
from genios_engine.context.waiting import WAITING_ONLY_FIELDS, compute_waiting

pytestmark = pytest.mark.unit

ORG = "org_pilot"
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


class Store:
    def __init__(self, engine):
        self.engine = engine


@pytest.fixture()
def store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for ddl in (
            # Every column `derived._UPSERT_FACT` names, in its order. A short fixture here
            # fails with `no such column`, which reads like a schema drift and is not one.
            "create table graph_facts (fact_version_id text primary key, fact_id text, "
            "org_id text, subject_node_id text, field text, value text, value_type text, "
            "status text, authority_rank integer, confidence real, occurred_at timestamp, "
            "valid_from timestamp, valid_to timestamp, visibility_scope text, "
            "derivation_type text, trace_id text, schema_version text, source_authority text, "
            "provenance_refs text)",
            # Shaped for `waiting._ASKS`, which joins observations to the outbound fact
            # through `graph_source_refs` and filters on `status` and `kind`.
            "create table graph_observations (org_id text, subject_node_id text, kind text, "
            "status text, created_by_event_id text, occurred_at timestamp)",
            "create table graph_edges (org_id text, edge_type text, from_node_id text, "
            "to_node_id text, valid_to timestamp)",
            "create table graph_source_refs (org_id text, event_id text, fact_version_id text)",
            "create table source_events (event_id text, org_id text, occurred_at timestamp)",
        ):
            c.execute(text(ddl))
    return Store(engine)


_SEQ = {"n": 0}


def message(store, node: str, field: str, at: datetime) -> None:
    """One directed message, in the three rows `waiting._TIMELINE` actually joins.

    The fact alone is not enough: the timeline reads its instant from `source_events` through
    `graph_source_refs`, because a fact's own `valid_from` is when GeniOS learned it and the
    waiting arithmetic is about when the message was SENT.
    """
    _SEQ["n"] += 1
    key = f"{node}_{_SEQ['n']}"
    with store.engine.begin() as c:
        c.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "  value, value_type, status, valid_from, occurred_at) "
            "values (:v,:f,:o,:n,:fd,'','ts','active',:at,:at)"),
            {"v": f"fv_{key}", "f": f"f_{key}", "o": ORG, "n": node, "fd": field, "at": at})
        c.execute(text("insert into source_events values (:e,:o,:at)"),
                  {"e": f"evt_{key}", "o": ORG, "at": at})
        c.execute(text("insert into graph_source_refs values (:o,:e,:v)"),
                  {"o": ORG, "e": f"evt_{key}", "v": f"fv_{key}"})


def timeline(store, node: str, *, out: list[datetime] = (), inbound: list[datetime] = ()):
    """The directed message facts `waiting._TIMELINE` reads."""
    for at in out:
        message(store, node, "thread.last_outbound", at)
    for at in inbound:
        message(store, node, "thread.last_inbound", at)


def waiting_facts(store, node: str, *, active_only: bool = True) -> dict[str, str]:
    clause = " and status='active' and valid_to is null" if active_only else ""
    with store.engine.connect() as c:
        return {r[0]: r[1] for r in c.execute(text(
            "select field, status from graph_facts where org_id=:o and subject_node_id=:n "
            "and field like 'thread.%'" + clause), {"o": ORG, "n": node}).all()}


# =============================================================================================
# 1. The waiting facts, and the day they stop being true.
# =============================================================================================
def test_a_counterparty_we_are_waiting_on_gets_the_waiting_facts(store):
    timeline(store, "p_a", out=[NOW - timedelta(days=29)])

    compute_waiting(store, ORG, now=NOW)

    assert "thread.days_waiting" in waiting_facts(store, "p_a")


def test_when_they_reply_the_waiting_facts_are_retired(store):
    """THE DEFECT. Sweep one writes `days_waiting=29`. They answer. Sweep two must not leave that
    row standing — `read_awaiting_response` reads it through `_WAITING_ROWS` and would keep
    minting an `awaiting_response` situation for an answered conversation, forever, at a frozen
    day count."""
    timeline(store, "p_a", out=[NOW - timedelta(days=29)])
    compute_waiting(store, ORG, now=NOW)
    assert "thread.days_waiting" in waiting_facts(store, "p_a")

    timeline(store, "p_a", inbound=[NOW - timedelta(days=1)])
    compute_waiting(store, ORG, now=NOW)

    assert "thread.days_waiting" not in waiting_facts(store, "p_a")


def test_every_waiting_only_field_goes_together(store):
    """A half-retired state is worse than either: `follow_up_count` without `days_waiting` reads
    as "we chased them three times and are not waiting", which describes nothing."""
    timeline(store, "p_a", out=[NOW - timedelta(days=29), NOW - timedelta(days=20)])
    compute_waiting(store, ORG, now=NOW)
    timeline(store, "p_a", inbound=[NOW - timedelta(days=1)])
    compute_waiting(store, ORG, now=NOW)

    live = waiting_facts(store, "p_a")

    assert not (set(WAITING_ONLY_FIELDS) & set(live)), live


def test_retiring_supersedes_rather_than_deletes(store):
    """The row is how a point-in-time read knows what we believed last week. `valid_to` is what
    makes that legible; a DELETE would make the past unreadable."""
    timeline(store, "p_a", out=[NOW - timedelta(days=29)])
    compute_waiting(store, ORG, now=NOW)
    timeline(store, "p_a", inbound=[NOW - timedelta(days=1)])
    compute_waiting(store, ORG, now=NOW)

    everything = waiting_facts(store, "p_a", active_only=False)

    assert everything.get("thread.days_waiting") == "superseded"


def test_what_stays_true_after_a_reply_is_not_retired(store):
    """`thread.last_heard_days` is MORE true once they answer, not less. Retiring it with the
    waiting facts would delete the very evidence that the wait ended."""
    timeline(store, "p_a", out=[NOW - timedelta(days=29)], inbound=[NOW - timedelta(days=1)])

    compute_waiting(store, ORG, now=NOW)

    assert "thread.last_heard_days" in waiting_facts(store, "p_a")


def test_retiring_twice_is_a_no_op(store):
    """Six drains a day. The second pass must find nothing active to close rather than churning
    rows and inflating the written count."""
    timeline(store, "p_a", out=[NOW - timedelta(days=29)])
    compute_waiting(store, ORG, now=NOW)
    timeline(store, "p_a", inbound=[NOW - timedelta(days=1)])
    compute_waiting(store, ORG, now=NOW)

    assert compute_waiting(store, ORG, now=NOW) == 1   # last_heard_days rewritten, nothing retired


def test_a_conversation_that_goes_quiet_again_gets_fresh_waiting_facts(store):
    """Retirement must not be a one-way door. They answered, we wrote again, and we are waiting
    on a NEW ask — which is a live situation with a new clock, not a closed one."""
    timeline(store, "p_a", out=[NOW - timedelta(days=40)], inbound=[NOW - timedelta(days=39)])
    compute_waiting(store, ORG, now=NOW)
    assert "thread.days_waiting" not in waiting_facts(store, "p_a")

    timeline(store, "p_a", out=[NOW - timedelta(days=10)])
    compute_waiting(store, ORG, now=NOW)

    assert waiting_facts(store, "p_a").get("thread.days_waiting") == "active"


def test_a_node_nobody_ever_wrote_to_is_not_touched(store):
    """Inbound only. There is nothing to retire and nothing to write — the retire statement must
    not run up a row count on every node in the graph every sweep."""
    timeline(store, "p_a", inbound=[NOW - timedelta(days=2)])

    assert compute_waiting(store, ORG, now=NOW) == 1   # last_heard_days, nothing else


# =============================================================================================
# 2. A human's decision.
# =============================================================================================
def _upsert_source() -> str:
    from genios_engine.context import support_situations

    return inspect.getsource(support_situations._upsert)


def test_the_drain_preserves_a_human_resolution():
    """The provenance was ERASED, not overridden: `resolved_by = null` on conflict, every six
    hours. Nothing downstream could tell a re-derived row from one nobody had ever touched, and
    `decide_lifecycle`'s "a human resolution sticks until new evidence" was unreachable."""
    source = _upsert_source()

    assert "resolved_by = null" not in source
    assert "context_situations.resolved_by = 'human'" in source


def test_the_facts_underneath_still_refresh():
    """Only the DECISION is preserved. Confidence, coverage and last_seen are this sweep's,
    because they are observations and an observation does not care what somebody decided."""
    source = _upsert_source()

    for column in ("confidence_overall", "coverage", "last_seen_at", "missing", "inputs"):
        assert f"{column} = excluded.{column}" in source, column


def test_a_situation_nobody_resolved_still_comes_back_active():
    """The guard must not become a way for any stale row to stick. Only `resolved_by = 'human'`
    is preserved; a machine-derived resolution is re-derived like everything else."""
    source = _upsert_source()

    assert "else 'active' end" in source


def test_the_document_register_writes_the_same_rule():
    """`document_register` carries its own copy of the upsert, and a rule enforced in one of two
    identical statements is a rule that holds until somebody uses the other door."""
    from genios_engine.context import document_register

    source = inspect.getsource(document_register)

    assert "resolved_by = null" not in source
    assert "context_situations.resolved_by = 'human'" in source


# =============================================================================================
# 3 & 4. The passes that only ran when new mail arrived.
# =============================================================================================
def _process_pending_source() -> str:
    return inspect.getsource(runner.process_pending)


def test_the_situation_refresh_runs_on_a_quiet_org():
    """Dormancy at 45 days and archival at 180 are computed by `decide_lifecycle` inside this
    pass. Gated on new mail, a six-month-dead situation on a quiet tenant stayed `active` and
    kept compiling into cards — and a quiet tenant is exactly the one whose silence is the
    finding."""
    source = _process_pending_source()
    refresh = source.index("situation_rows = 0")

    assert "if done or affected:" not in source[refresh:refresh + 400]


def test_the_attention_refresh_runs_on_a_quiet_org():
    """Its own comment said why — "recency decays even for untouched nodes" — and then gated the
    call on new mail arriving, which is the opposite."""
    source = _process_pending_source()
    attention = source.index("attention_rows = 0")

    assert "if done or affected:" not in source[attention:attention + 400]


def test_a_failing_attention_refresh_is_no_longer_silent():
    """It was the only bare `except Exception: pass` in `process_pending`, so a refresh that
    failed every sweep for a month looked exactly like one that ran."""
    source = _process_pending_source()
    attention = source.index("attention_rows = 0")
    block = source[attention:attention + 700]

    assert "attention refresh failed" in block
    assert "except Exception:      # noqa: BLE001 — attention is an ordering hint, never fatal\n" \
           "        from genios_engine.platform.logging import get_logger" in block


def test_the_derived_block_above_them_was_already_unconditional():
    """The precedent these two now follow, and the argument is recorded there: a reading measured
    against a CLOCK does not change because new mail arrived — it changes because time passed."""
    source = _process_pending_source()

    assert "RUNS EVERY PASS, not only when the drain committed something." in source


# =============================================================================================
# 5. Last week's period review is over.
# =============================================================================================
def _period_store():
    """`context_situations` and the two graph tables `refresh_period_situations` writes."""
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for ddl in (
            "create table context_situations (situation_id text, org_id text, "
            "correlation_id text, anchor_node_id text, situation_type text, domain text, "
            "status text, resolved_by text, resolved_at timestamp, resolution_note text, "
            "confidence_overall int, confidence_evidence int, confidence_freshness int, "
            "confidence_consistency int, confidence_identity int, coverage int, missing text, "
            "inputs text, first_seen_at timestamp, last_seen_at timestamp, "
            "computed_at timestamp)",
            "create unique index ux_sit on context_situations (org_id, correlation_id)",
        ):
            c.execute(text(ddl))
    return Store(engine)


def _period_row(store, corr: str, stype: str, *, status: str = "active",
                resolved_by: str | None = None) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, "
            "  situation_type, domain, status, resolved_by) "
            "values (:s,:o,:c,:t,'admin',:st,:rb)"),
            {"s": f"sit_{corr}", "o": ORG, "c": corr, "t": stype, "st": status, "rb": resolved_by})


def _close_periods(store, *, key: str, types: list[str]):
    """Exactly the statement `refresh_period_situations` runs, against SQLite.

    Extracted rather than calling the whole refresh because that needs the graph tables and a
    tenant node; the STATEMENT is the thing that was unverified — its own tests skip without
    `GENIOS_TEST_DATABASE_URL`, and a skip is not a pass.
    """
    from sqlalchemy import bindparam

    with store.engine.begin() as c:
        return c.execute(text(
            "update context_situations set status='resolved', resolved_at=:now, "
            "  resolution_note='period window closed' "
            "where org_id=:o and status='active' and situation_type in :types "
            "  and correlation_id like :prefix and correlation_id not like :current "
            "  and resolved_by is null").bindparams(bindparam("types", expanding=True)),
            {"o": ORG, "now": NOW, "types": types,
             "prefix": f"corr_period_%_{ORG}_%",
             "current": f"corr_period_%_{ORG}_{key}"}).rowcount


def _status(store, corr: str) -> str:
    with store.engine.connect() as c:
        return c.execute(text(
            "select status from context_situations where org_id=:o and correlation_id=:c"),
            {"o": ORG, "c": corr}).scalar()


def test_last_windows_period_situation_is_closed():
    """`context_situations` grew by one active row per period domain PER WEEK for the life of the
    tenant, every one served to Layer 3 — and the count was self-inflating, because
    `period.active_situations` counts active situations and last week's were inside it."""
    store = _period_store()
    _period_row(store, f"corr_period_admin_{ORG}_2026-W36", "admin_period_review")
    _period_row(store, f"corr_period_admin_{ORG}_2026-W37", "admin_period_review")

    assert _close_periods(store, key="2026-W37", types=["admin_period_review"]) == 1
    assert _status(store, f"corr_period_admin_{ORG}_2026-W36") == "resolved"


def test_this_windows_period_situation_is_left_open():
    store = _period_store()
    _period_row(store, f"corr_period_admin_{ORG}_2026-W37", "admin_period_review")

    _close_periods(store, key="2026-W37", types=["admin_period_review"])

    assert _status(store, f"corr_period_admin_{ORG}_2026-W37") == "active"


def test_a_human_who_resolved_last_weeks_review_keeps_their_provenance():
    """`resolved_by is null` in the predicate. Overwriting it would erase the same provenance the
    `_upsert` fix above exists to preserve, through a different door."""
    store = _period_store()
    corr = f"corr_period_admin_{ORG}_2026-W36"
    _period_row(store, corr, "admin_period_review", status="active", resolved_by="human")

    assert _close_periods(store, key="2026-W37", types=["admin_period_review"]) == 0


def test_only_period_types_are_closed():
    """A blunter "close every tenant-anchored situation" would take rows another writer owns."""
    store = _period_store()
    _period_row(store, f"corr_period_admin_{ORG}_2026-W36", "admin_period_review")
    _period_row(store, "corr_outreach_someone", "awaiting_response")

    _close_periods(store, key="2026-W37", types=["admin_period_review"])

    assert _status(store, "corr_outreach_someone") == "active"


def test_another_tenants_period_review_is_untouched():
    store = _period_store()
    with store.engine.begin() as c:
        c.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, "
            "  situation_type, domain, status) "
            "values ('s2','org_other','corr_period_admin_org_other_2026-W36',"
            "        'admin_period_review','admin','active')"))

    _close_periods(store, key="2026-W37", types=["admin_period_review"])

    with store.engine.connect() as c:
        assert c.execute(text(
            "select status from context_situations where org_id='org_other'")).scalar() == "active"


def test_closing_twice_is_a_no_op():
    store = _period_store()
    _period_row(store, f"corr_period_admin_{ORG}_2026-W36", "admin_period_review")

    _close_periods(store, key="2026-W37", types=["admin_period_review"])

    assert _close_periods(store, key="2026-W37", types=["admin_period_review"]) == 0


def test_the_expanding_bindparam_is_used():
    """Without it SQLAlchemy renders the type list as one scalar and the statement matches
    nothing — silently. The whole closure would look like it ran and change no row."""
    from genios_engine.context import periodic

    source = inspect.getsource(periodic.refresh_period_situations)

    assert 'bindparam("types", expanding=True)' in source


# =============================================================================================
# 6. A meeting from three years ago is not follow-through work.
# =============================================================================================
def _touch_store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for ddl in (
            "create table context_situations (situation_id text, org_id text, "
            "correlation_id text, anchor_node_id text, situation_type text, domain text, "
            "status text, resolved_by text, resolved_at timestamp, resolution_note text, "
            "confidence_overall int, confidence_evidence int, confidence_freshness int, "
            "confidence_consistency int, confidence_identity int, coverage int, missing text, "
            "inputs text, first_seen_at timestamp, last_seen_at timestamp, "
            "computed_at timestamp)",
            "create unique index ux_touch on context_situations (org_id, correlation_id)",
        ):
            c.execute(text(ddl))
    return Store(engine)


def _touch_row(store, corr: str, *, status: str = "active", resolved_by=None) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, "
            "  situation_type, domain, status, resolved_by) "
            "values (:s,:o,:c,'channel_touch','sales',:st,:rb)"),
            {"s": f"sit_{corr}", "o": ORG, "c": corr, "st": status, "rb": resolved_by})


def _reconcile_touches(store, *, keep: list[str]):
    """The closing statement `refresh_channel_touch_situations` runs."""
    from sqlalchemy import bindparam

    with store.engine.begin() as c:
        return c.execute(text(
            "update context_situations set status='resolved', resolved_at=:now, "
            "  resolution_note='meeting outside the follow-through window' "
            "where org_id=:o and status='active' and situation_type=:st "
            "  and correlation_id like :prefix and resolved_by is null "
            + ("and correlation_id not in :keep " if keep else "")
            ).bindparams(*([bindparam("keep", expanding=True)] if keep else [])),
            {"o": ORG, "now": NOW, "st": "channel_touch", "prefix": "corr_touch_sales_%",
             **({"keep": sorted(keep)} if keep else {})}).rowcount


def test_a_meeting_outside_the_window_has_its_situation_closed():
    """It was never closed by anything: a meeting that fell out of scope simply stopped being
    visited, and 'a finding that stops being produced is not a finding that ended' — the same
    defect `waiting.py` carried, one situation type over."""
    store = _touch_store()
    _touch_row(store, "corr_touch_sales_node_old")

    assert _reconcile_touches(store, keep=["corr_touch_sales_node_recent"]) == 1


def test_a_meeting_inside_the_window_is_kept():
    store = _touch_store()
    _touch_row(store, "corr_touch_sales_node_recent")

    assert _reconcile_touches(store, keep=["corr_touch_sales_node_recent"]) == 0


def test_a_tenant_with_no_live_meetings_closes_all_of_them():
    """The empty-`keep` branch, which renders a DIFFERENT statement — the `not in ()` SQLAlchemy
    would otherwise produce is a syntax error, so this path has to be built without the clause."""
    store = _touch_store()
    _touch_row(store, "corr_touch_sales_a")
    _touch_row(store, "corr_touch_sales_b")

    assert _reconcile_touches(store, keep=[]) == 2


def test_a_human_who_closed_a_meeting_keeps_their_provenance():
    store = _touch_store()
    _touch_row(store, "corr_touch_sales_old", resolved_by="human")

    assert _reconcile_touches(store, keep=[]) == 0


def test_freshness_is_the_meetings_own_age():
    """It was hard-coded to `CONFIDENCE_PCT`, so a row about a meeting eleven weeks ago claimed
    the same currency as one about yesterday."""
    from genios_engine.context.meeting_touch import CONFIDENCE_PCT, _freshness

    yesterday = _freshness(NOW - timedelta(days=1), NOW)
    eleven_weeks = _freshness(NOW - timedelta(days=77), NOW)

    assert yesterday > eleven_weeks
    assert yesterday == 100
    assert CONFIDENCE_PCT == 70


def test_an_undated_meeting_is_not_reported_as_stale():
    """`freshness_score` answers `known=False` for an undated meeting, and that is an ABSENCE of
    information about time — scoring it 0 would turn missing data into bad news."""
    from genios_engine.context.meeting_touch import CONFIDENCE_PCT, _freshness

    assert _freshness(None, NOW) == CONFIDENCE_PCT


def test_a_string_timestamp_is_accepted():
    """Postgres returns a datetime; a driver need not. The whole pass would silently skip every
    meeting on one that does not."""
    from genios_engine.context.meeting_touch import _as_utc

    assert _as_utc("2026-09-01T10:00:00+00:00") == datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    assert _as_utc("2026-09-01T10:00:00Z") == datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    assert _as_utc("not a date") is None
    assert _as_utc(None) is None


def test_a_naive_timestamp_is_read_as_utc():
    from genios_engine.context.meeting_touch import _as_utc

    assert _as_utc(datetime(2026, 9, 1, 10)).tzinfo is timezone.utc


def test_the_window_and_last_seen_are_the_meetings_not_the_sweeps():
    """`last_seen_at` was bumped to the sweep instant every six hours, so a three-year-old
    meeting sat at the top of `domain_shadow`'s newest-evidence ordering, ahead of this
    morning's mail."""
    from genios_engine.context import meeting_touch

    source = inspect.getsource(meeting_touch.refresh_channel_touch_situations)

    assert '"seen": start_at or now' in source
    assert "FOLLOW_THROUGH_DAYS" in source
