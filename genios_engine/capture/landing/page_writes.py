"""L1 rebuild C3 — one page of landing writes, one transaction.

Every captured mail used to open its own transaction per store: the dedup ledger row
(`source_events`), the encrypted body (`raw_payloads`), the masked text (`prepared_content`) and
the decision trace (`event_trace`) — four checkouts, four BEGIN/COMMIT pairs and the pool's
pre-ping on each, for every mail, against a remote pooler. A 25-mail page paid ~100 round trips
for writes that belong together.

`PageWrites` holds those four writes for one page and `flush()`es them in ONE transaction, in
foreign-key order (`raw_payloads.event_id` → `source_events`), with one `executemany` per table and
the SAME statements the stores run one by one (`*.INSERT`, `*_params`). Nothing else changes:

  * the dedup question (`exists`, `existing_keys`, `kept_child_exists`) is answered from the
    page's own pending rows first, so a mail landed earlier in this page is a duplicate exactly as
    a flushed one would be;
  * a reader of the masked text (`get_text`) sees the pending row;
  * every other store a capture writes to (documents, parks, fingerprints, costs, the extraction
    cache) still writes at once — none of them has a foreign key on these rows.

If the flush fails nothing of the page is written and the error raises out of `run_sync`; the
cursor has not moved, so the next run reads the page again (its extraction calls are already in
the extraction cache). A page is all-or-nothing, which is what "the cursor moves only after the
data is durable" asks for.

Engaged only when all four stores are the Postgres ones on ONE engine (`for_page`); any other
combination — the in-memory stores of the hermetic suite, a test double — writes as before.
"""
from __future__ import annotations

import threading
from typing import Any

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.page_writes")


class PageWrites:
    """The four landing writes of one page, held until `flush()`."""

    def __init__(self, engine, *, repo, payloads, prepared, traces) -> None:
        self._engine = engine
        self._lock = threading.Lock()
        self._events: list[dict] = []
        self._payloads: list[dict] = []
        self._prepared: list[dict] = []
        self._traces: list[dict] = []
        self._keys: dict[tuple[str, str], dict] = {}          # (org, dedup_key) -> event params
        self._texts: dict[tuple[str, str], str] = {}          # (org, event_id) -> clean text
        self._inner = (repo, payloads, prepared, traces)
        self.repo = _Repo(self, repo)
        self.payloads = _Payloads(self, payloads)
        self.prepared = _Prepared(self, prepared)
        self.traces = _Traces(self, traces)

    @classmethod
    def for_page(cls, *, repo, payloads, prepared, traces) -> "PageWrites | None":
        """A buffer when every store can be batched on one engine, else None (write as before)."""
        stores = (repo, payloads, prepared, traces)
        if any(s is None for s in stores):
            return None
        needed = (("add_params", "INSERT"), ("put_params", "INSERT"),
                  ("put_params", "INSERT"), ("rows_of", "INSERT"))
        if not all(all(hasattr(s, a) for a in attrs) for s, attrs in zip(stores, needed)):
            return None
        engines = {id(getattr(s, "_engine", None)) for s in stores}
        engine = getattr(repo, "_engine", None)
        if engine is None or len(engines) != 1:
            return None
        return cls(engine, repo=repo, payloads=payloads, prepared=prepared, traces=traces)

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._events) + len(self._payloads) + len(self._prepared) + len(self._traces)

    def flush(self) -> dict[str, int]:
        """Write the page in ONE transaction, parents first. Returns rows per table."""
        with self._lock:
            events, payloads = self._events, self._payloads
            prepared, traces = self._prepared, self._traces
            self._events, self._payloads, self._prepared, self._traces = [], [], [], []
            self._keys, self._texts = {}, {}
        counts = {"source_events": len(events), "raw_payloads": len(payloads),
                  "prepared_content": len(prepared), "event_trace": len(traces)}
        if not any(counts.values()):
            return counts
        repo, store, prep, trace = self._inner
        with self._engine.begin() as conn:
            if events:
                conn.execute(repo.INSERT, events)
            if payloads:
                conn.execute(store.INSERT, payloads)
            if prepared:
                conn.execute(prep.INSERT, prepared)
            if traces:
                conn.execute(trace.INSERT, traces)
        return counts


class _Delegate:
    def __init__(self, page: PageWrites, inner) -> None:
        self._page, self._inner = page, inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _Repo(_Delegate):
    def exists(self, org_id: str, dedup_key: str) -> bool:
        with self._page._lock:
            if (org_id, dedup_key) in self._page._keys:
                return True
        return self._inner.exists(org_id, dedup_key)

    def existing_keys(self, org_id: str, dedup_keys: list[str]) -> set[str]:
        with self._page._lock:
            pending = {k for k in dedup_keys if (org_id, k) in self._page._keys}
        rest = [k for k in dedup_keys if k not in pending]
        return pending | (self._inner.existing_keys(org_id, rest) if rest else set())

    def kept_child_exists(self, org_id: str, source: str, object_type: str,
                          parent_object_id: str) -> bool:
        with self._page._lock:
            for (org, _k), p in self._page._keys.items():
                if (org == org_id and p["source"] == source and p["object_type"] == object_type
                        and p["parent_object_id"] == parent_object_id
                        and p["outcome"] in ("emitted", "parked", "archived")):
                    return True
        return self._inner.kept_child_exists(org_id, source, object_type, parent_object_id)

    def add(self, event, outcome=None, **kw) -> None:
        params = self._inner.add_params(event, outcome, **kw)
        with self._page._lock:
            key = (event.org_id, event.dedup_key)
            if key in self._page._keys:              # `on conflict do nothing`, kept in the page
                return
            self._page._keys[key] = params
            self._page._events.append(params)


class _Payloads(_Delegate):
    def put(self, **kw) -> None:
        params = self._inner.put_params(**kw)
        with self._page._lock:
            self._page._payloads.append(params)


class _Prepared(_Delegate):
    def put(self, **kw) -> None:
        params = self._inner.put_params(**kw)
        with self._page._lock:
            self._page._prepared.append(params)
            self._page._texts[(params["o"], params["e"])] = params["txt"]

    def get_text(self, *, org_id, event_id):
        with self._page._lock:
            text = self._page._texts.get((org_id, event_id))
        return text if text is not None else self._inner.get_text(org_id=org_id,
                                                                  event_id=event_id)


class _Traces(_Delegate):
    def save(self, trace) -> None:
        rows = self._inner.rows_of(trace)
        if rows:
            with self._page._lock:
                self._page._traces.extend(rows)
