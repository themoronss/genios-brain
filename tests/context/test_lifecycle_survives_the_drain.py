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
