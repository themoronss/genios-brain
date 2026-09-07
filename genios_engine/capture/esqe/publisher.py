"""L1.6.10 · the SIGNAL PUBLISHER — the L1 -> L2 boundary, and the last thing Layer 1 does.

Everything before this file decided what a message MEANT. This file decides whether that meaning
is allowed to leave Layer 1, and writes the row that says it did. There is exactly one crossing
and this is it.

TWO UNITS, AND ONLY ONE OF THEM IS NEW
--------------------------------------
**U1 — the publication validator — IS NOT WRITTEN HERE.** `contracts/publication.py::
validate_publication` already enforces V-1..V-7 and is green under its own contract suite. This
module WIRES it. A second implementation of the seven rules would fork from the first the day
either was edited, and both halves would still typecheck — which is how a gate becomes two gates
that disagree about what a valid signal is.

Its three outcomes are honoured exactly as it states them:

    EMIT   — publish `decision.signal`.
    PARK   — V-1 only. `decision.parked` is a reviewable, recoverable record; nothing is stored.
    REJECT — nothing is stored. The failure list names every rule that broke, not just the first.

**`decision.signal`, NEVER the input.** V-5 is non-blocking: an unverified evidence span
DOWNGRADES confidence and emits. The downgrade rides on the object the decision returns (the gate
never mutates its argument), so a publisher that stored the signal it handed in would silently
re-inflate a confidence the gate had just reduced — in the one column a human reads it back from.
`_row_for` therefore takes `decision.signal` and asserts nothing else is reachable.

**U2 — emit and store** — is `signal_store.py` plus the assembly below.

WHY THE ASSEMBLY LIVES HERE
---------------------------
`normalize.py` says in its own docstring why it does NOT build a `QualifiedEnterpriseSignal`:
six fields had not been computed yet (`importance_bp`, `confidence_bp` and its vector,
`triage_lane`, `state`, `expires_at`), and a placeholder on a boundary contract is the defect
`coverage_ready` already demonstrated. This is the seam where all six finally have answers, so
this is where the C-12 is built — once, from typed inputs, and never from a default.

    importance_bp        <- the qualification VERDICT (ALG-18 judged it; this must not re-score)
    confidence_bp/vector <- ALG-13 `compose_confidence`, from the claims this signal rests on
    triage_lane          <- the `GatedEvent` the pipeline already built
    state/supersedes/expires_at <- ALG-19, through the lifecycle SEAM below

A SIGNAL THE CONSTRUCTOR REFUSES STILL GETS AN ANSWER
-----------------------------------------------------
Two of the seven rules describe objects `QualifiedEnterpriseSignal.__init__` cannot build at all:
V-1 (`visibility` is non-optional) and V-4 (`evidence_refs` is enforced non-empty). Raising there
would turn a REFUSAL into a traceback inside a sweep, which is precisely what
`contracts/publication.py` exists to prevent. So when the constructor refuses, the object is
rebuilt with `model_construct` — the documented bypass V-1 and V-4 exist to catch — and handed to
the gate, which parks or rejects it with the rule id and the sentence a ledger row needs.

That bypass is FAIL-CLOSED. If the gate would EMIT an object the constructor refused, the
refusal was for something outside V-1..V-7 (a lane outside P0..P3, a malformed identifier) and
the gate cannot see it. Such a signal is recorded as `unbuildable` and is NOT published. A gate
that emitted what the contract had just rejected would be worse than no gate.

PURITY
------
No clock. `eval_time` is a parameter and comes from the sweep's own frozen instant
(`qualification.sweep_eval_time`), so a replay ages evidence against the same moment. No float:
every number is basis points, and the one piece of arithmetic in this file (V-5's downgrade)
lives on the contract. No LLM: nothing here scores or ranks — the score arrives on the verdict.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from pydantic import ValidationError

from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.capture.esqe.qualification import (DROP_PAYLOAD_RETENTION_DAYS,
                                                      QualificationOutcome, UNSCORED_VERSION,
                                                      extend_payload_retention,
                                                      payload_ref_for, signal_ref,
                                                      sweep_eval_time)
from genios_engine.capture.validate.confidence import (ComposedConfidence, ConfidenceSource,
                                                       age_in_days, compose_confidence)
from genios_engine.capture.validate.authority import to_legacy_rank
from genios_engine.capture.validate.conflict_store import rows_for as conflict_rows_for
from genios_engine.capture.esqe.signal_store import ENVELOPE_KEYS, QualifiedSignalRow
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.parked import ParkedEvent
from genios_engine.contracts.publication import (PARKING_RULES, PUBLICATION_STAGE,
                                                 VISIBILITY_UNKNOWN, PublicationDecision,
                                                 PublicationOutcome, PublicationRule,
                                                 validate_publication)
from genios_engine.contracts.signal import QualifiedEnterpriseSignal
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.publisher")

#: The state an ALG-19-less build publishes into. `active` is the only state L2 correlates, and
#: it is the correct answer for a signal that has just been qualified: nothing has expired it,
#: nothing has superseded it, and nothing has resolved it. It is a DEFAULT, not a decision —
#: `lifecycle.py` (L1.6.9) is what turns it into one, through the seam below.
DEFAULT_STATE = "active"

#: What `outcome` says on a refusal the seven rules did not name. See the module docstring: a
#: signal the CONSTRUCTOR refused for a reason outside V-1..V-7 is fail-closed, never published,
#: and recorded under this word so it is countable and distinguishable from a real V-rule reject.
UNBUILDABLE = "unbuildable"

#: The table migration 0092 creates. Named once so the erasure list, the ledger and the tests all
#: spell it the same way — `SIGNAL_TABLE`'s discipline, for the other half of the gate.
REJECTION_TABLE = "publication_rejections"


# =============================================================================================
# The ALG-19 seam — `lifecycle.py` is L1.6.9's file and is not this agent's to write
# =============================================================================================
@dataclass(frozen=True)
class LifecycleStamp:
    """ALG-19's three answers about one signal: is it live, what does it replace, when does it
    stop being worth acting on.

    A typed record rather than a 3-tuple because two of the three are nullable and a tuple of
    `(str, None, None)` at a call site is unreadable — and because `supersedes` and `expires_at`
    have opposite meanings when absent (nothing replaced / nothing expires it), which a tuple
    position cannot say.
    """

    state: str = DEFAULT_STATE
    supersedes: str | None = None
    expires_at: datetime | None = None


class LifecycleStamper(Protocol):
    """What the publisher needs from ALG-19 for ONE signal.

    A Protocol and not a hard dependency on a named function, because there are two legitimate
    answers and the seam must take both: the sweep's own `LifecycleOutcome` when the lifecycle
    pass has already run on this path (it has — `api/routes._run_ledger` calls `sweep_lifecycle`
    immediately above the publish), and ALG-19's arithmetic alone when it has not (a direct
    caller, a replay of one event, a test).
    """

    def __call__(self, signal: NormalizedSignal, *, eval_time: datetime) -> LifecycleStamp: ...


def alg19_stamp(signal: NormalizedSignal, *, eval_time: datetime) -> LifecycleStamp:
    """ALG-19's answer for a signal nobody has aged yet: active, replacing nothing, expiring on
    a clock computed from the signal's OWN date fields.

    `lifecycle.plan_expiry` is CALLED, never re-derived here: doc 06's windows (30 days past a
    stated deadline or a renewal, 90 for a pending decision, 180 otherwise) live in L1.6.9 and a
    second copy of that table in this file would be the two-gates-that-disagree defect one layer
    down. The import is local because `lifecycle.py` is L1.6.9's file — if a build lands without
    it, publication must still work rather than fail to import, and `expires_at` is then null,
    which honestly says "nobody has decided" rather than naming a fabricated date.

    `supersedes` is NOT decided here, and that is the division of labour rather than an omission:
    supersession is a statement about a signal and something the tenant ALREADY holds, so it
    needs the store. `sweep_lifecycle` has that store; `stamper_for_outcome` below is how its
    answer reaches the published row.
    """
    try:
        from genios_engine.capture.esqe.lifecycle import ACTIVE, plan_expiry
    except ImportError:      # pragma: no cover - L1.6.9 absent from a partial build
        return LifecycleStamp()
    plan = plan_expiry(signal.signal_type, occurred_at=signal.occurred_at,
                       stated_date=getattr(signal, "primary_date", None))
    return LifecycleStamp(state=ACTIVE, supersedes=None, expires_at=plan.expires_at)


def stamper_for_outcome(outcome: Any) -> LifecycleStamper:
    """Read the states `sweep_lifecycle` just decided, so the published row agrees with them.

    THIS IS THE POINT OF THE SEAM. ALG-19 runs one line above the publish on the request path and
    knows three things this module cannot: which of the tenant's existing signals this one
    supersedes, whether its clock has already run out (a backfilled thread can arrive expired),
    and the expiry it planned. A publisher that stamped `active` regardless would write a row
    saying live about a signal the lifecycle pass had, in the same sweep, marked superseded — and
    `qualified_signals` is the table every downstream surface reads.

    A signal the outcome does not mention falls back to `alg19_stamp`, which is the honest answer
    rather than a failure: `lifecycle_records_for` and this function walk the same sweep, so the
    gap is either a signal the floor dropped (which never reaches here) or a build where the
    lifecycle pass returned nothing at all.
    """
    by_id = {record.signal_id: record for record in (getattr(outcome, "records", ()) or ())}

    def _stamp(signal: NormalizedSignal, *, eval_time: datetime) -> LifecycleStamp:
        record = by_id.get(signal_ref(signal))
        if record is None:
            return alg19_stamp(signal, eval_time=eval_time)
        return LifecycleStamp(state=record.state, supersedes=record.supersedes,
                              expires_at=record.expires_at)

    return _stamp


def resolve_lifecycle(explicit: LifecycleStamper | Any | None = None) -> LifecycleStamper:
    """The stamper to use: the caller's, whatever shape they handed over.

    A `LifecycleOutcome` is accepted directly — it is what the request path has in its hand, and
    making every caller remember to wrap it is how the wrapping eventually gets forgotten at one
    of the six sync doors. Anything callable is taken as a stamper; `None` is ALG-19's own
    arithmetic with no store behind it.
    """
    if explicit is None:
        return alg19_stamp
    if callable(explicit):
        return explicit
    if hasattr(explicit, "records"):
        return stamper_for_outcome(explicit)
    _log.warning("ignoring an unrecognised lifecycle argument of type %s",
                 type(explicit).__name__)
    return alg19_stamp


# =============================================================================================
# ALG-13 at the boundary — the confidence a published signal carries
# =============================================================================================
def _span_key(span: Any) -> tuple[str, int, int]:
    """A span's identity for matching, without relying on the contract being hashable."""
    return (str(getattr(span, "source_ref", "")), int(getattr(span, "start_offset", -1)),
            int(getattr(span, "end_offset", -1)))


