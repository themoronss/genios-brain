"""ALG-22 + ALG-23 · L1.5.0 — the claim group assembler. *Two claims about ONE amount.*

Conflict detection (L1.5.5) and signal supersession were both specified against a
``subject_key`` that no unit defined, and against a group that was assembled *per event*. Both
of those are defects, and the second one is the expensive kind — the kind that ships:

``capture/connectors/composio.py`` emits **one Gmail message as two events** — an
``email_message`` plus one ``email_attachment`` per file (``:512`` and ``:559``, the attachment
carrying ``parent_object_id=mid``, "links the file back to its email"). So a covering email
saying *\\$84,000* and the signed PDF attached to it saying *\\$74,000* are two rows in
``source_events``. Group by event and they are never compared; both facts publish, both look
confident, and the single case the conflict detector exists to catch is the one it cannot see.

This module is what makes those two claims one group.

TWO UNITS, ONE FILE
-------------------
* **U1 ``subject_key``** (ALG-22) — the ordered cascade, first match wins: a structured object's
  own id, else a document identity, else a canonical entity plus the field family, else the
  thread, else the event. It is DERIVED, never minted: the same real-world subject produces the
  same key from any event that mentions it, on any replay, in any process.
* **U2 ``assemble_claim_groups``** (ALG-23) — the group is the DOCUMENT GROUP, not the event.
  Claims join when their subject keys match, or when they share a thread and a field family.

WHY THE THREAD CLAUSE NEEDS A GUARD
-----------------------------------
Doc 05's failure table names both directions at once: *"group too wide → false conflicts across
unrelated deals"*, mitigated by *"subject_key must match, not merely the thread"*; and *"group
too narrow → the founder's example is missed"*. Joining everything in a thread satisfies the
second and violates the first — two unrelated deals quoted in one long thread would be
published as a contradiction.

The resolution is that not every subject key is equally *identifying*. A structured id and a
canonical entity say WHAT the claim is about; a document identity, a thread and an event id only
say WHERE it was found. So the thread clause joins claims freely while their identifying anchors
agree, and refuses when two claims carry DIFFERENT identifying anchors. The attached PDF has no
anchor of its own — it is anchored by the mail that carried it — so it joins the email's claim,
which is the founder's example. Two deals named in one thread have two anchors, and stay apart.

Where a thread holds two or more distinct anchors, the anchorless claims in it are NOT attached
to either: with two candidates and no evidence, attributing is a coin flip, and this file obeys
the same law ``canonical.py`` does — *ambiguity is not a match*.

PURITY, AND WHY IT IS LOAD-BEARING HERE
---------------------------------------
No float, no clock, no model, no database. ``eval_time`` is not needed at all: the window is
*unbounded in time* by specification, because a contract amendment six months later must still
conflict with the original, and a unit that read a clock would quietly stop comparing it.
The parent walk takes an injected ``event_lookup`` callable rather than a repository handle.

The stability requirement is stronger than "pure", and it is the reason nothing here iterates a
set or leans on ``hash()``: an unstable key regroups claims on every run, and a conflict
detector whose input regroups is a detector whose output is nondeterministic. Every ordering in
this file is an explicit sort over strings and integers, so a different ``PYTHONHASHSEED``
produces byte-identical groups — asserted from a subprocess in the test file.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from types import MappingProxyType
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import re

from genios_engine.capture.structured.registry import has_mapping
from genios_engine.capture.validate.authority import Provenance, rank_of, weigh_authority
from genios_engine.capture.validate.canonical import EntityFamily, ENTITY_TYPE_FAMILY, derive_key
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult,
                                                UnclassifiedObservation)
from genios_engine.contracts.source_event import SourceEvent, compute_dedup_key
from genios_engine.contracts.units import Money, ResolvedDate

__all__ = [
    "MAX_CLAIMS_PER_GROUP",
    "ClaimGroup",
    "ClaimValue",
    "FieldFamily",
    "NormalizedClaim",
    "SubjectTier",
    "assemble_claim_groups",
    "claims_from_extraction",
    "document_identity",
    "field_family_of",
    "subject_key",
    "thread_group_key",
]

#: Doc 05's cap: *"cap at 500 claims per group; beyond that, most-recent-500 by authority rank"*.
#: A ceiling rather than a warning because the consumer is O(n²) — ALG-12 compares every claim in
#: a group with every other one — and a five-year mailing-list thread is not a subject anyone is
#: reasoning about.
MAX_CLAIMS_PER_GROUP = 500

#: Object types that ARE a document rather than merely mentioning one. Attachment events are the
#: ones whose parent chain is two hops long (attachment -> email -> thread) and therefore the
#: ones a broken chain actually orphans; they are also the ones that carry a document identity.
_DOCUMENT_OBJECT_TYPES: frozenset[str] = frozenset({
    "email_attachment", "attachment", "file", "document", "upload", "drive_file",
})

#: Source families whose events ARE typed records — a CRM deal, a billing subscription, a row in
#: the tenant's database. Consulted alongside the structured mapping registry so that a system of
#: record whose mapping has not been registered yet still keys on its own object id rather than
#: falling through to the thread, which it does not have.
_STRUCTURED_FAMILIES: frozenset[str] = frozenset({"enterprise_system"})

_SLUG_JUNK = re.compile(r"[^a-z0-9]+")


class FieldFamily(str, Enum):
    """WHAT KIND of thing a claim asserts — the second half of an entity subject key.

    Two claims are only comparable when they answer the same question. An amount and a due date
    extracted from one sentence about one deal are both about that deal and are not in conflict
    with each other, so the family is part of the key rather than a label beside it: without it,
    ``entity:acme`` would gather every fact anyone ever stated about Acme into a single group
    and hand ALG-12 a pile of unrelated pairs to compare.

    A ``str`` enum so a key renders as the doc's own word and a stored group key stays readable.
    """

    AMOUNT = "amount"
    DATE = "date"
    COMMITMENT = "commitment"
    DECISION = "decision"
    DEPENDENCY = "dependency"
    ENTITY = "entity"
    OBSERVATION = "observation"


class SubjectTier(int, Enum):
    """Which rung of the ALG-22 cascade answered — and how much it is worth in a join.

    Ordered by specificity so ``min()`` over a group's members picks the most identifying key as
    the group's name. The split that matters is ``IDENTIFYING``: the first and third rungs name
    the SUBJECT, the rest name a LOCATION, and only the first kind may veto a thread-level join.
    """

    STRUCTURED = 1
    DOCUMENT = 2
    ENTITY = 3
    THREAD = 4
    EVENT = 5


#: The rungs that assert what a claim is ABOUT. A document identity is deliberately not one of
#: them: the same signed PDF states an amount, a date and a party, and "which file it was in" is
#: where it was read, not what it concerns. That is precisely why an attachment's claim is free
#: to join the claim in the mail that carried it.
_IDENTIFYING_TIERS: frozenset[SubjectTier] = frozenset({SubjectTier.STRUCTURED,
                                                        SubjectTier.ENTITY})

#: How a GROUP is named when its members answered at different rungs. Deliberately not the
#: cascade's own order: the cascade is ordered by how specifically a rung identifies THIS EVENT,
#: while a group's name should say what the group is ABOUT. A signed PDF's document identity is
#: the most specific thing to say about that file and the least useful thing to say about the
#: deal it and the covering mail both describe — so an identifying rung names the group whenever
#: one is present, and the located rungs only name groups that have nothing better.
_NAMING_ORDER: Mapping[SubjectTier, int] = MappingProxyType({
    SubjectTier.STRUCTURED: 0,
    SubjectTier.ENTITY: 1,
    SubjectTier.DOCUMENT: 2,
    SubjectTier.THREAD: 3,
    SubjectTier.EVENT: 4,
})

#: Every claim shape L1 extracts. Money and ResolvedDate are included even though neither carries
#: its own evidence list — a `Money`'s receipt is its `as_written` — because they are the two
#: claim kinds the founder's worked example is made of.
ClaimValue = (Money | ResolvedDate | Commitment | DecisionState | Dependency | EntityMention
              | UnclassifiedObservation)

_FAMILY_BY_TYPE: tuple[tuple[type, FieldFamily], ...] = (
    (Money, FieldFamily.AMOUNT),
    (ResolvedDate, FieldFamily.DATE),
    (Commitment, FieldFamily.COMMITMENT),
    (DecisionState, FieldFamily.DECISION),
    (Dependency, FieldFamily.DEPENDENCY),
    (EntityMention, FieldFamily.ENTITY),
    (UnclassifiedObservation, FieldFamily.OBSERVATION),
)


def field_family_of(claim: ClaimValue) -> FieldFamily:
    """The family a claim belongs to, from its contract type. Total over ``ClaimValue``.

    Type-driven rather than passed in, so a caller cannot file a due date under ``amount`` and
    put two incomparable claims in one group. An unknown object raises: a claim shape nobody
    declared has no comparison rules either, and grouping it as ``observation`` would invent a
    silent default that ALG-12 would then compare against real facts.
    """
    for kind, family in _FAMILY_BY_TYPE:
        if isinstance(claim, kind):
            return family
    raise TypeError(f"no field family for {type(claim).__name__}; ALG-22 groups the declared "
                    f"claim types only")


def _slug(text: str) -> str:
    """Lowercase, punctuation-folded, collapsed. The one normalisation applied to a file name.

    Fuzziness lives in how a key is DERIVED and never in how two keys are COMPARED — the rule
    ``canonical.py`` states and this module reuses, so ``"MSA_Signed v2.PDF"`` and
    ``"msa-signed-v2.pdf"`` converge while two genuinely different files stay apart forever.
    """
    return _SLUG_JUNK.sub("-", text.strip().lower()).strip("-")


def _is_document_event(event: SourceEvent) -> bool:
    object_type = (event.object_type or "").strip().lower()
    return object_type in _DOCUMENT_OBJECT_TYPES or object_type.endswith("_attachment")


def _is_structured_event(event: SourceEvent) -> bool:
    """A typed record, either by a registered field mapping or by its source family."""
    return (has_mapping(event.source, event.object_type)
            or (event.source_family or "") in _STRUCTURED_FAMILIES)


def document_identity(event: SourceEvent) -> str | None:
    """ALG-22 rule 2 — the identity of the FILE an event is, or None when it is not one.

    The Gmail connector mints an attachment's ``source_object_id`` as ``f"{mid}::{attachmentId
    or filename or idx}"`` (``composio.py:295``), so the tail after ``::`` is the file's own
    handle and the head is the message that happened to carry it. Keying on the tail is what
    makes the same PDF, forwarded into a second thread with its parent chain broken, land on the
    identity it had the first time — which is the mitigation doc 05 names for an orphaned
    attachment.

    Returns None rather than a guess for a non-document event: a rule that answered for every
    event would make rule 2 swallow the cascade and no claim would ever key on its entity.
    """
    if not _is_document_event(event):
        return None
    raw = event.source_object_id or ""
    tail = raw.rsplit("::", 1)[-1] if "::" in raw else raw
    slug = _slug(tail) or _slug(raw)
    return f"document:{slug}" if slug else None


def _org_anchor(extraction: ExtractionResult | None) -> str | None:
    """The ONE organisation an extraction is about, or None when that is not answerable.

    ``canonical_hint`` first (L1.5.4's proposal, already stable and closed under re-application),
    then ``derive_key`` on the surface form for a mention the canonicalizer had no table row for
    — deriving is what lets an org the alias table has never heard of still anchor its own
    claims. Only the ``org`` family counts: a person named in a deal thread is a participant, not
    the subject, and letting a person anchor the group would split one deal's claims by whoever
    happened to be cc'd.

    Zero mentions or two DIFFERENT organisations both return None. Two orgs in one message is
    exactly the introduction email in which nothing may be attributed to either, and picking the
    first is the invisible merge ``contracts/extraction.py`` warns about in its own field comment.
    """
    if extraction is None:
        return None
    hints: set[str] = set()
    for mention in extraction.entity_mentions:
        if ENTITY_TYPE_FAMILY.get((mention.entity_type or "").strip().lower()) is not EntityFamily.ORG:
            continue
        hint = (mention.canonical_hint or "").strip().lower()
        if not hint:
            hint = (derive_key(mention.surface_form, entity_type=mention.entity_type).key or "")
        if hint:
            hints.add(hint)
    return sorted(hints)[0] if len(hints) == 1 else None


#: How many hex characters of the rung-5 digest travel in a key. Eight bytes: long enough that
#: two different source objects colliding is not a thing that happens to a tenant, short enough
#: that a key stays readable in a log line beside the four rungs above it.
_EVENT_DIGEST_BYTES = 8


def event_subject_handle(event: SourceEvent) -> str:
    """Rung 5's stable handle for the event itself — a digest of its DEDUP KEY, never its id.

    ``capture/landing/normalize.py:33`` mints ``event_id`` fresh on every ingestion, so a rung-5
    key built from it MOVED every time the same message was captured again: a recovery re-scan, a
    reconnected mailbox, a replayed page. The claim then did not group with its own earlier self,
    supersession across the re-ingestion silently stopped happening, and the correction and the
    thing it corrected both stood with nothing raised. That is the one failure mode this rung has
    to be safe against, since a claim that reaches rung 5 has nothing else to be recognised by.

    ``dedup_key`` is the field that already answers "which source object is this", stably, by
    contract (``contracts/source_event.py:35``) — the same object at the same content version
    yields the same key from any process and any replay. So it is what is digested here. It is
    DIGESTED rather than embedded because a dedup key carries the provider's own identifiers and
    a subject key travels into conflict cards, logs and group names; the grouping property needs
    only equality, which a digest preserves exactly.

    An event whose dedup key is missing — a legacy row, a hand-built double — is re-derived from
    the same three fields ``compute_dedup_key`` uses rather than falling back to the minted id,
    because falling back to the id is the defect.
    """
    key = (event.dedup_key or "").strip()
    if not key:
        key = compute_dedup_key(event.source, event.object_type, event.source_object_id or "")
    return hashlib.blake2s(key.encode("utf-8"),
                           digest_size=_EVENT_DIGEST_BYTES).hexdigest()


def _derive_subject(claim: ClaimValue, extraction: ExtractionResult | None,
                    event: SourceEvent, *,
                    thread_key: str | None) -> tuple[SubjectTier, str]:
    """The ALG-22 cascade itself. First match wins; the tier travels with the key.

    Split from ``subject_key`` because the assembler needs the rung as well as the string, and a
    caller that had to re-derive "was that a structured id?" by inspecting the prefix would be
    one renamed source away from reading ``"entity"`` as a system name.

    DIVERGENCE FROM DOC 05, and it is deliberate: the doc writes the field family into rung 3
    only (``entity:{canonical_hint}:{field_family}``) and leaves rungs 1, 2, 4 and 5 without it.
    Every rung carries it here, because the family is what makes a group COMPARABLE and the doc's
    own reason for putting it on rung 3 applies unchanged to the others — without it, one HubSpot
    deal's amount, its close date and its stage share a key, and ALG-12 is handed a pile of pairs
    that answer different questions. The property the reverse prompt actually pins is untouched:
    two events about ``hubspot:deal:12345`` still derive one identical key for one claim kind.
    """
    family = field_family_of(claim).value
    if _is_structured_event(event) and event.source_object_id:
        return (SubjectTier.STRUCTURED,
                f"{event.source}:{event.object_type}:{event.source_object_id}:{family}")
    document = document_identity(event)
    if document is not None:
        return SubjectTier.DOCUMENT, f"{document}:{family}"
    anchor = _org_anchor(extraction)
    if anchor:
        return SubjectTier.ENTITY, f"entity:{anchor}:{family}"
    if thread_key:
        return SubjectTier.THREAD, f"{thread_key}:{family}"
    return SubjectTier.EVENT, f"event:{event_subject_handle(event)}:{family}"


def subject_key(claim: ClaimValue, extraction: ExtractionResult | None, event: SourceEvent, *,
                thread_key: str | None = None) -> str:
    """**L1.5.0-U1 (ALG-22).** What this claim is ABOUT, as a stable derived string.

    The cascade, first match wins:

    1. ``"{source}:{object_type}:{external_id}"`` for a typed record — ``hubspot:deal:12345``.
       A CRM deal IS an identity; nothing about a thread improves on it.
    2. the document identity, for an event that is a file (rule 2, ``document_identity``).
    3. ``"entity:{canonical_hint}:{field_family}"`` when exactly one organisation is named.
    4. ``"thread:{thread_group_key}"`` — pass the walk's answer as ``thread_key``.
    5. ``"event:{digest of the event's dedup_key}"`` — a claim about nothing else groups with
       the OTHER claims of the same source object and with nothing further, which is a group of
       one object and not a crash. Keyed on the dedup key rather than on the minted ``event_id``
       so that a re-ingestion of the same message lands on the key it had the first time; see
       ``event_subject_handle``.

    Never raises for a recognised claim type, and never reads a clock, a model or a row. Two
    events about one HubSpot deal produce one key by construction, because every input to rung 1
    is carried on the event itself.
    """
    return _derive_subject(claim, extraction, event, thread_key=thread_key)[1]


def thread_group_key(event: SourceEvent,
                     event_lookup: Callable[[str], SourceEvent | None]) -> str | None:
    """ALG-23's linkage walk — ``attachment --parent--> email --parent--> thread``.

    ``parent_object_id`` is already populated by the Gmail connector for both hops
    (``composio.py:562`` for file->message, ``:515`` for message->thread), so this walks what
    ingestion already wrote and needs no new capture work. ``event_lookup`` maps a
    ``source_object_id`` to its event and is injected as a CALLABLE — a repository handle here
    would make the unit untestable and impure at once.

    The root of the chain is a thread id, which is never itself an event: the walk therefore ends
    when a parent cannot be resolved, and the unresolved id IS the answer. The one case where
    that reading is wrong is an attachment whose message is missing — a forwarded file whose
    parent chain is broken — because its unresolved parent is a MESSAGE, not a thread, and
    answering ``thread:<message id>`` would mint a private thread for a file and quietly orphan
    it. That returns None, and ALG-22 rule 2 catches it by document identity, exactly as doc 05's
    failure table prescribes.

    Total: a cycle, a self-parent and a missing id all return an answer rather than looping.
    """
    parent = (event.parent_object_id or "").strip()
    if not parent:
        return None
    seen: set[str] = {(event.source_object_id or "").strip()}
    current = event
    while True:
        if parent in seen:                     # a cycle in the chain is data, not a reason to hang
            return f"thread:{parent}"
        seen.add(parent)
        try:
            found = event_lookup(parent)
        except Exception:                      # noqa: BLE001 — a lookup that fails is a miss
            found = None
        if found is None:
            # An attachment's parent is its MESSAGE. Unresolvable means the chain is broken and
            # the thread is unknown — not that the message id is a thread.
            return None if _is_document_event(current) else f"thread:{parent}"
        current = found
        next_parent = (found.parent_object_id or "").strip()
        if not next_parent:
            # The chain ends at an event with no parent: that event IS the root of the group.
            return f"thread:{(found.source_object_id or '').strip() or parent}"
        parent = next_parent


@dataclass(frozen=True, slots=True)
class NormalizedClaim:
    """One extracted claim, carrying everything grouping needs and nothing it does not.

    A wrapper rather than a field bolted onto the claim types for two reasons. ``Money`` carries
    no evidence and no event pointer at all — its receipt is its ``as_written`` — so a bare
    ``Money`` cannot say which event stated it, and the founder's example is made of two of them.
    And ``ExtractionResult`` is cached permanently: adding provenance to a stored contract to
    serve one downstream unit is how a boundary type acquires a consumer's fields.

    Frozen, and every field is a value: the same claim must produce the same group on a replay,
    and a mutable member is how one claim ends up in two.
    """

    event_id: str
    #: The claim itself, still its own contract type — ALG-12 reads `Money.minor_units`.
    claim: ClaimValue
    family: FieldFamily
    #: ALG-22's answer for this claim, derived once at construction.
    subject: str
    tier: SubjectTier
    #: ALG-14's rank (0..6) for the event that stated it — the cap's ordering, and the reason a
    #: signed attachment survives a 600-claim thread while a mailing-list reply does not.
    authority_rank: int
    #: The event's own ``occurred_at``. DATA, never a clock read: the window is unbounded and
    #: this is only ever a tie-break inside the cap.
    occurred_at: datetime
    #: Position within its extraction. The last tie-break, so two identical amounts in one
    #: message keep a stable order instead of one determined by dict iteration.
    ordinal: int = 0
    #: The identifying anchor, when the cascade found one. See `_IDENTIFYING_TIERS`.
    anchor: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimGroup:
    """Every claim that must be compared with every other one, and the subject they share.

    ``group_key`` is the most identifying subject key in the group — a structured id if any
    member had one — so the group is named by what it is about rather than by whichever claim
    happened to be assembled first.
    """

    group_key: str
    tier: SubjectTier
    claims: tuple[NormalizedClaim, ...]
    #: How many claims the cap discarded. Non-zero is the operator's signal that a group hit
    #: MAX_CLAIMS_PER_GROUP; silently truncating would make a thread's oldest half vanish with
    #: no record that it ever existed.
    truncated: int = 0

    @property
    def size(self) -> int:
        return len(self.claims)


def _as_utc(moment: datetime) -> datetime:
    """A naive stamp is read as UTC so the cap's tie-break can never raise mid-sweep."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _authority_rank(event: SourceEvent) -> int:
    """ALG-14's rank for an event, through ``weigh_authority`` rather than a second table."""
    return rank_of(weigh_authority(Provenance(
        source=event.source, object_type=event.object_type,
        internal_kind=event.internal_kind)).authority)


def _claim_values(extraction: ExtractionResult) -> Iterable[ClaimValue]:
    """Every claim an extraction holds, in a fixed field order. Order is part of stability."""
    yield from extraction.amounts
    yield from extraction.dates_mentioned
    yield from extraction.commitments
    yield from extraction.decision_states
    yield from extraction.dependencies
    yield from extraction.entity_mentions
    yield from extraction.unclassified_observations


def claims_from_extraction(event: SourceEvent, extraction: ExtractionResult, *,
                           event_lookup: Callable[[str], SourceEvent | None] | None = None,
                           ) -> tuple[NormalizedClaim, ...]:
    """Turn one event's ExtractionResult into grouping-ready claims. The seam L1 calls.

    The subject key is derived HERE, once per claim, and stored — not recomputed inside the
    assembler — because the cascade needs the ``ExtractionResult`` (rung 3 reads its entity
    mentions) and the assembler must not have to hold every extraction in memory to group across
    a whole thread. ``event_lookup`` is optional: without it, rung 4's thread key is unavailable
    and a claim with no entity of its own keys on its event, which groups alone rather than
    wrongly.
    """
    thread_key = thread_group_key(event, event_lookup) if event_lookup is not None else None
    rank = _authority_rank(event)
    occurred = _as_utc(event.occurred_at)
    built: list[NormalizedClaim] = []
    for ordinal, claim in enumerate(_claim_values(extraction)):
        tier, key = _derive_subject(claim, extraction, event, thread_key=thread_key)
        built.append(NormalizedClaim(
            event_id=event.event_id, claim=claim, family=field_family_of(claim),
            subject=key, tier=tier, authority_rank=rank, occurred_at=occurred, ordinal=ordinal,
            anchor=key if tier in _IDENTIFYING_TIERS else None))
    return tuple(built)


class _Union:
    """Disjoint sets over claim indices. Iteration order is never read; only sorted output is."""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, index: int) -> int:
        root = index
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[index] != root:      # path compression, iterative
            self._parent[index], index = root, self._parent[index]
        return root

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self._parent[max(a, b)] = min(a, b)


