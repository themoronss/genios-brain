from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field, replace as _dc_replace
from datetime import datetime
from typing import Any, Mapping, Sequence

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.documents.native import extract_native_text
from genios_engine.capture.documents.pages import from_record as page_map_from_record
from genios_engine.capture.domain.hints import domain_hints
# S4 (L1.6) — ESQE. Imported by their PUBLIC names only, on the same terms as `capture/semantic/*`
# below: the pipeline consumes the package, it never reaches inside it.
from genios_engine.capture.esqe.classifier import SignalClassification, classify_signals
from genios_engine.capture.esqe.detector import DetectionInput, DetectionOutcome, detect_signals
from genios_engine.capture.esqe.domain import DomainTagging, tag_domains
from genios_engine.capture.esqe.importance import (ImportanceScore, OrgBaseline,
                                                   score_importance)
from genios_engine.capture.esqe.normalize import (NormalizedSignal, ThreadContext,
                                                  normalize_signals)
from genios_engine.capture.esqe.relevance import (MAX_ITEM_CHARS, RelevanceCandidate,
                                                  RelevanceDecision, assess_relevance)
from genios_engine.capture.esqe.source_analyzer import SourceAttribution, analyze_source
from genios_engine.capture.gate.context import GateContext, GateResult
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import RelevanceClassifier
from genios_engine.capture.documents.store import DocumentJobStore
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.landing.repository import SourceEventRepository
from genios_engine.capture.payload_store import RawPayloadStore
from genios_engine.capture.preprocess.preprocess import preprocess
# S2 (L1.4). Imported by their PUBLIC names only — the pipeline consumes the semantic package,
# it does not reach inside it: `capture/semantic/*` is owned elsewhere and every name below is in
# its module's `__all__`.
from genios_engine.capture.semantic.batch import ExtractionRequest as SpendRequest
from genios_engine.capture.semantic.extractor import (STAGE as SEMANTIC_STAGE, EventEnvelope,
                                                      ExtractionRequest, envelope_chars, extract)
from genios_engine.capture.semantic.model_router import (NO_T3_BUDGET, T3Budget, TierDecision,
                                                         TierRequest, decide_tier,
                                                         demote_for_cost, record)
from genios_engine.capture.semantic.router import routing_input_for, select_profile
from genios_engine.capture.source_registry import DELIBERATE_SOURCES, family_of
from genios_engine.capture.structural.threads import (BallInCourt, ThreadMessage,
                                                      reconstruct_thread)
from genios_engine.capture.structural.tokens import router_counts, scan
from genios_engine.capture.structured.lane import run_structured_lane
from genios_engine.capture.structured.registry import get_mapping, has_mapping
from genios_engine.capture.validate.conflict import ConflictLane, ConflictOutcome
from genios_engine.capture.semantic.evidence_binder import (BinderCounters,
                                                           no_evidence_rate_bp,
                                                           rate_blocks_prompt_release)
from genios_engine.capture.validate.spans import apply_verdicts, unverified_rate_bp
from genios_engine.contracts.conflict import Conflict
from genios_engine.capture.trace_store import TraceRepository
from genios_engine.capture.triage.triage import triage_lane
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.gated_event import GatedEvent
from genios_engine.contracts.parked import ParkedEvent
from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.contracts.source_event import SourceEvent, SyncMode
from genios_engine.contracts.trace import EventTrace
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.pipeline")

#: The structured bypass's own trace stage. Distinct from `SEMANTIC_STAGE` because the two are
#: different answers to the same question and a reader has to be able to tell "no model was
#: needed" from "the model was called and this is what it said" — `run_semantic_lane` already
#: writes a short_circuit under the semantic stage for the same event, and two lines under one
#: name would read as one lane contradicting itself.
STRUCTURED_STAGE = "s2_structured_lane"


# ----------------------------------------------------------------------------------
# Step 1 — landing (dedup). Kept standalone so it is independently testable.
# ----------------------------------------------------------------------------------
@dataclass
class LandingResult:
    event: SourceEvent
    trace: EventTrace
    landed: bool


def land_raw_object(raw: RawObject, *, org_id: str, connection_id: str,
                    repo: SourceEventRepository,
                    sync_mode: SyncMode = SyncMode.incremental,
                    mailbox_owner: str | None = None,
                    trace: EventTrace | None = None) -> LandingResult:
    """Normalize + dedup check ONLY. Writing is deferred to after the gate so the
    ledger records the decision (and content is stored kept-only). `landed` here
    means "new" (not already seen), not "written"."""
    event = to_source_event(raw, org_id=org_id, connection_id=connection_id,
                            sync_mode=sync_mode, mailbox_owner=mailbox_owner)
    trace = trace or EventTrace(org_id=org_id, event_id=event.event_id,
                                dedup_key=event.dedup_key, source=event.source)
    if repo.exists(org_id, event.dedup_key):
        trace.record("landing", "drop", reason_code="duplicate", dedup_key=event.dedup_key)
        return LandingResult(event=event, trace=trace, landed=False)
    trace.record("landing", "pass", object_type=event.object_type)
    return LandingResult(event=event, trace=trace, landed=True)


# ----------------------------------------------------------------------------------
# Full L1 capture: raw → land → preprocess → gate → triage → gated_event, one trace.
# ----------------------------------------------------------------------------------
@dataclass
class CaptureResult:
    event: SourceEvent
    trace: EventTrace
    outcome: str                    # emitted | duplicate | dropped | park
    gated: GatedEvent | None
    #: S2's answer for this event, when a `SemanticLane` was supplied and the event took the
    #: unstructured route. `None` covers three different states on purpose — no lane wired, the
    #: structured bypass (which must cost zero model calls), and an extraction that failed — and
    #: the last of those is told apart by `extraction_parked` carrying the reason.
    extraction: ExtractionResult | None = None
    #: Park-never-drop, at the pipeline seam. A failed extraction does NOT fail the capture: the
    #: event still emits with its deterministic hints, and this row travels so a drain can retry a
    #: transport failure or a human can read a schema refusal. A pipeline that swallowed it would
    #: report a healthy sweep over messages nobody ever read.
    extraction_parked: ParkedEvent | None = None
    #: ALG-12's answer for the run SO FAR, when a `ConflictLane` was supplied. A conflict lives
    #: BETWEEN two events — the $74K signed attachment against the $84K email body are two
    #: separate source events — so this is the detection over every claim the lane has seen,
    #: not a property of this event alone. `None` means no lane was wired.
    conflicts: ConflictOutcome | None = None
    #: S4 (L1.6.1, ALG-15) — every signal kind the predicate table fired for this event, capped
    #: and precedence-ordered. `None` means there was no extraction to qualify (no lane wired, or
    #: the extraction parked); an EMPTY outcome means the detector ran and this event contains
    #: nothing a business should act on, which is a different fact and is what `no_signal_rate`
    #: counts.
    detection: DetectionOutcome | None = None
    #: S4 (L1.6.3, ALG-16) — the primary kind plus the secondaries, from the constant precedence
    #: order. `None` whenever `detection` is None or fired nothing: a signal-less event does not
    #: get a manufactured type.
    qualification: SignalClassification | None = None
    #: The WHOLE S4 answer — relevance (L1.6.5), domain tags (L1.6.6) and source authority
    #: (L1.6.4) alongside the two fields above, which are kept as their own attributes because
    #: they were on this object before the stage was assembled. `None` only for an event that
    #: never reached S4 (a duplicate, a gate drop, a park); an emitted event always carries one,
    #: because the stage does not need wiring to run.
    esqe: "EsqeOutcome | None" = None
    #: WHERE this event's extraction is filed — `l1_extraction_results.processing_key` for the
    #: semantic lane, `struct:<event_id>` for the structured one (the form `context/runner.py`
    #: and `context/pipeline.py` already file structured extractions under). `None` when no
    #: extraction ran.
    #:
    #: Carried because `QualifiedEnterpriseSignal` embeds the extraction while
    #: `qualified_signals.extraction_ref` POINTS at it — the extraction is the most expensive
    #: artifact in the database and it is content-addressed, so it must live exactly once. Only
    #: this function knows the key: `ExtractionResult` does not carry it (the key is a digest
    #: over the org, the content and the prompt, computed in `capture/semantic/cache.py`), so a
    #: consumer holding only the result cannot recompute it and would have to store a copy.
    extraction_ref: str | None = None
    #: The PII-masked prepared text this event produced, or None for a structured event and for
    #: every terminal outcome that never reached preprocessing. Carried so a SWEEP-level pass can
    #: locate a claim's receipt: `Money` and `ResolvedDate` carry no evidence list of their own
    #: (their receipt is the `as_written` characters), so a consumer that has only the extraction
    #: can either drop every amount for want of a span or fabricate one. Handing it the text the
    #: offsets are measured against is what makes the third answer — a REAL span — available.
    prepared: PreparedContent | None = None


_FREE_MAIL = ("gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
              "yahoo.com", "yahoo.co.in", "icloud.com", "proton.me")

# Raw-payload retention (days). L2 drains EMITTED events quickly; a PARKED event waits in the
# human-review queue for potentially weeks and must keep its body long enough to be /recover-ed —
# else recovery after the default 30 days re-emits an EMPTY event (the black hole this guards against).
_EMITTED_PAYLOAD_TTL_DAYS = 30
_PARKED_PAYLOAD_TTL_DAYS = 365
#: How long a JUDGED drop stays recoverable. A deterministic drop (a provider SPAM label, a
#: Gmail PROMOTIONS category) is a fact and needs no second look. An LLM saying "this looks like
#: junk" is a JUDGMENT, and judgments improve — the gate that deleted 109 of this org's emails is
#: not the gate we will be running next month. Keeping the body long enough to re-adjudicate is
#: what makes "we improved the filter" a statement anyone can act on rather than an assertion
#: about mail that no longer exists.
_JUDGED_DROP_PAYLOAD_TTL_DAYS = 90