def _claim_lanes(extraction: Any) -> Iterable[Any]:
    """Every claim on an extraction, in declaration order, whatever lane it lives in.

    Walked off the model's own fields rather than off a copied lane list. `normalize.py` keeps
    such a list (`_CLAIM_LANES`) for a different purpose — choosing an anchor, where the ORDER is
    the meaning — and a second copy here would be a second answer to "what counts as a claim"
    that drifts the day a lane is added. What defines a claim for THIS purpose is structural: it
    carries evidence and it carries a belief about itself.
    """
    fields = getattr(type(extraction), "model_fields", None) or {}
    for name in fields:
        value = getattr(extraction, name, None)
        if not isinstance(value, (list, tuple)):
            continue
        for item in value:
            if hasattr(item, "evidence") and hasattr(item, "confidence_bp"):
                yield item


def confidence_sources(signal: NormalizedSignal, extraction: Any, *,
                       eval_time: datetime) -> tuple[ConfidenceSource, ...]:
    """What this signal's confidence rests on, as ALG-13's typed inputs.

    One source per CLAIM whose evidence overlaps the signal's own spans — a claim is a thing the
    extractor believed and stated a number about, and that number is the belief being composed.
    `independence_key` is the span's `source_ref`, so two claims read out of the same prepared
    body are ONE witness that can only combine downward, while a claim from a signed attachment
    is a second witness that may corroborate upward. That is Rule 11's whole distinction, and
    getting it backwards is how five weak sources repeating one weak thing become certainty.

    THE FALLBACK, and why it is not a constant. A signal whose predicate read something other
    than a typed claim (INFORMATION_CONFLICT reads a conflict; the escalate predicates read
    `intent`) matches no claim. It still has evidence, and what we know about that evidence is
    the ARTIFACT CLASS it came from — ALG-14's answer, already computed on this signal's
    attribution, already priced in basis points by the same rank ladder ALG-17 uses. So the
    fallback source is that multiplier, named for the span it describes. A hardcoded 5000 would
    make a signed contract and an inferred aside publish the same confidence.
    """
    authority = getattr(getattr(signal.attribution, "evidence", None), "authority",
                        Authority.INFERRED)
    days_old = age_in_days(signal.occurred_at, eval_time=eval_time)
    wanted = {_span_key(span) for span in signal.evidence_refs}

    sources: list[ConfidenceSource] = []
    seen: set[str] = set()
    for claim in _claim_lanes(extraction):
        spans = [s for s in (getattr(claim, "evidence", ()) or ()) if _span_key(s) in wanted]
        if not spans:
            continue
        anchor = spans[0]
        name = f"{anchor.source_ref}@{anchor.start_offset}-{anchor.end_offset}"
        if name in seen:
            # Two claims resting on the identical span are one reading of one sentence. Counting
            # it twice would COMBINE the same belief with itself and quietly halve it.
            continue
        seen.add(name)
        sources.append(ConfidenceSource(
            name=name, confidence_bp=int(claim.confidence_bp),
            independence_key=str(anchor.source_ref), authority=authority, days_old=days_old))

    if sources:
        return tuple(sources)

    multiplier = getattr(getattr(signal.attribution, "evidence", None), "multiplier_bp", None)
    if multiplier is None:      # pragma: no cover - attribution always carries ALG-14's weight
        return ()
    for span in signal.evidence_refs:
        name = f"{span.source_ref}@{span.start_offset}-{span.end_offset}"
        if name in seen:
            continue
        seen.add(name)
        sources.append(ConfidenceSource(
            name=name, confidence_bp=int(multiplier),
            independence_key=str(span.source_ref), authority=authority, days_old=days_old))
    return tuple(sources)


