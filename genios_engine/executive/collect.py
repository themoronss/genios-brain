"""Layer 5 · Unit 10 — the Feedback Collection Unit.

Layer 7 currently learns from one source: what a human clicked on a card.  That is a good
signal and a narrow one — it measures whether a recommendation *looked* right at the moment it
arrived, which is not the same as whether acting on it worked.  A card everybody clicks and
nobody ever completes is, by the click metric, a triumph.

This unit closes that gap.  When a commitment reaches a terminal state it emits an outcome
record: what was recommended, what was committed to, how far it got, how much attention it cost
along the way, and whether the world produced the evidence the play declared as success.  That
record is the honest unit of learning, and it is something only this layer can produce, because
only this layer watched the commitment for its whole life.

Direction of travel matters.  Layer 5 **emits**; Layer 7 **reads**.  Nothing here imports
``feedback`` — a lower layer importing a higher one is exactly what the topology ratchet exists
to prevent, and it would also invert the dependency in the one place where the consumer should
be free to change its mind about what it wants to learn.

The label taxonomy below is the deliberate output.  Counting terminal states would flatten four
genuinely different endings into "not completed"; the distinction between *we ran out of time*
and *the deal closed while we were drafting* is the entire difference between "shorten the
window" and "this play was fine, the world moved on".

Pure: a closed commitment in, a record out.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.execution import ExecutionObject, ExecutionState
from genios_engine.contracts.validators import freeze_mapping, require_aware, require_identifier
from genios_engine.executive.monitor import ProgressReport
from genios_engine.platform.canonical import semantic_hash

COLLECT_VERSION = "collect.v1"

#: How an ending should be read by anything that learns from it.
#:
#: ``succeeded`` is the only label that proves the play works, because it is the only one backed
#: by evidence the system did not generate itself.  ``completed_unproven`` is kept separate on
#: purpose: a play that people finish but that never produces its declared outcome is the single
#: most expensive failure mode in a recommendation system, and merging it into ``succeeded``
#: would make it permanently invisible.
LABEL_SUCCEEDED = "succeeded"
LABEL_COMPLETED_UNPROVEN = "completed_unproven"
LABEL_EXPIRED_UNTOUCHED = "expired_untouched"
LABEL_EXPIRED_IN_PROGRESS = "expired_in_progress"
LABEL_CANCELLED_BY_HUMAN = "cancelled_by_human"
LABEL_CANCELLED_BY_WORLD = "cancelled_by_world"
LABEL_CANCELLED_BY_SYSTEM = "cancelled_by_system"

#: Guard reason codes grouped by *who or what* ended the commitment.  The grouping is what makes
#: the label actionable: a spike in "by human" is a relevance problem the pack can fix, a spike
#: in "by world" is usually correct behaviour, and a spike in "by system" is an incident.
_CANCEL_BY_HUMAN = frozenset({"human_dismissed"})
_CANCEL_BY_WORLD = frozenset({"subject_closed", "subject_missing", "superseded"})


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    """The record Layer 7 learns from.  One per closed commitment, immutable, hashable.

    Deliberately flat and self-contained.  A learner that has to join back to five tables to
    interpret a row will eventually interpret it wrong; everything needed to attribute this
    outcome to a pack, a play, a band and a routing rule is carried on the record itself.
    """

    org_id: str
    execution_id: str
    decision_hash: str
    capability_id: str
    capability_version: str
    play_id: str
    play_version: str
    terminal_state: ExecutionState
    reason_code: str
    label: str
    created_at: datetime
    closed_at: datetime
    seconds_to_close: int
    actions_total: int
    actions_completed: int
    progress_bp: int
    reminders_sent: int
    escalations_fired: int
    priority_bp: int
    confidence_bp: int
    band: str
    routing_rule: str
    outcome_kind: str | None = None
    outcome_observed_at: datetime | None = None
    assignee: str | None = None
    subject_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "org_id", require_identifier(self.org_id, "org id"))
        setattr_(self, "execution_id", require_identifier(self.execution_id, "execution id"))
        setattr_(self, "created_at", require_aware(self.created_at, "created_at"))
        setattr_(self, "closed_at", require_aware(self.closed_at, "closed_at"))
        if self.outcome_observed_at is not None:
            setattr_(self, "outcome_observed_at",
                     require_aware(self.outcome_observed_at, "outcome_observed_at"))
        setattr_(self, "metadata", freeze_mapping(self.metadata))
        if self.closed_at < self.created_at:
            raise ValueError("a commitment cannot close before it was created")

    @property
    def positive(self) -> bool:
        """Whether this outcome is evidence *for* the play.

        Only proven success counts.  Treating ``completed_unproven`` as positive would let a
        play train its own confidence upward on the strength of people ticking boxes.
        """
        return self.label == LABEL_SUCCEEDED

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "execution_id": self.execution_id,
                "decision_hash": self.decision_hash, "capability_id": self.capability_id,
                "capability_version": self.capability_version, "play_id": self.play_id,
                "play_version": self.play_version,
                "terminal_state": self.terminal_state.value, "reason_code": self.reason_code,
                "label": self.label, "created_at": self.created_at, "closed_at": self.closed_at,
                "seconds_to_close": self.seconds_to_close, "actions_total": self.actions_total,
                "actions_completed": self.actions_completed, "progress_bp": self.progress_bp,
                "reminders_sent": self.reminders_sent,
                "escalations_fired": self.escalations_fired, "priority_bp": self.priority_bp,
                "confidence_bp": self.confidence_bp, "band": self.band,
                "routing_rule": self.routing_rule, "outcome_kind": self.outcome_kind,
                "outcome_observed_at": self.outcome_observed_at, "assignee": self.assignee,
                "subject_ref": self.subject_ref, "metadata": self.metadata}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


#: ── WHAT A LABEL SAYS ABOUT THE RECOMMENDATION ───────────────────────────────────────────────
#: The labels above record HOW an execution ended. Whether that ending is evidence about the
#: RECOMMENDATION is a second, different question, and until this table existed every consumer
#: answered it by hand — with `else: failed`.
#:
#: THE COST OF THAT, measured in `feedback/units.py`. `unit_recommendation_learning` writes to
#: `LearningTarget.ADAPTIVE` — it changes the brain — and counted `negative = n - succeeded`. So a
#: play was penalised for `completed_unproven` (it worked; we cannot prove it), for
#: `expired_in_progress` (somebody was actively working on it), for `cancelled_by_world` (the
#: situation resolved itself) and for `cancelled_by_system` (our own tooling cancelled it). Two of
#: those are the inventory's LRN-01 and LRN-07 exactly, in the one unit that actually alters
#: behaviour.
#:
#: FOUR CLASSES, because three is not enough. `MECHANICAL` is separated from `NEUTRAL` on purpose:
#: both must stay out of the recommendation's score, and only one of them means something is
#: BROKEN. Folding them together would hide a play whose tooling fails every time behind a shrug.
LABEL_POSITIVE: frozenset[str] = frozenset({LABEL_SUCCEEDED})

#: Endings that are genuinely evidence against the recommendation. Nobody touched it before it
#: expired, or a human looked at it and cancelled it — both are the reader telling us something.
LABEL_NEGATIVE: frozenset[str] = frozenset({LABEL_EXPIRED_UNTOUCHED, LABEL_CANCELLED_BY_HUMAN})

#: Endings that say nothing either way. The work may well have been done — `completed_unproven` is
#: the case where it demonstrably was and no source can prove it — or the world moved underneath a
#: recommendation that was correct when it was made.
LABEL_NEUTRAL: frozenset[str] = frozenset({LABEL_COMPLETED_UNPROVEN, LABEL_EXPIRED_IN_PROGRESS,
                                           LABEL_CANCELLED_BY_WORLD})

#: Endings caused by our own machinery. Never evidence about the recommendation, and never
#: invisible: a play cancelled by the system every time is a real defect, it is simply a defect in
#: the tooling and must be counted as one.
LABEL_MECHANICAL: frozenset[str] = frozenset({LABEL_CANCELLED_BY_SYSTEM})


def label_class(label: str | None) -> str:
    """`positive` | `negative` | `neutral` | `mechanical` — or `unknown`.

    `unknown` is returned rather than defaulting to negative, and that direction is the whole
    point: a label this table has not been taught must not silently penalise a play. The drift
    test in `tests/executive/` fails when a new label arrives unclassified.
    """
    value = str(label or "").strip()
    if value in LABEL_POSITIVE:
        return "positive"
    if value in LABEL_NEGATIVE:
        return "negative"
    if value in LABEL_NEUTRAL:
        return "neutral"
    if value in LABEL_MECHANICAL:
        return "mechanical"
    return "unknown"


def counts_against_the_play(label: str | None) -> bool:
    """Whether this ending is evidence the recommendation was wrong."""
    return label_class(label) == "negative"


def classify_outcome(*, terminal_state: ExecutionState, reason_code: str,
                     outcome_kind: str | None, progress_bp: int) -> str:
    """Terminal state plus cause plus progress → a label something can learn from."""
    if terminal_state is ExecutionState.COMPLETED:
        return LABEL_SUCCEEDED if outcome_kind else LABEL_COMPLETED_UNPROVEN
    if terminal_state is ExecutionState.EXPIRED:
        return LABEL_EXPIRED_UNTOUCHED if progress_bp == 0 else LABEL_EXPIRED_IN_PROGRESS
    if terminal_state is ExecutionState.CANCELLED:
        if reason_code in _CANCEL_BY_HUMAN:
            return LABEL_CANCELLED_BY_HUMAN
        if reason_code in _CANCEL_BY_WORLD:
            return LABEL_CANCELLED_BY_WORLD
        return LABEL_CANCELLED_BY_SYSTEM
    return LABEL_CANCELLED_BY_SYSTEM


def collect_outcome(execution: ExecutionObject, *, terminal_state: ExecutionState,
                    reason_code: str, closed_at: datetime, report: ProgressReport,
                    reminders_sent: int = 0, escalations_fired: int = 0,
                    extra: Mapping[str, Any] | None = None) -> ExecutionOutcome:
    """Build the outcome record for a commitment that has just ended.

    Note what is recorded alongside the result: reminders sent and escalations fired.  Those are
    the *cost* of the recommendation in human attention, and an outcome without a cost is only
    half a data point — a play that succeeds once per four reminders and one escalation is not
    obviously better than one that quietly fails.
    """
    metadata = dict(execution.metadata)
    return ExecutionOutcome(
        org_id=execution.org_id,
        execution_id=execution.execution_id,
        decision_hash=execution.decision_hash,
        capability_id=execution.capability_id,
        capability_version=execution.capability_version,
        play_id=str(metadata.get("play_id") or execution.capability_id),
        play_version=str(metadata.get("play_version") or execution.capability_version),
        terminal_state=terminal_state,
        reason_code=reason_code,
        label=classify_outcome(terminal_state=terminal_state, reason_code=reason_code,
                               outcome_kind=report.outcome_kind, progress_bp=report.progress_bp),
        created_at=execution.created_at,
        closed_at=closed_at,
        seconds_to_close=max(0, int((closed_at - execution.created_at).total_seconds())),
        actions_total=len(execution.actions),
        actions_completed=len(report.completed_action_ids),
        progress_bp=report.progress_bp,
        reminders_sent=int(reminders_sent),
        escalations_fired=int(escalations_fired),
        priority_bp=execution.priority_bp,
        confidence_bp=execution.confidence_bp,
        band=str(metadata.get("band") or "standard"),
        routing_rule=str(metadata.get("routing_rule") or "unknown"),
        outcome_kind=report.outcome_kind,
        outcome_observed_at=report.outcome_observed_at,
        assignee=execution.communication.assignee,
        subject_ref=execution.subject_ref,
        metadata={"execution_type": metadata.get("execution_type"),
                  "artifact_kind": metadata.get("artifact_kind"),
                  "channel_id": execution.communication.channel_id,
                  "interrupt": execution.communication.interrupt,
                  "autonomy_allowed": execution.autonomy_allowed,
                  **dict(extra or {})},
    )


__all__ = ["COLLECT_VERSION", "LABEL_CANCELLED_BY_HUMAN", "LABEL_CANCELLED_BY_SYSTEM",
           "LABEL_CANCELLED_BY_WORLD", "LABEL_COMPLETED_UNPROVEN", "LABEL_EXPIRED_IN_PROGRESS",
           "LABEL_EXPIRED_UNTOUCHED", "LABEL_SUCCEEDED", "ExecutionOutcome", "classify_outcome",
           "collect_outcome"]