#: Reason codes whose drop was a model's opinion rather than a provider's fact.
_JUDGED_DROP_CODES = frozenset({"llm_junk", "low_relevance"})


def _linkage_hints(event: SourceEvent) -> list[dict]:
    """S3 — cheap deterministic entity hints for L2 (hints only; L2 decides identity).
    Company domain from the sender, and thread linkage from the parent object."""
    hints: list[dict] = []
    email = (event.actor.email or "").lower()
    if "@" in email:
        domain = email.split("@")[-1]
        if domain and domain not in _FREE_MAIL:
            hints.append({"type": "company_domain", "value": domain, "from": "sender"})
    if event.parent_object_id:
        hints.append({"type": "thread", "value": event.parent_object_id})
    return hints


# ----------------------------------------------------------------------------------
# Step 2 — S2, the semantic lane. Its own unit, injected as ONE parameter.
#
# Eleven modules under `capture/semantic/` were built, tested and never reached: no call site in
# `genios_engine/` named `extractor.extract`, so the Semantic Extraction Engine was a library with
# no consumer. This is the seam that consumes it, and it is a separate function rather than forty
# more lines inside `capture_event` for the reason the review stated outright — that function is
# already 155 lines and 17 parameters, and the cure for a long function is not a longer one.
#
# THREE things must stay true, all three asserted in tests/capture/test_semantic_lane.py:
#   * a STRUCTURED event makes ZERO model calls. `capture/gate/gate.py`'s short-circuit is the
#     whole point of the structured bypass, and a lane that ignored it would bill a model for
#     every CRM row and every calendar entry;
#   * an event with no derivable DIRECTION makes zero model calls. Doc 04 is explicit that a
#     missing envelope makes an outbound offer read as an inbound request — "a bug that already
#     occurred and was fixed once" — so a guess here is worse than an abstention;
#   * no lane at all changes nothing, which is what lets this land ahead of any activated tenant.
# ----------------------------------------------------------------------------------

#: Sources whose traffic is the company talking to itself: written canon, a human's note, an
#: agent's outcome. These have no counterparty to be inbound FROM, so the envelope's direction is
#: `internal` by construction and needs no mailbox identity to derive.
_INTERNAL_FAMILIES = frozenset({"internal", "human_input", "ai_generated"})


class T3Allowance:
    """One org's daily T3 budget, held across a sweep and safe to share between capture threads.

    `model_router.route()` is a pure function that takes a budget and returns the next one — the
    right shape for a unit and the wrong shape for `sync_runner`'s thread pool: ten workers each
    reading the same immutable budget would each be told they may spend it, and the daily
    frontier-model allowance would be exceeded by exactly the worker count. Serialising the
    read-decide-write is the whole job, and it is cheap: the decision is integer arithmetic over a
    fixed table, not I/O.

    Default `NO_T3_BUDGET`. An org with no configured allowance gets T2 and the demotion counter
    climbs where an admin can see it; the opposite default is discovered on an invoice.
    """

    def __init__(self, budget: T3Budget = NO_T3_BUDGET) -> None:
        self._budget = budget
        self._lock = threading.Lock()

    @property
    def budget(self) -> T3Budget:
        with self._lock:
            return self._budget

    def apply(self, request: TierRequest,
              cost: "_CostCeiling | None" = None) -> "TierOutcome":
        """Decide this extraction's tier against BOTH ceilings, and spend it — atomically.

        The money governor is consulted INSIDE the lock, before the allowance is charged, for a
        reason that is easy to get wrong: `record` must see the tier that will actually run. A
        T3 talked down to T2 by the budget after the allowance had already been charged would
        spend a frontier slot on a call that never went to a frontier model, and the demotion
        counter — the signal doc 04 asks be monitored — would show a grant instead.
        """
        with self._lock:
            decision = decide_tier(request, self._budget)
            outcome = TierOutcome(decision=decision, admitted=True, reason="")
            if cost is not None:
                outcome = cost.adjust(decision)
            if outcome.admitted:
                self._budget = record(self._budget, outcome.decision)
            return outcome


@dataclass(frozen=True)
class TierOutcome:
    """The tier this extraction will run at, and whether it may run at all.

    Two ceilings answer one question, so they produce one answer. `admitted=False` is a REFUSAL
    with a reason a customer's progress row can read ("paused for today, resumes tomorrow"), not
    an exception and not a silent None — the budget stopping work is a fact about the day, and
    the whole lesson of commit `7e17a6d` was that it has to be stated rather than crashed on.
    """

    decision: TierDecision
    admitted: bool
    reason: str


@dataclass(frozen=True)
class _CostCeiling:
    """One event's view of L1.4.8's money governor, in the shape `T3Allowance.apply` can use.

    Built per event because the price of a call depends on its CONTENT, and held as a value
    rather than a closure so the thing crossing the lock is typed and inspectable.
    """

    governor: Any                                   # capture.semantic.batch.CostGovernor
    event_id: str
    profile_id: str
    content: str
    envelope_chars: int

    def adjust(self, decision: TierDecision) -> TierOutcome:
        verdict = self.governor.decide(SpendRequest(
            event_id=self.event_id, profile_id=self.profile_id, content=self.content,
            requested_tier=decision.tier, envelope_chars=self.envelope_chars))
        if not verdict.admitted:
            return TierOutcome(decision=decision, admitted=False, reason=verdict.reason)
        if verdict.tier == decision.tier:
            return TierOutcome(decision=decision, admitted=True, reason="")
        # Back through the router, so a money demotion is counted by the same flag an allowance
        # demotion is. A private "we ran it cheaper" boolean here would be the silent downgrade
        # `tier_demoted` exists to make impossible.
        return TierOutcome(decision=demote_for_cost(decision, verdict.tier),
                           admitted=True, reason=verdict.reason)


@dataclass(frozen=True)
class SemanticLane:
    """Everything S2 needs, as ONE parameter on `capture_event`.

    A bundle rather than six more keyword arguments: the function below it is already the widest
    signature in the package, and the six values are only ever supplied together — an LLM client
    without a clock, or a cache without a client, is not a configuration anybody wants.

    `llm` is INJECTED rather than constructed, so a test passes a `FakeLLM` and the structured-lane
    gate can assert `call_count == 0` against an object that would raise if it were called at all.
    `eval_time` is a parameter for the reason this layer keeps repeating: a March message's "next
    week" must resolve to March on every replay, and a clock read inside the pipeline makes a
    replay a different extraction.
    """

    llm: Any
    eval_time: datetime
    #: An `ExtractionCacheStore`, or None for a caller that has no cache yet — that runs and pays
    #: for every call, which is slow but not wrong.
    cache: Any | None = None
    #: An `OpenLaneStore`, or None. L1.4.5's discovery lane: the names the model used that the
    #: closed key vocabulary has no field for. `None` still CLOSES the three untyped lanes — the
    #: invented name never reaches `l1_extraction_results` either way — it only means the refused
    #: names are not kept for review, so the vocabulary cannot grow from evidence.
    open_lane: Any | None = None
    budget: "T3Allowance" = field(default_factory=lambda: T3Allowance())
    #: L1.4.8's cost governor — one org's daily MONEY ceiling — or None when no cap is
    #: configured. `budget` above counts frontier extractions; this one counts cents, and it is
    #: the same ceiling `api/routes._llm_over_daily_cap` enforces before a sync starts rather
    #: than a second one nobody reconciles. None means the deployed pre-flight check is the only
    #: guard, which is exactly the behaviour every tenant had before this field existed.
    governor: Any | None = None
    #: The ORG's timezone. ALG-09 resolves relative dates in it and stores UTC.
    timezone: str = "UTC"
    #: The CONNECTION's declared locale, or None when it declares none. Never guessed — the
    #: day-month ambiguity is not a coin worth flipping.
    locale: str | None = None
    #: D6 · L1.6.5's PAGE seam (`esqe.relevance.RelevancePage`), or None. It rides on this
    #: bundle rather than on a seventh keyword because the lane is already the object every
    #: capture door — the sweep, the webhook, the manual intake — hands to `capture_event`, and
    #: a parameter added at six call sites is five places to forget. One page batcher per sweep:
    #: the ambiguous remainder of a page is bought in whole prompts and read per event, which is
    #: what makes the plan's "under 5% of events reach the model" a measured number instead of a
    #: per-event call rate nobody counted.
    relevance_page: Any | None = None


@dataclass(frozen=True)
class StructuredLane:
    """Everything L1.3.9-U5 needs that the pipeline cannot derive, as ONE parameter.

    It exists because the structured bypass USED to read these four values off `SemanticLane`,
    which coupled the typed-record route to the model route: a tenant with no LLM wiring — the
    state every unactivated tenant is in — got no structured signals either, and an activation
    row gated a path that never calls a model. A HubSpot deal is a typed record; the whole point
    of the bypass is that it needs no model, no extraction call and no activation.

    Unlike `SemanticLane`, `None` for this bundle does NOT turn the lane off. The lane is pure —
    no client, no clock, no I/O it was not handed — so the only thing a missing bundle costs is
    the two values that genuinely cannot be defaulted from the event: the ORG's timezone (UTC
    otherwise, the same fallback `platform/wiring._org_timezone` already makes) and the discovery
    store (absent otherwise, which still CLOSES every refused name — it only means they are not
    kept for review).
    """

    #: The instant ALG-09 resolves a typed date against. `None` = per event, and `capture_event`
    #: fills it in from the event's own `occurred_at` — a stored moment, never a clock read, so a
    #: replay of a March object is the same extraction it was in March.
    eval_time: datetime | None = None
    #: The ORG's IANA zone. Decides which calendar day a typed instant falls on.
    timezone: str = "UTC"
    #: The CONNECTION's declared locale, or None. Never guessed — the day-month ambiguity is not
    #: a coin worth flipping.
    locale: str | None = None
    #: An `OpenLaneStore`, or None. L1.4.5's discovery lane for the names a mapping declares that
    #: the graph cannot be queried by.
    open_lane: Any | None = None