def compose_for(signal: NormalizedSignal, extraction: Any, *,
                eval_time: datetime, coverage_bp: int = 0) -> ComposedConfidence | None:
    """ALG-13's answer for one signal, or `None` when there was nothing at all to compose from.

    `None` rather than a floor: `compose_confidence` refuses an empty source list on purpose
    ("a confidence composed from nothing"), and inventing one here would publish a belief the
    corpus never supported. The caller turns `None` into a V-4-shaped refusal, which is the same
    answer arrived at honestly — a signal with no readable evidence is not publishable.

    `coverage_bp` is the caller's, not this module's: it answers "can we trust an ABSENCE in this
    domain", which is `coverage_ready`'s question and is known one layer up.
    """
    sources = confidence_sources(signal, extraction, eval_time=eval_time)
    if not sources:
        return None
    return compose_confidence(sources, coverage_bp=coverage_bp)


# =============================================================================================
# Assembly — the one place a QualifiedEnterpriseSignal is built
# =============================================================================================
@dataclass(frozen=True)
class SignalInputs:
    """Everything the publisher needs about ONE signal that the normalized record does not carry.

    A bundle rather than nine keyword arguments, on `EsqeStage`'s terms: the assembly already has
    a long signature and every field here comes from a different producer, so a positional slip
    between two `str | None`s would be invisible. Frozen for the reason every record in this
    build is: it is an input to a decision that gets stored.
    """

    #: ALG-18's judged score. `None` is `QualificationReason.UNSCORED` — the signal qualified
    #: because a floor must never refuse what it could not measure. It publishes at 0 with
    #: `importance_version` reading `unscored`, which is what tells a reader the number is an
    #: absence rather than a low score. C-12 has no version field; the stored ROW does.
    importance_bp: int | None
    importance_components: Mapping[str, Any] = field(default_factory=dict)
    importance_version: str = UNSCORED_VERSION
    #: The whole S2 output. Embedded on the C-12 (the seam stays one object wide) and POINTED at
    #: by the row (`extraction_ref`), so the extraction still lives exactly once.
    extraction: Any = None
    #: `l1_extraction_results.processing_key`, or `struct:<event_id>` for the structured lane.
    extraction_ref: str = ""
    #: `prepared_content:<id>` or `raw_payload:<event_id>` — the reference a REFUSAL row stores
    #: so the signal that never published stays reconstructable. Computed by
    #: `qualification.payload_ref_for`, the same function the drop ledger's rows point through,
    #: rather than by a second spelling of the provenance form here: a rejection and a drop for
    #: one event must resolve to one body, not to two notions of "the source".
    payload_ref: str | None = None
    #: The `GatedEvent` this event emitted — `triage_lane`, `coverage_ready` and `versions`.
    gated: Any = None
    #: ALG-16's secondary kinds, and L1.6.6's domain tags.
    secondary_types: tuple[Any, ...] = ()
    domain_hints: tuple[Any, ...] = ()
    #: This event's own ALG-12 disagreements, already filtered to the event — the CONTRACT
    #: objects, which is what C-12 embeds.
    conflicts: tuple[Any, ...] = ()
    #: The `signal_conflicts.conflict_id` of each of those, so the stored row POINTS at the
    #: disagreement record instead of carrying a second copy of it. Computed by
    #: `conflict_store.rows_for` — the same function that writes the table — rather than by a
    #: second spelling of its digest here, because a content address computed twice is two
    #: addresses the day either copy is edited.
    conflict_ids: tuple[str, ...] = ()
    #: `SourceEvent.captured_at` — when WE saw it, as against `occurred_at`, when it happened.
    ingested_at: Any = None
    #: sha256 of the prepared text the claims were read out of. Computed once per event by
    #: `_inputs_for` from the SAME material the extraction cache hashes, so the two digests are
    #: comparable; `None` for an event with no prepared row (a structured object).
    content_hash: str | None = None
    #: `QualificationReason`'s value off the verdict — why the floor let this through.
    qualification_reason: str | None = None


def build_signal(signal: NormalizedSignal, inputs: SignalInputs, *, eval_time: datetime,
                 lifecycle: LifecycleStamper | None = None
                 ) -> tuple[QualifiedEnterpriseSignal, ComposedConfidence | None, str | None]:
    """Assemble one C-12. Returns `(signal, composed, construction_error)`.

    `construction_error` is not an exception and not a failure code — it is the sentence the
    contract's own constructor used to refuse, carried forward so a park or reject row can quote
    it. When it is set, the returned object came from `model_construct` and has NOT been
    validated; the gate is what decides what happens to it, and `publish_one` refuses to emit
    anything that carries one.
    """
    stamper = resolve_lifecycle(lifecycle)
    stamp = stamper(signal, eval_time=eval_time)
    gated = inputs.gated
    coverage_ready = getattr(gated, "coverage_ready", None)
    composed = compose_for(signal, inputs.extraction, eval_time=eval_time,
                           coverage_bp=(10000 if coverage_ready else 0))

    kwargs: dict[str, Any] = dict(
        org_id=signal.org_id,
        schema_version=1,
        # L1 mints no id for a trace: `event_trace` is keyed `(org_id, event_id)` (migration
        # 0001), so the event id IS the join a human follows backwards. Stated here rather than
        # invented, and flagged — a real trace id would be a change to `contracts/trace.py`.
        trace_id=signal.event_id,
        visibility=signal.visibility,
        signal_id=signal_ref(signal),
        event_id=signal.event_id,
        source=signal.source,
        object_type=signal.object_type,
        occurred_at=signal.occurred_at,
        signal_type=signal.signal_type,
        domain_hints=list(inputs.domain_hints),
        importance_bp=inputs.importance_bp if inputs.importance_bp is not None else 0,
        triage_lane=getattr(gated, "triage_lane", None) or "P2",
        extraction=inputs.extraction,
        evidence_refs=list(signal.evidence_refs),
        conflicts=list(inputs.conflicts),
        confidence_bp=composed.confidence_bp if composed is not None else 0,
        confidence_vector=dict(composed.vector) if composed is not None else {},
        coverage_ready=coverage_ready,
        state=stamp.state,
        supersedes=stamp.supersedes,
        expires_at=stamp.expires_at,
        internal_kind=signal.internal_kind,
        recipients=tuple(signal.recipients or ()),
        versions=dict(getattr(gated, "versions", None) or {}),
        # Migration 0115. Read off the inputs rather than re-derived here: the capture path is
        # the only place that knows when we saw the object and what its prepared text hashed to,
        # and a second derivation at the seam would be a second answer.
        ingested_at=inputs.ingested_at,
        content_hash=inputs.content_hash,
        qualification_reason=inputs.qualification_reason,
    )
    try:
        return QualifiedEnterpriseSignal(**kwargs), composed, None
    except (ValidationError, TypeError, ValueError) as exc:
        # The documented bypass, used deliberately and exactly where the contract says it will
        # be: V-1 and V-4 describe objects this constructor cannot build, and refusing them with
        # a traceback would destroy the reviewable record the rules exist to produce.
        #
        # THE PAIR BESIDE `ValidationError` IS NOT DEFENSIVE. Pydantic re-wraps a `ValueError` a
        # validator raises and does NOT wrap a `TypeError`, and this contract's validators raise
        # both — `require_no_float`, which is V-7's own check, raises `TypeError` from inside
        # `_versioned` on a float in `versions`. Catching only `ValidationError` therefore meant
        # a V-7 violation escaped this function, unwound through `publish_one`, and was swallowed
        # by the sweep guard: the whole page lost its publication instead of that one signal
        # losing its row, and the rule that exists to name the float never got to see it. Every
        # one of these three becomes a `construction_error` the gate can turn into a row.
        return QualifiedEnterpriseSignal.model_construct(**kwargs), composed, str(exc)


