"""16-U1 · what each source OFFERS, what we TAKE, and why we leave the rest.

> **Nothing can be extracted from a field that was never fetched.**

Every other step in this round improves what L1 *does with* a field. This one asks the question that
comes before all of them, and the reason it is worth a module is that a missing field fails
**silently**: no error, no drop row, no trace entry. It is invisible to every existing test, because
a unit test on the extractor passes perfectly well against a raw dict the test assembled itself.

⛔ **THE STEP'S OWN LIST OF GAPS WAS WRONG IN TWO OF THREE PLACES, WHICH IS WHY THE LIST HAD TO
BECOME A TABLE.**

    gap 3 · attendees.responseStatus   ALREADY CLOSED — step 13's `read_attendees` did it
    gap 1 · Gmail bcc                  IMPOSSIBLE — the provider does not supply it
    gap 2 · In-Reply-To / References   real, and closed here
    NEW   · thread position            every prompt in production said "message 1 of 1"

Two of those cost a full premise check to discover, and they would have cost it again next quarter.
**That recurring cost is what this table removes**, and it is why `reason` is not optional: a silent
omission and a considered one look identical without it, so `bcc` would be re-opened as an oversight
every time someone re-reads the connector.

**E1 — THE DISCIPLINE THAT KEEPS THIS HONEST.** The goal is **not** *"fetch everything"*. It is
*"know what we fetch, and why we do not fetch the rest."* A field captured and never read is not a
defect and is recorded as such: over-fetching costs payload size, deleting later is cheap, and
re-adding means a re-sync. Under-fetching is the expensive direction, so the two are not symmetric
and the table does not pretend they are.

**16-U3 — THE RATCHET FAILS IN BOTH DIRECTIONS**, modelled on
`tests/test_every_llm_call_site_is_metered.py`, the proven pattern in this codebase for exactly this
problem. A field that appears with no row is drift toward an undeclared capture; a declared field
that stops arriving is a provider that changed under us, which today nobody would notice at all.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field as _field


@dataclass(frozen=True, slots=True)
class Field:
    """One field of one source, and our stated position on it."""

    #: The key as it lands in `RawObject.raw`, or the provider's own path for something we do not
    #: take (`attendees.responseStatus`) — the provider's spelling is what a reader will search for.
    name: str
    #: Do we land it. `False` needs a `reason`; there is no third state, because *"we might"* is how
    #: gap 1 survived long enough to be written into a plan as a TODO.
    captured: bool
    #: Modules that consume it. Empty is legal and is E1: captured-but-unread is a recorded
    #: position, not a bug.
    read_by: tuple[str, ...] = ()
    #: **Required when `captured` is False.** Why not — and specifically whether the provider cannot
    #: give it, or we chose not to pay for it. Those are different futures.
    reason: str = ""


@dataclass(frozen=True, slots=True)
class SourceManifest:
    """One source's declared field set."""

    source: str
    fields: tuple[Field, ...] = _field(default_factory=tuple)

    def declared(self) -> frozenset[str]:
        """Names we say we land. The ratchet's reference set."""
        return frozenset(f.name for f in self.fields if f.captured)


def _m(source: str, *fields: Field) -> tuple[str, SourceManifest]:
    return source, SourceManifest(source=source, fields=fields)


