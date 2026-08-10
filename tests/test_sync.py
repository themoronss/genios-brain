from __future__ import annotations

from datetime import datetime, timezone

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