def structured_context(structured: "StructuredLane | None", semantic: "SemanticLane | None",
                       event: SourceEvent) -> "StructuredLane":
    """What the typed-record lane runs with, in precedence order: the caller's own bundle, else
    the semantic lane's values when a caller wired one (one org's zone, one discovery store — two
    bundles disagreeing about the zone would resolve one object's close date two ways), else the
    defaults. The frozen instant falls back to this event's world time in every case.
    """
    base = structured
    if base is None and semantic is not None:
        base = StructuredLane(eval_time=semantic.eval_time, timezone=semantic.timezone,
                              locale=semantic.locale, open_lane=semantic.open_lane)
    if base is None:
        base = StructuredLane()
    if base.eval_time is None:
        base = _dc_replace(base, eval_time=event.occurred_at)
    return base


@dataclass(frozen=True)
class SemanticVerdict:
    """What S2 did, in a form the pipeline can file and a trace can record.

    `skipped` and `outcome` are mutually exclusive on purpose: an extraction that ran and parked
    has an outcome carrying a park row, while an extraction that was never attempted has a skip
    reason and cost nothing. Collapsing the two would make "we chose not to read this" and "we
    tried and failed" the same fact, and only one of them is worth retrying.
    """

    outcome: Any | None = None                  # extractor.ExtractionOutcome
    skipped: str | None = None
    tier: str | None = None
    profile_id: str | None = None
    #: The router's demotion flag, carried out of the lane so the trace can state it. A budget
    #: that demoted a call and left no record of it is the silent downgrade doc 04's FAILURE
    #: MODES section requires be monitored — and the only place an operator can see the pattern
    #: is a stored row saying "this ran at T2 and was owed T3".
    tier_demoted: bool = False
    demotion_reason: str | None = None
    #: L1.5.1-U2's tally for this event — how many distinct receipts resolved and how many did
    #: not. Carried out of the lane so `_record_semantic` can put the rate on the trace: a
    #: prompt edit that breaks citation behaviour raises nothing and fails no test, and this is
    #: the number that turns it into an observable step change on a date. `None` when nothing was
    #: extracted to grade.
    spans: Any | None = None

    @property
    def result(self) -> ExtractionResult | None:
        return getattr(self.outcome, "result", None) if self.outcome is not None else None

    @property
    def parked(self) -> ParkedEvent | None:
        return getattr(self.outcome, "parked", None) if self.outcome is not None else None


def _envelope_direction(event: SourceEvent, mailbox_owner: str | None) -> str | None:
    """inbound | outbound | internal, or None when no rule can name it.

    None is a REFUSAL, not a gap for somebody downstream to fill. `capture/structural/threads.py`
    makes the same call for the same reason: with no identity for "us" every message looks
    inbound, which is how a product's own onboarding mail got modelled as a prospect asking for a
    demo. The extractor's `EventEnvelope` refuses an unknown direction at construction, so the only
    honest options here are a derived answer or no model call at all.

    A DELIBERATE SOURCE IS INTERNAL BY CONSTRUCTION, and reading `internal_kind` alone was not
    enough. `internal_kind` is set by a TAG — an upload tagged `policy`, `sop`, `pricing` — so an
    UNTAGGED upload (a signed MSA, an audit checklist, a vendor quote a founder drags into the
    dashboard) arrived with no kind, no mailbox owner and no sender, fell to the `not owner`
    branch, and was refused a direction. `run_semantic_lane` then skipped it as
    `direction_unknown`, S4 returned before detection because `extraction is None`, and the most
    deliberate source a tenant has produced no signal at all — visible only as one short-circuit
    row in `event_trace`. `DELIBERATE_SOURCES` is the registry's own answer to "who handed us
    this" (`upload`, `human`, `agent`, `internal`) and the gate already whitelists on it as W-05;
    the same set is used here rather than a second list, because a file the tenant put in front of
    us has no counterparty to be inbound FROM whatever tag it carries.
    """
    if (event.internal_kind or family_of(event.source) in _INTERNAL_FAMILIES
            or event.source in DELIBERATE_SOURCES):
        return "internal"
    owner = (mailbox_owner or "").strip().lower()
    sender = (event.actor.email or "").strip().lower()
    if not owner or not sender:
        return None
    return "outbound" if sender == owner else "inbound"


def _thread_place(raw: Mapping[str, Any]) -> tuple[int, int]:
    """(position, depth) from whatever the connector stated, or (1, 1) when it stated nothing.

    Clamped rather than trusted: `EventEnvelope` refuses a position past its depth, and a connector
    reporting message 4 of 3 must not be able to abort a capture. A single message with no thread
    metadata is genuinely the first of one, which is what the default says.
    """
    def _int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    depth = max(1, _int(raw.get("thread_depth")))
    position = _int(raw.get("thread_position")) or 1
    return min(max(1, position), depth), depth


#: Object types whose `parent_object_id` IS the thread root. An attachment's parent is its
#: MESSAGE (`connectors/composio.py:562` writes the message id there, `:515` writes the thread
#: id), and `claim_group.thread_group_key` refuses that case in as many words: answering
#: `thread:<message id>` mints a private thread for a file and quietly orphans it. Matched on
#: the suffix so a connector's `chat_message` or `sms_message` is covered without a new row,
#: while `email_attachment` and `calendar_event` are not.
_THREAD_PARENT_SUFFIX = "message"


def _thread_context(event: SourceEvent, raw: Mapping[str, Any],
                    mailbox_owner: str | None) -> ThreadContext:
    """The conversation S4 qualifies this event inside — derived, never guessed.

    Everything here is read off the envelope the connector already stated plus the identity of
    "us", which is the same pair `run_semantic_lane` builds its `EventEnvelope` from. It is
    derived at this seam rather than taken as a parameter because no capture caller supplies
    one: `sync_runner`, `push_ingest` and `api/routes` all reach `capture_event` without an
    `EsqeStage` at all, so a thread context that had to be injected would be a seam with no
    producer — the defect this whole round is closing.

    `ball_in_court` is ALG-03's answer, from ALG-03 — `structural/threads.reconstruct_thread`,
    CALLED, over the one message this seam holds. It used to be a re-implementation of that
    rule beside a comment promising it "follows it exactly", which is a promise no test can
    hold: `reconstruct_thread` had no caller anywhere in the engine, so the module that owns
    the rule could be re-tuned with every unit test green while this copy kept the old answer.
    A one-message thread is a legal thread (`assemble_chain` builds a one-link chain from it),
    and at capture time this event genuinely IS the newest message of its thread, which is the
    condition ALG-03's derivation is stated over.

    `internal` is the one direction ALG-03 has no word for — it is a fact about the SOURCE
    (an agent lane, a human note), not about who sent a message to whom — so it is not put to
    ALG-03 at all and keeps the `unknown` this seam has always answered for it. An underivable
    direction yields `unknown` for the same reason: answering "whose turn is it" from nothing is
    how a closed conversation keeps showing up as owed.
    """
    position, depth = _thread_place(raw)
    direction = _envelope_direction(event, mailbox_owner)
    ball = BallInCourt.unknown
    if direction in ("inbound", "outbound"):
        owner = (mailbox_owner or "").strip()
        ball = reconstruct_thread(
            [ThreadMessage(message_id=event.event_id, occurred_at=event.occurred_at,
                           thread_id=(event.parent_object_id or None),
                           actor_email=event.actor.email,
                           subject=str(raw.get("subject") or "") or None)],
            org_identities=(owner,) if owner else ()).ball_in_court
    parent = (event.parent_object_id or "").strip()
    thread_key = (f"thread:{parent}"
                  if parent and str(event.object_type or "").endswith(_THREAD_PARENT_SUFFIX)
                  else None)
    return ThreadContext(thread_key=thread_key, direction=direction, turn_index=position - 1,
                         thread_depth=depth, ball_in_court=ball.value)


