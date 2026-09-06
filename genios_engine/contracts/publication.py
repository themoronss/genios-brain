"""V-1..V-7 · the publication gate at L1.6.10 — the last thing that runs before a signal exists.

`QualifiedEnterpriseSignal` already refuses most of this at construction (universal rule 5: a
validator runs at the seam that produced the object), and that is deliberate — a signal that
cannot be built cannot be published by accident. What a contract's constructor cannot do is the
part this module owns, and it is the whole reason the doc puts a second gate at L1.6.10:

* **A refusal has to become a ROW, not a traceback.** A rejected signal must stay
  reconstructable — which rule refused it, with what detail — because "the engine produced
  nothing for that email" is unanswerable otherwise. A `ValidationError` thrown from inside a
  publisher loop is a log line, and the next question a tenant asks is always about the signal
  that never appeared.
* **V-1 PARKS rather than rejects.** Parked is not deleted (`contracts/parked.py`): it is
  reviewable, carries its reason, and is recoverable by re-injection. No constructor can express
  "refuse this, and keep it".
* **V-5 is non-blocking.** An unverified span degrades trust; it does not destroy the signal.
  The gate lowers `confidence_bp`, flags the signal, and emits it anyway. A constructor has only
  two answers — built or raised — and neither of them is "emit this, smaller".
* **V-6 needs a second input.** The ceiling is `min(source confidences)`, and the signal does not
  carry the source list. Only the caller that composed the confidence (ALG-13, L1.5.7) knows it,
  and only that caller knows whether independent evidence was explicitly named.

**Why a new module and not more of `validators.py`.** Two reasons, and the first is decisive:
`signal.py` imports `validators.py`, so a gate over `QualifiedEnterpriseSignal` living in
`validators.py` would be an import cycle the moment it typed its own argument. The second is
grammar. Every helper in `validators.py` fails closed by RAISING — that is its stated contract,
and the field-level primitives here reuse it unchanged. This module's contract is the opposite
and must be: an expected rejection returns a `PublicationDecision`, never an exception, because
the caller's next move is to write a ledger row rather than to unwind a stack.

**What the gate does NOT re-derive.** The arithmetic that already has a home stays there.
V-6's comparison is `QualifiedEnterpriseSignal.confidence_respects_sources`; V-7's walk is
`conflict.require_no_float`; V-2 and V-3 go through `require_enum` and `require_bp`. A second
copy of any of them would fork from the first the day either is edited, and both sides would
still typecheck.

**A note on `confidence_bp`.** The V-table gives it no range rule of its own — V-3 covers
`importance_bp` only. It is not unguarded: the constructor range-checks it through `require_bp`,
and V-7 is what catches a ratio smuggled into a bypassed construction, because a float anywhere
in the object is a reject regardless of which field holds it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from genios_engine.contracts.conflict import require_no_float
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.parked import ParkedEvent
from genios_engine.contracts.signal import QualifiedEnterpriseSignal, SignalType
from genios_engine.contracts.validators import (require_bp, require_enum, require_ordinal,
                                                require_non_negative, require_strings)
from genios_engine.contracts.visibility import Visibility

#: The stage string written onto a parked event and into its trace. It names the seam in the
#: doc's own vocabulary rather than the `S0`/`S1` shorthand the earlier gates use, because those
#: stages are the ROUTING pipeline (`capture/gate/gate.py`) and this one is the QUALIFYING
#: pipeline. A reviewer reading `parked_events.stage` must be able to tell "we never worked out
#: who could see this email" (S0.6) from "we qualified a signal and then could not establish its
#: audience" (here) — same reason code, two different bugs to go fix.
PUBLICATION_STAGE = "L1.6.10"

#: V-1's reason code, spelled exactly as `capture/gate/gate.py` already spells it at S0.6. One
#: string for one condition across both seams, so a reviewer filtering `parked_events` on it
#: sees every event whose audience was never established rather than the half that failed early.
VISIBILITY_UNKNOWN = "visibility_unknown"

#: The flag V-5 raises on an emitted signal. A flag, not a state: the signal is live, correlated
#: and acted on like any other — it simply says less loudly than it would have, and says so where
#: a human can see which quote to go check (`QualifiedEnterpriseSignal.unverified_spans`).
UNVERIFIED_EVIDENCE_FLAG = "unverified_evidence"


class PublicationOutcome(str, Enum):
    """What the gate decided. Three outcomes, and they are not three severities of one thing.

    A `str` enum so the value written into a ledger row reads as the word, while the set stays
    closed — a fourth outcome invented at a call site would be an emit nobody reviewed.
    """

    #: Publish it. The signal on the decision is the one to publish — it may carry a V-5
    #: downgrade the input did not, so publishing the input instead silently re-inflates it.
    EMIT = "emit"
    #: Do not publish, and do not discard. `parked` carries the reviewable, recoverable record.
    #: Only V-1 lands here.
    PARK = "park"
    #: Do not publish. The signal is not carried on the decision, so a caller cannot publish a
    #: rejected object by reaching through the result; the caller already holds the input and
    #: writes it, with `failures`, into the rejection ledger.
    REJECT = "reject"


class PublicationRule(str, Enum):
    """The seven rules, by the doc's own ids. The value is the id a ledger row stores.

    Ids rather than prose because the rules are cited by number across the L1 documents and in
    every card-provenance conversation that follows a missing signal. A rejection row that says
    `V-4` is joinable to the rule table; one that says "no evidence" is a sentence someone will
    later rewrite.
    """

    #: Envelope complete and `visibility is not None`. The only rule whose failure PARKS.
    V1 = "V-1"
    #: `signal_type` is one of the closed 14. Reject — never a coercion to a near neighbour.
    V2 = "V-2"
    #: `0 <= importance_bp <= 10000`. Reject.
    V3 = "V-3"
    #: `evidence_refs` non-empty. Reject — a claim with no receipt is a guess.
    V4 = "V-4"
    #: Every span verified. NON-BLOCKING: downgrade, flag, emit.
    V5 = "V-5"
    #: `confidence_bp <= min(source confidences)` unless independent evidence is named. Reject.
    V6 = "V-6"
    #: No float anywhere in the serialized object. Reject.
    V7 = "V-7"


#: V-5 alone. Kept as data rather than as an `if rule is V5` at the one site that needs it, so
#: the "which rules block" question has a single answer that a reader can see without tracing
#: control flow — and so a future non-blocking rule is a one-line change here rather than a
#: condition somebody has to remember to widen.
NON_BLOCKING_RULES: frozenset[PublicationRule] = frozenset({PublicationRule.V5})

#: The rules whose failure parks instead of rejecting. V-1 only, and the doc is explicit that it
#: is the only one: an event whose audience was never established is not a bad signal, it is an
#: unanswered question, and the answer is frequently recoverable (the connector re-syncs the
#: thread, an admin maps the workspace) in a way that a hallucinated quote never is.
PARKING_RULES: frozenset[PublicationRule] = frozenset({PublicationRule.V1})


class RuleFailure(BaseModel):
    """One rule that did not hold, with the sentence a reviewer needs.

    Frozen and extra-forbidding for the reason every record type in `contracts/` is: this is a
    record of a decision that was made, and a record that can be edited afterwards is not one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Which rule. See `PublicationRule`.
    rule: PublicationRule
    #: WHY it failed, in one line, naming the offending value where there is one. This is the
    #: text that lands in the rejection ledger, so it must stand alone: by the time anyone reads
    #: it the signal object is a row in a different table and the stack that produced it is gone.
    detail: str

    @property
    def blocking(self) -> bool:
        """False only for V-5. A non-blocking failure is still a failure that gets recorded —
        it changed the number a human will read, and that is worth a row."""
        return self.rule not in NON_BLOCKING_RULES


