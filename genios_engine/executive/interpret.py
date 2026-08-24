"""Layer 5 · Unit 1 — the Decision Interpreter.

Layer 4 hands over a ``ReasoningDecision``: an outcome, a ranked set of candidates, a
confidence, an expiry, and a sentence about what happens if nobody moves.  That is a
*judgement*.  Before anything can be planned, it has to be read as an *instruction*: what is
being committed to, about which entity, under what constraints, and does a human have to be
in the loop.

This unit does exactly that translation and nothing else.  It is the layer's front door, and
front doors are where fail-closed matters most:

* Only ``DecisionOutcome.DECISION`` produces an execution context.  ``no_action`` means the
  reasoner looked and concluded nothing should happen — turning that into a task would be the
  system inventing work.  ``defer``, ``blocked``, ``insufficient_context`` and ``failed``
  likewise describe a *non*-commitment, and each gets its own refusal code so the operator can
  tell "we decided not to" apart from "we could not decide".
* A selected candidate with no declared steps is refused rather than padded.  A commitment
  whose steps GeniOS made up is not traceable to a pack, and the whole execution chain rests
  on the pack being the author of what a human is asked to do.

**Time and world-state are deliberately not checked here.**  Interpretation is structural: it
asks "is this decision shaped like an instruction?".  Whether the instruction is still worth
acting on — expired, superseded, already satisfied by something that happened since — belongs
to the Execution Validation Unit, which runs against live context immediately before delivery.
Splitting them means a decision can be interpreted and planned deterministically from stored
bytes alone, and re-validated cheaply as often as we like.

Pure: no clock, no database, no model.  Same decision in, same context out, forever.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.reasoning import (
    CandidateDisposition,
    DecisionCandidate,
    DecisionOutcome,
    ReasoningDecision,
)
from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_identifier,
    require_sorted_unique,
    require_strings,
    require_text,
)

INTERPRETER_VERSION = "interpret.v1"

#: Play metadata key declaring how far GeniOS may go on its own.  ``human_approval_required``
#: is the only value the shipped packs use; anything unrecognised is treated as the strictest
#: reading, because a boundary we do not understand is not a boundary we may cross.
EXECUTION_BOUNDARY_KEY = "execution_boundary"
AUTONOMOUS_BOUNDARY = "autonomous"

#: Play tags that independently demand a human gate, regardless of the boundary declaration.
HUMAN_GATE_TAGS: frozenset[str] = frozenset({"human_approval", "approval", "review"})


class ExecutionType(str, Enum):
    """What kind of work this commitment is, which shapes planning and channel choice.

    Derived from what the play *declares* — its artifact kind, tags and recipient flag — never
    from reading the step text with a model.  Two plays with identical declarations always
    classify identically, which is what makes the downstream plan reproducible.
    """

    COMMUNICATION = "communication"          # something must reach a person outside GeniOS
    TASK = "task"                            # internal work with a deliverable
    DECISION_REQUIRED = "decision_required"  # a human must choose before anything moves
    MONITORING = "monitoring"                # watch and report; no action today


class RefusalCode(str, Enum):
    """Why a decision produced no execution context.

    Enumerated rather than free text so the refusal rate per code is a metric: a spike in
    ``no_steps`` is a pack authoring bug, a spike in ``outcome_no_action`` is the reasoner
    working correctly, and a single "could not interpret" counter would hide both.
    """

    OUTCOME_NO_ACTION = "outcome_no_action"
    OUTCOME_DEFER = "outcome_defer"
    OUTCOME_BLOCKED = "outcome_blocked"
    OUTCOME_INSUFFICIENT_CONTEXT = "outcome_insufficient_context"
    OUTCOME_FAILED = "outcome_failed"
    NO_SELECTED_CANDIDATE = "no_selected_candidate"
    CANDIDATE_NOT_ELIGIBLE = "candidate_not_eligible"
    NO_STEPS = "no_steps"


_OUTCOME_REFUSALS: Mapping[DecisionOutcome, RefusalCode] = MappingProxyType({
    DecisionOutcome.NO_ACTION: RefusalCode.OUTCOME_NO_ACTION,
    DecisionOutcome.DEFER: RefusalCode.OUTCOME_DEFER,
    DecisionOutcome.BLOCKED: RefusalCode.OUTCOME_BLOCKED,
    DecisionOutcome.INSUFFICIENT_CONTEXT: RefusalCode.OUTCOME_INSUFFICIENT_CONTEXT,
    DecisionOutcome.FAILED: RefusalCode.OUTCOME_FAILED,
})


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """The decision, restated as an instruction the planner can act on.

    Stays inside ``executive/`` on purpose.  It is scaffolding between this layer's own units,
    not a cross-layer artifact — only the finished ``ExecutionObject`` leaves the layer, and
    keeping the intermediate out of ``contracts/`` means it can be reshaped without a contract
    migration.
    """

    org_id: str
    goal: str
    steps: tuple[str, ...]
    execution_type: ExecutionType
    capability_id: str
    capability_version: str
    play_id: str
    play_version: str
    decision_hash: str
    candidate_id: str
    context_snapshot_id: str
    reasoning_run_id: str
    config_snapshot_id: str
    expires_at: datetime
    do_nothing_consequence: str
    priority_bp: int
    confidence_bp: int
    urgency_bp: int
    window_days: int
    read_only: bool
    requires_human: bool
    external_recipient_required: bool
    tags: tuple[str, ...] = ()
    success_events: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    subject_ref: str | None = None
    subject_type: str | None = None
    subject_label: str | None = None
    play_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "org_id", require_identifier(self.org_id, "org id"))
        setattr_(self, "goal", require_text(self.goal, "goal"))
        setattr_(self, "steps", require_strings(self.steps, "step"))
        setattr_(self, "tags", require_sorted_unique(self.tags, "tag"))
        setattr_(self, "success_events",
                 require_sorted_unique(self.success_events, "success event"))
        setattr_(self, "constraints", require_sorted_unique(self.constraints, "constraint"))
        setattr_(self, "evidence_ids", require_sorted_unique(self.evidence_ids, "evidence id"))
        setattr_(self, "expires_at", require_aware(self.expires_at, "expires_at"))
        setattr_(self, "play_metadata", freeze_mapping(self.play_metadata))
        if not self.steps:
            raise ValueError("an execution context needs at least one declared step")

    @property
    def artifact_kind(self) -> str:
        return str(self.play_metadata.get("artifact_kind", "draft"))

    @property
    def interactive(self) -> bool:
        """True when a person has to do something, as opposed to merely be told something."""
        return self.execution_type is not ExecutionType.MONITORING


@dataclass(frozen=True, slots=True)
class Interpretation:
    """Either an instruction, or a named reason there is none.  Never an exception.

    Refusal is the common path — most decisions in a healthy sweep are ``no_action`` — so it is
    modelled as a value.  Exceptions would make the ordinary case expensive and, worse, would
    tempt a caller into a bare ``except`` that swallowed the genuinely broken ones too.
    """

    context: ExecutionContext | None
    reason_code: str
    detail: str

    @property
    def actionable(self) -> bool:
        return self.context is not None

    def require(self) -> ExecutionContext:
        if self.context is None:
            raise ValueError(f"decision is not actionable: {self.reason_code} — {self.detail}")
        return self.context


def _selected(decision: ReasoningDecision) -> DecisionCandidate | None:
    return next((candidate for candidate in decision.candidates
                 if candidate.candidate_id == decision.selected_candidate_id), None)


def classify_execution_type(*, tags: tuple[str, ...], metadata: Mapping[str, Any],
                            requires_human: bool,
                            external_recipient_required: bool) -> ExecutionType:
    """Declared facts in, category out.  Ordered most-specific first.

    ``DECISION_REQUIRED`` outranks ``COMMUNICATION`` because a draft awaiting approval is not
    yet a message: routing it as one would page a recipient about something the owner has not
    agreed to send.  ``MONITORING`` is only reachable when nothing is drafted and nobody is
    written to — otherwise "monitor" is a step *within* a task, not the shape of the task.
    """
    artifact = str(metadata.get("artifact_kind", "")).strip().lower()
    if external_recipient_required and requires_human:
        return ExecutionType.DECISION_REQUIRED
    if external_recipient_required:
        return ExecutionType.COMMUNICATION
    if requires_human and (artifact.startswith("draft") or "draft" in tags):
        return ExecutionType.DECISION_REQUIRED
    if artifact.startswith("draft") or "draft" in tags:
        return ExecutionType.COMMUNICATION
    if "monitor" in artifact or "monitor" in tags or "watch" in tags:
        return ExecutionType.MONITORING
    return ExecutionType.TASK


def requires_human_gate(*, tags: tuple[str, ...], metadata: Mapping[str, Any],
                        read_only: bool) -> bool:
    """Fails closed in three independent ways, and any one of them is enough.

    A pack author who forgets the boundary key still gets a gate; a pack author who writes an
    unrecognised boundary value still gets a gate; and a play that is not read-only always gets
    a gate no matter what it declares, because a play that changes the outside world without a
    human in front of it is the one failure mode with no undo.
    """
    if not read_only:
        return True
    boundary = str(metadata.get(EXECUTION_BOUNDARY_KEY, "")).strip().lower()
    if boundary != AUTONOMOUS_BOUNDARY:
        return True
    return bool(HUMAN_GATE_TAGS & set(tags))


def build_context(*, org_id: str, parameters: Mapping[str, Any], capability_id: str,
                  capability_version: str, play_id: str, play_version: str, decision_hash: str,
                  candidate_id: str, context_snapshot_id: str, reasoning_run_id: str,
                  config_snapshot_id: str, expires_at: datetime, do_nothing_consequence: str,
                  priority_bp: int, confidence_bp: int, urgency_bp: int | None = None,
                  outcome_window_days: int | None = None, uncertainty: tuple[str, ...] = (),
                  evidence_ids: tuple[str, ...] = (), subject_ref: str | None = None,
                  subject_type: str | None = None,
                  subject_label: str | None = None) -> Interpretation:
    """Read a selected play's declared parameters as an instruction.

    Split out from ``interpret_decision`` because Layer 5 reaches its decisions two ways: from a
    live ``ReasoningDecision`` object in the same process, and from the immutable audit rows a
    sweep reads hours later.  Both must produce a byte-identical context or the same decision
    would yield two different commitments depending on which path found it first — so both go
    through this one function rather than through two similar-looking ones.
    """
    steps = require_strings(parameters.get("steps", ()), "step")
    if not steps:
        return Interpretation(None, RefusalCode.NO_STEPS.value,
                              f"play {play_id}@{play_version} declares no steps; "
                              "GeniOS will not invent them")

    tags = require_sorted_unique(parameters.get("tags", ()), "tag")
    metadata = dict(parameters.get("metadata", {}) or {})
    read_only = bool(parameters.get("read_only", True))
    requires_human = requires_human_gate(tags=tags, metadata=metadata, read_only=read_only)
    external = bool(metadata.get("external_recipient_required", False))

    # `window_days` is the play's declared outcome window; the decision may narrow it. The
    # tighter of the two wins, because widening a window here would let Layer 5 keep chasing
    # an outcome past the point Layer 4 agreed to stand behind it.
    play_window = int(parameters.get("window_days", 0) or 0)
    decision_window = int(outcome_window_days or 0)
    windows = tuple(value for value in (play_window, decision_window) if value > 0)

    context = ExecutionContext(
        org_id=org_id,
        goal=require_text(parameters.get("label") or play_id, "goal"),
        steps=steps,
        execution_type=classify_execution_type(
            tags=tags, metadata=metadata, requires_human=requires_human,
            external_recipient_required=external),
        capability_id=capability_id,
        capability_version=capability_version,
        play_id=play_id,
        play_version=play_version,
        decision_hash=decision_hash,
        candidate_id=candidate_id,
        context_snapshot_id=context_snapshot_id,
        reasoning_run_id=reasoning_run_id,
        config_snapshot_id=config_snapshot_id,
        expires_at=expires_at,
        do_nothing_consequence=do_nothing_consequence,
        priority_bp=priority_bp,
        confidence_bp=confidence_bp,
        # Urgency has its own component in the ranking weights; when a capability does not
        # publish one, utility is the honest stand-in — it is the number that ordered the queue.
        urgency_bp=int(urgency_bp if urgency_bp is not None else priority_bp),
        window_days=min(windows) if windows else 7,
        read_only=read_only,
        requires_human=requires_human,
        external_recipient_required=external,
        tags=tags,
        success_events=require_sorted_unique(parameters.get("success_events", ()), "event"),
        # Everything the reasoner was unsure about travels with the instruction. The planner
        # cannot resolve these, but the human doing the work is entitled to see them, and the
        # guard uses them to decide how hard to re-check before delivery.
        constraints=uncertainty,
        evidence_ids=evidence_ids,
        subject_ref=subject_ref,
        subject_type=subject_type,
        subject_label=subject_label,
        play_metadata=metadata,
    )
    return Interpretation(context, "interpreted",
                          f"{play_id}@{play_version} → {context.execution_type.value}")


def interpret_decision(decision: ReasoningDecision, *, org_id: str, reasoning_run_id: str,
                       config_snapshot_id: str, decision_hash: str,
                       subject_ref: str | None = None, subject_type: str | None = None,
                       subject_label: str | None = None) -> Interpretation:
    """Read one Layer 4 decision as an instruction, or say precisely why it is not one."""
    refusal = _OUTCOME_REFUSALS.get(decision.outcome)
    if refusal is not None:
        return Interpretation(None, refusal.value,
                              f"{decision.capability_id} returned {decision.outcome.value}")
    candidate = _selected(decision)
    if candidate is None:
        # Unreachable through the contract's own validation, which already refuses a DECISION
        # without a selected candidate.  Kept because this module is also the entry point for
        # decisions rehydrated from storage, where the guarantee is only as good as the row.
        return Interpretation(None, RefusalCode.NO_SELECTED_CANDIDATE.value,
                              "decision outcome is 'decision' but no candidate is selected")
    if candidate.disposition is not CandidateDisposition.ELIGIBLE:
        return Interpretation(None, RefusalCode.CANDIDATE_NOT_ELIGIBLE.value,
                              f"selected candidate {candidate.play_id} is "
                              f"{candidate.disposition.value}")

    return build_context(
        org_id=org_id, parameters=candidate.parameters,
        capability_id=decision.capability_id,
        capability_version=decision.capability_version,
        play_id=candidate.play_id, play_version=candidate.play_version,
        decision_hash=decision_hash, candidate_id=candidate.candidate_id,
        context_snapshot_id=decision.context_snapshot_id,
        reasoning_run_id=reasoning_run_id, config_snapshot_id=config_snapshot_id,
        expires_at=decision.expires_at,
        do_nothing_consequence=decision.do_nothing_consequence,
        priority_bp=candidate.utility_bp, confidence_bp=decision.confidence_bp,
        urgency_bp=int(candidate.score_components.get("urgency", candidate.utility_bp)),
        outcome_window_days=decision.outcome_window_days,
        uncertainty=decision.uncertainty, evidence_ids=candidate.evidence_ids,
        subject_ref=subject_ref, subject_type=subject_type, subject_label=subject_label)


__all__ = ["AUTONOMOUS_BOUNDARY", "EXECUTION_BOUNDARY_KEY", "HUMAN_GATE_TAGS",
           "INTERPRETER_VERSION", "ExecutionContext", "ExecutionType", "Interpretation",
           "RefusalCode", "build_context", "classify_execution_type", "interpret_decision",
           "requires_human_gate"]