def run_semantic_lane(event: SourceEvent, prepared: PreparedContent | None,
                      raw: RawObject, *, lane: SemanticLane, is_structured: bool,
                      mailbox_owner: str | None) -> SemanticVerdict:
    """L1.4 for ONE event: profile -> tier -> envelope -> the one model call, or a stated skip.

    Every decision the model is NOT allowed to make is made before it is called: L1.4.1 picks the
    profile from the content's shape, L1.4.10 picks the tier from S1's deterministic counts, and
    L1.4.9's cache decides whether the call happens at all. The model is handed a prompt and asked
    for JSON; it never picks its own profile, its own tier or its own budget.
    """
    if is_structured:
        return SemanticVerdict(skipped="structured_bypass")
    if prepared is None or not prepared.clean_text.strip():
        return SemanticVerdict(skipped="no_prepared_text")
    direction = _envelope_direction(event, mailbox_owner)
    if direction is None:
        return SemanticVerdict(skipped="direction_unknown")

    body = raw.raw or {}
    choice = select_profile(routing_input_for(
        event, mime=str(body.get("mime") or ""), filename=str(body.get("filename") or "")))
    position, depth = _thread_place(body)
    # The envelope is built BEFORE the tier is decided because its length is billable: it is the
    # one term L1.4.8's planner cannot measure for itself, and a governor charged the 512-char
    # default for a real 900-character envelope is a governor that authorises spend nobody
    # approved — the same under-count `fixed_prompt_tokens` was written to remove.
    envelope = EventEnvelope(
        direction=direction, sender=event.actor.email or "",
        recipients=tuple(getattr(event, "recipients", ()) or ()),
        thread_position=position, thread_depth=depth,
        subject=str(body.get("subject") or ""))
    ceiling = None if lane.governor is None else _CostCeiling(
        governor=lane.governor, event_id=event.event_id, profile_id=choice.profile_id,
        content=prepared.clean_text, envelope_chars=envelope_chars(envelope))
    outcome = lane.budget.apply(TierRequest(
        profile_id=choice.profile_id,
        content_length=len(prepared.clean_text),
        counts=router_counts(scan(prepared.clean_text)),
        attachment_present=bool(body.get("document") or body.get("attachments")),
        thread_depth=depth,
        internal_kind=event.internal_kind), ceiling)
    if not outcome.admitted:
        # The day's budget is spent. Refusing here is what makes the ceiling real: it costs the
        # provider nothing, it reaches no model, and the reason travels to the trace so the run
        # reads as "paused for today" instead of as an extraction that quietly never happened.
        return SemanticVerdict(skipped=outcome.reason or "budget_exhausted",
                               tier=outcome.decision.tier, profile_id=choice.profile_id)
    decision = outcome.decision
    # L1.3.4-U5 · the document's own coordinates, read off what the connector attached. Both
    # halves travel to the extractor (which attaches them to every receipt at the alignment seam)
    # and to ALG-08 (which must be able to recompute a page when it RELOCATES a quote). One
    # object, read once, handed to both — a second read is a second answer.
    document = body.get("document") if isinstance(body.get("document"), Mapping) else None
    page_map = page_map_from_record(document)
    section = _section_of(body)
    request = ExtractionRequest(
        org_id=event.org_id, event_id=event.event_id, source=event.source,
        profile_id=choice.profile_id, tier=decision.tier, prepared=prepared, envelope=envelope,
        eval_time=lane.eval_time, timezone=lane.timezone, locale=lane.locale,
        page_map=page_map, section=section)
    outcome = extract(request, llm=lane.llm, store=lane.cache, open_lane=lane.open_lane)
    outcome, counters = _grade_spans(outcome, prepared.clean_text, locale=lane.locale,
                                     prepared=prepared, page_map=page_map, section=section)
    return SemanticVerdict(outcome=outcome, spans=counters,
                           tier=decision.tier, profile_id=choice.profile_id,
                           tier_demoted=decision.tier_demoted,
                           demotion_reason=decision.demotion_reason)


def _section_of(body: Mapping[str, Any]) -> str | None:
    """The heading this event's text sits under, as the door stated it. Never inferred.

    An upload chunk carries its chunker-detected `section_title`; a message carries nothing, and
    nothing is what it gets. Inferring a section from the first line of an email would put a
    subject line into a field that is supposed to mean "the heading in the document", and a
    citation reading *Termination · "we are cancelling"* about an email is a receipt that lies
    about where it came from.
    """
    document = body.get("document")
    title = document.get("section_title") if isinstance(document, Mapping) else None
    return title if isinstance(title, str) and title.strip() else None


def _grade_spans(outcome: Any, source_text: str, *, locale: str | None,
                 prepared: Any = None, page_map=None, section: str | None = None):
    """**L1.5.1 (ALG-08) ON THE PRODUCTION PATH** — the step that stamps `verified`.

    THE DEFECT THIS CLOSES. `capture/semantic/evidence_binder.py` builds every receipt with
    `verified=False` and says why in its own docstring: *"that stamp belongs to L1.5.1 alone: the
    binder runs at the extractor seam, so a span leaving here wearing a checkmark would be the
    extractor grading its own homework."* L1.5.1's whole-extraction entry point,
    `validate/spans.apply_verdicts`, was then never called by anything on a request path — built,
    tested, and reachable only from its own test file. Three measured consequences, none of which
    raises anything:

    * doc 06's group gate requires *">= 1 verified evidence span"* on 95% of published signals.
      It was **0%** — every span in `qualified_signals.evidence_refs` said `verified: false`;
    * V-5 therefore downgraded the confidence of EVERY signal for unverified evidence, so the
      one rule that exists to mark the rare unsubstantiated claim was marking all of them;
    * G10's *"unverified span rate < 5%"* was 100%, and had no production caller to measure it
      with either (`spans.unverified_rate_bp`, same file, same state).

    ON THE WAY OUT OF THE LANE, NOT ON THE WAY IN. `extract` files its result in L1.4.9's
    permanent cache before this runs, so what is stored is the extractor's own unverified output
    — which is what `apply_verdicts` asks for in as many words ("the input is left alone, because
    the unverified original is what a replay and an audit need to see") — and every reader,
    cache HIT included, is graded here. Grading is pure integer work over a string, so paying for
    it on a hit costs nothing and skipping it on a hit would make a replayed event's evidence
    differ from a freshly extracted one's.

    A park has no result to grade and passes through untouched. Never raises: a grading failure
    would cost a whole sweep to save one signal's checkmark, so it is caught and the ungraded
    extraction travels — visibly, with no counters, rather than silently.
    """
    result = getattr(outcome, "result", None)
    if result is None:
        return outcome, None
    try:
        graded, counters = apply_verdicts(result, source_text, locale=locale,
                                          prepared=prepared, page_map=page_map, section=section)
    except Exception:      # noqa: BLE001 — a grading failure costs a checkmark, never the sweep
        _log.warning("could not grade evidence spans for event=%s",
                     getattr(outcome, "event_id", "?"), exc_info=True)
        return outcome, None
    return _dc_replace(outcome, result=graded), counters


def _record_semantic(trace: EventTrace, verdict: SemanticVerdict) -> None:
    """One trace line per event that met S2 — including the ones it declined to read.

    A skip that leaves no record is indistinguishable from a lane that was never wired, and the
    whole reason this wave exists is that nobody could tell those two apart for eleven modules.
    """
    if verdict.skipped is not None:
        trace.record(SEMANTIC_STAGE, "short_circuit", reason_code=verdict.skipped)
        return
    outcome = verdict.outcome
    if outcome is None:
        return
    if outcome.parked is not None:
        trace.record(SEMANTIC_STAGE, "park", reason_code=outcome.parked.reason_code,
                     tier=verdict.tier, profile=verdict.profile_id,
                     model_calls=outcome.model_calls)
        return
    # L1.5.1-U2's rate, on the trace of the event it was measured over. `unverified_rate_bp`
    # shipped with no production caller at all, which meant the one number that makes a
    # silently-degrading extractor visible — a prompt edit that quietly stops citing — could be
    # computed by nothing but its own unit test. Read it beside `spans_total`: an extraction that
    # cited nothing reports a 0 rate and is not an extraction that cited well.
    counters = verdict.spans
    # L1.4.6-U1's rate, the binder's half of the same question, and it had the same problem
    # `unverified_rate_bp` had: `no_evidence_rate_bp` shipped with no caller because
    # `ExtractionDiagnostics` — where its numerator and denominator both live — was never read
    # by anything on the request path. The two rates fail differently and both matter: the span
    # rate says the model cited text that is not in the message, this one says it made claims it
    # cited nothing at all for. A prompt edit can hold one flat while wrecking the other.
    diagnostics = outcome.diagnostics
    # ALL SIX COUNTERS, and this rebuilt four. The two the branch added — a claim killed because
    # its receipt was somebody else's quoted sentence, and one killed because its receipt was a
    # bare timestamp or salutation — were computed by the binder and dropped here, so the two
    # newest drop reasons were invisible on every request path.
    binder = BinderCounters(claims_in=diagnostics.claims_in,
                            carried_own_evidence=diagnostics.claims_bound,
                            synthesized=diagnostics.synthesized_spans,
                            no_evidence=diagnostics.no_evidence_drops,
                            quoted_history=diagnostics.quoted_history_drops,
                            unsubstantive=diagnostics.unsubstantive_drops)
    no_evidence_bp = no_evidence_rate_bp(binder)
    trace.record(SEMANTIC_STAGE, "pass", tier=verdict.tier, profile=verdict.profile_id,
                 cache_hit=outcome.cache_hit, model_calls=outcome.model_calls,
                 input_tokens=outcome.input_tokens, output_tokens=outcome.output_tokens,
                 tier_demoted=verdict.tier_demoted,
                 demotion_reason=verdict.demotion_reason,
                 spans_total=(None if counters is None else counters.total_spans),
                 spans_resolved=(None if counters is None else counters.resolved_spans),
                 unverified_rate_bp=(None if counters is None
                                     else unverified_rate_bp(counters)),
                 claims_in=diagnostics.claims_in,
                 no_evidence_drops=diagnostics.no_evidence_drops,
                 no_evidence_rate_bp=no_evidence_bp,
                 # U1's own release bar, evaluated where the number is produced rather than
                 # left for a reader to re-derive the threshold: "a sustained rise above 5%
                 # blocks the next prompt version". One event is not a sustained rise, so this
                 # is a per-event flag an operator aggregates — never a gate that drops mail.
                 no_evidence_over_bar=rate_blocks_prompt_release(no_evidence_bp))


# ----------------------------------------------------------------------------------
# Step 3 — the coverage verdict. Also its own unit, for the same reason.
# ----------------------------------------------------------------------------------