class PublicationDecision(BaseModel):
    """The gate's answer: what to do, which rules failed, and what the emitted signal now says.

    Deliberately not a bool and deliberately not an exception. A bool cannot carry the downgrade
    V-5 applied, cannot name the rule a rejection ledger has to record, and cannot hold the
    `ParkedEvent` V-1 produces — and an exception cannot be written to a row at all without the
    caller re-deriving, from a message string, what it already knew.

    Read `outcome` first; `signal` is populated only on EMIT and `parked` only on PARK, so the
    two ways of publishing something that should not have been published are both unreachable by
    construction rather than by discipline.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: emit | park | reject. See `PublicationOutcome`.
    outcome: PublicationOutcome
    #: Every rule that did not hold, in V-order — including V-5, which does not block. Empty on
    #: a clean emit. All of them are recorded rather than only the first, because a signal that
    #: fails V-2 and V-4 has two different upstream bugs and fixing one would otherwise reveal
    #: the other a day later.
    failures: tuple[RuleFailure, ...] = ()
    #: Rules the caller explicitly lifted, with grounds the doc names. Today only V-6, waived by
    #: naming independent evidence. Recorded rather than merely honoured: a confidence that
    #: exceeded its sources because somebody passed a name must stay auditable, since "we named
    #: independent evidence" is exactly the claim that would otherwise be invisible in the row.
    waived: tuple[PublicationRule, ...] = ()
    #: Advisory marks carried by the EMITTED signal — today `UNVERIFIED_EVIDENCE_FLAG` alone.
    #: Empty unless the outcome is EMIT: a flag describes something that was published, and a
    #: flag on a rejected signal is a caveat about an object nobody will ever see.
    flags: tuple[str, ...] = ()
    #: The signal to publish, with any V-5 downgrade already applied. `None` on park and reject.
    #: This is a COPY when a downgrade was applied and the input object itself otherwise — the
    #: gate never mutates its argument, because a caller that logs the input after a rejected
    #: publish must log what it actually handed over.
    signal: QualifiedEnterpriseSignal | None = None
    #: V-1's output: the reviewable, recoverable record. `None` unless the outcome is PARK.
    parked: ParkedEvent | None = None
    #: The confidence the emitted signal carries, post-downgrade. Zero on park and reject,
    #: because nothing was published — a confidence attached to an unpublished object is a number
    #: that eventually gets read as if it had been.
    published_confidence_bp: int = 0
    #: How many basis points V-5 removed, 0 when nothing was downgraded. Stored as the delta
    #: rather than as the original, because the delta is the thing the policy owns and the
    #: original is still on the caller's own object.
    confidence_downgrade_bp: int = 0
    #: How many of `evidence_refs` did not resolve against real source text at L1.5.1 (ALG-08).
    #: The spans themselves stay on the signal (`unverified_spans`) so the flag can name the
    #: quote a human should go look at; only the count is duplicated here, for the row.
    unverified_span_count: int = 0

    @property
    def should_emit(self) -> bool:
        """The single question a publisher asks. Never `not decision.failures` — a V-5 failure
        is a failure that still emits, and reading the list instead of this property is exactly
        how the one non-blocking rule quietly becomes blocking."""
        return self.outcome is PublicationOutcome.EMIT

    @property
    def failed_rules(self) -> tuple[PublicationRule, ...]:
        """Just the ids, in V-order — what a ledger row stores in its rule column."""
        return tuple(failure.rule for failure in self.failures)

    @property
    def blocking_rules(self) -> tuple[PublicationRule, ...]:
        """The failures that actually stopped the emit. Distinct from `failed_rules` by V-5."""
        return tuple(failure.rule for failure in self.failures if failure.blocking)


def downgrade_for_unverified(confidence_bp: int, *, total_spans: int, verified_spans: int) -> int:
    """V-5's policy number, in integers: how far confidence falls when spans did not resolve.

    The shape of the rule is fixed by two things the documents already state. ALG-08 (L1.5.1)
    keeps a claim whose span could not be resolved at HALVED confidence, so half is the floor —
    an unverified receipt is not worthless, because the claim may be perfectly true and merely
    quoted loosely. And V-5 is non-blocking, so the ceiling is the composed confidence itself.
    Between those two, the fall is proportional to how much of the evidence failed::

        published = confidence_bp * (total + verified) // (2 * total)

    Every span unverified gives exactly ALG-08's halving; every span verified gives the number
    unchanged (and V-5 did not fire at all); half the spans unverified gives three quarters.
    Integer arithmetic with the multiply before the divide, so the result is deterministic and
    replays identically — a ratio here would be a float in the one field the whole document
    insists is basis points, and it would round differently on a different machine.

    Floor division rounds DOWN, which is the direction that cannot manufacture certainty: a
    downgrade that rounded up would, on the margins, publish a larger number than the policy
    says. Lives here rather than on the contract because it is a policy number — the boundary
    type every stored row was validated against must not carry one, or re-tuning the policy
    would retroactively invalidate rows.
    """
    confidence = require_bp(confidence_bp, "confidence_bp")
    total = require_ordinal(total_spans, "total_spans")
    verified = require_non_negative(verified_spans, "verified_spans")
    if verified > total:
        raise ValueError(
            f"verified_spans ({verified}) cannot exceed total_spans ({total}) — they count the "
            "same list")
    return confidence * (total + verified) // (2 * total)


def _refusal(rule: PublicationRule, check: Callable[[], Any]) -> RuleFailure | None:
    """Run one field-level check and turn its exception into a row instead of a stack unwind.

    The checks are the same `require_*` helpers the constructor uses — reused, not reimplemented,
    so the gate and the seam that produced the object can never disagree about what a valid value
    is. They raise, by design; this is the single place that translates that grammar into this
    module's. Only `TypeError` and `ValueError` are caught, which is the exact pair every helper
    in `validators.py` raises: anything else is a bug in the gate, and swallowing it here would
    turn "the publisher is broken" into "that signal was rejected".
    """
    try:
        check()
    except (TypeError, ValueError) as exc:
        return RuleFailure(rule=rule, detail=str(exc))
    return None


def _envelope_failure(signal: QualifiedEnterpriseSignal) -> RuleFailure | None:
    """V-1 — is the envelope complete, and is `visibility` actually there?

    Read defensively, with `getattr`, and that is not paranoia about the type annotation. A
    constructed `QualifiedEnterpriseSignal` cannot fail this rule — `visibility` is non-optional
    and the three ids are validated — but pydantic offers two documented ways round the
    constructor that this codebase's own contracts call out by name: `model_construct()` and
    `model_copy(update=...)`, neither of which runs a validator. V-1 exists precisely so that an
    object which took one of those routes is parked rather than published, and a check that
    trusted the annotation would be a rule that only ever passes.

    All four parts are checked, and any of them failing parks under `visibility_unknown` — the
    doc gives V-1 one reason code, so the detail line is what says which part was missing.
    """
    problems: list[str] = []

    org_id = getattr(signal, "org_id", None)
    if not isinstance(org_id, str) or not org_id.strip():
        problems.append("org_id is missing — nothing can be tenant-scoped without it")

    trace_id = getattr(signal, "trace_id", None)
    if not isinstance(trace_id, str) or not trace_id.strip():
        problems.append("trace_id is missing — the signal could not be explained backwards")

    schema_version = getattr(signal, "schema_version", None)
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) \
            or schema_version < 1:
        problems.append(
            f"schema_version must be a positive integer, got {schema_version!r} — a row that "
            "cannot name the contract it was written against cannot be read back")

    visibility = getattr(signal, "visibility", None)
    if not isinstance(visibility, Visibility):
        problems.append(
            "visibility is not established — the audience of a derived insight can never be "
            "wider than the audience of its evidence, and L1 is the last layer that knows it")

    if not problems:
        return None
    return RuleFailure(rule=PublicationRule.V1, detail="; ".join(problems))


def _park(signal: QualifiedEnterpriseSignal, failure: RuleFailure) -> ParkedEvent:
    """Turn a V-1 failure into the reviewable record. Parked is not deleted.

    The identity fields are read with `getattr` and coerced to text for the same reason V-1
    reads them that way: the object that fails this rule is by definition one that skipped a
    constructor, so `event_id` may be absent. A park row with a blank `event_id` is still
    reviewable — it carries the org, the source and the reason — while raising here would
    destroy the one artifact the rule exists to produce.

    The trace entry mirrors the shape `capture/parked/store.parked_from_trace` writes
    (`stage` / `action` / `reason`) so both producers land in one readable column, and adds the
    rule id and detail, which are what a reviewer needs to know what to go fix.
    """
    return ParkedEvent(
        event_id=str(getattr(signal, "event_id", "") or ""),
        org_id=str(getattr(signal, "org_id", "") or ""),
        source=str(getattr(signal, "source", "") or ""),
        reason_code=VISIBILITY_UNKNOWN,
        stage=PUBLICATION_STAGE,
        trace=[{"stage": PUBLICATION_STAGE, "action": "park", "reason": VISIBILITY_UNKNOWN,
                "rule": failure.rule.value, "detail": failure.detail}],
    )


def _unverified(signal: QualifiedEnterpriseSignal) -> list[EvidenceSpan]:
    """V-5's read, defensively: which spans did L1.5.1 not resolve against real source text?

    `QualifiedEnterpriseSignal.unverified_spans` says the same thing and is the sanctioned read;
    it is not used here only because this function must also survive an `evidence_refs` that a
    bypassed construction left as `None`, which the property would raise on before V-4 ever got
    the chance to reject it for exactly that.
    """
    spans = getattr(signal, "evidence_refs", None) or ()
    return [span for span in spans if getattr(span, "verified", False) is not True]


def validate_publication(
    signal: QualifiedEnterpriseSignal,
    *,
    source_confidences: Sequence[int] = (),
    independent_evidence: Sequence[str] = (),
) -> PublicationDecision:
    """Run V-1..V-7 and return what to do about it. Never raises for an expected rejection.

    ``source_confidences`` is V-6's ceiling: the confidences of the sources this signal's
    ``confidence_bp`` was composed FROM (ALG-13, Rule 11, L1.5.7). Empty means the rule does not
    apply — there is no ceiling to respect — which a caller must read as "V-6 was not in play"
    rather than as "V-6 passed". Passing the composed confidence back in as its own source would
    make the rule trivially true, so the list is the sources, never the result.

    ``independent_evidence`` is the exception the rule itself names: composition may exceed the
    weakest source when independent evidence is EXPLICITLY named, because two genuinely separate
    sources agreeing is corroboration while two copies of one weak source agreeing is an echo.
    Naming it waives V-6 and is recorded on the decision, since a waiver nobody can see is a
    ceiling that was never really there. Only the caller can tell an independent source from a
    copy of one, which is why the contract cannot decide this and the publisher must.

    Order is V-1 first and alone: a park short-circuits, because every rule after it reads an
    envelope V-1 has just established is not there. The remaining rules are all evaluated even
    once one has failed, so a rejection row names every broken thing rather than the first —
    fixing them one release apart is how a pipeline stays broken for three releases.

    PRECONDITION, stated because V-5 is where it bites: ``signal`` is expected to have been built
    through the contract's constructor, which range-checks ``confidence_bp``. The V-5 downgrade
    calls ``require_bp`` on it, so an object that skipped the constructor AND carries a
    non-basis-point confidence raises here. That is a programming error rather than an expected
    rejection — the object could not have come from the qualification pipeline — and it is the
    one input this gate refuses to launder into a row.
    """
    envelope = _envelope_failure(signal)
    if envelope is not None:
        return PublicationDecision(outcome=PublicationOutcome.PARK, failures=(envelope,),
                                   parked=_park(signal, envelope))

    #: `None` entries are the rules that PASSED — `_refusal` returns one row or nothing, and
    #: filtering once at the end keeps the seven checks reading in V-order down the page.
    failures: list[RuleFailure | None] = []
    waived: list[PublicationRule] = []

    # V-2 — the closed 14. `require_enum` is reused rather than an `isinstance` check so a
    # bypassed construction that left the literal wire string in place still passes when the
    # string IS one of the members: the rule is membership of the set, not identity of the type.
    failures.append(_refusal(
        PublicationRule.V2,
        lambda: require_enum(getattr(signal, "signal_type", None), SignalType, "signal_type")))

    # V-3 — importance is basis points. `require_bp` already refuses a bool and a non-int, so a
    # 0.87 that pydantic's lax mode would have rounded to 0 is caught as the float it is.
    failures.append(_refusal(
        PublicationRule.V3,
        lambda: require_bp(getattr(signal, "importance_bp", None), "importance_bp")))

    # V-4 — a claim with no receipt is a guess. Checked here as well as at construction because
    # this is the seam that has to record WHY nothing was published.
    if not (getattr(signal, "evidence_refs", None) or ()):
        failures.append(RuleFailure(
            rule=PublicationRule.V4,
            detail="evidence_refs is empty — a claim with no receipt is a guess, and a guess "
                   "must not reach a human wearing the same typography as a fact"))

    # V-5 — non-blocking. Evaluated unconditionally so the failure is recorded even on a signal
    # that some other rule rejects; the DOWNGRADE below is applied only if we go on to emit,
    # because lowering the confidence of something nobody publishes changes nothing but the row.
    unverified = _unverified(signal)
    if unverified:
        failures.append(RuleFailure(
            rule=PublicationRule.V5,
            detail=f"{len(unverified)} of {len(signal.evidence_refs)} evidence spans did not "
                   f"resolve against source text at L1.5.1 (first: {unverified[0].quote!r}) — "
                   "confidence downgraded and the signal flagged, not dropped"))

    # V-6 — Rule 11's ceiling, unless independent evidence is explicitly named. The arithmetic
    # lives on the contract (`confidence_respects_sources`) and is called, not copied; it runs
    # `require_bp` over each source confidence, so a ratio in the caller's list is refused as the
    # V-6 failure it is rather than silently becoming a smaller ceiling.
    independent = require_strings(independent_evidence, "independent evidence")
    if independent:
        waived.append(PublicationRule.V6)
    else:
        sources = list(source_confidences or ())

        def _check_ceiling() -> None:
            if not signal.confidence_respects_sources(sources):
                raise ValueError(
                    f"confidence_bp {signal.confidence_bp} exceeds the weakest source it was "
                    f"composed from ({min(sources)}) and no independent evidence was named — "
                    "several weak sources repeating one weak thing is not corroboration")

        failures.append(_refusal(PublicationRule.V6, _check_ceiling))

    # V-7 — no float anywhere. `require_no_float` walks the live object rather than
    # `model_dump()`: it has a BaseModel branch and mirrors `platform.canonical`'s accept-list,
    # so it reaches every value a dump would emit without paying for a second copy of the whole
    # object — and it sees what `mode="json"` would have quietly coerced on the way out.
    failures.append(_refusal(PublicationRule.V7, lambda: require_no_float(signal, "signal")))

    recorded = tuple(failure for failure in failures if failure is not None)
    blocking = [failure for failure in recorded if failure.blocking]
    if blocking:
        return PublicationDecision(outcome=PublicationOutcome.REJECT, failures=recorded,
                                   waived=tuple(waived),
                                   unverified_span_count=len(unverified))

    published = signal
    downgrade = 0
    if unverified:
        lowered = downgrade_for_unverified(
            signal.confidence_bp,
            total_spans=len(signal.evidence_refs),
            verified_spans=len(signal.evidence_refs) - len(unverified))
        downgrade = signal.confidence_bp - lowered
        # A copy, because the gate must not mutate its argument: the caller logs what it handed
        # over. `model_copy` alone would skip validation, so the new value is ASSIGNED — the
        # contract sets `validate_assignment=True` for exactly this, and the assignment re-runs
        # `require_bp` on the downgraded number instead of trusting the arithmetic above.
        published = signal.model_copy(deep=True)
        published.confidence_bp = lowered

    return PublicationDecision(
        outcome=PublicationOutcome.EMIT,
        failures=recorded,
        waived=tuple(waived),
        flags=(UNVERIFIED_EVIDENCE_FLAG,) if unverified else (),
        signal=published,
        published_confidence_bp=published.confidence_bp,
        confidence_downgrade_bp=downgrade,
        unverified_span_count=len(unverified))


__all__ = ["NON_BLOCKING_RULES", "PARKING_RULES", "PUBLICATION_STAGE", "UNVERIFIED_EVIDENCE_FLAG",
           "VISIBILITY_UNKNOWN", "PublicationDecision", "PublicationOutcome", "PublicationRule",
           "RuleFailure", "downgrade_for_unverified", "validate_publication"]
