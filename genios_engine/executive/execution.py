"""Layer 5 · Unit 10 — the Execution Object Builder.

Everything upstream produced a piece: an instruction, a plan, an owner, a channel, a ladder.
This is where they become the one artifact the layer is allowed to emit, and where the
composition is checked as a whole rather than piecewise.

The builder is the last place that can refuse cheaply.  Once an execution object exists it will
be stored, delivered, reminded on and escalated; a commitment that was already dead on arrival —
its window closed, its decision lapsed — costs a person's attention every day it survives.  So
the builder refuses by value, with a named code, rather than emitting something the guard will
have to kill a moment later.

**One decision, one commitment.**  ``ExecutionObject.execution_id`` is content-addressed over
``(org, decision hash, plan hash)``, so running the sweep twice over the same decision produces
the same id and the database's unique index absorbs the second write.  This is what makes the
whole layer safe to run on a timer: idempotence is a property of the artifact, not a flag
somebody remembered to check.

Pure.  Every input — the owner directory's answer, the org's channels, the clock — is passed in.
The SQL that gathers them lives in ``executive.execution_store``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.execution import EXECUTION_VERSION, ExecutionObject
from genios_engine.contracts.reasoning import ReasoningDecision
from genios_engine.contracts.visibility import Visibility
from genios_engine.executive.assignment import Assignment, SeatDirectory, resolve_owner
from genios_engine.executive.communication import band_of, plan_communication
from genios_engine.executive.escalation import build_ladder
from genios_engine.executive.interpret import ExecutionContext, interpret_decision
from genios_engine.executive.planning import plan_actions, plan_deadline, plan_is_autonomous

BUILDER_VERSION = "exec_build.v1"

#: Where the layer's tunables live inside the effective config.  Nested under ``scoring`` because
#: that is the block ``packs.merge`` actually merges, pins and guardrails — putting it anywhere
#: else would give tenants a config surface that silently ignores their overrides.
EXECUTION_CONFIG_KEY = "execution"


def execution_config(effective: Mapping[str, Any] | None) -> dict[str, Any]:
    """Pull the layer's config out of a tenant's effective pack config.

    Returns an empty mapping when absent, which every unit reads as "use the engine defaults".
    A missing block is the normal state for a pack that has not opted into tuning, not an error.
    """
    scoring = (effective or {}).get("scoring") or {}
    block = scoring.get(EXECUTION_CONFIG_KEY) or {}
    return dict(block) if isinstance(block, Mapping) else {}


@dataclass(frozen=True, slots=True)
class BuildResult:
    """An execution object, or a named reason there is none.

    Same shape as ``Interpretation`` and for the same reason: refusal is an expected outcome on
    a healthy sweep, so it is a value to be counted, not an exception to be caught.
    """

    execution: ExecutionObject | None
    reason_code: str
    detail: str

    @property
    def built(self) -> bool:
        return self.execution is not None

    def require(self) -> ExecutionObject:
        if self.execution is None:
            raise ValueError(f"no execution object: {self.reason_code} — {self.detail}")
        return self.execution


def build_execution(context: ExecutionContext, *, assignment: Assignment, eval_time: datetime,
                    available_channels: frozenset[str] | set[str] | None = None,
                    cfg: Mapping[str, Any] | None = None,
                    visibility: Visibility | Mapping[str, Any] | None = None) -> BuildResult:
    """Compose the units into one commitment, or refuse with a reason.

    The order matters.  Planning runs before routing because the plan decides whether the work
    is autonomous, and autonomy decides whether a human is routed to at all.  The ladder runs
    last because it is capped by the same expiry the plan is capped by, and building it against
    an unvalidated deadline would produce rungs that the contract then rejects.
    """
    settings = dict(cfg or {})

    # A decision whose authority window has already closed cannot authorise anything. Refusing
    # here rather than clamping is the point: a commitment silently shortened to "due now" reads
    # to a human as an emergency, when in fact it is an expired conclusion.
    if context.expires_at <= eval_time:
        return BuildResult(None, "decision_expired",
                           f"decision expired at {context.expires_at.isoformat()}")

    deadline = plan_deadline(context, eval_time=eval_time)
    if deadline <= eval_time:
        return BuildResult(None, "window_closed",
                           f"outcome window of {context.window_days}d leaves no time to act")

    actions = plan_actions(context, eval_time=eval_time, cfg=settings.get("planning"))
    autonomous = plan_is_autonomous(actions, context)
    communication = plan_communication(
        context, assignment, available_channels=available_channels, autonomous=autonomous,
        cfg=settings.get("communication"))
    band = band_of(context.priority_bp, settings.get("communication"))
    escalation = build_ladder(
        eval_time=eval_time, expires_at=context.expires_at, band=band,
        # A commitment nobody can be reached about is still tracked, but a ladder that escalates
        # into an empty room is noise. It gets its rungs back the moment someone claims it.
        remindable=communication.routable,
        cfg=settings.get("escalation"))

    execution = ExecutionObject(
        org_id=context.org_id,
        version=EXECUTION_VERSION,
        goal=context.goal,
        capability_id=context.capability_id,
        capability_version=context.capability_version,
        decision_hash=context.decision_hash,
        reasoning_run_id=context.reasoning_run_id,
        candidate_id=context.candidate_id,
        context_snapshot_id=context.context_snapshot_id,
        config_snapshot_id=context.config_snapshot_id,
        actions=actions,
        communication=communication,
        escalation=escalation,
        priority_bp=context.priority_bp,
        confidence_bp=context.confidence_bp,
        created_at=eval_time,
        deadline_at=deadline,
        expires_at=context.expires_at,
        do_nothing_consequence=context.do_nothing_consequence,
        success_events=context.success_events,
        subject_ref=context.subject_ref,
        monitored=bool(context.success_events) or context.interactive,
        remindable=communication.routable,
        autonomy_allowed=autonomous,
        visibility=(visibility.model_dump() if isinstance(visibility, Visibility)
                    else dict(visibility or Visibility().model_dump())),
        metadata={
            "builder_version": BUILDER_VERSION,
            "execution_type": context.execution_type.value,
            "play_id": context.play_id,
            "play_version": context.play_version,
            "artifact_kind": context.artifact_kind,
            "band": band,
            "routing_rule": assignment.reason_code,
            "subject_type": context.subject_type,
            "subject_label": context.subject_label,
            # Carried, not resolved. The planner cannot answer what the reasoner was unsure
            # about, but the person doing the work is entitled to see it on the card.
            "uncertainty": context.constraints,
            "evidence_ids": context.evidence_ids,
        },
    )
    # Cheap here, unfixable later: a commitment whose stored form does not rehydrate to itself
    # would deliver fine today and leave an audit trail nobody could reconcile afterwards.
    execution.verify_round_trip()
    return BuildResult(execution, "built", execution.describe().splitlines()[0])


def build_from_decision(decision: ReasoningDecision, *, org_id: str, reasoning_run_id: str,
                        config_snapshot_id: str, decision_hash: str, eval_time: datetime,
                        directory: SeatDirectory,
                        facts: Mapping[str, Any] | None = None,
                        attrs: Mapping[str, Any] | None = None,
                        available_channels: frozenset[str] | set[str] | None = None,
                        subject_ref: str | None = None, subject_type: str | None = None,
                        subject_label: str | None = None,
                        cfg: Mapping[str, Any] | None = None,
                        visibility: Visibility | Mapping[str, Any] | None = None) -> BuildResult:
    """The whole layer's build path in one call: decision in, commitment or refusal out.

    Exists so callers — the sweep, the API, the tests — cannot accidentally assemble the units in
    a different order and get a subtly different commitment for the same decision.
    """
    interpretation = interpret_decision(
        decision, org_id=org_id, reasoning_run_id=reasoning_run_id,
        config_snapshot_id=config_snapshot_id, decision_hash=decision_hash,
        subject_ref=subject_ref, subject_type=subject_type, subject_label=subject_label)
    if not interpretation.actionable:
        return BuildResult(None, interpretation.reason_code, interpretation.detail)
    assignment = resolve_owner(facts=facts, attrs=attrs, directory=directory)
    return build_execution(interpretation.require(), assignment=assignment, eval_time=eval_time,
                           available_channels=available_channels, cfg=cfg,
                           visibility=visibility)


__all__ = ["BUILDER_VERSION", "EXECUTION_CONFIG_KEY", "BuildResult", "build_execution",
           "build_from_decision", "execution_config"]