def coverage_verdict(hints: Sequence[Any], coverage_fn) -> bool | None:
    """Whether a NEGATIVE inference about this event's domain is licensed — True, False or None.

    `None` survives as a legal value for exactly one honest case: an event with no domain hint at
    all. "We did not classify this" and "this domain is under-connected" are different states and a
    caller must be able to tell them apart; collapsing them to False would make an unclassified
    event look like an under-connected tenant.

    A `DomainHint` is a PYDANTIC MODEL, never a dict. The original read
    `isinstance(hints[0], dict)`, which was False on every call ever made, so the branch was dead
    code with a passing type signature and `coverage_ready` stayed None even for a caller that did
    pass a `coverage_fn`. Both shapes are read here so a test double built either way works.
    """
    if not hints or coverage_fn is None:
        return None
    try:
        first = hints[0]
        domain = (first.get("domain") if isinstance(first, dict)
                  else getattr(first, "domain", None))
        if not domain:
            return None
        return bool(coverage_fn(domain).get("coverage_ready"))
    except Exception:      # noqa: BLE001 — a readiness hint never fails a capture
        return None


# ----------------------------------------------------------------------------------
# S4 (L1.6) — the ESQE stage. Runs AFTER the validate lane, because every one of its four
# consumers reads something validation produced: the detector reads typed claims, the conflict
# list is one of its predicates, relevance counts those claims, and the analyzer ranks the
# artifact that carried them. Its own function rather than another limb of `capture_event`,
# which is already the widest signature in the package.
# ----------------------------------------------------------------------------------
ESQE_STAGE = "s4_esqe"

@dataclass(frozen=True)
class EsqeStage:
    """Everything S4 needs that the pipeline cannot derive, as ONE parameter.

    Same bundle discipline as `SemanticLane` and for the same reason: `capture_event` is already
    a seventeen-parameter function and five more keywords would make the wiring of this stage
    the least readable thing in the file. `None` for the whole bundle = not wired, and the
    pipeline then behaves exactly as it did before S4 existed.
    """

    #: The instant deadlines are judged against. A parameter, never a clock: `COMMITMENT_DUE` is
    #: a statement about a moment and a replay that read `now()` would re-detect last March's
    #: commitment as due today.
    #:
    #: `None` means "resolve it per event", which is what a SWEEP-level bundle must say. The
    #: sweep's org baseline is one value for a whole run, but the frozen instant is not: an
    #: unactivated tenant judges each event against its own stored `occurred_at`. `capture_event`
    #: fills it in — from the semantic lane's instant when there is one, from the event's world
    #: time otherwise — so the bundle can carry what is per-ORG without pinning what is
    #: per-EVENT, and a caller that already knows the instant still states it here.
    eval_time: datetime | None = None
    #: LLM-5's client, INJECTED. `None` means the rules-only path — which is not a degraded mode:
    #: the plan bounds the model to under 5% of events, so a caller with no client still gets a
    #: decision on 95%+ of its traffic and fails the remainder open rather than filtered.
    relevance_llm: Any | None = None
    #: D6 · the page batcher this event belongs to, when the caller has one. Present = the
    #: ambiguous remainder of this page was already judged in whole prompts, and this event
    #: READS the verdict. Absent = the per-event path, which still decides correctly and still
    #: counts its own call; what it cannot do is spend once for a page.
    relevance_page: Any | None = None
    #: The graph's answer for this sender's role, when the caller has one. Never guessed here.
    actor_role: str | None = None
    #: The org's own email domains, for the analyzer's same-domain rung.
    org_domains: tuple[str, ...] = ()
    #: Whether the artifact is an executed (signed) document. The document layer's answer.
    executed: bool = False
    #: L1.6.7-U2's answer for this tenant — what a typical contract costs here, and which
    #: counterparties matter. `None` is not "do not score": it falls back to
    #: `OrgBaseline.cold_start`, which switches ALG-17's money term onto the absolute ladder
    #: and flags `baseline_estimated`. Doc 06 is explicit that a missing baseline must never
    #: block scoring, and a day-one tenant whose signals all scored alike is the exact defect
    #: L1.6.7 exists to remove.
    org_baseline: OrgBaseline | None = None
    #: ALG-17's five weights, INJECTED like the baseline beside them. `score_importance` has
    #: taken a `weights=` argument since it was written and NOTHING EVER PASSED ONE, so every
    #: tenant scored on doc 06's verbatim defaults whatever their business valued. A law firm
    #: weights DEADLINE far above MONEY — a limitation period is not negotiable and a fee note
    #: is; a payments company weights the other way. Neither is a defect in the shipped table;
    #: they are businesses it was calibrated without.
    #:
    #: THE TOTAL CHECK IS NOT RELAXED. `ImportanceWeights` refuses a set that does not sum to
    #: 10000, because `/ 10000` in the formula is only a weighted MEAN while it does — and that
    #: is a gate on arithmetic, not a limit on expressiveness. It stays.
    #:
    #: `None` means the shipped weights, which is every tenant that has not said otherwise.
    importance_weights: Any | None = None


@dataclass(frozen=True)
class EsqeOutcome:
    """What S4 concluded about one event.

    `detection` and `classification` are `None` for two different reasons and the difference is
    the point: no extraction to read (a structured event with no mapping, a parked extraction),
    or an extraction that fired no predicate. Neither is an error, and neither is "we did not
    run S4" — that state is the outcome being `None` on the `CaptureResult` altogether.
    """

    relevance: RelevanceDecision
    domains: DomainTagging
    attribution: SourceAttribution
    detection: DetectionOutcome | None = None
    classification: SignalClassification | None = None
    #: L1.6.2's canonical records — one per kept detected signal, in the detector's precedence
    #: order. Empty whenever `detection` is None or fired nothing; this is the shape L1.6.7
    #: scores, so it is the field the next wave consumes rather than `detection` itself.
    normalized: tuple[NormalizedSignal, ...] = ()
    #: The conversation this event sits in — whose turn it is, which thread, how deep. Computed
    #: for EVERY event, relevant or not, on the same terms as `domains` and `attribution`: it is
    #: envelope provenance and it stays true about a message we decided not to act on.
    thread: ThreadContext | None = None
    #: L1.6.7 (ALG-17) — one `ImportanceScore` per normalized signal, INDEX-ALIGNED with
    #: `normalized`. A parallel tuple rather than a field on `NormalizedSignal` because
    #: L1.6.2's record is the canonical SHAPE and a score is a judgement about it; and aligned
    #: rather than keyed by type because one event can produce two signals of the same kind
    #: with different amounts, which a dict would silently merge into one score.
    #:
    #: Empty exactly when `normalized` is empty. Never `None`: "we ran the scorer and there was
    #: nothing to score" is the same fact as "there were no signals", and a second nullable
    #: field would invite a consumer to tell them apart when they cannot be.
    importance: tuple[ImportanceScore, ...] = ()

    @property
    def qualified(self) -> bool:
        """Did anything survive S4 — a relevant event that fired at least one predicate."""
        return self.relevance.relevant and self.classification is not None

    @property
    def primary_importance(self) -> ImportanceScore | None:
        """The score for the signal ALG-16 named primary — the number the CARD is ranked by.

        Found by walking the aligned pair rather than assuming index 0: `normalized` is in the
        DETECTOR's precedence order, and while that order and ALG-16's agree today, a build
        that changed one and not the other would silently rank every card by the wrong signal's
        importance and no test of either unit alone would see it.
        """
        if self.classification is None:
            return None
        for signal, score in zip(self.normalized, self.importance):
            if signal.signal_type is self.classification.primary:
                return score
        return None


def _esqe_headers(raw: Mapping[str, Any]) -> Mapping[str, str]:
    """The message headers, whichever of the two shapes a connector normalised them into.

    Read defensively rather than assumed: the bulk-mail rule is the one relevance rule that can
    say NOT RELEVANT on header evidence alone, and a header dict this function silently read as
    empty would turn that rule off for a whole source without any test going red.
    """
    headers = raw.get("headers")
    if isinstance(headers, Mapping):
        return {str(k): str(v) for k, v in headers.items() if v is not None}
    if isinstance(headers, Sequence) and not isinstance(headers, (str, bytes)):
        out: dict[str, str] = {}
        for item in headers:
            if isinstance(item, Mapping):
                name, value = item.get("name"), item.get("value")
                if name is not None:
                    out[str(name)] = str(value or "")
        return out
    return {}


def _typed_claim_count(extraction: ExtractionResult | None) -> int:
    """How many TYPED claims this event produced — the second half of the service-account rule.

    A billing robot that emitted a real amount with a real due date is a machine saying the
    company owes money, and the rule must not drop it on the sender pattern alone.
    """
    if extraction is None:
        return 0
    return (len(extraction.commitments) + len(extraction.decision_states)
            + len(extraction.dependencies) + len(extraction.amounts)
            + len(extraction.dates_mentioned))


def _normalize_detected(signals: Sequence[Any], extraction: ExtractionResult,
                        event: SourceEvent,
                        attribution: SourceAttribution,
                        thread: ThreadContext) -> tuple[NormalizedSignal, ...]:
    """L1.6.2 over the detected signals — the canonical shape L1.6.7 will score.

    `attribution` is PASSED rather than left to the normalizer to recompute. L1.6.4's answer is a
    property of the event, this stage already computed it once with the bundle's own `executed`,
    `actor_role` and `org_domains`, and a second call without those would attribute the same
    message differently from the trace row this pipeline just wrote about it.
    """
    return normalize_signals(signals, event=event, extraction=extraction,
                             attribution=attribution, thread=thread)


def _conflicts_for(event: SourceEvent, outcome: ConflictOutcome | None) -> tuple[Conflict, ...]:
    """This event's own contract-level conflicts, unwrapped from ALG-12's detection rows.

    Two unwrappings, and both are corrections rather than plumbing. The lane yields
    `DetectedConflict` — a `Conflict` plus the event ids the competing claims came from — and the
    detector's `INFORMATION_CONFLICT` predicate reads `Conflict.field`, so handing it the wrapper
    is an `AttributeError` on the second event of every run with a conflict lane wired.

    The filter is the second. A conflict lives BETWEEN events and the lane's detection covers the
    whole run so far, so an unfiltered list would raise `INFORMATION_CONFLICT` on every
    subsequent event in the sync for a disagreement between two OTHER messages — the top of
    ALG-16's precedence, on an event that contradicts nothing.
    """
    if outcome is None:
        return ()
    return tuple(row.conflict for row in outcome.detection.conflicts
                 if event.event_id in row.event_ids)