def _cap(members: list[NormalizedClaim], limit: int) -> tuple[tuple[NormalizedClaim, ...], int]:
    """Doc 05's cap: keep the most authoritative, then the most recent, up to ``limit``.

    Authority first and recency second, in that order, because the reason a group overflows is a
    long thread of chatter around a small number of authoritative artifacts — and dropping the
    signed contract because forty replies came after it would defeat the whole comparison.
    """
    # Three stable passes rather than one composite key: a descending datetime cannot be
    # expressed as a negated sort term without turning it into a float, and this file takes no
    # float anywhere. Python's sort is stable, so each pass keeps the previous one's tie order.
    ordered = sorted(members, key=lambda c: (c.event_id, c.ordinal))
    ordered.sort(key=lambda c: c.occurred_at, reverse=True)
    ordered.sort(key=lambda c: c.authority_rank, reverse=True)
    if len(ordered) <= limit:
        return tuple(ordered), 0
    return tuple(ordered[:limit]), len(ordered) - limit


def assemble_claim_groups(claims: Sequence[NormalizedClaim], events: Sequence[SourceEvent], *,
                          event_lookup: Callable[[str], SourceEvent | None] | None = None,
                          max_group_size: int = MAX_CLAIMS_PER_GROUP,
                          ) -> tuple[ClaimGroup, ...]:
    """**L1.5.0-U2 (ALG-23).** Every claim that must be compared with every other one.

    ``claim_group = all claims where subject_key matches, OR thread_group_key matches AND field
    family matches`` — with the anchor guard the failure table demands, so a thread carrying two
    deals does not become one contradiction. The window is unbounded in time: an amendment six
    months after the original is in the same group, because nothing here consults a clock.

    ``events`` supplies both the per-claim event (for its thread) and the default parent lookup;
    ``event_lookup`` overrides it for a caller that can reach beyond the batch — a repository
    closure at the sync seam, which is what lets page two of a backfill join page one. Claims
    whose event is absent still group by their own subject key rather than being dropped.

    Deterministic end to end: groups come back sorted by tier then key, members sorted by the
    cap's ordering, and no result depends on iteration order anywhere.
    """
    by_source_object: dict[str, SourceEvent] = {}
    by_event_id: dict[str, SourceEvent] = {}
    for event in events:
        object_id = (event.source_object_id or "").strip()
        if object_id and object_id not in by_source_object:
            by_source_object[object_id] = event
        by_event_id[event.event_id] = event
    lookup = event_lookup if event_lookup is not None else by_source_object.get

    members = list(claims)
    union = _Union(len(members))

    # (a) identical subject keys — the unbounded structured/document/entity join.
    first_by_subject: dict[str, int] = {}
    for index, claim in enumerate(members):
        anchor_index = first_by_subject.setdefault(claim.subject, index)
        union.union(anchor_index, index)

    # (b) same thread + same field family, guarded by the identifying anchor.
    buckets: dict[tuple[str, str], list[int]] = {}
    for index, claim in enumerate(members):
        event = by_event_id.get(claim.event_id)
        if event is None:
            continue
        thread = thread_group_key(event, lookup)
        if thread is None:
            continue
        buckets.setdefault((thread, claim.family.value), []).append(index)

    for key in sorted(buckets):
        indices = buckets[key]
        anchors = sorted({members[i].anchor for i in indices if members[i].anchor})
        if len(anchors) > 1:
            # Two named subjects in one thread. Join each anchor's own claims and leave the
            # anchorless ones where they are — attributing them would be a coin flip.
            by_anchor: dict[str, list[int]] = {}
            for i in indices:
                if members[i].anchor:
                    by_anchor.setdefault(members[i].anchor, []).append(i)
            for anchored in by_anchor.values():
                for i in anchored[1:]:
                    union.union(anchored[0], i)
            continue
        for i in indices[1:]:
            union.union(indices[0], i)

    grouped: dict[int, list[NormalizedClaim]] = {}
    for index, claim in enumerate(members):
        grouped.setdefault(union.find(index), []).append(claim)

    groups: list[ClaimGroup] = []
    for root in sorted(grouped):
        bucket = grouped[root]
        _, tier, name = min((_NAMING_ORDER[c.tier], c.tier, c.subject) for c in bucket)
        kept, dropped = _cap(bucket, max_group_size)
        groups.append(ClaimGroup(group_key=name, tier=tier, claims=kept, truncated=dropped))
    groups.sort(key=lambda g: (_NAMING_ORDER[g.tier], g.group_key))
    return tuple(groups)