# =============================================================================================
# The gate, wired — U1
# =============================================================================================
@dataclass(frozen=True)
class PublishedSignal:
    """One signal that crossed, with the decision that let it and the row that recorded it."""

    decision: PublicationDecision
    row: QualifiedSignalRow

    @property
    def signal(self) -> QualifiedEnterpriseSignal:
        """The PUBLISHED object — `decision.signal`, carrying any V-5 downgrade."""
        assert self.decision.signal is not None      # EMIT always populates it
        return self.decision.signal

    @property
    def downgraded(self) -> bool:
        return self.decision.confidence_downgrade_bp > 0


@dataclass(frozen=True)
class RefusedSignal:
    """One signal that did not cross, in the shape a rejection ledger row needs.

    Carries no signal object. That is `PublicationDecision`'s own discipline repeated: a caller
    that cannot reach a rejected signal through the result cannot publish one by accident.
    """

    org_id: str
    signal_id: str
    event_id: str
    #: `reject` for a V-rule refusal, `unbuildable` for a constructor refusal outside V-1..V-7.
    outcome: str
    rules: tuple[str, ...] = ()
    detail: str = ""
    #: The kind the refused object carried, as text. Carried because the LEDGER needs it and
    #: because V-2's whole failure mode is a kind outside the closed 14 — so this is the one
    #: place in the build where `signal_type` may legitimately not be a `SignalType`, which is
    #: also why `publication_rejections.signal_type` has no CHECK constraint.
    signal_type: str = ""
    #: `prepared_content:<id>` / `raw_payload:<event_id>`, off `SignalInputs`. Without it a
    #: rejection row is regrettable rather than auditable: the sentence says what broke and
    #: nothing says which body it broke on.
    payload_ref: str | None = None


@dataclass(frozen=True)
class PublicationReport:
    """What one publish pass concluded. Every signal lands in exactly one of the three lists."""

    emitted: tuple[PublishedSignal, ...] = ()
    parked: tuple[ParkedEvent, ...] = ()
    refused: tuple[RefusedSignal, ...] = ()
    #: How many rows the store actually accepted. Distinct from `len(emitted)` on purpose: the
    #: store logs and returns 0 on a database error rather than raising into the sweep, so a
    #: publish that decided EMIT and stored nothing is a visible, countable state.
    stored: int = 0
    #: How many rejection rows the ledger accepted. Distinct from `len(refused)` for exactly the
    #: reason `stored` is distinct from `len(emitted)`: "the gate refused nine signals and the
    #: ledger took none" is a database incident, and it must not report as a quiet Tuesday.
    rejections_filed: int = 0

    @property
    def downgraded(self) -> tuple[PublishedSignal, ...]:
        """The V-5 half — emitted, flagged, and carrying less confidence than composed."""
        return tuple(p for p in self.emitted if p.downgraded)


def _row_for(published: QualifiedEnterpriseSignal, inputs: SignalInputs, *,
             authority_rank: int | None = None) -> QualifiedSignalRow:
    """The stored row, built from the PUBLISHED signal and never from the input.

    This function taking `decision.signal` is the whole of the V-5 correctness argument: the
    downgrade lives on the returned copy, so a row built from the caller's own object would
    carry a confidence the gate had already reduced.

    `authority_rank` is `legacy_authority_rank`'s output, passed IN rather than computed here:
    the authority lives on the NormalizedSignal's attribution, which the published C-12 does not
    carry, and re-reading it off the contract would mean inventing a second place the ALG-14 ->
    legacy translation happens.
    """
    return QualifiedSignalRow(
        signal_id=published.signal_id,
        org_id=published.org_id,
        event_id=published.event_id,
        trace_id=published.trace_id,
        signal_type=published.signal_type.value,
        secondary_types=tuple(getattr(t, "value", str(t)) for t in inputs.secondary_types),
        importance_bp=published.importance_bp,
        importance_components=dict(inputs.importance_components),
        importance_version=inputs.importance_version,
        confidence_bp=published.confidence_bp,
        confidence_vector=dict(published.confidence_vector),
        domain_hints=tuple({"domain": getattr(h, "domain", ""),
                            "source": getattr(h, "source", "")}
                           for h in published.domain_hints),
        visibility=published.visibility.model_dump(mode="json"),
        coverage_ready=published.coverage_ready,
        extraction_ref=inputs.extraction_ref or f"struct:{published.event_id}",
        evidence_refs=tuple(span.model_dump(mode="json") for span in published.evidence_refs),
        conflict_ids=tuple(inputs.conflict_ids),
        state=published.state,
        supersedes=published.supersedes,
        expires_at=published.expires_at,
        internal_kind=published.internal_kind,
        occurred_at=published.occurred_at,
        envelope=_envelope_of(published),
        authority_rank=authority_rank,
        # Migration 0115. Read off the PUBLISHED signal on this function's own stated argument:
        # the row is built from what the gate returned, never from the caller's input, so a value
        # a validator normalised is the value that gets stored. `superseded_by` is absent by
        # design — the store writes it when the replacement lands.
        ingested_at=published.ingested_at,
        content_hash=published.content_hash,
        qualification_reason=published.qualification_reason,
    )