def run_esqe_stage(event: SourceEvent, prepared: PreparedContent | None, raw: Mapping[str, Any],
                   *, stage: EsqeStage, extraction: ExtractionResult | None,
                   conflicts: ConflictOutcome | None, sender_known: bool, is_structured: bool,
                   coverage_fn=None, mailbox_owner: str | None = None) -> EsqeOutcome:
    """S4 for one event: is it ours, which domains, who said it, and what kind of thing is it.

    Order is the design. Relevance runs FIRST and gates the detector, because the detector is
    the expensive-to-be-wrong step: a newsletter carrying a date and an amount qualifies as a
    `FINANCIAL_OBLIGATION` on the predicate table alone, and running detection before relevance
    is exactly how 115 cards were produced of which four were worth reading. Domain tagging and
    source attribution run for EVERY event, relevant or not, because both are provenance — the
    facts stay true about a message we decided not to act on, and an operator asking "why was
    this not relevant?" needs them.
    """
    text = prepared.clean_text if prepared else None
    # A sweep-level bundle carries what is true for the whole ORG and leaves the per-EVENT
    # instant open; `capture_event` fills it, and this is the belt for a direct caller that did
    # not. Resolved ONCE, here, and passed by value: two reads of `stage.eval_time` inside one
    # stage is how a detector and a scorer end up judging one event against two moments.
    eval_time = stage.eval_time if stage.eval_time is not None else event.occurred_at
    candidate = RelevanceCandidate(
        event_id=event.event_id,
        # The page pass knew this object by the CONNECTOR's id — `event_id` is minted at
        # landing, after the page was primed — so the stable key travels with the candidate.
        page_key=getattr(event, "source_object_id", None) or None,
        sender=getattr(event.actor, "email", "") or "",
        sender_known=sender_known,
        internal_kind=event.internal_kind,
        is_structured=is_structured,
        headers=_esqe_headers(raw),
        typed_claim_count=_typed_claim_count(extraction),
        subject=str(raw.get("subject") or ""),
        snippet=text or "",
    )
    # D6 · one call per PAGE, not one per ambiguous event. `RelevancePage.decide` runs the same
    # five-rule cascade first and reaches its cache only for the remainder no rule could decide,
    # so the page can never overrule `known_counterparty` — the ordering is still the design.
    # Without a page (the manual door, a retry) this falls back to the one-event batch, which is
    # correct and honest about the call it makes.
    decision = (stage.relevance_page.decide(candidate) if stage.relevance_page is not None
                else assess_relevance([candidate], llm=stage.relevance_llm).decisions[0])

    domains = tag_domains(event.source, text, coverage_fn=coverage_fn)
    # Derived for every event, before the relevance short-circuit: whose turn it is stays true
    # about a message we decided not to act on, and an operator asking "why was this not
    # relevant?" is asking about a conversation, not an orphan message.
    thread = _thread_context(event, raw, mailbox_owner)
    # `SourceEvent` carries no prepared-content pointer — that field lives on `GatedEvent`,
    # which is built later — so the ref is composed here from the prepared row this event
    # actually produced, in the `prefix:id` form ALG-14's provenance table matches on.
    source_ref = (f"prepared_content:{prepared.prepared_content_id}"
                  if prepared is not None else None)
    attribution = analyze_source(event, source_ref=source_ref,
                                 executed=stage.executed, actor_role=stage.actor_role,
                                 mailbox_owner=mailbox_owner, org_domains=stage.org_domains)

    if not decision.relevant or extraction is None:
        return EsqeOutcome(relevance=decision, domains=domains, attribution=attribution,
                           thread=thread)

    detection = detect_signals(DetectionInput(
        extraction=extraction, eval_time=eval_time,
        conflicts=_conflicts_for(event, conflicts),
        # `None` unless the caller knew the thread's history. ALG-15's own rule: that is not
        # the same as "the thread had no participants", and RELATIONSHIP_CHANGE must not fire
        # on everyone because we captured one message in isolation.
        thread_parties=thread.parties))
    classification = classify_signals(detection.types)
    normalized = _normalize_detected(detection.signals, extraction, event, attribution, thread)
    # L1.6.7 (ALG-17) — the score Layer 4's utility formula has never had. Runs with NO wiring
    # parameter, on the same terms as every other S4 unit: it is pure, integer, unbilled and
    # clockless, so gating it behind a supplied baseline would mean an activated tenant kept
    # emitting signals with no intrinsic size — which is the defect, not a safe default.
    baseline = stage.org_baseline or OrgBaseline.cold_start(event.org_id,
                                                            computed_against=eval_time)
    # THE TENANT'S WEIGHTS, THEN THE SHIPPED ONES. `score_importance` has always accepted
    # `weights=`; the defect was that no caller ever supplied one, so the argument was a door
    # nobody opened — the exact shape this branch has found eleven times.
    importance = tuple(
        score_importance(signal, baseline, eval_time=eval_time,
                         **({"weights": stage.importance_weights}
                            if stage.importance_weights is not None else {}))
        for signal in normalized)

    return EsqeOutcome(relevance=decision, domains=domains, attribution=attribution,
                       detection=detection, classification=classification,
                       normalized=normalized, thread=thread, importance=importance)


def page_relevance_candidate(raw, *, sender_known: bool) -> RelevanceCandidate:
    """One pushed object as a relevance candidate, from what the RAW object already carries.

    Everything the five-rule cascade reads is here except `typed_claim_count` — S2 has not run
    when a page is primed — which is why `prime` is asked with `claims_unknown=True` below.
    `page_key` is the connector's id and not `event_id`: the event id does not exist yet (it is
    minted inside `capture_event`), and it is the only key both passes can agree on.
    """
    body = str(raw.raw.get("body") or raw.raw.get("snippet") or "")
    return RelevanceCandidate(
        event_id=f"{raw.source}:{raw.source_object_id}",
        page_key=raw.source_object_id,
        sender=raw.actor_email or "",
        sender_known=sender_known,
        headers=_esqe_headers(raw.raw),
        subject=str(raw.raw.get("subject") or ""),
        snippet=body[:MAX_ITEM_CHARS])


def prime_relevance_page(objects, semantic, sender_resolver=None) -> None:
    """D6 · ONE connector page is ONE prompt for its ambiguous remainder.

    THE SEAM. Both capture doors that receive a whole page call this before capturing any of it:
    `connectors/push_ingest.ingest_pushed_objects` (one pushed payload) and — as one line inside
    its page loop — `acquire/sync_runner.run_sync` (one fetched page). Priming stops each
    ambiguous object on a page from buying its own LLM-5 call — the defect the plan's "under 5%
    of events reach the model" bound could not see, because a bound on a share is meaningless
    until something represents the population.

    Best-effort, exactly like the sweep's `relevance.prime`: a page that could not be primed
    costs the door its batching, never its message. Every event still gets a decision from
    `capture_event`, which falls back to the per-event path.
    """
    page = getattr(semantic, "relevance_page", None)
    if page is None or not objects:
        return
    try:
        page.prime([page_relevance_candidate(
            raw, sender_known=bool(sender_resolver(raw)) if sender_resolver else False)
            for raw in objects], claims_unknown=True)
    except Exception:      # noqa: BLE001 — batching must never break an ingest
        _log.warning("relevance page priming failed for a page of %d objects", len(objects),
                     exc_info=True)



def _record_esqe(trace: EventTrace, outcome: EsqeOutcome) -> None:
    """One trace row for S4. `short_circuit` when the event was ruled out of the business —
    a distinct action from `pass`, because "we read it and it is not ours" is the answer to a
    question a tenant asks by name."""
    trace.record(
        ESQE_STAGE, "pass" if outcome.relevance.relevant else "short_circuit",
        reason_code=outcome.relevance.rule,
        decided_by=outcome.relevance.decided_by,
        relevance_bp=outcome.relevance.relevance_bp,
        domains=list(outcome.domains.domains),
        degraded_compile=outcome.domains.degraded_compile,
        # The conversation, on the row: "why is this signal about that subject?" and "who is
        # this waiting on?" are both answered here or nowhere.
        thread_key=outcome.thread.thread_key if outcome.thread else None,
        ball_in_court=outcome.thread.ball_in_court if outcome.thread else None,
        turn_index=outcome.thread.turn_index if outcome.thread else None,
        actor_authority_bp=outcome.attribution.actor_authority_bp,
        evidence_authority_rank=outcome.attribution.evidence_authority_rank,
        signal_type=outcome.classification.primary.value if outcome.classification else None,
        secondary_types=[t.value for t in outcome.classification.secondary_types]
                        if outcome.classification else [],
        signals=len(outcome.detection.signals) if outcome.detection else 0,
        # ALG-17 on the row, next to the classification it belongs to. The components ride
        # along because "why is this an 8100?" has to be answerable from the stored trace and
        # not by re-running a scorer whose weights may since have been retuned.
        importance_bp=(outcome.primary_importance.importance_bp
                       if outcome.primary_importance else None),
        importance_version=(outcome.primary_importance.importance_version
                            if outcome.primary_importance else None),
        importance_components=(outcome.primary_importance.components.as_record()
                               if outcome.primary_importance else None))


