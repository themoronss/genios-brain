from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.acquire.sync_runner import backfill_drain
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

# On a huge first connect, the incremental sync (newest-first + advancing watermark, capped at
# max_pages) skipped the older tail permanently. backfill_drain pages to cursor-exhaustion so the
# WHOLE history lands, without touching the incremental watermark.


class _PagedConnector:
    source = "gmail"

    def __init__(self, pages: list[list[RawObject]]) -> None:
        self.pages = pages

    def initial_snapshot(self, cursor, limit) -> SourceBatch:
        idx = int(cursor) if cursor else 0
        objs = self.pages[idx] if idx < len(self.pages) else []
        nxt = str(idx + 1) if idx + 1 < len(self.pages) else None
        return SourceBatch(objects=objs, next_cursor=nxt)

    def incremental_changes(self, cursor, limit, since=None) -> SourceBatch:
        return self.initial_snapshot(cursor, limit)


def _obj(oid: str) -> RawObject:
    return RawObject(source="gmail", object_type="email", source_object_id=oid,
                     occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                     actor_type="external_contact", actor_email="a@acme.io",
                     raw={"body": "hello there, this is a real business message about the proposal.",
                          "subject": "proposal"})


def test_drain_pages_the_full_history_to_exhaustion():
    pages = [[_obj("m1"), _obj("m2")], [_obj("m3")], [_obj("m4"), _obj("m5")]]
    repo = InMemorySourceEventRepository()
    total = backfill_drain(_PagedConnector(pages), org_id="o", connection_id="c",
                           repo=repo, source="gmail", limit=10)
    assert total.scanned == 5            # all 3 pages drained — not just the first ~max_pages
    assert total.next_cursor is None     # cursor exhausted, nothing left behind


def test_drain_is_bounded_by_max_rounds():
    # a connector that never exhausts must not loop forever
    class _Endless:
        source = "gmail"

        def initial_snapshot(self, cursor, limit):
            return SourceBatch(objects=[_obj(f"m{cursor or 0}")], next_cursor=str((int(cursor or 0)) + 1))

        def incremental_changes(self, cursor, limit, since=None):
            return self.initial_snapshot(cursor, limit)

    total = backfill_drain(_Endless(), org_id="o", connection_id="c",
                           repo=InMemorySourceEventRepository(), source="gmail", max_rounds=3)
    assert total.scanned == 3            # stopped at the runaway guard, not infinite
    assert total.next_cursor is not None