def _envelope_of(published: QualifiedEnterpriseSignal) -> dict[str, Any]:
    """The six C-12 fields the doc's DDL has no column for, in one jsonb value.

    Checked against `ENVELOPE_KEYS` rather than merely matching it by eye, on
    `ComposedConfidence.vector`'s terms: the constant is what `signal_store` documents as the
    round-trip contract, and a key added to one side and not the other would make a row that
    LOOKS rebuildable and is not. The guard fails at this line instead of at a replay months
    later.
    """
    envelope: dict[str, Any] = {
        "source": published.source,
        "object_type": published.object_type,
        "triage_lane": published.triage_lane,
        "recipients": list(published.recipients),
        "versions": dict(published.versions),
        "schema_version": published.schema_version,
    }
    missing = set(ENVELOPE_KEYS) - set(envelope)
    if missing:      # pragma: no cover - contract drift guard
        raise ValueError(f"the stored envelope is missing {sorted(missing)} — a row without them "
                         "cannot be rebuilt into the signal it came from")
    return envelope


def parking_failures(decision: PublicationDecision) -> tuple[PublicationRule, ...]:
    """The decision's blocking failures that the DECLARED rule set says to park rather than
    refuse.

    `contracts/publication.PARKING_RULES` existed and nothing read it. The publisher decided
    park-versus-reject by matching one outcome value, so the declared set was documentation:
    moving a rule into it changed a comment and nothing else, which is the same defect as a
    threshold that lives in two places except that here the second place is prose.

    Read as DATA, here and in `rejecting_failures` below, so "which rules park" has exactly one
    answer a reader can see without tracing control flow — the reason the constant is a
    frozenset in the contract rather than an `if rule is V1` at its own single call site.
    """
    return tuple(f.rule for f in decision.failures if f.blocking and f.rule in PARKING_RULES)


def rejecting_failures(decision: PublicationDecision) -> tuple[PublicationRule, ...]:
    """The blocking failures that are NOT parkable — the ones a rejection row has to name.

    The complement rather than a second membership table, so the two can never both claim a rule
    or both disown one.
    """
    return tuple(f.rule for f in decision.failures if f.blocking and f.rule not in PARKING_RULES)


def _reason_code_for(rule: PublicationRule) -> str:
    """The `parked_events.reason_code` a parking rule files under.

    V-1 keeps `visibility_unknown`, spelled exactly as `capture/gate/gate.py` spells it at S0.6
    and as `contracts/publication` does — one string for one condition across all three, so a
    reviewer filtering on it sees every event whose audience was never established. Any OTHER
    rule promoted into `PARKING_RULES` gets a code derived from its own id: a park is only
    reviewable if the reviewer can tell what to go do about it, and filing a receipt-less claim
    under "we do not know who could see this" would send them to fix the wrong thing.
    """
    if rule is PublicationRule.V1:
        return VISIBILITY_UNKNOWN
    return "publication_" + rule.value.replace("-", "").lower()


def _park_for(signal: NormalizedSignal, rules: Sequence[PublicationRule],
              decision: PublicationDecision) -> ParkedEvent:
    """A reviewable record for a parking rule the CONTRACT still returns REJECT for.

    Needed because `validate_publication` builds its own `ParkedEvent` for V-1 alone — the rule
    it short-circuits on — while `PARKING_RULES` is a set that may hold more than one member.
    The contract is frozen and its V-table is not this module's to widen; what IS this module's
    is what it DOES with a failure, and a rule the declared set calls parkable must leave a
    parked row rather than a rejection. The trace mirrors the shape both other producers write
    (`stage` / `action` / `reason`) so all three land in one readable column.
    """
    first = rules[0]
    detail = "; ".join(f.detail for f in decision.failures if f.rule in set(rules))
    return ParkedEvent(
        event_id=str(getattr(signal, "event_id", "") or ""),
        org_id=str(getattr(signal, "org_id", "") or ""),
        source=str(getattr(signal, "source", "") or ""),
        reason_code=_reason_code_for(first),
        stage=PUBLICATION_STAGE,
        trace=[{"stage": PUBLICATION_STAGE, "action": "park",
                "reason": _reason_code_for(first), "rule": first.value, "detail": detail}])


def legacy_authority_rank(signal: NormalizedSignal) -> int | None:
    """This signal's ALG-14 authority on the 0..4 scale Layer 2 writes facts at, or `None`.

    `capture/validate/authority.to_legacy_rank` is that module's own stated "one sanctioned
    crossing" between ALG-14's 0..6 ladder and `context.pipeline.FACT_CONF_BY_RANK`, and it had
    no caller outside its test — so the translation it exists to own was going to be re-derived
    at whatever call site needed it first, "usually as `rank - 1`, which is wrong for four of the
    seven classes". Doing it HERE, once, at the L1 -> L2 write, is what the authority module's
    own docstring asks for: *translate at the write, never before*.

    `None` when the signal carries no recognisable authority — a `model_construct`ed object, a
    stub attribution. An absence, never a floor: a defaulted 2 would tell Layer 2 that we read
    this in prose when in fact we do not know what we read it in.
    """
    authority = getattr(getattr(signal.attribution, "evidence", None), "authority", None)
    if not isinstance(authority, Authority):
        return None
    return to_legacy_rank(authority)


def publish_one(signal: NormalizedSignal, inputs: SignalInputs, *, eval_time: datetime,
                lifecycle: LifecycleStamper | None = None
                ) -> tuple[PublishedSignal | None, ParkedEvent | None, RefusedSignal | None]:
    """Run the gate over ONE signal. Exactly one of the three is non-None.

    The gate's arguments come from ALG-13's own output, not from a second list assembled here:
    `ComposedConfidence` returns `source_confidences` and `independent_evidence` shaped for
    `validate_publication` precisely so V-6's ceiling and the composer's ceiling can never be two
    different lists. When nothing could be composed both are empty, which the contract reads as
    "V-6 was not in play" — and a signal with no composable evidence fails V-4 anyway.
    """
    built, composed, construction_error = build_signal(signal, inputs, eval_time=eval_time,
                                                       lifecycle=lifecycle)
    decision = validate_publication(
        built,
        source_confidences=(composed.source_confidences if composed is not None else ()),
        independent_evidence=(composed.independent_evidence if composed is not None else ()))

    signal_id = str(getattr(built, "signal_id", "") or signal_ref(signal))
    signal_type = str(getattr(getattr(signal, "signal_type", ""), "value",
                              getattr(signal, "signal_type", "")) or "")

    # PARK OR REJECT IS DECIDED BY THE DECLARED SET, not by the outcome value.
    #
    # `validate_publication` returns PARK for V-1 and REJECT for the other five, which is the
    # V-table's own answer and correct. What it cannot answer is what a build does with a rule
    # someone later declares parkable, because `PARKING_RULES` lives beside the table and the
    # table short-circuits on V-1 before the rest of it runs. Reading the set here is what makes
    # that constant load-bearing: a rule moved into it parks, out of it rejects, with no edit to
    # this function. Parking is also the WEAKER answer — a signal that ALSO broke a
    # non-parkable rule is rejected, because "reviewable, recover it later" must not be the
    # verdict on something that is unpublishable for a reason nothing can recover.
    parking = parking_failures(decision)
    rejecting = rejecting_failures(decision)
    if parking and not rejecting:
        return None, decision.parked or _park_for(signal, parking, decision), None
    if rejecting:
        return None, None, RefusedSignal(
            org_id=signal.org_id, signal_id=signal_id, event_id=signal.event_id,
            outcome=PublicationOutcome.REJECT.value,
            rules=tuple(rule.value for rule in rejecting),
            detail="; ".join(f.detail for f in decision.failures if f.rule in set(rejecting)),
            signal_type=signal_type, payload_ref=inputs.payload_ref)

    if construction_error is not None:
        # FAIL CLOSED. The seven rules found nothing wrong, but the contract's own constructor
        # had refused this object for something they do not cover. Publishing here would put a
        # row in `qualified_signals` that `QualifiedEnterpriseSignal` cannot read back.
        _log.warning("refusing to publish an unbuildable signal for org=%s event=%s: %s",
                     signal.org_id, signal.event_id, construction_error)
        return None, None, RefusedSignal(
            org_id=signal.org_id, signal_id=signal_id, event_id=signal.event_id,
            outcome=UNBUILDABLE, detail=construction_error, signal_type=signal_type,
            payload_ref=inputs.payload_ref)

    # `decision.signal`, never `built` — see the module docstring and `_row_for`.
    return PublishedSignal(
        decision=decision,
        row=_row_for(decision.signal, inputs,
                     authority_rank=legacy_authority_rank(signal))), None, None