def _build_gated_event(event: SourceEvent, prepared: PreparedContent | None,
                       gate: GateResult, lane: str, structured_fields: dict,
                       hints: list[dict], links: list[dict],
                       coverage_ready: bool | None = None,
                       degraded_compile: bool | None = None) -> GatedEvent:
    return GatedEvent(
        event_id=event.event_id,
        org_id=event.org_id,
        source=event.source,
        object_type=event.object_type,
        occurred_at=event.occurred_at,
        payload_ref=event.payload_ref,
        prepared_content_ref=prepared.prepared_content_id if prepared else None,
        route=gate.route or "needs_extraction",
        structured_fields=structured_fields,
        domain_hints=hints,
        linkage_hints=links,
        triage_lane=lane,
        # Bound, not left dangling. The field was declared on the contract and never written by
        # its only constructor, so the one seam that could tell L2 "a negative inference about
        # this domain is licensed" carried nothing.
        coverage_ready=coverage_ready,
        # S4's domain tagger already answered this on this very event; the flag used to reach
        # the trace row and stop there, so the consumer that reads gated events rather than
        # traces — L2 — could not tell a degraded compile from a full one.
        degraded_compile=degraded_compile,
        internal_kind=event.internal_kind,
        # The qualifying half of the QES: participants + audience travel to L2 as structure,
        # not as fields that die inside the payload blob.
        recipients=tuple(getattr(event, "recipients", ()) or ()),
        visibility=event.visibility,
        versions={
            "preprocessor": prepared.preprocessor_version if prepared else None,
            "gate_rules": "gate-1",
        },
    )


def _finish(event: SourceEvent, trace: EventTrace, outcome: str,
            gated: GatedEvent | None, trace_repo: TraceRepository | None,
            *, extraction: ExtractionResult | None = None,
            extraction_parked: ParkedEvent | None = None,
            conflicts: ConflictOutcome | None = None,
            detection: DetectionOutcome | None = None,
            qualification: SignalClassification | None = None,
            esqe: "EsqeOutcome | None" = None,
            prepared: PreparedContent | None = None,
            extraction_ref: str | None = None) -> CaptureResult:
    """Single exit: persist the decision trace (all outcomes) and return the result."""
    if trace_repo is not None:
        trace_repo.save(trace)
    return CaptureResult(event=event, trace=trace, outcome=outcome, gated=gated,
                         extraction=extraction, extraction_parked=extraction_parked,
                         conflicts=conflicts, detection=detection, qualification=qualification,
                         esqe=esqe, prepared=prepared, extraction_ref=extraction_ref)


