"""`03` F148 · a mail read late keeps the dates its writer meant.

    pytest tests/capture/test_a_backlog_mail_keeps_its_dates.py -q

`yc2_w27_align` M34.C2.L-logic.V1.U14. A sync reads mail when it runs, not when the mail was written:
on a first connect, after downtime, and in STEP-08's re-sync of history, weeks or months late. The
sweep's semantic lane carries ONE clock — the sync's — and every request was built with it, so every
relative date in every message of the sweep was resolved against the day it was READ: golden case
F48's 16 Jul *"this week"*, read on 30 Jul, was due at the sweep's own instant. Capture now hands the
extractor each message's own time (`ExtractionRequest.written_at`, U13), and ALG-09 resolves against
when the words were written.

Driven through `run_sync`, the function every capture path goes through, with a real `SemanticLane`
and a `FakeLLM` that answers the one extraction it is asked — hermetic, no database.
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

#: Written on Thursday 16 Jul, read by a sync on 30 Jul — two weeks late, as a re-sync reads.
WRITTEN = datetime(2026, 7, 16, 7, 10, tzinfo=timezone.utc)
READ = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
OWNER = "arjun@nimbuslabs.test"
BODY = "Thanks Mira, appreciate it! Will connect with Tarun this week, and I will send the deck by Friday."


def _cite(quote: str) -> list[dict]:
    start = BODY.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


#: What the model says: a promise due "this week", and a date "by Friday". Its own windows are
#: absent — ALG-09 computes them, and that computation is what this file is about.
ANSWER = {
    "intent": "commit", "stance": "positive",
    "dates_mentioned": [{"as_written": "by Friday", "evidence": _cite("by Friday")}],
    "commitments": [{"actor": "Arjun Rao", "action": "connect with Tarun", "beneficiary": "Tarun",
                     "is_conditional": False,
                     "due": {"as_written": "this week", "evidence": _cite("this week")},
                     "evidence": _cite("Will connect with Tarun this week"),
                     "confidence_bp": 9000}],
}


class _Mailbox:
    source = "gmail"

    def __init__(self, occurred_at: datetime) -> None:
        self._objects = [RawObject(
            source="gmail", object_type="email_message", source_object_id="m_backlog",
            occurred_at=occurred_at, actor_email=OWNER, recipients=("mira@linkbridge.test",),
            raw={"subject": "Re: Intro", "body": BODY, "thread_depth": 2})]

    def validate_connection(self) -> bool:
        return True

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=list(self._objects), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=list(self._objects), next_cursor=None)

    def fetch_content(self, object_ref: str) -> dict:
        return {}


def _extracted(fake_llm, *, occurred_at: datetime):
    llm = fake_llm(ANSWER)
    summary = run_sync(_Mailbox(occurred_at), org_id="org_backlog", connection_id="con_backlog",
                       repo=InMemorySourceEventRepository(), mailbox_owner=OWNER,
                       semantic=P.SemanticLane(llm=llm, eval_time=READ))
    assert llm.call_count == 1, "the one extraction was not asked"
    (result,) = summary.results
    assert result.extraction is not None, result.extraction_parked
    return result.extraction


def test_a_promise_read_two_weeks_late_is_due_the_week_it_named(fake_llm):
    """"this week", written Thursday 16 Jul, is the week ending Sunday 19 Jul in the org's zone —
    not the week of the sync that read it, and not the sync's own instant."""
    due = _extracted(fake_llm, occurred_at=WRITTEN).commitments[0].due
    assert due is not None
    assert due.resolved_against == WRITTEN
    assert due.latest < READ, f"due by {due.latest}: resolved against the sync, not the mail"


def test_a_date_read_two_weeks_late_is_the_friday_it_named(fake_llm):
    (date,) = _extracted(fake_llm, occurred_at=WRITTEN).dates_mentioned
    assert date.resolved_against == WRITTEN
    assert date.earliest.date() == datetime(2026, 7, 17).date(), date.earliest


def test_a_mail_read_as_it_arrives_is_unchanged(fake_llm):
    """Live mail: written and read in the same minute, the two clocks agree, as they always did."""
    due = _extracted(fake_llm, occurred_at=READ).commitments[0].due
    assert due is not None and due.resolved_against == READ


def test_a_mail_with_no_zone_on_its_time_resolves_against_the_sync(fake_llm):
    """A time without a zone names no instant — the lane's clock stands, and capture does not fail."""
    due = _extracted(fake_llm, occurred_at=WRITTEN.replace(tzinfo=None)).commitments[0].due
    assert due is not None and due.resolved_against == READ
