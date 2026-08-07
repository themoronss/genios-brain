"""The signal lifecycle — when a captured signal stops being worth acting on.

The architecture asks Layer 1's output to carry `expires_at` and a `state` of
`new | active | satisfied | expired`. Neither existed: every signal ever captured stayed
equally current forever, so a meeting that finished in March and an email that arrived
this morning reached the reasoning engine as equally live evidence.

**Expiry is not deletion.** An expired signal keeps its ledger row, its trace and its
facts; it stops being *fresh*. Layers above read the state instead of re-deriving decay
from timestamps they would each interpret differently.

Only the two ends of the vocabulary belong to Layer 1:

  * `new`      — stamped at emit. Every signal starts here.
  * `expired`  — stamped by the sweep when `expires_at` has passed and nothing above
                 claimed it. Pure clock arithmetic; no business knowledge involved.

`active` and `satisfied` are Layer 2+'s to write: knowing that a commitment was FULFILLED
requires knowing what fulfils it, which is exactly the reasoning Layer 1 must not do.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.contracts.source_event import SourceEvent

NEW = "new"
ACTIVE = "active"
SATISFIED = "satisfied"
EXPIRED = "expired"
SUPERSEDED = "superseded"

SIGNAL_STATES: frozenset[str] = frozenset({NEW, ACTIVE, SATISFIED, EXPIRED, SUPERSEDED})

# Shelf life by source family, in days. These are decay horizons for the EVIDENCE, not
# retention limits for the data — `raw_payloads` (30d) and `prepared_content` (180d) hold
# the storage TTLs, and they are a different question with a different answer.
_TTL_DAYS: dict[str, int] = {
    "communication": 30,      # an unanswered email stops being news after a month
    "knowledge": 180,         # a doc stays true far longer than a message
    "enterprise_system": 90,  # a CRM/DB row is superseded by its own next version
    "operational": 60,        # a ticket or commit ages out of relevance
    "live_event": 7,          # a webhook happening is about right now
    "human_input": 30,
    "ai_generated": 30,
    "external": 90,
    "intelligence": 30,
    "unclassified": 30,
}
_DEFAULT_TTL_DAYS = 30

# A meeting is live until it ENDS, then immediately stale — its own end time beats any
# family default. Grace so a just-finished meeting is still actionable for a day.
_MEETING_GRACE = timedelta(days=1)


def _parse(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def expires_at_for(event: SourceEvent, structured_fields: dict | None = None,
                   raw: dict | None = None) -> datetime | None:
    """When this signal stops being current. `None` means it never does.

    Company canon never expires: a refund policy the org wrote down is true until the org
    writes down a different one, and that arrives as a supersede (a new content_version),
    not as a clock running out. Expiring canon would silently drain the organisation's own
    account of itself.
    """
    if event.internal_kind:
        return None

    # A dated object states its own horizon; nothing beats the source's own answer.
    fields = structured_fields or {}
    raw = raw or {}
    if event.object_type == "calendar_event":
        end = _parse(fields.get("end") or raw.get("end")) or _parse(
            fields.get("start") or raw.get("start"))
        if end:
            return end + _MEETING_GRACE

    days = _TTL_DAYS.get(event.source_family, _DEFAULT_TTL_DAYS)
    return event.occurred_at + timedelta(days=days)


def is_expired(expires_at: datetime | None, now: datetime | None = None) -> bool:
    if expires_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now