# =============================================================================================
# THE REJECTION LEDGER — "why did I never see X?", for the five rules that answered nobody
# =============================================================================================
#
# Built on `qualification_drops`' own terms and by reusing its parts, not by inventing a second
# design: a content-addressed id so a replayed sweep upserts one row instead of appending a
# second copy of one refusal, a `payload_ref` in the same `prefix:id` provenance form ALG-14
# matches on, the same 90-day retention promise EXTENDED BY THE SAME WRITER
# (`qualification.extend_payload_retention`) in the same transaction as the rows, the same
# put/list/get triple with an in-memory sibling for a dev run, and the same rule that a ledger
# never raises into a sweep. What is not shared is the TABLE, and migration 0092 says why:
# `qualification_drops` carries `check (importance_bp < floor_bp)`, so a V-2 rejection could only
# live there by inventing a floor to satisfy an invariant that has nothing to do with it.
def rejection_id(org_id: str, signal_id: str, outcome: str, rules: Sequence[str]) -> str:
    """The content address of one REFUSAL by the publication gate.

    `drop_id`'s digest, over this decision's own dimensions: the rules are IN it because a signal
    that fails V-4 today and V-4 + V-6 tomorrow was refused for two different reasons and each
    deserves its row, while the same signal refused for the same rules twice is one fact
    re-observed. `evaluated_at` is deliberately excluded — it is the only field a replay changes,
    and putting it in the digest would turn the ledger into an append-only log of one refusal.

    The rules are sorted before hashing so a caller that hands them in V-order and one that hands
    them in set order address the same row.
    """
    payload = f"{org_id}:{signal_id}:{outcome}:{','.join(sorted(rules))}"
    return "prj_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class RejectionRow:
    """One refused signal, in the shape the table holds it.

    `rules` is a tuple of the rule IDS ('V-4') rather than of `PublicationRule` members, on
    `DropRow.components`' terms: this type crosses the database boundary in BOTH directions, and
    a row written when the V-table had seven rules must stay readable by a build that has eight.
    Re-typing is a reader's decision, never the store's.
    """

    org_id: str
    rejection_id: str
    signal_id: str
    event_id: str
    signal_type: str
    outcome: str
    rules: tuple[str, ...]
    reason: str
    payload_ref: str | None
    evaluated_at: datetime
    retain_until: datetime


def rejection_rows(refusals: Sequence[RefusedSignal], *,
                   eval_time: datetime) -> tuple[RejectionRow, ...]:
    """The gate's refusals as rows. A free function, on `qualification.drop_rows`' terms: the
    SHAPE of a stored refusal is decided once, so the in-memory ledger and the Postgres one agree
    by construction rather than by two implementations that happen to match today.

    `retain_until` is `eval_time` plus the SAME window a drop promises
    (`DROP_PAYLOAD_RETENTION_DAYS`), imported rather than restated: a tenant asking why an email
    produced nothing does not know or care which half of the gate refused it, and two retention
    windows would mean half those questions became unanswerable a month before the other half.
    """
    until = eval_time + timedelta(days=DROP_PAYLOAD_RETENTION_DAYS)
    return tuple(
        RejectionRow(
            org_id=r.org_id,
            rejection_id=rejection_id(r.org_id, r.signal_id, r.outcome, r.rules),
            signal_id=r.signal_id, event_id=r.event_id, signal_type=r.signal_type,
            outcome=r.outcome, rules=tuple(r.rules), reason=r.detail,
            payload_ref=r.payload_ref, evaluated_at=eval_time, retain_until=until)
        for r in refusals)


class RejectionLedger(Protocol):
    """A sweep files what the gate refused; a tenant asks why an email produced nothing."""

    def put(self, rows: Sequence[RejectionRow]) -> int: ...

    def list(self, org_id: str, event_id: str | None = None) -> list[RejectionRow]: ...

    def get(self, org_id: str, rejection_id: str) -> RejectionRow | None: ...