MANIFESTS: dict[str, SourceManifest] = dict([
    # ==========================================================================================
    _m("gmail",
       Field("subject", True, ("semantic/extractor", "gate/rules")),
       Field("body", True, ("preprocess", "semantic/extractor")),
       Field("snippet", True, ("landing/normalize",)),
       Field("to", True, ("landing/normalize", "esqe/visibility_rules")),
       Field("cc", True, ("landing/normalize", "esqe/visibility_rules")),
       Field("headers", True, ("gate/rules",),
             reason="N-01 Auto-Submitted, N-02 List-Unsubscribe, N-04 Precedence, plus the "
                    "Reply-To/Sender relay pair and step 16's In-Reply-To/References"),
       Field("labelIds", True, ("gate/rules", "context/runner")),
       Field("thread_position", True, ("pipeline._thread_place",),
             reason="Step 16. Derived from References at no API cost; see thread_position.py"),
       Field("thread_depth", True, ("pipeline._thread_place",),
             reason="Equals position — capture always happens at the tip of the thread"),
       Field("has_attachment", True, ("gate/rules",)),
       Field("important_attachment", True, ("gate/rules.whitelist",)),
       Field("document", True, ("gate/rules", "documents",)),
       Field("mime", True, ()),
       Field("page_offsets", True, ("documents",)),
       # -- not captured -------------------------------------------------------------------
       Field("bcc", False,
             reason="THE PROVIDER DOES NOT SUPPLY IT. Gmail's API returns no Bcc header, and on a "
                    "message we RECEIVED the bcc list is invisible by definition — that is what "
                    "bcc means. Step 13 added the `bcc_recipients` field so the contract can carry "
                    "one if a source ever offers one; it is empty everywhere. NOT a TODO."),
       Field("threads.get", False,
             reason="An exact thread size costs one request PER THREAD against a shared rate "
                    "limit on every sync. `References` gives the position for free; the total is "
                    "not worth a second API call, and `depth = position` is true at capture."),
       Field("historyId", False,
             reason="Incremental-sync cursor. `connectors/backfill.py` owns the window and "
                    "`sync_runner` owns the cursor; a second cursor would be a second source of "
                    "truth about what we have read, which step 5's denominator depends on."),
       ),
    # ==========================================================================================
    _m("gcal",
       Field("summary", True, ("semantic/extractor",)),
       Field("description", True, ("preprocess", "semantic/extractor")),
       Field("start", True, ("esqe/instants", "structural")),
       Field("end", True, ("structural",)),
       Field("status", True, ("gate/rules",)),
       Field("organizer", True, ("landing/normalize",)),
       Field("attendees", True, ("landing/normalize",)),
       Field("attendee_people", True, ("connectors/attendees", "esqe/importance"),
             reason="Step 13. Typed, so the participant set outlives the encrypted raw payload"),
       Field("attendees.responseStatus", True, ("connectors/attendees.joinability_bp",),
             reason="CLOSED BY STEP 13, not by this step. `read_attendees` keeps responseStatus, "
                    "displayName and the address-less attendees calendar.py used to drop."),
       Field("meeting_kind", True, ("connectors/attendees", "esqe/importance")),
       Field("calendar_owner", True, ("pipeline._envelope_direction",)),
       Field("eventType", True, ("gate/rules",)),
       Field("location", True, ()),
       Field("attachments", True, ("documents",)),
       Field("attachment_file_ids", True, ("documents",)),
       Field("updated", True, ("contracts/source_event.content_version",)),
       Field("conferenceId", True, ("structured/registry",)),
       # E1 · captured, read by nothing. Recorded rather than deleted: the cost is payload bytes,
       # and re-adding it later would mean a re-sync of the calendar.
       Field("hangoutLink", True, (),
             reason="Captured, read by nothing today. Kept because removing it is free now and "
                    "expensive to undo — see E1."),
       # -- not captured -------------------------------------------------------------------
       Field("recurringEventId", False,
             reason="`meeting_kind` already separates a recurring session from a one-off, which "
                    "is the only distinction anything downstream makes. The series id itself has "
                    "no reader, and an unread capture is still a capture to maintain."),
       Field("attendees.optional", False,
             reason="`joinability_bp` reads responseStatus, which is the stronger signal: an "
                    "optional attendee who ACCEPTED is more present than a required one who "
                    "never answered."),
       ),
    # ==========================================================================================
    _m("gdrive",
       Field("name", True, ("semantic/extractor",)),
       Field("subject", True, ("semantic/extractor",)),
       Field("body", True, ("preprocess",)),
       Field("text", True, ("preprocess",)),
       Field("file_id", True, ("documents",)),
       Field("mime", True, ("documents",)),
       Field("owner_email", True, ("landing/normalize",)),
       Field("created_at", True, ()),
       Field("modified_at", True, ("contracts/source_event.content_version",)),
       Field("document", True, ("gate/rules", "documents")),
       Field("page_offsets", True, ("documents",)),
       Field("transcript_export", True, ("documents",)),
       Field("has_attachment", True, ("gate/rules",)),
       # -- not captured -------------------------------------------------------------------
       Field("permissions", False,
             reason="Who a doc is SHARED with is not who acted on it, and L1 attributes to "
                    "actors. Sharing belongs to L2's graph, and fetching it costs a request per "
                    "file."),
       Field("revisions", False,
             reason="`modified_at` drives content_version, which is what re-lands a changed file. "
                    "A revision list would be a second history beside the one we keep."),
       ),
    # ==========================================================================================
    _m("notion",
       Field("subject", True, ("semantic/extractor",)),
       Field("body", True, ("preprocess",)),
       Field("url", True, ()),
       # -- not captured -------------------------------------------------------------------
       Field("properties", False,
             reason="A Notion database's property schema is per-workspace and unmapped. "
                    "`structured/registry` maps typed provider fields; there is no stable Notion "
                    "shape to add a row for."),
       Field("last_edited_by", False,
             reason="Notion returns a user id, not an address, and L1 attributes on email. "
                    "Resolving ids to people is a second API call and an L2 concern."),
       ),
    # ==========================================================================================
    _m("linear",
       Field("id", True, ()),
       Field("identifier", True, ("semantic/extractor",)),
       Field("title", True, ("semantic/extractor",)),
       Field("state_name", True, ("structured/registry",)),
       Field("state_type", True, ("structured/registry",)),
       Field("assignee_email", True, ("landing/normalize",)),
       Field("project", True, ("structured/registry",)),
       Field("team", True, ("structured/registry",)),
       Field("due_date", True, ("esqe/instants.due_at_of",),
             reason="Step 14. A stated due date is a world instant and does not need inferring"),
       Field("completed_at", True, ("esqe/signal_states",)),
       Field("url", True, ()),
       Field("labels", True, ()),
       # -- not captured -------------------------------------------------------------------
       Field("description", False,
             reason="The issue BODY is not fetched by `list_issues`; taking it means a second "
                    "call per issue. Deliberate and reversible — recorded so the next reader "
                    "knows it is a price, not an oversight."),
       Field("comments", False,
             reason="A comment thread is a conversation and would need its own object_type and "
                    "dedup key rather than being folded into the issue's raw."),
       ),
    # ==========================================================================================
    _m("hubspot",
       Field("dealname", True, ("structured/registry",)),
       Field("dealstage", True, ("structured/registry",)),
       Field("amount", True, ("structured/registry", "esqe/importance")),
       Field("closedate", True, ("esqe/instants.due_at_of",)),
       Field("contacts", True, ("landing/normalize",)),
       Field("contact_email", True, ("landing/normalize",)),
       # -- not captured -------------------------------------------------------------------
       Field("engagements", False,
             reason="HubSpot's logged calls and emails duplicate what the Gmail connector already "
                    "lands, and the same conversation arriving twice under two dedup keys is the "
                    "one failure the dedup key exists to prevent."),
       Field("associations.company", False,
             reason="Company resolution is L2's entity graph. L1 lands the contact addresses it "
                    "was given and does not decide which org they belong to."),
       ),
])


def undeclared_captures(source: str, *, captured: Iterable[str]) -> tuple[str, ...]:
    """16-U3, one direction · fields arriving that no row declares.

    Drift toward an undeclared capture, which is how a manifest becomes decoration. Sorted, so a
    failure message reads the same on every run.
    """
    manifest = MANIFESTS.get(source)
    known = {f.name for f in manifest.fields} if manifest else set()
    return tuple(sorted(set(captured) - known))


def missing_captures(source: str, *, captured: Iterable[str]) -> tuple[str, ...]:
    """16-U3, the other direction · declared fields that stopped arriving.

    **This is the half that has never existed anywhere in the codebase.** A provider drops a field
    and today nothing notices: the corpus quietly loses a column, and every reading built on it
    weakens without a single test going red.
    """
    manifest = MANIFESTS.get(source)
    if manifest is None:
        return ()
    return tuple(sorted(manifest.declared() - set(captured)))


__all__ = ["MANIFESTS", "Field", "SourceManifest", "missing_captures", "undeclared_captures"]
