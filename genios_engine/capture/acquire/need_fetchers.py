"""GeniOS-008 L1 E2 · the fetchers — L1 answering L2's named question through the SAME capture door.

`need_executor.build_fetchers` returned `{}` and said why: no connector was wired, and a stub that "found
nothing" would close every question permanently. This is the wiring, on three refusals:

  1. ⛔ OFF BY DEFAULT. `GENIOS_NEED_FETCHERS=on` arms it, per deployment, after Harsh has run one fetch by
     hand (`speedrun008/GeniOS-008/layer-1-enterprise-signals/04-FOR-HARSH.md`). Off, `build_fetchers` stays
     `{}` and the executor refuses exactly as before — no question is closed.
  2. ⛔ THROUGH THE DOOR, NEVER AROUND IT. A fetch does not write rows itself: it hands ONE batch to
     `run_sync` (wrapped in `ScopedBatchConnector`), so the fetched mail is deduplicated, gated, extracted,
     qualified, published and BUNDLED like every other mail — and Layer 2 sees the answer as a new bundle on
     its subject.
  3. ⛔ A PROVIDER REFUSAL IS NOT "NOTHING FOUND". `raise_if_refused` raises; the executor closes the need
     `unavailable` with the error's name, never as an empty window (L1 A1's rule).

Two fetches, both Gmail:
  FETCH_THREAD     `thread:<gmail thread id>` → the thread's messages (`GMAIL_FETCH_MESSAGE_BY_THREAD_ID`);
  BACKFILL_WINDOW  a need with a window → the mail in it (`after:` / `before:` — Gmail's own query words).
REEXTRACT is not wired: re-running extraction on a stored payload belongs to the document job store, and a
need that asks for it stays OPEN (the executor's refusal 2) rather than closing on a fetch that cannot run.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from genios_engine.capture.acquire.evidence_need import BACKFILL_WINDOW, FETCH_THREAD
from genios_engine.capture.connectors.base import SourceBatch
from genios_engine.capture.connectors.composio_base import raise_if_refused
from genios_engine.contracts.evidence import EvidenceNeed

FETCHERS_ENV = "GENIOS_NEED_FETCHERS"
THREAD_SLUG = "GMAIL_FETCH_MESSAGE_BY_THREAD_ID"
WINDOW_MAX = 50


def armed() -> bool:
    return os.environ.get(FETCHERS_ENV, "").strip().lower() in ("1", "on", "true", "yes")


class ScopedBatchConnector:
    """A connector that returns ONE batch it was handed, once, and delegates everything else (content,
    attachments) to the real connector — so `run_sync` can carry a fetched thread through the door."""

    def __init__(self, inner: Any, batch: SourceBatch) -> None:
        self._inner, self._batch, self._spent = inner, batch, False

    def _once(self) -> SourceBatch:
        if self._spent:
            return SourceBatch(objects=[])
        self._spent = True
        return self._batch

    def validate_connection(self) -> bool:
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._once()

    def incremental_changes(self, cursor: str | None = None, limit: int = 50, **_: Any) -> SourceBatch:
        return self._once()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def thread_id_of(need: EvidenceNeed) -> str | None:
    ref = (need.subject_ref or "").strip()
    while ref.startswith("thread:"):
        ref = ref[len("thread:"):]
    return ref or None


def _gmail_day(at: Any) -> str | None:
    if isinstance(at, str):
        try:
            at = datetime.fromisoformat(at)
        except ValueError:
            return None
    return at.strftime("%Y/%m/%d") if isinstance(at, datetime) else None


def window_query(need: EvidenceNeed) -> str | None:
    """Gmail's own query words for the need's window — None when it names none."""
    after, before = _gmail_day(need.window_from), _gmail_day(need.window_to)
    words = [w for w in (f"after:{after}" if after else None, f"before:{before}" if before else None) if w]
    return " ".join(words) or None


def make_fetchers(*, connector_for: Callable[[], Any], sync: Callable[[Any], Any]) -> dict[str, Callable]:
    """The two Gmail fetchers. `connector_for` builds the tenant's Gmail connector; `sync` carries a scoped
    connector through the tenant's capture door and returns its summary. Both injected: `capture/` may not
    import the composition root."""

    def _captured(summary: Any) -> int:
        return int(getattr(summary, "emitted", 0) or 0) + int(getattr(summary, "duplicate", 0) or 0)

    def fetch_thread(need: EvidenceNeed) -> dict[str, Any] | None:
        tid = thread_id_of(need)
        if not tid:
            return None
        connector = connector_for()
        args: dict[str, Any] = {"thread_id": tid, "user_id": "me"}
        if getattr(connector, "_account", None):
            args["connected_account_id"] = connector._account
        result = raise_if_refused(THREAD_SLUG, connector._execute(THREAD_SLUG, args))
        batch = connector._to_batch(result)
        if not batch.objects:
            return None
        summary = sync(ScopedBatchConnector(connector, batch))
        return {"source": "gmail", "kind": FETCH_THREAD, "objects": len(batch.objects),
                "captured": _captured(summary)}

    def backfill_window(need: EvidenceNeed) -> dict[str, Any] | None:
        query = window_query(need)
        if not query:
            return None
        connector = connector_for()
        batch = connector._to_batch(connector._fetch(max_results=WINDOW_MAX, query=query))
        if not batch.objects:
            return None
        summary = sync(ScopedBatchConnector(connector, batch))
        return {"source": "gmail", "kind": BACKFILL_WINDOW, "objects": len(batch.objects),
                "captured": _captured(summary)}

    return {FETCH_THREAD: fetch_thread, BACKFILL_WINDOW: backfill_window}


__all__ = ["FETCHERS_ENV", "ScopedBatchConnector", "THREAD_SLUG", "WINDOW_MAX", "armed", "make_fetchers",
           "thread_id_of", "window_query"]
