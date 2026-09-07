"""C-11 · SignalType and C-12 · QualifiedEnterpriseSignal — the object that crosses L1 -> L2.

Everything else in `contracts/` describes a part of a message. This module describes the one
thing Layer 1 is allowed to hand upward, and it is deliberately the only shape L2 knows: no
`SourceEvent`, no `PreparedContent`, no `ExtractionResult` reaches the seam by itself. One row
per signal in `qualified_signals`, one object per row, and nothing else in the contract.

**What this replaces, and why the replacement was necessary.** `GatedEvent` carried the
ROUTING half of L1's job — structured values versus needs-extraction, plus cheap hints — and
says so in its own docstring: it "was missing its qualifying half". A router's output answers
*how do we process this*; it never answers *what kind of thing is this, how big is it, do we
believe it, and is it still true*. Those four questions are what an upper layer actually
consumes, so every layer above was left to re-derive them from raw facts, each in its own way
and none of them reproducibly. The concrete cost is recorded upstream: with no per-event
importance at L1, Layer 4's utility formula had nothing to score on, `priority_override`
replaced it outright, and ranking collapsed into authored YAML constants that hand two
different tenants an identical ordering. This object carries BOTH halves — the routing-era
provenance AND the qualification — which is what lets the formula upstream start deciding.

`GatedEvent` is not deleted for this. It is demoted to the internal S1 -> S2 handoff
(renamed `RoutedEvent` in a later wave) because its versionability, its visibility stamping
and its domain hints are genuinely good work that must not be lost in the move.

**Three properties hold across the whole object, and each closes a specific failure:**

* **Every number is an integer.** `importance_bp`, `confidence_bp` and every value inside
  `confidence_vector` are basis points 0..10000 through the single shared `require_bp`. V-7
  goes further than the annotations can: `versions` is typed `Any`-valued, so `require_no_float`
  (imported from `conflict.py`, not re-implemented) walks it and refuses a ratio smuggled in at
  any depth. A float that reaches `qualified_signals` as jsonb comes back out as a number
  nobody can trace to a source string.
* **Every signal carries a receipt.** `evidence_refs` is non-empty at construction, not merely
  at the publishing gate — V-4's own stated reason is that a claim with no receipt is a guess.
  Unverified spans are a different matter: V-5 is the one non-blocking rule, so an unverified
  span degrades trust (the publisher downgrades `confidence_bp` and flags) and never destroys
  the signal.
* **Visibility is required, not optional.** `SourceEvent.visibility` and
  `GatedEvent.visibility` are both `Visibility | None`, because they exist before the answer is
  known. By this seam the answer is known or the event never got here: V-1 PARKS an event with
  reason code `visibility_unknown` (`contracts/parked.py`, reviewable and recoverable) rather
  than emitting a signal whose audience nobody established. It is the only V-rule whose failure
  action is park rather than reject, and typing the field non-optional is what makes that rule
  unbypassable instead of merely documented.

**What this module does NOT own.** The same boundary `evidence.py` and `conflict.py` draw.
Classification is ALG-16 (L1.6.3) and it owns the precedence order that picks a primary type
when several predicates fire; scoring is ALG-17 (L1.6.7) and it owns the weights, the log
bucket table and the per-type nudge; lifecycle transitions are ALG-19 (L1.6.9) and it owns
when a signal supersedes, expires or resolves. None of those tables is copied here. A second
copy of a lookup table in a contract is a table that forks from the first the day either is
edited, and the fork is invisible because both sides still typecheck. What is enforced below
is the *shape* every one of those algorithms must produce.

GAP FLAG — no `payload_ref` / `prepared_content_ref`. `GatedEvent` carries both, doc 08's C-12
block lists neither, and the migration table maps neither, so the link from a published signal
back to the raw bytes it came from is dropped by the spec as written. It is not reintroduced
here (the contract is the doc's), but it is not costless either: `trace_id` reaches the
`EventTrace` and `event_id` reaches the landing row, so the path back exists — it is one join
longer and depends on the landing repository keeping the reference. Whoever builds L1.6.10
should confirm that join is real before the first tenant asks where a number came from.

GAP FLAG — no `secondary_types`, `importance_components`, `importance_version` or
`extraction_ref`. All four are columns in doc 06's `qualified_signals` DDL and ALG-16's own
acceptance criterion is that a 4-predicate event records three secondaries. Doc 08's C-12
declares none of them, so none is declared here; the DDL and the contract disagree, and the
publisher (L1.6.10) will have to source those columns from the qualification pipeline rather
than from this object. Note also that the DDL stores `extraction_ref` as a POINTER into
`l1_extraction_results` while this contract embeds the whole `ExtractionResult` — the object
that crosses the seam carries the payload, the row that records it carries the cache key.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from genios_engine.contracts.conflict import Conflict, require_no_float
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.gated_event import DomainHint
from genios_engine.contracts.validators import (require_aware, require_bool, require_bp,
                                                require_enum, require_hash64, require_identifier,
                                                require_ordinal, require_strings, require_text)
from genios_engine.contracts.visibility import Visibility

#: The lifecycle states ALG-19 (L1.6.9) may put a signal in. Closed, and closed for a reason:
#: `state` is what tells L2 whether to correlate a fact or ignore it, so a fifth spelling
#: ("dead", "closed") reaching the column would make a renewal about a cancelled contract look
#: live to every query that filters on the four it knows. Globe Rule 08 — stale beats wrong —
#: applied at L1.
#:
#: DIVERGENCE FROM HOUSE STYLE, deliberate: this is a closed set and house style says Enum, but
#: doc 08 types the field `str` and the DDL stores `text not null default 'active'`. The set is
#: enforced as a frozenset against a `str` field instead, which keeps the wire form, the column
#: and the contract identical while still refusing a value outside it. `SignalType` IS an enum
#: because the doc writes it as one.
SIGNAL_STATES: frozenset[str] = frozenset({"active", "superseded", "expired", "resolved"})

#: PROCESSING ORDER, and nothing else. `capture/triage/triage.py` scores an event on cheap
#: deterministic signals (urgency words, a deadline word, a known sender, a question mark) and
#: buckets it here; `context/runner.py` sorts its work queue by this string. It is NOT priority
#: — priority is "what should this person do first", it is relative to the person's whole book,
#: it changes when the book changes, and it belongs to Layer 4. Conflating the two is the exact
#: mistake doc 06 spends a table separating, so the two names never appear on one field.
TRIAGE_LANES: tuple[str, ...] = ("P0", "P1", "P2", "P3")

#: The four components of `confidence_vector`, exactly. ALG-13 (Rule 11, L1.5.7) composes
#: `confidence_bp` from these, and a vector missing one of them does not compose to a smaller
#: number — it composes to a *differently-derived* number that still looks like a confidence.
#: Requiring all four means "we did not measure freshness" cannot be read as "freshness was
#: fine", which is what an absent key would say to every consumer that uses `.get(key, 0)`.
CONFIDENCE_COMPONENTS: frozenset[str] = frozenset({"evidence", "expertise", "freshness",
                                                   "coverage"})


class SignalType(str, Enum):
    """C-11 · the closed 14-member taxonomy of what kind of thing a signal is.

    v1 had no signal taxonomy at all — an event was routed, hinted and stored, and every
    consumer above pattern-matched the prose again to work out whether it was looking at a
    promise, a deadline or a renewal. That is why two tenants got identical rankings: with no
    kind, there is nothing to weigh but authored constants.

    A `str` enum so the wire form, the `qualified_signals.signal_type` column and the code all
    read as the same literal word, while the set stays closed. Closed means closed: a value
    outside these 14 is a V-2 REJECT, never a coercion to a near neighbour, because the nearest
    neighbour of an unrecognised kind is exactly where a novel pattern would be silently
    absorbed and never noticed. Something genuinely new goes to the OPEN LANE
    (`UnclassifiedObservation`, C-08), which is stored, read by no rule, and reviewed weekly —
    that is the only sanctioned route from "we have no word for this" into the vocabulary.

    Adding a member is a schema version bump and a corpus review, never a casual edit. The
    reason is downstream: ALG-16 owns a precedence order over these names and ALG-17 owns a
    per-type weight for each one, so a fifteenth member added here without touching either is a
    type that can be classified and then scored as if it were nothing in particular.

    The ALG-16 precedence order and the ALG-17 type weights are deliberately NOT mirrored in
    this module — see the module docstring. The three-line rationale for the top of that order
    is worth knowing while reading the members: a conflict means we may be about to tell a
    founder something false, an escalation is time-bound, and an approval request is blocking a
    human right now. Those outrank everything merely descriptive.
    """

    #: Someone promised to do something. C-05 `Commitment` is the claim behind it.
    COMMITMENT_MADE = "commitment_made"
    #: A promise whose due date is at hand — the same commitment, later in its life. Separate
    #: from COMMITMENT_MADE because the two are actionable at different moments and ALG-19
    #: expires them on different clocks (deadline + 30d).
    COMMITMENT_DUE = "commitment_due"
    #: A date the source stated as binding, with no promise attached to it.
    DEADLINE_STATED = "deadline_stated"
    #: A decision that has not been made yet — the open loop L2 correlates across a thread.
    DECISION_PENDING = "decision_pending"
    #: A decision that HAS been made. It closes the loop above, and it is what stops a
    #: resolved question being surfaced again next week.
    DECISION_MADE = "decision_made"
    #: Somebody is waiting on a human to say yes. Blocking, hence high in ALG-16's precedence.
    APPROVAL_REQUESTED = "approval_requested"
    #: A contract is coming up for renewal — the signal a missed renewal date is made of.
    CONTRACT_RENEWAL = "contract_renewal"
    #: Money is owed or committed. C-02 `Money` (integer minor units) is the claim behind it.
    FINANCIAL_OBLIGATION = "financial_obligation"
    #: A stated risk: a slipping delivery, a named legal exposure, a dependency in trouble.
    RISK_FLAGGED = "risk_flagged"
    #: An opening — expansion, referral, a stated intent to buy more.
    OPPORTUNITY_SIGNAL = "opportunity_signal"
    #: The people changed: a new counterparty, a departure, an owner handover. Cheap to miss
    #: and expensive to have missed, because every later fact is attributed to the wrong human.
    RELATIONSHIP_CHANGE = "relationship_change"
    #: Two sources disagree about the same field. Top of ALG-16's precedence: a conflict means
    #: we may be about to state something false with a receipt that looks legitimate, and the
    #: C-10 `Conflict` records both sides rather than picking one quietly.
    INFORMATION_CONFLICT = "information_conflict"
    #: Something was escalated. Time-bound by nature, so second in precedence.
    ESCALATION = "escalation"
    #: The catch-all for a validated departure from the normal pattern — an unusual amount, an
    #: unusual sender, an unusual cadence. NOT the open lane: an anomaly is a recognised kind
    #: with no recognised cause, while an open-lane observation has no recognised kind at all.
    ANOMALY = "anomaly"


class QualifiedEnterpriseSignal(BaseModel):
    """C-12 · Layer 1's only output. Nothing else crosses the L1 -> L2 seam.

    Read the module docstring for what this replaces and why. What follows is what a reader
    holding one of these objects needs to know.

    **Four groups of fields, four different jobs.** The envelope says which tenant, which
    trace and which audience — it is what makes the object routable and what makes a leak
    impossible. The qualification (`signal_type`, `domain_hints`, `importance_bp`,
    `triage_lane`) is the half that did not exist before this type. The trust block
    (`evidence_refs`, `conflicts`, `confidence_bp`, `confidence_vector`, `coverage_ready`) is
    what lets a human check us instead of believing us. The lifecycle block (`state`,
    `supersedes`, `expires_at`) is what stops a dead signal being correlated as a live one.

    **`coverage_ready` is a real, assigned field here.** On `GatedEvent` it was declared and
    never assigned by its only constructor: `capture/pipeline.py` around line 279 tested
    `isinstance(hints[0], dict)` while `domain_hints()` returns `DomainHint` pydantic models, so
    the branch was False on every call and the field stayed `None` on 100% of events ever
    produced — while `capture/coverage/model.py` computed the real answer and discarded it, and
    `coverage_fn` was passed by no production caller at all. A dead field on a boundary contract
    is worse than a missing one: `None` reads as "unknown" exactly where a caller most wants a
    yes, so every consumer that could have made a negative inference quietly declined to make
    any. L1.1-U1 wires it — coverage is computed per sweep from the org's active connections,
    persisted to `source_coverage`, and passed down so every emitted event carries a real
    verdict. `None` survives as a legal value for one honest case only: an event with no domain
    hint at all, where "we did not classify this" and "this domain is under-connected" are
    different states a caller must be able to tell apart.

    **What `coverage_ready` actually buys.** It is the licence to make a NEGATIVE inference —
    "they never replied", "no meeting was booked", "the invoice was never sent". Those are the
    most valuable things an assistant can say and the most dangerous: said without coverage they
    mean "we did not see it", which is not the same claim at all and is wrong the moment a
    tenant has a channel we are not connected to.

    **Mutable, with `validate_assignment`.** Unlike `EvidenceSpan` and `Conflict`, which are
    frozen because they record something that happened, a qualified signal has a life: ALG-19
    moves `state` from active to superseded, expired or resolved as the world changes. Freezing
    would push every transition through `model_copy(update=...)`, which skips validators — so a
    lifecycle manager would be able to write a state no rule allows. `validate_assignment=True`
    means an assignment re-runs the checks below instead of evading them. `extra="forbid"` is
    load-bearing for the same reason it is on `Conflict`: with 24 fields, a mistyped kwarg is
    otherwise a value that silently never arrives.

    **Publication (V-1..V-7) still belongs to L1.6.10.** Most of it is enforced here at
    construction, which is stricter and earlier, and that is intentional — the doc's own
    universal rule 5 says a validator runs at the seam that produced the object, and a signal
    that cannot be built is a signal that cannot be published by accident. What the publisher
    keeps is the part a contract cannot do: turning a refusal into a ledger row (a rejected
    signal must stay reconstructable), parking rather than raising for V-1, applying V-5's
    downgrade policy, and V-6's comparison against the source confidences this object does not
    carry. `all_spans_verified` and `confidence_respects_sources()` below are the reads it needs.
    """

    #: See the class docstring. `validate_assignment` is what makes an ALG-19 state transition
    #: revalidate rather than bypass; `extra="forbid"` turns a mistyped field name into an error
    #: at the seam instead of a stored row that is missing something nobody notices.
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # --- envelope: which tenant, which trace, who may see it ---

    #: The tenant boundary. Every query above filters on it, so it is validated as an identifier
    #: rather than free text: this string reaches SQL, log lines and cache keys.
    org_id: str
    #: The contract version this row was written against. INT here, and deliberately NOT
    #: unified with `ExtractionResult.schema_version`, which is a `str` — doc 08 states both
    #: literally, and that value is already part of a cache key over stored extraction rows, so
    #: retyping it would change every key and orphan the cache it exists to protect.
    schema_version: int = 1
    #: Ties this signal back to its `EventTrace` (`contracts/trace.py`), which holds the
    #: per-stage record of what happened to the event that produced it. This is the join a
    #: human follows backwards when they want to know why a card says what it says.
    trace_id: str
    #: Who could see the ORIGINAL. Source-stamped at the normalize seam and never widened by any
    #: layer above — the audience of a derived insight can never be wider than the audience of
    #: the evidence it came from, and L1 is the last layer that still knows the answer. Required,
    #: not optional: see the module docstring on V-1.
    visibility: Visibility

    # --- identity ---

    #: The signal's own id, distinct from the event's. One event routinely yields several
    #: signals — a single email can state a renewal, a pending decision and an approval request
    #: — and they expire, supersede and resolve independently, so they cannot share a key.
    signal_id: str
    #: The event this was qualified from. From `GatedEvent`, unchanged. Many signals to one
    #: event; this is the many-side pointer.
    event_id: str
    #: Which connector produced the event. From `GatedEvent`, unchanged.
    source: str
    #: What kind of object it was — message, deal, note, document. From `GatedEvent`, unchanged.
    object_type: str
    #: WORLD time — when the thing happened, not when we ingested it. tz-aware UTC. Everything
    #: about recency, expiry and ordering reads this, and an ingest timestamp in its place makes
    #: a two-month-old backfilled thread look like this morning's news.
    occurred_at: datetime

    # --- qualification: the half that did not exist before this type ---

    #: What KIND of thing this is, assigned by ALG-16's decision table at L1.6.3. Exactly one
    #: primary type even when several predicates fire, chosen by a fixed precedence constant so
    #: two runs over the same event agree.
    signal_type: SignalType
    #: Which business domains this signal is a candidate for, and HOW each was guessed
    #: (`scope` | `keyword` | `history`). Reused verbatim from `contracts/gated_event.py` rather
    #: than redefined — a second DomainHint would be a second answer to the same question.
    #: A multi-domain signal keeps every tag; the empty list is legitimate and means unhinted,
    #: which is exactly the case `coverage_ready=None` exists for.
    domain_hints: list[DomainHint] = Field(default_factory=list)
    #: HOW BIG IS THIS THING, intrinsically — 0..10000, computed by ALG-17 at L1.6.7 from facts
    #: that have already been span-validated, money-normalised and date-resolved.
    #:
    #: This is the single field v1 refused to compute and v2 computes deterministically, and the
    #: distinction that resolves the old objection is that importance is not priority: importance
    #: is intrinsic to the event and does not change when the person's book changes; priority is
    #: relative to everything else competing for the same attention and belongs to Layer 4. An
    #: $84K renewal is a big thing on any day; whether to look at it before the board deck is a
    #: different question that only Layer 4 can see the inputs for.
    #:
    #: The LLM is FORBIDDEN from producing this — `ExtractionResult` refuses the field name at
    #: construction. A score emitted by the model alongside its own claims is derived from
    #: unvalidated input and does not reproduce across replays, so caching it would freeze one
    #: run's guess into every future reading of the same message.
    importance_bp: int
    #: PROCESSING ORDER ONLY, P0..P3 — see `TRIAGE_LANES` for why it is never priority.
    #:
    #: DIVERGENCE FROM `GatedEvent`, which defaulted this to "P2": required here, with no
    #: default, because doc 08 declares none and because the producer always has an answer
    #: (`triage_lane()` returns one for every event). A default lane is a lane nobody chose,
    #: and it is indistinguishable in the column from one that was computed.
    triage_lane: str

    # --- semantic payload ---

    #: The WHOLE S2 output, embedded rather than referenced. This is how L2 receives the
    #: extraction without ever importing `ExtractionResult` by itself — the type stays internal
    #: to L1, and the seam stays one object wide. Note the DDL stores a pointer
    #: (`extraction_ref` into the permanent extraction cache) while the in-flight object carries
    #: the payload: the extraction lives once, and every replay reads it from the cache.
    extraction: ExtractionResult

    # --- trust ---

    #: The spans this SIGNAL rests on — the union of the triggering claims' evidence, not every
    #: span in the extraction. Required with NO default, on purpose: an empty list is a V-4
    #: reject, and a `default_factory=list` would quietly invite exactly the object the rule
    #: exists to refuse. Non-emptiness is enforced at construction below, for the doc's own
    #: reason — a claim with no receipt is a guess.
    evidence_refs: list[EvidenceSpan]
    #: Disagreements detected across this signal's sources, both sides retained (C-10 keeps no
    #: `winner`). May legitimately be empty — most signals have nothing to disagree about — but
    #: required with no default so an empty list is something a producer stated rather than
    #: something the contract assumed on its behalf.
    conflicts: list[Conflict]
    #: How much we believe the signal, 0..10000, composed by ALG-13 (Rule 11, L1.5.7) from the
    #: vector below. V-6 is the rule that gives it meaning: a composed confidence may never
    #: exceed the weakest source it was composed from unless independent evidence is explicitly
    #: named. Without that ceiling, composition becomes a way of manufacturing certainty out of
    #: several weak sources that all say the same weak thing.
    confidence_bp: int
    #: The four named components, each in basis points: `evidence` (are the spans real),
    #: `expertise` (do we know this domain), `freshness` (how old is the input), `coverage` (did
    #: we see enough to be talking about this at all). Exactly these four keys — see
    #: `CONFIDENCE_COMPONENTS`. Kept beside the composed number because a single 6200 explains
    #: nothing: the vector is what tells a human whether to go connect a source or go read a
    #: document.
    confidence_vector: dict[str, int]
    #: Can we make a NEGATIVE inference in this signal's domain? See the class docstring — this
    #: is the field that was dead on `GatedEvent` and is assigned by L1.1-U1 here. `None` means
    #: unhinted, and is not a synonym for `False`.
    coverage_ready: bool | None

    # --- lifecycle (ALG-19, L1.6.9) ---

    #: One of `SIGNAL_STATES`. `active` is the only state L2 correlates; the other three are the
    #: three ways a signal stops being true. A renewal signal about a contract that was cancelled
    #: must be marked dead, or the founder is nudged about something that resolved last week.
    state: str
    #: The `signal_id` this one replaces, or None. A supersede happens when a newer signal covers
    #: the same subject and type with at least equal authority; a newer LOWER-authority signal
    #: does not supersede a higher-authority older one, which is why the rule lives in ALG-19
    #: with the ranks in front of it and not here. Revival is the same mechanism: new evidence on
    #: an expired signal creates a NEW signal that supersedes the old one, and never mutates the
    #: expired row back to active — history has to stay readable.
    #:
    #: GAP FLAG (cross-doc): C-12's field note says this points at the signal being REPLACED
    #: (the new signal points back), while doc 06's ALG-19 pseudocode writes `old.supersedes
    #: points forward`. The two readings disagree about direction and nothing here can settle
    #: it, so only the one invariant true under both is enforced: a signal may not supersede
    #: itself. L1.6.9 must pick a direction and state it in one place.
    supersedes: str | None
    #: When this signal stops being worth acting on, tz-aware UTC. ALG-19 defaults it by type —
    #: a due commitment or stated deadline expires 30 days past the date, a renewal 30 days past
    #: the renewal, a pending decision in 90 days, everything else in 180 — computed from the
    #: signal's OWN date fields, never from ingest time. Required with no default; None is legal
    #: and means nothing expires this signal on a clock.
    expires_at: datetime | None

    # --- provenance ---

    #: Company-canon authority class (`capture.internal_knowledge.INTERNAL_KINDS`) — the
    #: authority this event carries into the graph. `None` = observed traffic, ordinary rank.
    #: From `GatedEvent`, unchanged. It is what lets an uploaded pricing policy outrank an email
    #: that recalls it, and it is one of the inputs to the actor authority term of ALG-17.
    internal_kind: str | None
    #: The FULL participant set. Without it there is no way to tell a conversation from a
    #: broadcast, or an introducer from a counterparty. From `GatedEvent`, unchanged in meaning
    #: — but required here rather than defaulting to `()`, because "nobody else was on this" and
    #: "we never populated this" are different facts and the empty tuple was the only spelling of
    #: both. A tuple, not a list, so the value is hashable and cannot be appended to in place
    #: after the visibility that was derived from it has been stamped.
    recipients: tuple[str, ...]
    #: EVERY version that produced this signal — prompt, schema, model snapshot, vocabulary,
    #: pack. This is `GatedEvent`'s MUT-01 versionability carried forward intact, and it is what
    #: makes a decision from March reproduce in September instead of being reinterpreted by code
    #: that did not write it. Values are `Any`, which is the hole V-7 exists for:
    #: `require_no_float` walks the whole mapping.
    versions: dict[str, Any]

    # --- the four provenance answers the seam used to drop (migration 0115) ---
    #
    # All four are optional and default to None, deliberately. Every one of them is knowable on
    # the capture path and unknowable afterwards, so a row that carries None is a row written
    # before this existed or by a door that genuinely could not answer — never a placeholder.

    #: WHEN WE FIRST SAW IT. `occurred_at` is world time: when the email was sent, when the
    #: meeting starts. That is the right instant to reason about and the wrong one to operate on,
    #: because it says nothing about whether the message reached us in ten seconds or in a
    #: backfill three weeks later. `SourceEvent.captured_at`, carried across the seam.
    ingested_at: datetime | None = None
    #: sha256 of the PREPARED text these claims were read out of — the same digest
    #: `capture/semantic/cache.py` folds into its key, so a signal and its cached extraction can
    #: be compared without re-reading either. Stored rather than derived on demand because
    #: `prepared_content` has a retention window and this must outlive it: when the body is gone,
    #: the hash is the only thing left that can say the source has not silently changed.
    content_hash: str | None = None
    #: WHY ALG-18 let this through — `QualificationReason`'s value. A refusal has always carried
    #: its reason into `qualification_drops`; an acceptance carried none, so "at or above the
    #: floor", "could not be scored and therefore travels", "carries a conflict" and "company
    #: canon" were four different decisions that all read as a published row.
    qualification_reason: str | None = None
    #: The FORWARD half of the supersession link — the signal that REPLACED this one. `supersedes`
    #: points backwards from the new row; without this, reaching the replacement from the old id
    #: meant scanning every row for one pointing at you. Written by the store when the replacement
    #: is published, so the two halves are set in one place and cannot disagree.
    superseded_by: str | None = None

    @field_validator("ingested_at", mode="before")
    @classmethod
    def _ingested(cls, value: Any) -> Any:
        """Aware or absent. A naive capture time is the same replay hazard `occurred_at` refuses,
        one column over: it reads as UTC on one host and as local on another."""
        return None if value is None else require_aware(value, "ingested_at")

    @field_validator("content_hash", mode="before")
    @classmethod
    def _content_hash(cls, value: Any) -> Any:
        """64 lowercase hex, or nothing. An upper-cased or truncated digest compares unequal to
        the same content hashed by the extraction cache, which is the one use this field has."""
        return None if value is None else require_hash64(value, "content_hash")

    @model_validator(mode="after")
    def _supersession_is_not_a_loop(self) -> "QualifiedEnterpriseSignal":
        """Neither half of the link may point at its own row. The database carries the same two
        checks (migration 0115); stating them here is what stops an in-memory dev run from being
        the place a cycle of one first becomes possible."""
        if self.superseded_by is not None and self.superseded_by == self.signal_id:
            raise ValueError(f"signal {self.signal_id} cannot be superseded by itself")
        if (self.superseded_by is not None and self.supersedes is not None
                and self.superseded_by == self.supersedes):
            raise ValueError(
                f"signal {self.signal_id} both replaces and is replaced by {self.supersedes} — "
                "one of the two halves of the link was written in the wrong direction")
        return self

    # ------------------------------------------------------------------ envelope + identity

    @field_validator("org_id", "trace_id", "signal_id", "event_id", mode="before")
    @classmethod
    def _identifier(cls, value: Any, info: ValidationInfo) -> str:
        """The four keys that travel into SQL, URLs, log lines and content addresses.

        `require_identifier` keeps the character class narrow enough that none of those four
        contexts ever needs to escape one — which is a correctness property, not tidiness: a key
        that needs escaping in one of them is a key that is eventually not escaped in it.
        """
        return require_identifier(value, info.field_name or "identifier")

    @field_validator("source", "object_type", "state", "triage_lane", mode="before")
    @classmethod
    def _required_label(cls, value: Any, info: ValidationInfo) -> str:
        """Presence and stripping only. Membership for the two closed ones is checked below,
        after pydantic has bound a real `str`."""
        return require_text(value, info.field_name or "label")

    @field_validator("schema_version", mode="before")
    @classmethod
    def _positive_version(cls, value: Any) -> int:
        """Versions count from 1. `require_ordinal` also refuses a bool, which the `int`
        annotation would happily accept as 1 and store as a version nobody released."""
        return require_ordinal(value, "schema_version")

    @field_validator("occurred_at")
    @classmethod
    def _aware_occurred_at(cls, value: datetime) -> datetime:
        """Tz-aware, normalised to UTC — and run AFTER pydantic's parse, not before it, so a
        stored row rehydrates: `require_aware` type-checks for a `datetime` and would reject the
        ISO-8601 string a `qualified_signals` row comes back as. A naive datetime is an
        unanswered timezone question whose silent offset expresses itself later as a reminder
        that fires on the wrong day."""
        return require_aware(value, "occurred_at")

    # ------------------------------------------------------------------ qualification

    @field_validator("signal_type", mode="before")
    @classmethod
    def _closed_taxonomy(cls, value: Any) -> SignalType:
        """V-2 — a value outside the 14 is a REJECT, never a coercion.

        `require_enum` is used rather than pydantic's own enum error purely for the message: it
        names the field and shows the offending value, which is what a publisher writes into the
        rejection ledger row.
        """
        return require_enum(value, SignalType, "signal_type")

    @field_validator("importance_bp", "confidence_bp", mode="before")
    @classmethod
    def _score(cls, value: Any, info: ValidationInfo) -> int:
        """V-3 and CV-BP through the one shared helper — it already refuses a bool, refuses
        anything that is not an exact integer (pydantic's lax mode would round `0.87` to `0`
        and call it a confidence), and range-checks 0..10000."""
        return require_bp(value, info.field_name or "score")

    @field_validator("triage_lane")
    @classmethod
    def _known_lane(cls, value: str) -> str:
        """A lane outside P0..P3 sorts unpredictably in `context/runner.py`'s ORDER BY, which
        does not fail — it just works the queue in an order nobody designed."""
        if value not in TRIAGE_LANES:
            raise ValueError(
                f"triage_lane must be one of {TRIAGE_LANES}, got {value!r} — the lane is "
                "processing order, and an unknown lane silently reorders the queue")
        return value

    # ------------------------------------------------------------------ trust

    @field_validator("confidence_vector", mode="before")
    @classmethod
    def _four_components(cls, value: Any) -> dict[str, int]:
        """CV-BP inside the dict, plus the exact key set.

        The `dict[str, int]` annotation stops nothing on its own: lax coercion would turn a 0.62
        ratio into 0 and store it as a component. Both directions of the key check matter — a
        missing component is read as a zero by every consumer doing `.get(key, 0)`, and an extra
        key is a component somebody invented that ALG-13 does not compose.
        """
        if not isinstance(value, Mapping):
            raise TypeError("confidence_vector must be a mapping of component to basis points")
        vector = {require_text(name, "confidence_vector key"): require_bp(score, f"{name} bp")
                  for name, score in value.items()}
        missing = sorted(CONFIDENCE_COMPONENTS - set(vector))
        unknown = sorted(set(vector) - CONFIDENCE_COMPONENTS)
        if missing or unknown:
            raise ValueError(
                f"confidence_vector must carry exactly {sorted(CONFIDENCE_COMPONENTS)}; "
                f"missing={missing} unknown={unknown} — an absent component reads as zero "
                "confidence in that dimension, which is not what an unmeasured one means")
        return vector

    @field_validator("coverage_ready", mode="before")
    @classmethod
    def _tri_state_coverage(cls, value: Any) -> bool | None:
        """A literal bool or a literal None. Truthiness coercion is precisely how the licence to
        make a negative inference would be granted by an empty string or a zero."""
        return None if value is None else require_bool(value, "coverage_ready")

    # ------------------------------------------------------------------ lifecycle

    @field_validator("state")
    @classmethod
    def _known_state(cls, value: str) -> str:
        """A state outside the four is a signal L2's `state = 'active'` filters neither include
        nor exclude on purpose — it just disappears from every query that was written against
        the vocabulary ALG-19 documents."""
        if value not in SIGNAL_STATES:
            raise ValueError(
                f"state must be one of {sorted(SIGNAL_STATES)}, got {value!r}")
        return value

    @field_validator("supersedes", mode="before")
    @classmethod
    def _superseded_id(cls, value: Any) -> str | None:
        """Same identifier rules as `signal_id`, since this is a pointer at one."""
        return None if value is None else require_identifier(value, "supersedes")

    @field_validator("expires_at")
    @classmethod
    def _aware_expiry(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware(value, "expires_at")

    # ------------------------------------------------------------------ provenance

    @field_validator("internal_kind", mode="before")
    @classmethod
    def _canon_class(cls, value: Any) -> str | None:
        """Present or absent, never blank. The membership check against `INTERNAL_KINDS` lives
        in `capture/internal_knowledge.py` and is not duplicated here — contracts may not import
        capture, and a second copy of that frozenset would fork from the first."""
        return None if value is None else require_text(value, "internal_kind")

    @field_validator("recipients", mode="before")
    @classmethod
    def _participant_set(cls, value: Any) -> tuple[str, ...]:
        """Non-empty strings, order preserved.

        Order is kept rather than sorted because the first recipient is frequently the addressee
        and the rest are cc — information the participant set would lose if it were normalised
        into a set. Blank entries are refused: they inflate every "was this a broadcast" count by
        one without naming anybody.
        """
        if value is None or isinstance(value, (str, bytes)) or isinstance(value, Mapping):
            raise TypeError("recipients must be a sequence of addresses")
        return require_strings(value, "recipient")

    @field_validator("versions", mode="before")
    @classmethod
    def _versioned(cls, value: Any) -> dict[str, Any]:
        """V-7 over the one field wide enough to smuggle a float, plus replayability.

        `require_no_float` is imported from `conflict.py`, which wrote it for exactly this reuse
        rather than growing a second copy — it walks the whole structure, because a ratio nested
        three keys deep reaches the jsonb column just as easily as one at the top.

        GAP FLAG: non-emptiness is enforced here and doc 08 does not state it. The grounds are
        the field's own stated purpose — "every version that produced this signal", required for
        replay. An unversioned signal cannot be replayed at all: there is no way to know which
        prompt, vocabulary or model produced it, so a September re-run silently re-derives it
        with today's code and calls the result the same decision.
        """
        if not isinstance(value, Mapping):
            raise TypeError("versions must be a mapping of component to version")
        versions = {require_text(name, "versions key"): require_no_float(item, f"versions.{name}")
                    for name, item in value.items()}
        if not versions:
            raise ValueError(
                "versions is required — a signal that cannot name the prompt, schema, model and "
                "vocabulary that produced it cannot be replayed, only re-guessed")
        return versions

    # ------------------------------------------------------------------ whole-object rules

    @model_validator(mode="after")
    def _publishable(self) -> QualifiedEnterpriseSignal:
        """The rules that need more than one field — V-4 and the two lifecycle coherences.

        V-4 first, and it is the reason this validator exists at all: `evidence_refs` non-empty,
        because a claim with no receipt is a guess and a guess must not reach a human wearing the
        same typography as a fact. Enforced at construction rather than only at L1.6.10 so that
        an unpublishable signal cannot be built, stored, or handed to L2 by a caller that forgot
        to run the gate.

        The two lifecycle rules close states that are unreadable rather than merely wrong. A
        signal marked `expired` with no `expires_at` claims a clock ran out and names no clock —
        ALG-19 expires only when `expires_at` has passed, so the state cannot honestly exist
        without the field. And a signal that supersedes itself is a cycle: `supersedes` is walked
        to reconstruct a subject's history, and a self-pointer makes that walk non-terminating
        while looking perfectly ordinary in a single row.

        GAP FLAG: the `expired`-implies-`expires_at` rule is not in doc 08's V-table. It is
        enforced anyway, on the same grounds `conflict.py` enforced its converse rule — the state
        it admits is unexplainable to a user ("this expired" next to a blank) and nothing
        downstream would catch it.
        """
        if not self.evidence_refs:
            raise ValueError(
                "evidence_refs must be non-empty — a claim with no receipt is a guess")
        if self.state == "expired" and self.expires_at is None:
            raise ValueError(
                "an expired signal must carry the expires_at it passed — ALG-19 expires on that "
                "clock, and a state that names no clock cannot be explained or replayed")
        if self.supersedes is not None and self.supersedes == self.signal_id:
            raise ValueError(
                f"a signal may not supersede itself ({self.signal_id!r}) — supersedes is walked "
                "to reconstruct history, and a self-pointer never terminates")
        return self

    # ------------------------------------------------------------------ reads for L1.6.10

    @property
    def all_spans_verified(self) -> bool:
        """V-5's read: did L1.5.1 (ALG-08) resolve every span against real source text?

        The DOWNGRADE policy is not applied here on purpose. V-5 is the one non-blocking rule —
        the publisher lowers `confidence_bp`, flags the signal and emits it anyway — and the size
        of that lowering is a policy number that belongs with the publisher, not frozen into a
        boundary type every stored row was validated against. What a contract can honestly say is
        whether the condition holds.
        """
        return all(span.verified for span in self.evidence_refs)

    @property
    def unverified_spans(self) -> list[EvidenceSpan]:
        """The spans that did not resolve, for the flag V-5 raises. Returned rather than counted
        so the flag can name the quote a human should go look at."""
        return [span for span in self.evidence_refs if not span.verified]

    @property
    def is_live(self) -> bool:
        """True only in `active`. The three other states are the three ways a signal stopped
        being true, and L2 correlates none of them — a superseded renewal correlated as live is
        the ghost ALG-19 exists to prevent."""
        return self.state == "active"

    def has_expired_by(self, evaluated_at: datetime) -> bool:
        """Has this signal's own clock run out as of `evaluated_at`?

        The instant is a PARAMETER, never `datetime.now()` read inside the object: a clock read
        here would make a replay of a March signal answer differently in September, and this
        object is evidence. Returns False when `expires_at` is None — nothing expires it on a
        clock — which is not the same as "it is still true", a question `state` answers.
        """
        if self.expires_at is None:
            return False
        return require_aware(evaluated_at, "evaluated_at") >= self.expires_at

    def confidence_respects_sources(self, source_confidences: list[int]) -> bool:
        """V-6's arithmetic, in one place and in integers.

        Rule 11 (ALG-13, L1.5.7): a composed confidence may never exceed the weakest source it
        was composed from. Several weak sources repeating one weak thing is not corroboration,
        and without this ceiling composition becomes a machine for manufacturing certainty.

        The publisher owns the exception the rule names — independent evidence explicitly
        named — because this object does not carry the source list and cannot tell an independent
        source from a copy of one. An empty list returns True: there is no ceiling to respect,
        which the caller must read as "V-6 did not apply here", not as "V-6 passed".
        """
        if not source_confidences:
            return True
        floor = min(require_bp(value, "source confidence") for value in source_confidences)
        return self.confidence_bp <= floor


__all__ = ["CONFIDENCE_COMPONENTS", "SIGNAL_STATES", "TRIAGE_LANES",
           "QualifiedEnterpriseSignal", "SignalType"]
