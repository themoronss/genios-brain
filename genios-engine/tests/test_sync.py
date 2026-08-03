from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository


class MixedConnector:
    """Two business emails + one no-reply newsletter → 2 emitted, 1 dropped."""
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
    s = run_sync(MixedConnector(), org_id="o", connection_id="c", repo=repo)

    assert s.scanned == 3
    assert s.emitted == 2
    assert s.dropped == 1
    assert len(s.gated) == 2
    assert s.next_cursor == "cur_2"


def test_resync_is_idempotent():
    repo = InMemorySourceEventRepository()
    conn = MixedConnector()
    run_sync(conn, org_id="o", connection_id="c", repo=repo)
    s2 = run_sync(conn, org_id="o", connection_id="c", repo=repo)   # same batch again
    # every event was already SEEN on the first sync (landed for dedup+audit, even the
    # one that was gate-dropped), so the whole re-sync is duplicates — nothing reprocessed.
    assert s2.emitted == 0
    assert s2.duplicate == 3
    assert repo.count() == 3      # stable; never double-counted