class InMemoryRejectionLedger:
    """A dict, for dev and hermetic tests. Keyed on `(org, rejection_id)` rather than the id
    alone — the real table's tenant boundary, so a hermetic test cannot pass while the real
    ledger hands one tenant's quoted sentences to another."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], RejectionRow] = {}

    def put(self, rows: Sequence[RejectionRow]) -> int:
        for row in rows:
            self._rows[(row.org_id, row.rejection_id)] = row
        return len(rows)

    def list(self, org_id: str, event_id: str | None = None) -> list[RejectionRow]:
        rows = [r for (o, _), r in self._rows.items()
                if o == org_id and (event_id is None or r.event_id == event_id)]
        # `order by evaluated_at desc, rejection_id` — the index's own order, spelled as two
        # stable sorts because the two keys run in OPPOSITE directions and a single reversed
        # tuple sort would silently reverse the tie-break as well. A dev run and a Postgres run
        # must hand a reader the same page, ties included.
        rows.sort(key=lambda r: r.rejection_id)
        rows.sort(key=lambda r: r.evaluated_at, reverse=True)
        return rows

    def get(self, org_id: str, rejection_id_: str) -> RejectionRow | None:
        return self._rows.get((org_id, rejection_id_))

    def erase(self, org_id: str) -> int:
        """What `/reset` does to the real table, for a dev run."""
        keys = [k for k in self._rows if k[0] == org_id]
        for key in keys:
            del self._rows[key]
        return len(keys)


_REJECTION_COLUMNS = ("rejection_id, org_id, signal_id, event_id, signal_type, outcome, rules, "
                      "reason, payload_ref, evaluated_at, retain_until")


class PostgresRejectionLedger:
    """The real ledger. UPSERT by `rejection_id`, and never raises into a sweep.

    `put` extends `raw_payloads.expires_at` for every referenced event to at least `retain_until`
    IN THE SAME TRANSACTION as the rows, through `qualification.extend_payload_retention` — the
    same function `PostgresDropLedger` uses, so the promise cannot be kept by one ledger and
    quietly broken by the other. A row that outlived the body it points at is a receipt for
    something nobody can fetch, which is a worse answer to "why did I never see X?" than no row
    at all: it looks like an answer.
    """

    def __init__(self, database_url: str) -> None:
        from genios_engine.platform.db import get_engine
        self._engine = get_engine(database_url)

    def put(self, rows: Sequence[RejectionRow]) -> int:
        from sqlalchemy import text
        if not rows:
            return 0
        try:
            with self._engine.begin() as conn:
                for row in rows:
                    conn.execute(text(
                        f"insert into {REJECTION_TABLE} ({_REJECTION_COLUMNS}) values "
                        "(:id, :o, :sig, :ev, :st, :out, cast(:rules as jsonb), :reason, "
                        " :ref, :at, :until) "
                        "on conflict (rejection_id) do update set "
                        "signal_type=excluded.signal_type, rules=excluded.rules, "
                        "reason=excluded.reason, payload_ref=excluded.payload_ref, "
                        "evaluated_at=excluded.evaluated_at, "
                        "retain_until=excluded.retain_until"),
                        {"id": row.rejection_id, "o": row.org_id, "sig": row.signal_id,
                         "ev": row.event_id, "st": row.signal_type, "out": row.outcome,
                         "rules": json.dumps(list(row.rules)), "reason": row.reason,
                         "ref": row.payload_ref, "at": row.evaluated_at,
                         "until": row.retain_until})
                extend_payload_retention(conn, rows)
        except Exception as exc:      # noqa: BLE001 — a rejection ledger never kills a sweep
            _log.warning("could not file %d publication rejection(s) for org=%s: %s",
                         len(rows), rows[0].org_id, exc)
            return 0
        return len(rows)

    def list(self, org_id: str, event_id: str | None = None) -> list[RejectionRow]:
        from sqlalchemy import text
        clause = " and event_id=:ev" if event_id else ""
        params: dict[str, Any] = {"o": org_id}
        if event_id:
            params["ev"] = event_id
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select {_REJECTION_COLUMNS} from {REJECTION_TABLE} where org_id=:o{clause} "
                "order by evaluated_at desc, rejection_id"), params).all()
        return [_to_rejection_row(r) for r in rows]

    def get(self, org_id: str, rejection_id_: str) -> RejectionRow | None:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(text(
                f"select {_REJECTION_COLUMNS} from {REJECTION_TABLE} "
                "where org_id=:o and rejection_id=:id"),
                {"o": org_id, "id": rejection_id_}).first()
        return _to_rejection_row(row) if row is not None else None


def _to_rejection_row(row: Any) -> RejectionRow:
    """One database row as the dataclass. The rules column decoded, nothing revalidated."""
    rules = row.rules if isinstance(row.rules, list) else json.loads(row.rules or "[]")
    return RejectionRow(
        org_id=row.org_id, rejection_id=row.rejection_id, signal_id=row.signal_id,
        event_id=row.event_id, signal_type=row.signal_type, outcome=row.outcome,
        rules=tuple(str(r) for r in rules), reason=row.reason, payload_ref=row.payload_ref,
        evaluated_at=row.evaluated_at, retain_until=row.retain_until)


# =============================================================================================
# THE SEAM — one sweep's qualified signals, gated and stored. The production entry point.
# =============================================================================================
def _conflicts_for(summary: Any, event_id: str) -> tuple[Any, ...]:
    """This event's own contract-level conflicts, unwrapped off the sweep.

    Read off the summary here rather than imported from `capture/pipeline` for the reason
    `qualification._event_carries_conflict` states: the pipeline imports this package, so the
    dependency cannot point back. Filtered by event id, because ALG-12's detection covers the
    whole sweep and an unfiltered list would attach a disagreement between two OTHER messages to
    every signal on the page.
    """
    detection = getattr(getattr(summary, "conflicts", None), "detection", None)
    return tuple(row.conflict for row in (getattr(detection, "conflicts", ()) or ())
                 if event_id in (getattr(row, "event_ids", ()) or ()))


def _conflict_ids_for(conflict_rows: Sequence[Any], event_id: str) -> tuple[str, ...]:
    """The stored ids of the disagreements THIS event took part in.

    Read off `conflict_store.rows_for`'s own output, computed once per sweep by the caller. That
    is what makes a `conflict_ids` entry resolve: the id here and the id in `signal_conflicts`
    come out of one function, so they cannot be two content addresses for one disagreement.
    """
    return tuple(row.conflict_id for row in conflict_rows
                 if event_id in (getattr(row, "event_ids", ()) or ()))


def prepared_content_hash(result: Any) -> str | None:
    """sha256 of the prepared text this event's claims were read out of, or None.

    THE SAME DIGEST THE EXTRACTION CACHE COMPUTES. `capture/semantic/cache.py` hashes
    `PreparedContent.clean_text` into its key under the name `content_hash`, and the whole value
    of storing it on the signal is that the two can be compared — so this reuses that module's
    `content_digest` rather than spelling `hashlib.sha256(...)` a second time. Two spellings of
    one content address are two addresses the day either is changed.

    `None` when the event has no prepared row at all: a structured object (a CRM deal) carries
    typed fields and no prose, and hashing the empty string would give every one of them the same
    non-answer dressed as a digest.
    """
    prepared = getattr(result, "prepared", None)
    text = getattr(prepared, "clean_text", None)
    if not text or not str(text).strip():
        return None
    from genios_engine.capture.semantic.cache import content_digest
    return content_digest(str(text))


def _inputs_for(result: Any, signal: NormalizedSignal, verdict: Any, summary: Any, *,
                conflict_rows: Sequence[Any] = ()) -> SignalInputs:
    """Everything about one signal that the normalized record does not carry, read off the
    sweep's own objects. Nothing is defaulted that a producer already answered."""
    esqe = getattr(result, "esqe", None)
    classification = getattr(esqe, "classification", None)
    domains = getattr(esqe, "domains", None)
    event = getattr(result, "event", None)
    reason = getattr(verdict, "reason", None)
    return SignalInputs(
        importance_bp=getattr(verdict, "importance_bp", None),
        importance_components=dict(getattr(verdict, "components", None) or {}),
        importance_version=getattr(verdict, "importance_version", None) or UNSCORED_VERSION,
        extraction=getattr(result, "extraction", None),
        extraction_ref=str(getattr(result, "extraction_ref", None) or ""),
        payload_ref=payload_ref_for(result),
        gated=getattr(result, "gated", None),
        secondary_types=tuple(getattr(classification, "secondary_types", ()) or ()),
        domain_hints=tuple(getattr(domains, "hints", ()) or ()),
        conflicts=_conflicts_for(summary, signal.event_id),
        conflict_ids=_conflict_ids_for(conflict_rows, signal.event_id),
        ingested_at=getattr(event, "captured_at", None),
        content_hash=prepared_content_hash(result),
        qualification_reason=getattr(reason, "value", reason))


