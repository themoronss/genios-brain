"""L1.1-U2 · the waitlist — where a source a tenant wants but cannot connect is RECORDED.

Half of registry honesty is not showing a tile that errors. The other half is what happens
next. A founder who came to connect Slack and finds "coming soon" has told us something
worth more than the click: which system their work actually lives in. Until now that ended
at a disabled button, so the answer to "what should we build after HubSpot?" was whoever
asked loudest on a call.

WHY IT IS DERIVED, NOT DUPLICATED. A row here is `(org, source)` and a count. It stores no
family, no capability and no "is this built yet" flag — those are read back from
`source_registry` at read time. Storing them would create the fifth hand-maintained list
this package spent a refactor deleting, and it would be a list that goes stale in the one
way that matters: the day Slack ships, every waitlist row would still say `connectable:
false`, and the report that is supposed to say "these 12 tenants can be told it's ready"
would say nothing.

THREE REFUSALS, and each is a defect it would otherwise hide:

* a **connectable** source is refused. If the UI asks to waitlist Gmail, the UI is reading a
  stale catalog — the honest response is an error the frontend developer sees today, not a
  row that quietly means nothing and a tenant who is never told to just go connect it.
* a **deliberate** source (upload, internal, human, agent) is refused. There is no connector
  to wait for; the door is open and is a different door. "We'll let you know when uploads
  are ready" is a lie about a feature that already shipped.
* a malformed id is refused. An unREGISTERED id is not: `clickup` is a source we have not
  described, and "which systems do tenants ask for that we have never even listed" is the
  single most valuable question this table can answer. Refusing it because it is unknown
  would throw away exactly the demand we cannot get any other way. It is bounded instead —
  slug-shaped and short — so the table cannot become free text.

The clock is a parameter, as everywhere else in capture/: a request, a re-request and a
report inside one test must agree about when "now" was.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import text

from genios_engine.capture.source_registry import capability_of, descriptor_of, offer_of
from genios_engine.platform.db import get_engine

#: A source id is a slug, and a short one. Long enough for `google_calendar`, far too short
#: for a sentence — the bound is what keeps an open-vocabulary column from becoming a
#: free-text notes field that no report can group on.
MAX_SOURCE_CHARS = 64

#: The one free-text field, capped. "We use it for invoicing, via the Xero app" is worth
#: keeping; a pasted email thread is not.
MAX_NOTE_CHARS = 500

_SLUG = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


class WaitlistRefused(ValueError):
    """The request must not be recorded, and the caller is told which of the three reasons."""


@dataclass(frozen=True, slots=True)
class WaitlistRequest:
    """One tenant asking, once, for one source."""

    org_id: str
    source: str
    requested_by: str | None
    note: str | None
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WaitlistEntry:
    """A tenant's standing interest in one source — the stored count, plus what the registry
    says about that source RIGHT NOW.

    `registered` distinguishes "we have described this source and have not built it" from
    "a tenant named a system we have never heard of". Both are demand; only the second one
    is also a gap in the taxonomy.
    """

    org_id: str
    source: str
    family: str
    capability: str | None
    registered: bool
    requests: int
    first_requested_at: datetime
    last_requested_at: datetime
    latest_note: str | None
    latest_requested_by: str | None


class SourceWaitlistStore(Protocol):
    """The persistence seam. Two calls, both typed — no dict crosses this boundary."""

    def record(self, request: WaitlistRequest) -> WaitlistEntry: ...

    def entries_for(self, org_id: str) -> tuple[WaitlistEntry, ...]: ...


def normalize_source(raw: str) -> str:
    """Canonicalize a requested source id, or raise `WaitlistRefused`.

    Aliases collapse to their canonical descriptor (`google_calendar` → `gcal`) so that ten
    tenants asking for the same system in three spellings are ten votes for one row rather
    than three rows nobody adds up.
    """
    candidate = (raw or "").strip().lower()
    if not candidate:
        raise WaitlistRefused("a source id is required")
    if len(candidate) > MAX_SOURCE_CHARS:
        raise WaitlistRefused(f"source id is longer than {MAX_SOURCE_CHARS} characters")
    if not _SLUG.match(candidate):
        raise WaitlistRefused(
            "source id must be a slug: lowercase letters, digits, '_', '-' or '.'")
    descriptor = descriptor_of(candidate)
    return descriptor.source if descriptor is not None else candidate


def normalize_note(raw: str | None) -> str | None:
    """Trim the free-text field, or refuse it for length. Blank becomes None so that a later
    re-request with no note cannot erase the note that explained the first one."""
    if raw is None:
        return None
    note = raw.strip()
    if not note:
        return None
    if len(note) > MAX_NOTE_CHARS:
        raise WaitlistRefused(f"note is longer than {MAX_NOTE_CHARS} characters")
    return note


def request_source(store: SourceWaitlistStore, *, org_id: str, source: str,
                   requested_by: str | None = None, note: str | None = None,
                   eval_time: datetime) -> WaitlistEntry:
    """Record a tenant's interest in a source it cannot connect. THE public callable.

    Refuses a source that is connectable today (the caller is reading a stale catalog) and
    one that is reached deliberately rather than by connector (there is nothing to wait
    for). Everything else — described-but-unbuilt, or never described at all — is recorded.
    """
    canonical = normalize_source(source)
    offer = offer_of(canonical)
    if offer is not None and offer.status == "connectable":
        raise WaitlistRefused(
            f"'{canonical}' is connectable today — connect it instead of waiting for it")
    if offer is not None and offer.status == "deliberate":
        raise WaitlistRefused(
            f"'{canonical}' has no connector by design — it is written or uploaded directly, "
            "so there is nothing to wait for")
    if not org_id:
        raise WaitlistRefused("an org id is required")
    return store.record(WaitlistRequest(
        org_id=org_id, source=canonical, requested_by=requested_by,
        note=normalize_note(note), requested_at=eval_time))


def _entry(*, org_id: str, source: str, requests: int, first_requested_at: datetime,
           last_requested_at: datetime, latest_note: str | None,
           latest_requested_by: str | None) -> WaitlistEntry:
    """Join a stored row to the live registry — the one place that derivation happens."""
    descriptor = descriptor_of(source)
    return WaitlistEntry(
        org_id=org_id, source=source,
        family=descriptor.family if descriptor is not None else "unclassified",
        capability=capability_of(source), registered=descriptor is not None,
        requests=requests, first_requested_at=first_requested_at,
        last_requested_at=last_requested_at, latest_note=latest_note,
        latest_requested_by=latest_requested_by)


class InMemorySourceWaitlist:
    """The no-database store: same semantics, same types, kept for dev and hermetic tests."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], WaitlistEntry] = {}

    def record(self, request: WaitlistRequest) -> WaitlistEntry:
        key = (request.org_id, request.source)
        held = self._rows.get(key)
        entry = _entry(
            org_id=request.org_id, source=request.source,
            requests=1 if held is None else held.requests + 1,
            first_requested_at=request.requested_at if held is None else held.first_requested_at,
            last_requested_at=request.requested_at,
            # A re-request with no note keeps the note that explained the first one.
            latest_note=request.note if request.note is not None
            else (held.latest_note if held else None),
            latest_requested_by=request.requested_by if request.requested_by is not None
            else (held.latest_requested_by if held else None))
        self._rows[key] = entry
        return entry

    def entries_for(self, org_id: str) -> tuple[WaitlistEntry, ...]:
        return tuple(sorted((row for key, row in self._rows.items() if key[0] == org_id),
                            key=lambda e: (-e.requests, e.source)))


