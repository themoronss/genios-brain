from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class RawObject:
    """A raw object returned by a source (via Composio or native), pre-normalization.
    Connectors differ only in how they produce this; downstream is source-agnostic."""

    source: str
    object_type: str
    source_object_id: str
    occurred_at: datetime
    actor_email: str | None = None
    #: The display name the source gave for the actor, when it gave one. See `Actor.name`.
    actor_name: str | None = None
    actor_type: str = "external_contact"
    parent_object_id: str | None = None
    # For MUTABLE structured objects (CRM deal, calendar event, DB row) a connector sets a
    # content version (updatedAt / etag / watermark). It folds into dedup_key so a CHANGED
    # object re-lands and updates the graph. Email/message leave it None → stable dedup (an
    # email never edits). Without this, deal.stage froze at its first-seen value forever.
    content_version: str | None = None
    # Set ONLY when the company is deliberately asserting something about itself (a
    # written policy, an upload tagged `pricing`). One of internal_knowledge.INTERNAL_KINDS.
    # It promotes the event's family to `internal` and its facts to authority rank 4 —
    # so company canon outranks a third-party system of record. None for observed traffic.
    internal_kind: str | None = None
    # The clock the incremental cursor advances on. For a message `occurred_at` (when it was
    # sent) IS the right watermark. For a calendar event it is catastrophically wrong:
    # `occurred_at` is when the MEETING STARTS, so one event booked for next month pushes the
    # cursor into the future and every subsequent sync asks the provider for changes "since"
    # a date that has not happened — the connector goes permanently silent while still
    # reporting success. Mutable sources must set this to their own last-modified stamp.
    synced_at: datetime | None = None
    #: Everyone else the message was addressed to (To + Cc), lowercased. Connectors already parse
    #: these — the Gmail path extracts them and drops them into an untyped dict — so this is a
    #: contract, not new work: it makes the participant set survive past the payload TTL.
    recipients: tuple[str, ...] = ()
    # ------------------------------------------------------------------------------------------
    # L1.2.x-U1 · THE TO/CC SPLIT (step 13, 2026-09-24) — P4's join key.
    #
    # `recipients` keeps meaning EXACTLY what it meant: everyone on the message. The gate,
    # `derive_visibility`, the audience multiplier and the thread reconstructor all read it, and a
    # step that redefined it to "to only" would silently change the audience size on every scored
    # signal in the system. These two are ADDITIVE.
    #
    # WHAT THEY FIX. `composio.py` read `to_emails` and `cc_emails` separately from the headers and
    # then wrote `recipients=tuple(to_emails) + tuple(cc_emails)` — the distinction destroyed one
    # line after it was read. It survived in the raw dict, and `context/runner.py:161` flattened it
    # a SECOND time. Three chances, all missed, and nobody ever needed to re-derive it.
    #
    # Why it matters: "was this person written TO, or copied?" is the difference between a
    # participant and an observer, and the Radhesh finding — *a person introduced and then never
    # in a To: field* — is a question about exactly that.
    # ------------------------------------------------------------------------------------------
    to_recipients: tuple[str, ...] = ()
    cc_recipients: tuple[str, ...] = ()
    #: E5, CORRECTED. The step assumes bcc is available and governs it with `visibility_rules.py`.
    #: **Gmail's API never hands it to us** — `grep -rn bcc connectors/` is empty, and on a message
    #: we RECEIVED the bcc list is invisible by definition.
    #:
    #: The field exists so a source that DOES supply it has somewhere to put it, and it is empty
    #: everywhere today. An empty field with a reason is honest; a missing one means the next
    #: connector author invents a key and the split drifts again.
    bcc_recipients: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)
    #: An audience the DOOR already knows, which no per-source rule could derive. Set only by a
    #: deliberate-intake door that was told who the object is for — a seat's PERSONAL upload is
    #: `private` to that seat, where the `upload` rule would say `org`. None (every connector) =
    #: derive it from the source's rule, exactly as before.
    visibility: Any = None

    @property
    def watermark_at(self) -> datetime:
        """The timestamp the cursor may advance to for this object."""
        return self.synced_at or self.occurred_at


@dataclass
class SourceBatch:
    objects: list[RawObject]
    next_cursor: str | None = None
    # ------------------------------------------------------------------------------------------
    # L1.2.x · THE DENOMINATOR (step 5, 2026-09-23)
    #
    # How many objects the PROVIDER says exist for this query — not how many we fetched. Without
    # it, "we found no follow-up from Acme" and "we indexed 8% of the mailbox" are the same
    # sentence, which is precisely the benchmark failure this was built against: Gemini reported
    # "18 threads read of 18 that exist" against a mailbox of ~465, stating the size of what it
    # read as the size of what exists.
    #
    # `None` IS THE HONEST DEFAULT and most providers keep it. A connector that offers no count
    # must not report 0 — "the window is empty" and "we were not told" are different answers, and
    # only one of them is a reason to stop looking.
    # ------------------------------------------------------------------------------------------
    claimed_total: int | None = None
    #: Whether `claimed_total` is an ESTIMATE. Gmail's `resultSizeEstimate` is, and the label has
    #: to travel with the number or it becomes a fact at the first reader — "465" then reads as a
    #: count somebody could be held to.
    #:
    #: DEFAULT TRUE, and that direction is deliberate: a connector that sets a total without
    #: saying which kind it is gets the cautious reading. The mistake that costs something is
    #: presenting an estimate as exact, never the reverse.
    claimed_is_estimate: bool = True


@runtime_checkable
class SourceConnector(Protocol):
    """One interface, every source implements. Composio sits BEHIND this (auth +
    data delivery only); a native adapter can replace any one connector without
    changing landing/gate/graph. Our contract stays ours."""

    source: str

    def validate_connection(self) -> bool: ...
    def initial_snapshot(self, cursor: str | None, limit: int) -> SourceBatch: ...
    def incremental_changes(self, cursor: str | None, limit: int,
                            since: Optional[datetime] = None) -> SourceBatch: ...
    def fetch_content(self, object_ref: str) -> dict[str, Any]: ...