def publish_sweep(summary: Any, outcome: QualificationOutcome, *, org_id: str,
                  store: Any = None, parked_store: Any = None, rejections: Any = None,
                  lifecycle: LifecycleStamper | None = None,
                  eval_time: datetime | None = None) -> PublicationReport:
    """THE SEAM. Every signal this sweep QUALIFIED, gated by V-1..V-7 and stored.

    Takes the `QualificationOutcome` rather than re-deriving it, and joins it to the sweep's
    normalized signals by `signal_ref` — the same content address `qualification` files its drop
    rows under, so the two halves of one decision (what was refused, what crossed) are joinable
    by id. This function must never re-score: ALG-18 already judged these, and a second scoring
    pass here would be a second answer to the one question doc 06 gives L1.6.7.

    A BELOW-FLOOR SIGNAL NEVER REACHES THE GATE. `outcome.qualified` is the input, not
    `outcome.verdicts` — a dropped signal has its ledger row and stops there. That is the
    ordering the floor exists for, and it is asserted by a test of this function rather than
    left as a property of the caller.

    Never raises. Publication is downstream of capture on exactly the terms `qualify_sweep` and
    `persist_sweep_conflicts` are: losing a published row costs a card, raising costs the tenant
    their mail.
    """
    try:
        return _publish_sweep(summary, outcome, org_id=org_id, store=store,
                              parked_store=parked_store, rejections=rejections,
                              lifecycle=lifecycle, eval_time=eval_time)
    except Exception:      # noqa: BLE001 — downstream of capture, never above it
        _log.warning("publication failed for org=%s", org_id, exc_info=True)
        return PublicationReport()


def _publish_sweep(summary: Any, outcome: QualificationOutcome, *, org_id: str,
                   store: Any, parked_store: Any, rejections: Any,
                   lifecycle: LifecycleStamper | None,
                   eval_time: datetime | None) -> PublicationReport:
    """`publish_sweep` without the guard, so the guard has exactly one job and the body reads."""
    qualified = {v.signal_id: v for v in outcome.qualified if v.org_id == org_id}
    if not qualified:
        return PublicationReport()
    instant = eval_time or sweep_eval_time(summary)
    if instant is None:
        return PublicationReport()

    stamper = resolve_lifecycle(lifecycle)
    # Once per sweep, not once per signal: the digest walks both claims of every disagreement,
    # and a page with forty signals over four conflicts would otherwise hash the same four rows
    # forty times.
    detection = getattr(getattr(summary, "conflicts", None), "detection", None)
    conflict_rows = conflict_rows_for(detection, org_id=org_id) if detection is not None else []
    emitted: list[PublishedSignal] = []
    parked: list[ParkedEvent] = []
    refused: list[RefusedSignal] = []

    for result in getattr(summary, "results", ()) or ():
        esqe = getattr(result, "esqe", None)
        for signal in (getattr(esqe, "normalized", ()) if esqe is not None else ()):
            verdict = qualified.get(signal_ref(signal))
            if verdict is None:      # dropped by the floor, or another tenant's row
                continue
            published, park, refusal = publish_one(
                signal, _inputs_for(result, signal, verdict, summary,
                                    conflict_rows=conflict_rows),
                eval_time=instant, lifecycle=stamper)
            if published is not None:
                emitted.append(published)
            elif park is not None:
                parked.append(park)
            elif refusal is not None:
                refused.append(refusal)

    stored = 0
    if store is not None and emitted:
        # Guarded SEPARATELY from the pass above, not by the outer `publish_sweep` catch. Both
        # guards keep the sweep alive; only this one keeps the DECISION. `PublicationReport`
        # documents `stored` as distinct from `len(emitted)` so that "the gate said EMIT and the
        # store took nothing" is a countable state — and it is countable only if a database error
        # leaves the emitted list standing. Swallowed one level up, a store outage and a sweep
        # with no signals report the identical empty tuple, and those are a database incident and
        # a quiet Tuesday.
        try:
            stored = store.put([p.row for p in emitted])
        except Exception:      # noqa: BLE001 — a store outage costs rows, never the sweep
            _log.warning("could not store %d published signal(s) for org=%s", len(emitted),
                         org_id, exc_info=True)
    if parked_store is not None:
        for park in parked:
            try:
                parked_store.add(park)
            except Exception:      # noqa: BLE001 — a park row is a record, not a gate
                _log.warning("could not file a publication park row for org=%s", org_id,
                             exc_info=True)

    filed = 0
    if rejections is not None and refused:
        # THE ROW FIVE RULES NEVER LEFT. `refused` was assembled on every pass of the loop above
        # and then discarded with the report, so V-2, V-3, V-4, V-6 and V-7 each refused a signal
        # and wrote nothing anywhere — a tenant asking "this email produced nothing, why?" got
        # silence for five of the seven rules and an answer for two.
        #
        # Guarded SEPARATELY from the outer `publish_sweep` catch, on the store's own terms: both
        # guards keep the sweep alive, only this one keeps the REFUSALS on the report. Swallowed
        # one level up, a ledger outage and a sweep that refused nothing report the identical
        # empty tuple.
        try:
            filed = rejections.put(rejection_rows(refused, eval_time=instant))
        except Exception:      # noqa: BLE001 — a ledger outage costs an explanation, not mail
            _log.warning("could not file %d publication rejection(s) for org=%s", len(refused),
                         org_id, exc_info=True)
    if refused:
        _log.info("publication refused %d signal(s) for org=%s: %s", len(refused), org_id,
                  ", ".join(f"{r.signal_id}:{r.outcome}:{'/'.join(r.rules)}" for r in refused))
    return PublicationReport(emitted=tuple(emitted), parked=tuple(parked),
                             refused=tuple(refused), stored=stored, rejections_filed=filed)


__all__ = ["DEFAULT_STATE", "REJECTION_TABLE", "UNBUILDABLE", "InMemoryRejectionLedger",
           "LifecycleStamp", "LifecycleStamper", "PostgresRejectionLedger", "PublicationReport",
           "PublishedSignal", "RefusedSignal", "RejectionLedger", "RejectionRow", "SignalInputs",
           "alg19_stamp", "build_signal", "compose_for", "confidence_sources",
           "legacy_authority_rank", "parking_failures", "publish_one", "publish_sweep",
           "rejecting_failures", "rejection_id", "rejection_rows", "resolve_lifecycle",
           "stamper_for_outcome"]