_COLUMNS = ("org_id, source, requests, first_requested_at, last_requested_at, latest_note, "
            "latest_requested_by")

_RECORD_SQL = f"""
insert into source_waitlist ({_COLUMNS})
values (:org_id, :source, 1, :at, :at, :note, :by)
on conflict (org_id, source) do update set
  requests = source_waitlist.requests + 1,
  last_requested_at = excluded.last_requested_at,
  latest_note = coalesce(excluded.latest_note, source_waitlist.latest_note),
  latest_requested_by = coalesce(excluded.latest_requested_by,
                                 source_waitlist.latest_requested_by)
returning {_COLUMNS}
"""


class PostgresSourceWaitlist:
    """The real store. One upsert: re-asking is a louder vote, never a duplicate row, and the
    count is incremented in SQL so two seats asking at once cannot both read 1 and write 2."""

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def record(self, request: WaitlistRequest) -> WaitlistEntry:
        with self._engine.begin() as conn:
            row = conn.execute(text(_RECORD_SQL), {
                "org_id": request.org_id, "source": request.source,
                "at": request.requested_at, "note": request.note,
                "by": request.requested_by}).first()
        return _entry(org_id=row.org_id, source=row.source, requests=int(row.requests),
                      first_requested_at=row.first_requested_at,
                      last_requested_at=row.last_requested_at, latest_note=row.latest_note,
                      latest_requested_by=row.latest_requested_by)

    def entries_for(self, org_id: str) -> tuple[WaitlistEntry, ...]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select {_COLUMNS} from source_waitlist where org_id=:o "
                "order by requests desc, source asc"), {"o": org_id}).all()
        return tuple(_entry(org_id=r.org_id, source=r.source, requests=int(r.requests),
                            first_requested_at=r.first_requested_at,
                            last_requested_at=r.last_requested_at, latest_note=r.latest_note,
                            latest_requested_by=r.latest_requested_by) for r in rows)


__all__ = ["MAX_NOTE_CHARS", "MAX_SOURCE_CHARS", "InMemorySourceWaitlist",
           "PostgresSourceWaitlist", "SourceWaitlistStore", "WaitlistEntry", "WaitlistRefused",
           "WaitlistRequest", "normalize_note", "normalize_source", "request_source"]
