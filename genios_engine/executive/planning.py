"""Layer 5 · Unit 2 — the Execution Planning Unit.

The interpreter produced an instruction: a goal and an ordered list of step sentences the pack
author wrote.  This unit turns that into a *plan* — actions with kinds, dependencies, waves,
owners, resources and individual deadlines — and it does so without a model anywhere in the
path.

Why no model.  A plan is the thing a human is asked to do and the thing an agent may be
allowed to do unattended.  If a language model classified "Send the renewal notice" as an
internal draft on Monday and as an outbound send on Tuesday, the same play would sometimes
require approval and sometimes not.  Approval boundaries cannot be probabilistic.  So
classification is a fixed, ordered lexicon: the same sentence always yields the same kind, and
when the lexicon does not recognise a step it falls to ``PREPARE``, the kind with no external
effect and therefore no way to cause harm by being wrong.

The one piece of genuine interpretation this unit performs is the **read-only downgrade**.  A
read-only play that says "Send the follow-up" is not asking GeniOS to send anything; it is
asking GeniOS to get a send ready for a person to approve.  Rather than refuse such a step or
quietly let it through as an external effect, the planner records the declared kind in
metadata, plans the action GeniOS is actually committing to, and attaches the approval gate.
The audit trail therefore shows both what the pack said and what the system did about it.

Pure and deterministic: no clock beyond the evaluation time passed in, no database, no model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from genios_engine.contracts.execution import (
    EXTERNAL_EFFECT_KINDS,
    ActionKind,
    AudienceClass,
    PlannedAction,
)
from genios_engine.executive.interpret import ExecutionContext, ExecutionType

PLANNER_VERSION = "exec_plan.v1"


class ExecutionPlanningError(RuntimeError):
    """A pack declared something that cannot be planned.

    Raised, not swallowed.  Every case that reaches here is a deployment fault — a play with no
    steps, a play with an implausible number of them — and a deployment fault must be loud at
    the moment it is deployed rather than quiet until the day a human is handed nonsense.
    """


#: Approval phrases, checked before anything else.  These are unambiguous — every one of them
#: names a handoff to a person — and getting them wrong is the only classification mistake that
#: can *remove* a gate rather than add one, so they win outright.
#:
#: Bare "review" is deliberately absent.  Pack steps open with "Review the deal history" far
#: more often than they end with "for review", and typing the former as an approval gate would
#: put a human checkpoint in front of reading a file.
_APPROVAL_PHRASES: tuple[str, ...] = (
    "approval", "approve", "sign off", "sign-off", "for review", "for human",
    "present the", "leave the draft", "hand to", "confirm with", "await confirmation",
)

#: The step's leading verb, which is how pack authors actually write these sentences: an
#: imperative followed by its object.  Reading the verb is both more accurate than scanning for
#: the strongest keyword anywhere in the sentence and far easier for an author to predict —
#: "Draft a warm outreach note" is a draft, even though "outreach" appears later in it.
_LEADING_VERB: Mapping[str, ActionKind] = {
    "draft": ActionKind.DRAFT, "write": ActionKind.DRAFT, "compose": ActionKind.DRAFT,
    "produce": ActionKind.DRAFT, "propose": ActionKind.DRAFT, "outline": ActionKind.DRAFT,
    "suggest": ActionKind.DRAFT,
    "send": ActionKind.SEND, "email": ActionKind.SEND, "reply": ActionKind.SEND,
    "respond": ActionKind.SEND, "message": ActionKind.SEND, "notify": ActionKind.SEND,
    "share": ActionKind.SEND, "deliver": ActionKind.SEND, "forward": ActionKind.SEND,
    "schedule": ActionKind.SCHEDULE, "book": ActionKind.SCHEDULE, "invite": ActionKind.SCHEDULE,
    "log": ActionKind.RECORD, "record": ActionKind.RECORD, "update": ActionKind.RECORD,
    "create": ActionKind.RECORD, "file": ActionKind.RECORD, "set": ActionKind.RECORD,
    "monitor": ActionKind.MONITOR, "watch": ActionKind.MONITOR, "track": ActionKind.MONITOR,
    "observe": ActionKind.MONITOR, "wait": ActionKind.MONITOR,
    "escalate": ActionKind.ESCALATE, "flag": ActionKind.ESCALATE, "involve": ActionKind.ESCALATE,
    "summarize": ActionKind.PREPARE, "summarise": ActionKind.PREPARE,
    "identify": ActionKind.PREPARE, "gather": ActionKind.PREPARE, "collect": ActionKind.PREPARE,
    "review": ActionKind.PREPARE, "read": ActionKind.PREPARE, "pull": ActionKind.PREPARE,
    "assemble": ActionKind.PREPARE, "verify": ActionKind.PREPARE, "check": ActionKind.PREPARE,
    "confirm": ActionKind.PREPARE, "analyze": ActionKind.PREPARE, "analyse": ActionKind.PREPARE,
    "list": ActionKind.PREPARE, "find": ActionKind.PREPARE, "prepare": ActionKind.PREPARE,
    "map": ActionKind.PREPARE, "compare": ActionKind.PREPARE, "quantify": ActionKind.PREPARE,
}

#: Last resort when the step does not open with a recognised verb — an ordered scan of the whole
#: sentence, strongest signal first.  Tokens match on word boundaries, so "record" does not fire
#: on "recorded": a past-tense mention is describing context, not requesting an act.
_LEXICON: tuple[tuple[ActionKind, tuple[str, ...]], ...] = (
    (ActionKind.ESCALATE, ("escalate", "hand off", "hand over", "loop in", "bring in")),
    (ActionKind.SCHEDULE, ("schedule", "book a", "set up a meeting", "set up a call",
                           "propose a time", "calendar")),
    (ActionKind.SEND, ("send", "email", "reply", "reach out", "outreach", "notify")),
    (ActionKind.RECORD, ("log", "record", "update the crm", "update crm", "create a ticket")),
    (ActionKind.DRAFT, ("draft", "write", "compose", "produce", "propose")),
    (ActionKind.MONITOR, ("monitor", "watch", "track", "observe", "wait for", "check for")),
    (ActionKind.PREPARE, ("summarize", "summarise", "identify", "gather", "collect", "review",
                          "read", "pull", "assemble", "verify", "check")),
)

#: What a step becomes when the play forbids external effects.  ``SEND``/``RECORD``/``SCHEDULE``
#: all reduce to producing the artifact a human will act on; ``ESCALATE`` reduces to asking a
#: human to escalate.  Every downgrade carries an approval gate, which is the whole point.
_READ_ONLY_DOWNGRADE: Mapping[ActionKind, ActionKind] = {
    ActionKind.SEND: ActionKind.DRAFT,
    ActionKind.RECORD: ActionKind.DRAFT,
    ActionKind.SCHEDULE: ActionKind.DRAFT,
}

DEFAULTS: Mapping[str, Any] = {
    # How soon the *first* action is due, by urgency band.  Urgency shapes when work starts;
    # the outcome window shapes when it must be finished.  Conflating the two is how a system
    # ends up demanding a fourteen-day commitment be complete this afternoon.
    "first_action_hours": {"critical": 4, "high": 24, "standard": 72},
    "urgency_critical_bp": 8_000,
    "urgency_high_bp": 6_000,
    # A play with more steps than this is an authoring error, not an ambitious plan. Twelve is
    # already twice the longest shipped play; the cap exists to catch generated garbage.
    "max_actions": 12,
}


def _config(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULTS, **dict(cfg or {})}
    merged["first_action_hours"] = {**DEFAULTS["first_action_hours"],
                                    **dict(merged.get("first_action_hours") or {})}
    return merged


def _matches(haystack: str, token: str) -> bool:
    """Word-boundary containment without a regex compile per call.

    A plain ``in`` test would let "notify" match inside "unnotified" and "send" match inside
    "sender"; both would silently reclassify a step into a kind that carries an approval gate
    it does not need, or worse, out of one it does.
    """
    start = haystack.find(token)
    while start != -1:
        before_ok = start == 0 or not haystack[start - 1].isalnum()
        end = start + len(token)
        after_ok = end == len(haystack) or not haystack[end].isalnum()
        if before_ok and after_ok:
            return True
        start = haystack.find(token, start + 1)
    return False


def classify_step(step: str) -> tuple[ActionKind, str]:
    """Return the declared kind and the token that decided it.

    Three passes, in this order and for this reason:

    1. **Approval phrases** — the only signal that can remove a gate if missed, so it is never
       overruled by anything later in the sentence.
    2. **The leading verb** — how imperative pack steps are actually written.  This is what
       makes the classifier predictable to a pack author: change the first word, change the
       kind, and nothing else in the sentence can quietly override it.
    3. **Whole-sentence scan** — for steps that open with something unrecognised.

    The deciding token is returned rather than discarded so every action records *why* it was
    typed the way it was.  When an author disagrees with a classification, the fix is a one-word
    edit, and they can only find that word if we tell them which one it was.
    """
    text = " ".join(str(step or "").lower().split())
    for phrase in _APPROVAL_PHRASES:
        if _matches(text, phrase):
            return ActionKind.REVIEW, phrase
    leading = text.split(" ", 1)[0].strip(".,:;")
    if leading in _LEADING_VERB:
        return _LEADING_VERB[leading], leading
    for kind, tokens in _LEXICON:
        for token in tokens:
            if _matches(text, token):
                return kind, token
    return ActionKind.PREPARE, "default"


def _urgency_band(urgency_bp: int, cfg: Mapping[str, Any]) -> str:
    if urgency_bp >= int(cfg["urgency_critical_bp"]):
        return "critical"
    if urgency_bp >= int(cfg["urgency_high_bp"]):
        return "high"
    return "standard"


def plan_deadline(context: ExecutionContext, *, eval_time: datetime) -> datetime:
    """When the whole commitment is due.

    The play's outcome window, hard-capped by the decision's own expiry.  Layer 4 said how long
    it stands behind this conclusion; Layer 5 does not get to keep chasing it afterwards, so
    the earlier of the two always wins.
    """
    window_end = eval_time + timedelta(days=max(1, int(context.window_days)))
    return min(window_end, context.expires_at)


def _stage_deadlines(*, eval_time: datetime, deadline: datetime, stage_count: int,
                     urgency_bp: int, cfg: Mapping[str, Any]) -> tuple[datetime, ...]:
    """Spread the window across the waves, in whole seconds.

    Stage 0 is due at the urgency-driven first-action time; the final stage is due at the
    commitment deadline; the middle interpolates evenly.  Integer seconds only — a float here
    would make two identical plans hash differently on different platforms.
    """
    if stage_count <= 0:
        return ()
    band = _urgency_band(urgency_bp, cfg)
    first_hours = int(cfg["first_action_hours"][band])
    first = min(eval_time + timedelta(hours=first_hours), deadline)
    if stage_count == 1:
        return (deadline,)
    span = int((deadline - first).total_seconds())
    if span < 0:                                   # window already closed to a point
        span = 0
    return tuple(first + timedelta(seconds=(span * index) // (stage_count - 1))
                 for index in range(stage_count))


def _resources(context: ExecutionContext, kind: ActionKind) -> tuple[str, ...]:
    """What the person or agent needs in hand to do this action.

    Evidence is attached only to the actions that consume it — preparation and review.  Listing
    every evidence id on every action would be technically true and practically useless; the
    point of a resource list is to be short enough to read.
    """
    resources: list[str] = []
    if context.subject_ref:
        resources.append(f"entity:{context.subject_ref}")
    if kind in {ActionKind.PREPARE, ActionKind.REVIEW}:
        resources.extend(f"evidence:{item}" for item in context.evidence_ids)
    if kind in {ActionKind.DRAFT, ActionKind.SEND}:
        resources.append(f"artifact:{context.artifact_kind}")
    if kind is ActionKind.RECORD:
        resources.append("system:crm")
    if kind is ActionKind.SCHEDULE:
        resources.append("system:calendar")
    return tuple(resources)


def _stages(kinds: Sequence[ActionKind]) -> tuple[int, ...]:
    """Which actions could honestly happen at the same time.

    Pack steps are written as a sequence, so the safe default is a strict chain.  The one real
    exception is the opening run of ``PREPARE`` steps: gathering the deal history and looking
    up a stakeholder do not depend on each other, and pretending they do would push every
    downstream deadline out for no reason.  Once anything is produced, decided or sent, the
    chain resumes — because from that point on each step consumes the last one's output.
    """
    stages: list[int] = []
    leading = 0
    while leading < len(kinds) and kinds[leading] is ActionKind.PREPARE:
        leading += 1
    for index in range(len(kinds)):
        if index < leading:
            stages.append(0)
        else:
            stages.append(index - leading + (1 if leading else 0))
    return tuple(stages)


def plan_actions(context: ExecutionContext, *, eval_time: datetime,
                 cfg: Mapping[str, Any] | None = None) -> tuple[PlannedAction, ...]:
    """Steps in, a fully-specified plan out.

    The action ids are positional (``a1``, ``a2``, …) rather than content-addressed.  That is
    deliberate: they only have to be unique and stable *within* one execution object, and the
    object as a whole is already content-addressed.  Hashing each action into its own id would
    make dependency references unreadable in every log line for no added guarantee.
    """
    settings = _config(cfg)
    steps = context.steps
    if not steps:
        raise ExecutionPlanningError(
            f"play {context.play_id}@{context.play_version} reached the planner with no steps")
    if len(steps) > int(settings["max_actions"]):
        raise ExecutionPlanningError(
            f"play {context.play_id}@{context.play_version} declares {len(steps)} steps; "
            f"the ceiling is {settings['max_actions']}")

    declared = [classify_step(step) for step in steps]
    effective: list[ActionKind] = []
    for kind, _token in declared:
        if context.read_only and kind in _READ_ONLY_DOWNGRADE:
            effective.append(_READ_ONLY_DOWNGRADE[kind])
        elif context.read_only and kind in EXTERNAL_EFFECT_KINDS:
            effective.append(ActionKind.PREPARE)
        else:
            effective.append(kind)

    stages = _stages(effective)
    deadline = plan_deadline(context, eval_time=eval_time)
    stage_deadlines = _stage_deadlines(
        eval_time=eval_time, deadline=deadline, stage_count=max(stages) + 1,
        urgency_bp=context.urgency_bp, cfg=settings)

    actions: list[PlannedAction] = []
    last_index = len(steps) - 1
    for index, step in enumerate(steps):
        kind = effective[index]
        declared_kind, token = declared[index]
        downgraded = declared_kind is not kind
        # An action depends on the whole previous wave, not just the previous action: when the
        # opening PREPARE steps run together, the first DRAFT genuinely needs all of them.
        depends_on = tuple(action.action_id for action in actions
                           if action.stage == stages[index] - 1)
        requires_approval = (
            kind is ActionKind.REVIEW
            or downgraded
            or (context.requires_human and index == last_index)
            or kind in EXTERNAL_EFFECT_KINDS)
        actions.append(PlannedAction(
            ordinal=index + 1,
            stage=stages[index],
            action_id=f"a{index + 1}",
            label=step,
            kind=kind,
            depends_on=depends_on,
            audience=(AudienceClass.MANAGER if kind is ActionKind.ESCALATE
                      else AudienceClass.OWNER),
            requires_approval=requires_approval,
            read_only=kind not in EXTERNAL_EFFECT_KINDS,
            deadline_at=stage_deadlines[stages[index]],
            resources=_resources(context, kind),
            # Success evidence proves the *outcome*, and the outcome is the last action's
            # responsibility. Attaching it to every action would report a commitment complete
            # the moment its first step finished.
            completion_events=context.success_events if index == last_index else (),
            metadata={"declared_kind": declared_kind.value, "matched_token": token,
                      "read_only_downgrade": downgraded,
                      "execution_type": context.execution_type.value},
        ))
    return tuple(actions)


def plan_is_autonomous(actions: Sequence[PlannedAction], context: ExecutionContext) -> bool:
    """May this whole plan run without a person?

    Three independent conditions, all required.  A monitoring commitment with no gates and no
    external effects is the only shape that qualifies today, and that is the intended answer:
    autonomy is something a pack earns per action, not something a plan claims for itself.
    """
    if context.requires_human or context.external_recipient_required:
        return False
    if context.execution_type is not ExecutionType.MONITORING:
        return False
    return all(action.autonomous_allowed for action in actions)


__all__ = ["DEFAULTS", "PLANNER_VERSION", "ExecutionPlanningError", "classify_step",
           "plan_actions", "plan_deadline", "plan_is_autonomous"]