def capture_event(raw: RawObject, *, org_id: str, connection_id: str,
                  repo: SourceEventRepository,
                  sender_known: bool = False, is_structured: bool = False,
                  structured_fields: dict | None = None, in_scope: bool = True,
                  mask_phone: bool = False,
                  relevance: RelevanceClassifier | None = None,
                  trace_repo: TraceRepository | None = None,
                  payload_store: RawPayloadStore | None = None,
                  prepared_store=None,
                  document_job_store: DocumentJobStore | None = None,
                  # domain -> coverage dict. Injected rather than imported so capture stays
                  # testable without a connection registry, and so a caller that cannot assess
                  # coverage simply passes nothing instead of getting a fabricated answer.
                  coverage_fn=None,
                  # The connected account's own address (gmail: the mailbox email). Only used to
                  # complete the participants set on communication events — the owner could see
                  # everything in their own mailbox by definition.
                  mailbox_owner: str | None = None,
                  # S2 (L1.4), as ONE parameter. `None` = not wired for this caller, and the
                  # pipeline then behaves exactly as it did before the lane existed — which is
                  # what makes a strangler-fig activation safe to land ahead of any tenant.
                  semantic: SemanticLane | None = None,
                  # L1.3.9-U5's bundle — the org's zone and its discovery store for the TYPED
                  # route. Unlike `semantic`, `None` does not turn anything off: the structured
                  # lane runs on any mapped object either way, this only decides which calendar
                  # day a typed instant falls on and whether refused names are kept for review.
                  structured: StructuredLane | None = None,
                  # L1.5.5 (ALG-12), as ONE parameter, on the same terms as `semantic` above:
                  # `None` = not wired, and the pipeline behaves exactly as it did before the
                  # detector existed. The lane is stateful and scoped to one org's sync run,
                  # because a conflict spans events and something has to hold the email's claim
                  # until its attachment lands.
                  conflict_lane: ConflictLane | None = None,
                  # S4 (L1.6), as ONE parameter. Unlike the two lanes above, `None` does NOT turn
                  # the stage off — ESQE is pure and unbilled, so it always runs. The bundle
                  # supplies only what cannot be defaulted: LLM-5's client, the graph's role for
                  # this sender, and the org's own email domains.
                  esqe: EsqeStage | None = None,
                  sync_mode: SyncMode = SyncMode.incremental) -> CaptureResult:
    """The L1 pipeline for one raw object, fully traced. Terminal outcomes:
    duplicate (landing), dropped/park (gate), or emitted (gated_event → L2).

    Everything L1 computes is PERSISTED at the seam: the decision (route/lane/hints)
    lands on the source_events row and the PII-masked prepared text (+offset map) in
    prepared_content — so L2 reads the seam instead of re-deriving it, and evidence
    can trace back to exact source characters."""
    structured_fields = structured_fields or {}

    landing = land_raw_object(raw, org_id=org_id, connection_id=connection_id,
                              repo=repo, sync_mode=sync_mode, mailbox_owner=mailbox_owner)
    trace, event = landing.trace, landing.event
    if not landing.landed:
        return _finish(event, trace, "duplicate", None, trace_repo)

    # auto-detect structured sources (CRM/calendar/DB): a registry mapping means the
    # object is typed → structured route (gate short-circuit), no LLM extraction.
    # An enterprise-system source (CRM / billing / the client's OWN database) is structured
    # even with NO mapping yet: its rows carry no prose `body`, so the unstructured lane
    # would read "" and the noise gate would N-10 DROP the whole table as empty. Marking it
    # structured routes it to the gate's mapping_missing PARK (recoverable, human-review)
    # instead of silently losing it — store-don't-delete. (gcal etc. always have a mapping.)
    if not is_structured and (has_mapping(event.source, event.object_type)
                              or family_of(event.source) == "enterprise_system"):
        is_structured = True

    # preprocess (unstructured text only; structured events carry typed fields).
    # HTML is stripped HERE (heavy at ingestion): the gate's OOO/empty checks and the
    # persisted seam text both want prose, and L2 used to re-strip it per event.
    # SUBJECT IS PART OF THE PROSE and is masked WITH the body — prepending a raw
    # subject downstream would leak unmasked PII from subject lines to the LLM.
    # Offset map note: src coordinates refer to the stripped text, not raw HTML bytes.
    prepared: PreparedContent | None = None
    if not is_structured:
        source_text = raw.raw.get("body") or raw.raw.get("snippet") or ""
        stripped = extract_native_text(mime="text/html", data=source_text) or source_text
        subject = str(raw.raw.get("subject") or "")
        full_text = (subject + "\n\n" + stripped) if subject else stripped
        prepared = preprocess(full_text, event_id=event.event_id, mask_phone=mask_phone)
        trace.record("preprocess", "pass", language=prepared.language,
                     masked=len(prepared.masked_spans),
                     protected=len(prepared.protected_spans))

    ctx = GateContext(event=event, prepared=prepared, raw=raw.raw,
                      content_version=raw.content_version,
                      is_structured=is_structured, structured_fields=structured_fields,
                      sender_known=sender_known, in_scope=in_scope)
    gate = run_gate(ctx, trace, relevance=relevance)

    # Decision-first ledger: write the lightweight source_events row (metadata + the
    # decision) AFTER the gate, for every new object — this is the dedup + audit ledger
    # ("already fetched?" check reads it).
    outcome = {"drop": "dropped", "park": "parked"}.get(gate.action, "emitted")
    kept = outcome in ("emitted", "parked")

    # The seam, computed ONCE for kept events (dropped noise gets only the ledger row):
    # deterministic hints persisted WITH the decision so L2 and any replay read them
    # instead of recomputing. The triage lane is the L2 DRAIN order, so it exists only
    # for emitted events — a parked event's terminal trace record stays the gate's
    # park decision (recovery re-emits and the drain treats lane-less as P3).
    hints: list[dict] = []
    links: list[dict] = []
    lane: str | None = None
    if kept:
        text = prepared.clean_text if prepared else None
        hints = domain_hints(event.source, text)
        links = _linkage_hints(event)
    if gate.action not in ("drop", "park"):
        lane = triage_lane(ctx, prepared)
        trace.record("triage", "pass", lane=lane)

    # KEPT content: stash the raw body (encrypted, short TTL) for EMITTED and PARKED events.
    # Parked = a human-review queue (grey-zone), so it MUST keep content to be recoverable — was
    # a bug: parked stored no payload, dedup blocked re-fetch, /recover was a no-op → black hole.
    # Dropped noise still gets NO content — only the ledger row (L1 stays a filter, not a warehouse).
    # A judged drop keeps its body. Not because L1 should become a warehouse — a deterministic
    # drop still stores nothing — but because a model's verdict is the one kind of deletion we
    # might be wrong about, and 657 dropped events with zero payloads made "did we lose anything
    # real?" permanently unanswerable. Absence of evidence became evidence of absence.
    judged_drop = (outcome == "dropped"
                   and str(gate.reason_code or "") in _JUDGED_DROP_CODES)
    if (kept or judged_drop) and payload_store is not None:
        event.payload_ref = new_id("pay")
    repo.add(event, outcome=outcome, route=gate.route, triage_lane=lane,
             domain_hints=hints or None, linkage_hints=links or None)
    if (kept or judged_drop) and payload_store is not None:
        # full raw object → L2 reads body (unstructured) or maps fields (structured); a recovered
        # parked event flips to 'emitted' and L2 reads this same payload. Parked items sit for weeks,
        # so their body gets a long TTL — a 30-day expiry made /recover a no-op after a month.
        payload_store.put(payload_id=event.payload_ref, org_id=org_id,
                          event_id=event.event_id, content=json.dumps(raw.raw, default=str),
                          ttl_days=(_PARKED_PAYLOAD_TTL_DAYS if outcome == "parked"
                                    else _JUDGED_DROP_PAYLOAD_TTL_DAYS if judged_drop
                                    else _EMITTED_PAYLOAD_TTL_DAYS))
    if kept and prepared is not None and prepared_store is not None:
        # the PII-masked, replayable form + offset map — retained longer than the raw payload
        # `direction` PASSED, NOT RE-DERIVED. `_envelope_direction` is the one place that decides
        # inbound/outbound/internal, and it REFUSES with None when no rule can name it — a second
        # answer here would eventually disagree with the one the extractor was given. It is the
        # column that makes the form numbers mean anything: "our emails are getting longer" is a
        # statement about what WE sent, and without direction it would average in everything the
        # counterparty wrote back.
        prepared_store.put(org_id=org_id, prepared=prepared,
                           direction=_envelope_direction(event, mailbox_owner))

    # document provenance (native vs OCR + status) for any file-type event
    doc = raw.raw.get("document")
    if doc and document_job_store is not None:
        document_job_store.put(org_id=org_id, event_id=event.event_id, doc=doc,
                               fmt=raw.raw.get("mime"))

    if gate.action in ("drop", "park"):
        return _finish(event, trace, outcome, None, trace_repo)

    # structured route: derive fields from the mapping registry (data-driven, no LLM)
    #
    # A MAPPING IS THE ONLY CONDITION. This used to read `mapping and semantic is not None`,
    # falling back to `apply_mapping` — the same sift with the extraction half left off — for
    # everyone else. That coupled the typed-record route to the MODEL route: a tenant with no
    # LLM wiring, which is every unactivated tenant, got the projection and no extraction, so no
    # claims, no conflict comparison and no qualified signal ever came out of its CRM. The
    # bypass exists precisely because a HubSpot deal needs no model and no activation.
    #
    # Nothing here calls one: `run_structured_lane` has no client parameter and imports none, and
    # `structured_context` supplies the clock from the event's own `occurred_at` when no caller
    # froze one. `tests/capture/structured/test_lane.py` drives this branch with LLM-5's client
    # set to a double that RAISES on contact.
    structured_extraction: ExtractionResult | None = None
    if is_structured and not structured_fields:
        mapping = get_mapping(event.source, event.object_type)
        if mapping:
            slane = structured_context(structured, semantic, event)
            lane_outcome = run_structured_lane(
                mapping, raw.raw, org_id=org_id, event_id=event.event_id,
                eval_time=slane.eval_time, tz=slane.timezone, locale=slane.locale,
                open_lane=slane.open_lane)
            structured_fields = dict(lane_outcome.fields)
            structured_extraction = lane_outcome.result
            trace.record(STRUCTURED_STAGE,
                         "pass" if lane_outcome.extracted else "short_circuit",
                         reason_code=lane_outcome.failure,
                         mapping=mapping.mapping_id, fields=len(lane_outcome.fields),
                         refused=len(lane_outcome.refused),
                         # L1.3.9 steps 4-6, on the trace because the request path is the only
                         # place they can be observed. `absent_names` is doc 03's first failure
                         # mode made visible: a mapping that drifts from the provider's schema
                         # produces silently-empty fields, and a column that appears here on
                         # EVERY object of a source is that drift — the case that lost the whole
                         # extraction for a HubSpot deal whose `deal_currency_code` went away,
                         # with nothing anywhere naming the column responsible.
                         absent=len(lane_outcome.absent),
                         absent_names=list(lane_outcome.absent),
                         refused_names=list(lane_outcome.refused_targets),
                         # ALG-14's rank, from `weigh_authority`'s own table rather than a digit
                         # written down twice, plus the basis that answers "why is it a 4?".
                         authority=(lane_outcome.authority.authority.value
                                    if lane_outcome.authority else None),
                         authority_basis=(lane_outcome.authority.basis.value
                                          if lane_outcome.authority else None),
                         # The span coordinate system and the per-target confidences, counted
                         # rather than copied: the trace says a receipt exists for every field
                         # that arrived, and the outcome carries the receipts themselves.
                         source_refs=len(lane_outcome.source_index),
                         confident_fields=len(lane_outcome.field_confidence),
                         discoveries=lane_outcome.capture.stored)

    # S2 — the semantic lane. AFTER S1 (structural + documents, which produced `prepared` and the
    # gate's verdict) and BEFORE anything that validates a claim, because validation grades what
    # the model said and there is nothing to grade until it has said it. The structured route never
    # reaches a model: `run_semantic_lane` refuses it on the same `is_structured` flag the gate
    # short-circuited on, so the bypass stays free.
    extraction: ExtractionResult | None = None
    extraction_parked: ParkedEvent | None = None
    #: The cache key the extraction is FILED under, carried out beside the extraction itself so
    #: `qualified_signals.extraction_ref` can point at the row instead of copying it. Only this
    #: block can know it: the key is a digest computed inside the semantic lane, and
    #: `ExtractionResult` does not carry it.
    extraction_ref: str | None = None
    if semantic is not None:
        verdict = run_semantic_lane(event, prepared, raw, lane=semantic,
                                    is_structured=is_structured, mailbox_owner=mailbox_owner)
        _record_semantic(trace, verdict)
        extraction, extraction_parked = verdict.result, verdict.parked
        if extraction is not None:
            extraction_ref = getattr(verdict.outcome, "processing_key", None)
    # The structured route's extraction survives the semantic block, which declined to read a
    # typed object and therefore has no result of its own to put here. Written as a fallback
    # rather than as a branch so that the two lanes can never both claim the field.
    if extraction is None and structured_extraction is not None:
        extraction = structured_extraction
        # The form `context/runner.py:114` and `context/pipeline.py:551` already file a
        # structured extraction under. Same string, so the pointer resolves for both lanes.
        extraction_ref = f"struct:{event.event_id}"

    # ALG-12 — conflict detection, AFTER extraction because there is no claim to compare until
    # the lane has produced one, and BEFORE the emit so the gated event's trace carries the fact
    # that this event contradicted an earlier one. The detector never fails a capture: a
    # disagreement we could not compute is a missing card, while a raised exception is a lost
    # sweep.
    conflicts: ConflictOutcome | None = None
    if conflict_lane is not None and extraction is not None:
        conflicts = conflict_lane.observe(event, extraction)
        trace.record("conflict", "pass",
                     conflicts=len(conflicts.detection.conflicts),
                     detected=conflicts.detection.total_detected,
                     truncated=conflicts.detection.truncated,
                     escalations=len(conflicts.escalations))

    # S4 (L1.6) — the ESQE stage, in one call. AFTER conflict detection, because
    # INFORMATION_CONFLICT is one of the fourteen predicates and a detector that ran first would
    # never fire it; BEFORE the emit so the trace records what KIND of thing this event was
    # rather than only where it came from.
    #
    # The stage runs whether or not a bundle was supplied, because ALG-15/16, the domain tagger
    # and the authority cascade are pure functions with no clock, no model and no I/O — gating
    # them behind a flag would only mean an activated tenant could still be routing events
    # instead of qualifying them. What the bundle adds is what cannot be defaulted: LLM-5's
    # client, the graph's role for this sender, and the org's own domains. Without it the frozen
    # instant falls back to the event's own `occurred_at`, so "due within 7 days" is still judged
    # against a stored moment and never against `now()`.
    #
    # The bundle is COMPLETED here rather than replaced. It used to be all-or-nothing — a
    # caller that passed one lost both defaults — and the sweep is now a caller that passes one:
    # `platform/wiring.make_esqe_stage` supplies the org's L1.6.7 baseline for the whole run and
    # cannot know either per-event value. So the two per-EVENT fields are filled in when the
    # bundle left them open, and the org-level fields the bundle states are kept:
    #   * `eval_time`      — the semantic lane's frozen instant, else this event's world time;
    #   * `relevance_page` — D6's page seam, which reaches S4 through the lane every door passes
    #                        (`getattr`, because a caller may hand a lane-shaped stub; a missing
    #                        attribute means "no page", which is the pre-D6 behaviour exactly).
    # Before this, wiring the baseline through the bundle would have SILENTLY taken the page seam
    # away from every swept event — the same shape of defect one line up.
    stage = esqe if esqe is not None else EsqeStage()
    if stage.eval_time is None:
        stage = _dc_replace(stage, eval_time=(semantic.eval_time if semantic is not None
                                              else event.occurred_at))
    if stage.relevance_page is None:
        stage = _dc_replace(stage, relevance_page=getattr(semantic, "relevance_page", None))
    esqe_outcome = run_esqe_stage(
        event, prepared, raw.raw, stage=stage,
        extraction=extraction, conflicts=conflicts, sender_known=sender_known,
        is_structured=is_structured, coverage_fn=coverage_fn, mailbox_owner=mailbox_owner)
    _record_esqe(trace, esqe_outcome)
    detection = esqe_outcome.detection
    qualification = esqe_outcome.classification

    # Coverage is assessed against the domain THIS event was hinted into.
    coverage_ready = coverage_verdict(hints, coverage_fn)

    gated = _build_gated_event(event, prepared, gate, lane or "P3", structured_fields,
                               hints, links, coverage_ready,
                               esqe_outcome.domains.degraded_compile)
    trace.record("emit", "emit", route=gated.route, lane=lane)
    return _finish(event, trace, "emitted", gated, trace_repo,
                   extraction=extraction, extraction_parked=extraction_parked,
                   conflicts=conflicts, detection=detection, qualification=qualification,
                   esqe=esqe_outcome, prepared=prepared, extraction_ref=extraction_ref)
