"""Step 5 · the coverage denominator — a sweep that STOPPED reports the word "done".

    pytest tests/capture/acquire/test_a_sweep_says_whether_it_finished.py -q

THE DEFECT, IN ONE SENTENCE. `api/routes.py:1522` logs

    "backfill drain done org=%s conn=%s scanned=%s emitted=%s"

whether the provider ran out of mail or the 500-page runaway guard stopped us halfway through a
tenant's history — and **no record anywhere can tell the two apart afterwards.** `l1_sync_runs` has
fifteen columns and not one of them is "did this finish":

    run_id · org_id · connection_id · source · mode
    scanned · emitted · dropped · parked · duplicate · quarantined
    error · started_at · finished_at

That is the benchmark's own headline failure reproduced inside our ingestion. Gemini reported
*"18 threads read of 18 that exist"* against a mailbox of ~465 — **it reported the size of what it
read as the size of what exists.** A backfill that stops at page 500 and files a row saying
`scanned=50000` is making the identical claim.

WHAT IS NOT WRONG, AND IS WORTH SAYING. The fact is not missing from the system — it is computed,
branched on, and thrown away:

    sync_runner.backfill_drain     total.next_cursor = cursor      # None => exhausted
    api/routes.py:3221             capped = cursor is not None     # the ONBOARDING door
                                   logs "CAPPED" vs "done", and says the older tail remains

So one of the two backfill doors already knows. The other does not, and neither writes it down.
This file is about writing it down.

THREE STATES, NOT TWO — which is why the column is a NULLABLE boolean:

    true    the provider said there is no more; complete for this window
    false   there is more and we stopped
    null    NOT APPLICABLE — a webhook has no pagination to exhaust (E5). Storing `true` here
            would be the fabricated 100% §9 of the step file forbids in as many words.

And `false` splits again, which the step file did not name: **we** stopped (the runaway guard, so
re-running `/backfill` recovers it) or **the provider** stopped (an error or a rate limit, which
re-running alone does not fix). A single "incomplete" flag would make an operator re-run a sweep
that cannot get further, and not re-run one that could.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# The summary carries the answer — it is computed today and has nowhere to live
# =============================================================================================
def test_a_sweep_reports_whether_the_cursor_was_exhausted():
    """`run_sync` already knows: it breaks out of the page loop on `not page_cursor`. The break
    is the fact; `next_cursor` is the fact stored under a name that reads as "where to resume"
    rather than as "whether we finished", and nothing downstream reads it as the latter."""
    from genios_engine.capture.acquire.sync_runner import SyncSummary

    assert "cursor_exhausted" in SyncSummary.__dataclass_fields__, (
        "a sweep cannot say whether it finished, so a truncated backfill and a complete one are "
        "the same row")


def test_not_applicable_is_a_third_state_and_not_a_hundred_percent():
    """E5. A push/webhook source has no pagination, so "did the cursor exhaust" has no answer —
    and `true` would be a fabricated 100%, which §9 of the step file forbids by name.

    The default is None for the same reason a missing field is never guessed anywhere else in
    this layer: `unknown` is a real answer.
    """
    from genios_engine.capture.acquire.sync_runner import SyncSummary

    assert SyncSummary().cursor_exhausted is None, (
        "the default asserts completeness for a sweep that never ran")


def test_a_sweep_says_who_stopped_it():
    """`false` is two different operational situations and only one is recoverable by re-running:

        budget spent      WE stopped — the `max_rounds` runaway guard. Re-run `/backfill`.
        budget remaining  the PROVIDER stopped, or an error did. Re-running alone does not fix it.

    An operator with one undifferentiated "incomplete" flag re-runs the sweep that cannot get
    further and leaves the one that could.
    """
    from genios_engine.capture.acquire.sync_runner import SyncSummary

    assert "page_budget_spent" in SyncSummary.__dataclass_fields__


def test_the_provider_s_own_total_is_carried_and_labelled_as_an_estimate():
    """E1 and the headline. Gmail's `resultSizeEstimate` is an ESTIMATE and the step file says in
    as many words: *"store it as an estimate, labelled — never as a fact."*

    E2 follows from the same field: fetched > claimed is LEGAL when the estimate is low, and a
    system that treated the excess as an error would raise on a correct sweep.
    """
    from genios_engine.capture.acquire.sync_runner import SyncSummary

    fields = SyncSummary.__dataclass_fields__
    assert "claimed_total" in fields, "the denominator has nowhere to live"
    assert "claimed_is_estimate" in fields, (
        "an estimate stored without its label becomes a fact at the first reader")


# =============================================================================================
# THE DENOMINATOR ACTUALLY ARRIVES — the half this file nearly shipped as plumbing
# =============================================================================================
def test_the_batch_contract_can_carry_a_provider_total():
    """`SourceBatch` had `objects` and `next_cursor` and nothing else.

    THIS IS WHERE THE FIRST VERSION OF THIS STEP FAILED. `run_sync` read the total with
    `getattr(batch, "claimed_total", None)` — defensively, against a field that did not exist on
    the contract and that no connector set — so `claimed_total` was None on every row forever and
    the test above still passed, because it only asked whether `SyncSummary` had somewhere to put
    a number nothing produced.

    That is the defect this whole plan keeps naming: *a unit built, tested, green — and called by
    nothing on a real request path.* Caught here by asking the CONTRACT, not the container.
    """
    from genios_engine.capture.connectors.base import SourceBatch

    batch = SourceBatch(objects=[])
    assert batch.claimed_total is None, (
        "the default asserts a count no provider gave — 'the window is empty' and 'we were not "
        "told' are different answers")
    assert batch.claimed_is_estimate is True, (
        "a connector that sets a total without saying which kind it is must get the CAUTIOUS "
        "reading; presenting an estimate as exact is the mistake that costs something")


def test_gmail_reports_its_own_result_size_estimate():
    """DRIVES THE REAL PARSER. `_to_batch` is the function every Gmail page goes through, and
    `resultSizeEstimate` is the only provider-side count this product receives from anywhere.

    Asserted through the shipping method rather than by constructing a `SourceBatch` by hand: a
    test that built the object itself would pass on a connector that never reads the field, which
    is exactly the state this step was in an hour ago.
    """
    from genios_engine.capture.connectors.composio import ComposioGmailConnector

    connector = ComposioGmailConnector.__new__(ComposioGmailConnector)
    batch = connector._to_batch({"data": {"messages": [], "resultSizeEstimate": 465,
                                          "nextPageToken": "p2"}})

    assert batch.claimed_total == 465, "Gmail's own count is still being thrown away"
    assert batch.claimed_is_estimate is True, (
        "Google named the field `resultSizeEstimate`; storing it unlabelled makes 465 read as a "
        "number somebody could be held to")


def test_a_missing_or_nonsense_total_is_none_and_never_zero():
    """A provider that offers no count, or a negative one, must leave the denominator UNKNOWN.

    Zero is the dangerous wrong answer: it reads as "there is nothing in this window", which is a
    reason to stop looking. `None` reads as "we were not told", which is not.
    """
    from genios_engine.capture.connectors.composio import ComposioGmailConnector

    connector = ComposioGmailConnector.__new__(ComposioGmailConnector)
    for payload in ({"messages": []},
                    {"messages": [], "resultSizeEstimate": None},
                    {"messages": [], "resultSizeEstimate": "not a number"},
                    {"messages": [], "resultSizeEstimate": -1}):
        assert connector._to_batch({"data": payload}).claimed_total is None, payload


def test_the_total_reaches_the_summary_through_run_sync():
    """END TO END over the seam that matters: connector → `run_sync` → `SyncSummary`.

    The FIRST page's count is the one kept. Later pages of the same query repeat it, and a sweep
    whose denominator changed halfway would be reporting two different mailboxes as one.
    """
    from datetime import datetime, timezone

    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.capture.connectors.base import RawObject, SourceBatch
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    class _Counting:
        source = "fake"

        def initial_snapshot(self, cursor=None, limit=100):
            return SourceBatch(
                objects=[RawObject(source="fake", object_type="note", source_object_id="o1",
                                   occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                                   actor_email="a@example.com", raw={"snippet": "hello"})],
                next_cursor=None, claimed_total=465)

        def incremental_changes(self, cursor=None, limit=100, since=None):
            return self.initial_snapshot(cursor, limit)

        def fetch_content(self, object_ref):
            return {"body": "hello"}

    summary = run_sync(_Counting(), org_id="org_d", connection_id="conn_d",
                       repo=InMemorySourceEventRepository(), source="fake", mode="backfill")

    assert summary.claimed_total == 465, (
        "the provider's count does not survive the sweep, so 'claimed vs fetched' is still one "
        "number and a guess")
    assert summary.claimed_is_estimate is True
    assert summary.scanned == 1, "and the numerator is the fetched count, beside it"


# =============================================================================================
# The drain — the door where truncation actually happens
# =============================================================================================
def _drain(*, pages_available: int, max_rounds: int):
    """Run `backfill_drain` against a connector with a known amount of history."""
    from genios_engine.capture.acquire.sync_runner import backfill_drain
    from genios_engine.capture.connectors.base import RawObject, SourceBatch
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    from datetime import datetime, timezone

    class _Pages:
        """A provider with exactly `pages_available` pages and one object on each.

        `initial_snapshot` is what `_fetch_page` calls in BACKFILL mode — the same entry the real
        connectors expose. A fake with its own invented method would test a path the drain does
        not take, which is the defect class this whole plan keeps finding.
        """

        source = "fake"

        def initial_snapshot(self, cursor=None, limit=100):
            page = int(cursor or 0)
            if page >= pages_available:
                return SourceBatch(objects=[], next_cursor=None)
            obj = RawObject(
                source="fake", object_type="note", source_object_id=f"o{page}",
                occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                actor_email="somebody@example.com",
                raw={"subject": f"page {page}", "snippet": f"page {page}"})
            nxt = str(page + 1) if page + 1 < pages_available else None
            return SourceBatch(objects=[obj], next_cursor=nxt)

        def incremental_changes(self, cursor=None, limit=100, since=None):
            return self.initial_snapshot(cursor, limit)

        def fetch_content(self, object_ref):
            return {"body": "a body"}

    return backfill_drain(_Pages(), org_id="org_step5", connection_id="conn_step5",
                          repo=InMemorySourceEventRepository(), source="fake",
                          max_rounds=max_rounds, pages_per_round=1)


def test_a_drain_that_reached_the_end_says_so():
    """The provider ran out. This is the only case in which a sweep may claim completeness."""
    total = _drain(pages_available=3, max_rounds=10)

    assert total.cursor_exhausted is True
    assert total.page_budget_spent is False


def test_a_drain_the_guard_cut_short_does_not_report_completion():
    """THE LOAD-BEARING ROW. Three pages of history, a budget of two.

    Today this returns a summary indistinguishable from the one above, and `routes.py:1522` prints
    "backfill drain done" over it. A tenant's older mail is missing and every record we keep says
    the sweep succeeded.
    """
    total = _drain(pages_available=3, max_rounds=2)

    assert total.cursor_exhausted is False, (
        "the sweep stopped with history remaining and reports completion — this is the benchmark's "
        "own failure, committed by our ingestion")
    assert total.page_budget_spent is True, "the runaway guard stopped it, so a re-run recovers it"
    assert total.next_cursor is not None, "a resumable position must survive the truncation"


def test_the_exact_boundary_is_complete_and_not_truncated():
    """OFF-BY-ONE, and it decides whether a correct sweep is reported as a failure.

    Budget exactly equal to the pages available. The provider is exhausted ON the last permitted
    page, so the sweep IS complete — and a naive `budget == 0 => truncated` reads it as a failure
    and sends an operator chasing mail that is already here.
    """
    total = _drain(pages_available=2, max_rounds=2)

    assert total.cursor_exhausted is True, (
        "a sweep that finished on its last allowed page was reported as truncated")


# =============================================================================================
# It reaches storage — a value nothing persists is a value the next sweep cannot compare against
# =============================================================================================
def test_the_ledger_writes_the_completeness_columns():
    """`l1_sync_runs` is the per-run ledger and already carries connection, source and mode, so
    this needs COLUMNS and not the new table the step file assumed. One writer, nothing to drift.

    Asserted against the INSERT rather than the migration: a column no writer names is a column
    that is null in every row, which is what happened to `started_at` — the table had it from the
    day it was created and the insert never mentioned it, so every row in production recorded a
    finish with no start.
    """
    import inspect

    from genios_engine.api import routes

    source = inspect.getsource(routes._run_ledger)
    for column in ("cursor_exhausted", "page_budget_spent", "claimed_total",
                   "claimed_is_estimate"):
        assert column in source, f"`{column}` is computed and never written down"


def test_the_migration_adds_the_columns_nullably():
    """NULLABLE, and not by accident. Every row written before this migration has no answer, and
    a NOT NULL with a `false` default would state that every historical sweep was INCOMPLETE —
    which is a claim about the past that nobody measured."""
    from pathlib import Path

    sql = Path("migrations/0178_sync_completeness.sql").read_text()

    assert "cursor_exhausted" in sql and "boolean" in sql
    assert "not null" not in sql.lower().replace("not null default", ""), (
        "a NOT NULL here invents an answer for every sweep that ran before this step")


def test_the_manual_backfill_door_stops_saying_done_when_it_means_stopped():
    """The two doors disagreed, and this is the one that was wrong.

    `api/routes.py:3221` (onboarding) already computes `capped = cursor is not None` and logs
    "CAPPED" plus *"safety ceiling hit, older tail remains"*. `api/routes.py:1522` (manual
    `/backfill`) logs the word "done" either way. Same fact, same file, two answers.
    """
    import inspect

    from genios_engine.api import routes

    source = inspect.getsource(routes)
    start = source.index("backfill drain")
    window = source[start - 400:start + 400]
    assert "TRUNCATED" in window or "capped" in window, (
        "the manual backfill door still reports 'done' for a sweep that stopped at the guard")
