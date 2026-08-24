from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository


class _JunkGate:
    """Stub S2 LLM junk-gate: drops the newsletter (no-reply/digest), keeps business mail.

    The drop now happens at the S2 gate on judgment, not a regex — a plain no-reply sender is no
    longer hard-dropped at S1 (a receipt/invoice comes from noreply@ too), so the gate is what
    stops the newsletter."""

    def classify(self, ctx, prepared):
        from genios_engine.capture.gate.relevance import RelevanceVerdict
        email = (ctx.event.actor.email or "").lower()
        subject = (ctx.raw.get("subject") or "").lower()
        junk = "no-reply" in email or "digest" in subject
        return RelevanceVerdict(not junk, 0.1 if junk else 0.8,
                                disposition="drop" if junk else "keep")


class MixedConnector:
    """Two business emails + one no-reply newsletter → 2 emitted, 1 dropped (by the S2 gate)."""
    source = "gmail"

    def _objs(self):
        t = datetime(2026, 7, 28, tzinfo=timezone.utc)
        return [
            RawObject("gmail", "email_message", "m1", t, actor_email="priya@acme.com",
                      raw={"snippet": "Can you send the contract by Friday?"}),
            RawObject("gmail", "email_message", "m2", t, actor_email="arjun@beta.io",
                      raw={"snippet": "Following up on pricing."}),
            RawObject("gmail", "email_message", "m3", t, actor_email="no-reply@news.io",
                      raw={"subject": "Weekly digest", "snippet": "news"}),
        ]

    def incremental_changes(self, cursor=None, limit=100, since=None):
        return SourceBatch(objects=self._objs(), next_cursor="cur_2")

    def initial_snapshot(self, cursor=None, limit=100):
        return SourceBatch(objects=self._objs(), next_cursor="cur_2")


def test_sync_counts_and_cursor():
    repo = InMemorySourceEventRepository()
    s = run_sync(MixedConnector(), org_id="o", connection_id="c", repo=repo, relevance=_JunkGate())

    assert s.scanned == 3
    assert s.emitted == 2
    assert s.dropped == 1
    assert len(s.gated) == 2
    assert s.next_cursor == "cur_2"


def test_resync_is_idempotent():
    repo = InMemorySourceEventRepository()
    conn = MixedConnector()
    run_sync(conn, org_id="o", connection_id="c", repo=repo, relevance=_JunkGate())
    s2 = run_sync(conn, org_id="o", connection_id="c", repo=repo, relevance=_JunkGate())   # same batch again
    # every event was already SEEN on the first sync (landed for dedup+audit, even the
    # one that was gate-dropped), so the whole re-sync is duplicates — nothing reprocessed.
    assert s2.emitted == 0
    assert s2.duplicate == 3
    assert repo.count() == 3      # stable; never double-counted


class _RecordingCursorStore:
    """Captures what run_sync persists, so a watermark assertion is about the STORED value."""

    def __init__(self) -> None:
        self.saved: dict = {}

    def get(self, *_a, **_kw):
        return None

    def save(self, org_id, connection_id, source, *, cursor=None, watermark=None):
        self.saved = {"org_id": org_id, "connection_id": connection_id, "source": source,
                      "cursor": cursor, "watermark": watermark}


class _FutureMeetingConnector:
    """A calendar whose events START in the future but were UPDATED in the past.

    This is an ordinary calendar: booking next month's board meeting today is not an edge case.
    """
    source = "gcal"

    def __init__(self, *, start, updated):
        self._start, self._updated = start, updated

    def _objs(self):
        return [RawObject("gcal", "calendar_event", "ev1", self._start,
                          actor_email="founder@acme.com", actor_type="internal_user",
                          synced_at=self._updated,
                          raw={"summary": "Board meeting", "status": "confirmed"})]

    def incremental_changes(self, cursor=None, limit=100, since=None):
        return SourceBatch(objects=self._objs(), next_cursor="cur_1")

    def initial_snapshot(self, cursor=None, limit=100):
        return SourceBatch(objects=self._objs(), next_cursor="cur_1")


def test_watermark_advances_on_last_modified_not_on_meeting_start():
    """A future meeting must never push the cursor past now, or the connector goes silent.

    Regression: the gcal cursor advanced on `occurred_at`, which for a calendar event is the
    MEETING START. One event booked for next month set the watermark to a future date, so every
    later incremental sync asked Google for changes "since" a date that had not happened — nine
    consecutive runs scanned 1 object and found 0 new, while `l1_sync_runs` still reported
    success and `can_evaluate_no_meeting` still read *fresh* from a dead connector.
    """
    now = datetime.now(timezone.utc)
    future_start = now.replace(microsecond=0) + timedelta(days=30)
    real_update = now.replace(microsecond=0) - timedelta(hours=2)

    cursors = _RecordingCursorStore()
    run_sync(_FutureMeetingConnector(start=future_start, updated=real_update),
             org_id="o", connection_id="c", repo=InMemorySourceEventRepository(),
             cursor_store=cursors, relevance=_JunkGate())

    stored = cursors.saved["watermark"]
    assert stored is not None
    assert stored <= datetime.now(timezone.utc), (
        f"watermark {stored.isoformat()} is in the future — the connector will go silent")
    assert stored == real_update, "the cursor must advance on `updated`, not on the meeting start"


def test_a_connector_cannot_persist_a_future_watermark_even_if_it_tries():
    """The clamp is a floor under every connector, not a calendar-specific patch.

    `synced_at` is connector-supplied, so a buggy or hostile source could still hand back a
    future stamp. run_sync refuses it rather than trusting the caller.
    """
    now = datetime.now(timezone.utc)
    bogus = now + timedelta(days=365)

    cursors = _RecordingCursorStore()
    run_sync(_FutureMeetingConnector(start=bogus, updated=bogus),
             org_id="o", connection_id="c", repo=InMemorySourceEventRepository(),
             cursor_store=cursors, relevance=_JunkGate())

    stored = cursors.saved["watermark"]
    assert stored <= datetime.now(timezone.utc), "run_sync must clamp a future watermark to now"


def test_source_is_taken_from_the_connector_not_a_default():
    """A caller must never be able to file a gcal sync under the gmail cursor key.

    `source` defaulted to "gmail", so any caller that omitted it read the wrong watermark and
    wrote a second `(connection_id, source)` row for the same connection — two cursors for one
    connector, each advancing independently, neither obviously wrong from the outside.
    """
    cursors = _RecordingCursorStore()
    now = datetime.now(timezone.utc)
    run_sync(_FutureMeetingConnector(start=now, updated=now - timedelta(hours=1)),
             org_id="o", connection_id="c", repo=InMemorySourceEventRepository(),
             cursor_store=cursors, relevance=_JunkGate())          # no source= on purpose

    assert cursors.saved["source"] == "gcal", (
        "the cursor was filed under the default source, not the connector's own")


def test_a_source_that_contradicts_the_connector_is_refused():
    """Passing the wrong source explicitly is a caller bug, not something to paper over."""
    import pytest

    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="contradicts connector.source"):
        run_sync(_FutureMeetingConnector(start=now, updated=now),
                 org_id="o", connection_id="c", repo=InMemorySourceEventRepository(),
                 source="gmail", relevance=_JunkGate())
