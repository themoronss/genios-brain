"""The Execution Object — Layer 5's single output, and the only thing Layer 5.2 is allowed to carry.

Layer 4 answers *what should happen*.  This contract answers *how it happens*: the ordered
actions, who owns each one, by when, through which channel, what proves it was done, and
what happens on each day nobody does it.  A reasoning decision is an opinion; an execution
object is a commitment with a clock attached.

Three properties earn this file its weight.

**It is immutable and content-addressed.**  Nothing here is a mutable row.  The lifecycle —
created → pending → running → … → archived — lives in a database row that *points at* an
execution object; the object itself never changes.  That separation is what makes "why did
this remind me on day 7?" answerable months later: the ladder that fired is still byte-for-byte
the ladder that was planned, even if the pack has since been retuned.

**Identity is the decision plus the plan, not the routing.**  ``execution_id`` hashes
``(org_id, decision_hash, plan_hash)`` and deliberately excludes the communication plan.
Reassigning an execution to a different person is a real operation that must not mint a second
execution object for the same commitment; conversely a *different plan* for the same decision
is genuinely a different commitment.  ``semantic_hash`` still covers every field, so audit and
replay see the whole artifact.

**Every number is an integer.**  Floats are refused by ``platform.canonical``; priority and
confidence are basis points.  A content address that drifted with the platform's float
formatting would make two identical executions look different, which is the one failure this
whole design exists to prevent.

Import rule: this module sits in ``contracts/`` and may import nothing above ``platform``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_bool,
    require_bp,
    require_enum,
    require_hash64,
    require_identifier,
    require_non_negative,
    require_ordinal,
    require_sorted_unique,
    require_text,
)
from genios_engine.platform.canonical import decanonicalize, semantic_hash, stable_id

EXECUTION_VERSION = "execution.v1"


class ExecutionState(str, Enum):
    """Where a commitment stands.

    ``created`` exists separately from ``pending`` because an execution object is built before
    it is validated: the guard (``executive.execution_guard``) can retire one that was already
    stale by the time it was planned, and that retirement must be visible as a state, not as a
    row that silently never appears.
    """

    CREATED = "created"          # built, not yet cleared for delivery
    PENDING = "pending"          # validated and queued for Layer 5.2; nobody has touched it
    RUNNING = "running"          # a human or agent has picked it up
    WAITING = "waiting"          # acted on; waiting for the world to respond (reply, signature)
    BLOCKED = "blocked"          # cannot proceed — a dependency or an explicit human block
    COMPLETED = "completed"      # the success evidence landed
    CANCELLED = "cancelled"      # withdrawn: superseded, invalidated, or dismissed by a human
    EXPIRED = "expired"          # the deadline passed with no completion evidence
    ARCHIVED = "archived"        # terminal, closed out, retained for learning


#: The only legal moves.  Held here rather than in the lifecycle module so the SQL guard, the
#: state machine and the tests all read the same table — a transition that exists in one place
#: and not another is how audit trails start lying.
ALLOWED_TRANSITIONS: MappingProxyType = MappingProxyType({
    ExecutionState.CREATED:   (ExecutionState.PENDING, ExecutionState.CANCELLED),
    ExecutionState.PENDING:   (ExecutionState.RUNNING, ExecutionState.BLOCKED,
                               ExecutionState.COMPLETED, ExecutionState.CANCELLED,
                               ExecutionState.EXPIRED),
    ExecutionState.RUNNING:   (ExecutionState.WAITING, ExecutionState.BLOCKED,
                               ExecutionState.COMPLETED, ExecutionState.CANCELLED,
                               ExecutionState.EXPIRED),
    ExecutionState.WAITING:   (ExecutionState.RUNNING, ExecutionState.BLOCKED,
                               ExecutionState.COMPLETED, ExecutionState.CANCELLED,
                               ExecutionState.EXPIRED),
    ExecutionState.BLOCKED:   (ExecutionState.RUNNING, ExecutionState.WAITING,
                               ExecutionState.COMPLETED, ExecutionState.CANCELLED,
                               ExecutionState.EXPIRED),
    ExecutionState.COMPLETED: (ExecutionState.ARCHIVED,),
    ExecutionState.CANCELLED: (ExecutionState.ARCHIVED,),
    ExecutionState.EXPIRED:   (ExecutionState.ARCHIVED,),
    ExecutionState.ARCHIVED:  (),
})

#: States in which a commitment is still live: reminders, monitoring and escalation apply.
OPEN_STATES: frozenset[ExecutionState] = frozenset({
    ExecutionState.PENDING, ExecutionState.RUNNING,
    ExecutionState.WAITING, ExecutionState.BLOCKED})

#: States that end the clock.  Nothing may nudge, escalate or monitor these.
TERMINAL_STATES: frozenset[ExecutionState] = frozenset({
    ExecutionState.COMPLETED, ExecutionState.CANCELLED,
    ExecutionState.EXPIRED, ExecutionState.ARCHIVED})


def can_transition(current: ExecutionState, target: ExecutionState) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, ())


class ActionKind(str, Enum):
    """What a planned action *is*, which decides who may perform it unattended.

    The kind is not decoration.  ``SEND`` and ``RECORD`` mutate the world outside GeniOS, so a
    read-only play may not contain one, and an autonomous agent may not perform one without an
    approval gate ahead of it.  Classifying the step is therefore a safety decision, and it is
    made deterministically from a fixed lexicon rather than by asking a model.
    """

    PREPARE = "prepare"      # gather, read, look up — no external effect
    DRAFT = "draft"          # produce an artifact that a human will review
    REVIEW = "review"        # a human decision gate
    SEND = "send"            # outbound communication to a party outside the org
    SCHEDULE = "schedule"    # book time with someone
    RECORD = "record"        # write to a system of record (CRM, ticket, doc)
    MONITOR = "monitor"      # observe and wait for a response
    ESCALATE = "escalate"    # hand the commitment up


#: Kinds whose effects leave the building.  These gate autonomy and read-only enforcement.
EXTERNAL_EFFECT_KINDS: frozenset[ActionKind] = frozenset({
    ActionKind.SEND, ActionKind.SCHEDULE, ActionKind.RECORD})


class AudienceClass(str, Enum):
    """Who a communication is aimed at — the *class*, resolved to a seat separately.

    Keeping the class alongside the resolved assignee means an escalation ladder can say
    "on day 7, the manager" without knowing on planning day who the manager will be.
    """

    OWNER = "owner"              # the person who holds the commitment
    TEAM = "team"                # the owner's peers
    MANAGER = "manager"          # one level up
    EXECUTIVE = "executive"      # leadership
    AGENT = "agent"              # a machine executor registered against the org
    ADMIN_QUEUE = "admin_queue"  # nobody could be resolved; a human must triage


class ChannelClass(str, Enum):
    """How it travels.  ``channel_id`` names the concrete adapter; this names the intent."""

    IN_APP = "in_app"        # the card surface — always available, never interrupts
    CHAT = "chat"            # Slack and friends — interrupts
    EMAIL = "email"
    DIGEST = "digest"        # batched; explicitly the low-interrupt option
    AGENT = "agent"          # machine transport (signed webhook)
    NONE = "none"            # deliberately not communicated (silent tracking)


class EscalationAction(str, Enum):
    NOTIFY = "notify"        # first touch, same audience
    REMIND = "remind"        # nudge, same audience, higher salience
    ESCALATE = "escalate"    # widen the audience
    CRITICAL = "critical"    # widen and interrupt


@dataclass(frozen=True, slots=True)
class PlannedAction:
    """One step of the commitment, with its own owner, gate and clock.

    ``label`` is carried verbatim from the play's declared step text.  It is never generated,
    because the invention validator (``executive.validate``) will refuse any rendered copy
    containing a name, number or date absent from the fact corpus — and a paraphrased step is
    exactly how an invented number gets in.
    """

    ordinal: int
    stage: int
    action_id: str
    label: str
    kind: ActionKind
    depends_on: tuple[str, ...] = ()
    audience: AudienceClass = AudienceClass.OWNER
    requires_approval: bool = False
    read_only: bool = True
    deadline_at: datetime | None = None
    resources: tuple[str, ...] = ()
    completion_events: tuple[str, ...] = ()
    metadata: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "ordinal", require_ordinal(self.ordinal, "action ordinal"))
        setattr_(self, "stage", require_non_negative(self.stage, "action stage"))
        setattr_(self, "action_id", require_identifier(self.action_id, "action id"))
        setattr_(self, "label", require_text(self.label, "action label"))
        setattr_(self, "kind", require_enum(self.kind, ActionKind, "action kind"))
        setattr_(self, "depends_on", require_sorted_unique(self.depends_on, "action dependency"))
        setattr_(self, "audience", require_enum(self.audience, AudienceClass, "action audience"))
        setattr_(self, "requires_approval",
                 require_bool(self.requires_approval, "requires_approval"))
        setattr_(self, "read_only", require_bool(self.read_only, "read_only"))
        if self.deadline_at is not None:
            setattr_(self, "deadline_at", require_aware(self.deadline_at, "action deadline"))
        setattr_(self, "resources", require_sorted_unique(self.resources, "action resource"))
        setattr_(self, "completion_events",
                 require_sorted_unique(self.completion_events, "completion event"))
        setattr_(self, "metadata", freeze_mapping(self.metadata))
        if self.action_id in self.depends_on:
            raise ValueError(f"action {self.action_id} depends on itself")
        if self.read_only and self.kind in EXTERNAL_EFFECT_KINDS:
            raise ValueError(
                f"action {self.action_id} is marked read-only but is a {self.kind.value} step; "
                "a read-only play may not change the world outside GeniOS")

    @property
    def external_effect(self) -> bool:
        return self.kind in EXTERNAL_EFFECT_KINDS

    @property
    def autonomous_allowed(self) -> bool:
        """May a machine executor perform this without a human in front of it?

        Fails closed: anything with an external effect, and anything explicitly gated, needs a
        person.  Autonomy is granted step by step, never play by play.
        """
        return not self.requires_approval and not self.external_effect

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "stage": self.stage, "action_id": self.action_id,
                "label": self.label, "kind": self.kind.value, "depends_on": self.depends_on,
                "audience": self.audience.value, "requires_approval": self.requires_approval,
                "read_only": self.read_only,
                "deadline_at": self.deadline_at, "resources": self.resources,
                "completion_events": self.completion_events, "metadata": self.metadata}


@dataclass(frozen=True, slots=True)
class CommunicationPlan:
    """Who hears about this, where, how loudly, and why that was the right call.

    Layer 5 owns this decision end to end — audience, seat, channel and interrupt — and Layer 5.2
    executes it.  ``reason_code`` is mandatory because a routing choice a human cannot
    interrogate is indistinguishable from a bug: when the wrong person gets paged at 2am, the
    first question is always "why them?", and the answer must already be in the row.
    """

    audience: AudienceClass
    channel_class: ChannelClass
    channel_id: str
    interrupt: bool
    tone: str
    format_kind: str
    reason_code: str
    assignee: str | None = None
    cc: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "audience", require_enum(self.audience, AudienceClass, "audience"))
        setattr_(self, "channel_class",
                 require_enum(self.channel_class, ChannelClass, "channel class"))
        setattr_(self, "channel_id", require_identifier(self.channel_id, "channel id"))
        setattr_(self, "interrupt", require_bool(self.interrupt, "interrupt"))
        setattr_(self, "tone", require_identifier(self.tone, "tone"))
        setattr_(self, "format_kind", require_identifier(self.format_kind, "format kind"))
        setattr_(self, "reason_code", require_identifier(self.reason_code, "routing reason code"))
        if self.assignee is not None:
            setattr_(self, "assignee", require_identifier(self.assignee, "assignee"))
        setattr_(self, "cc", require_sorted_unique(self.cc, "cc recipient"))
        if self.channel_class is ChannelClass.NONE and self.interrupt:
            raise ValueError("a silent communication plan cannot interrupt")
        if self.audience is AudienceClass.ADMIN_QUEUE and self.assignee is not None:
            raise ValueError("an admin-queue plan has no assignee by definition")

    @property
    def routable(self) -> bool:
        """True when there is somebody to deliver to.  An unrouted commitment still exists —
        it is tracked, escalated and reported on; it simply reaches the triage queue instead."""
        return self.assignee is not None

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"audience": self.audience.value, "channel_class": self.channel_class.value,
                "channel_id": self.channel_id, "interrupt": self.interrupt, "tone": self.tone,
                "format_kind": self.format_kind, "reason_code": self.reason_code,
                "assignee": self.assignee, "cc": self.cc}


@dataclass(frozen=True, slots=True)
class EscalationStep:
    """One rung of the ladder: on day N, do this, to this audience.

    Planned up front and frozen, not computed at fire time.  If the ladder were recomputed on
    the day it fires, retuning the pack would silently rewrite the history of commitments that
    were made under the old ladder, and every "why was I escalated?" answer would be a guess.
    """

    day_offset: int
    action: EscalationAction
    audience: AudienceClass
    interrupt: bool
    fires_at: datetime
    reason_code: str

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "day_offset", require_non_negative(self.day_offset, "escalation day"))
        setattr_(self, "action", require_enum(self.action, EscalationAction, "escalation action"))
        setattr_(self, "audience",
                 require_enum(self.audience, AudienceClass, "escalation audience"))
        setattr_(self, "interrupt", require_bool(self.interrupt, "escalation interrupt"))
        setattr_(self, "fires_at", require_aware(self.fires_at, "escalation fires_at"))
        setattr_(self, "reason_code",
                 require_identifier(self.reason_code, "escalation reason code"))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"day_offset": self.day_offset, "action": self.action.value,
                "audience": self.audience.value, "interrupt": self.interrupt,
                "fires_at": self.fires_at, "reason_code": self.reason_code}


@dataclass(frozen=True, slots=True)
class ExecutionObject:
    """Layer 5's entire output.  One decision in, one commitment out.

    Provenance is not optional.  Every field from ``capability_id`` through
    ``config_snapshot_id`` binds this commitment to the exact immutable reasoning run and
    effective config that produced it, so the authority check that Layer 5.2 runs before every
    send has something real to check *against*.  A commitment whose decision was revoked must
    be stoppable in flight, and that is only possible if the link is carried, not inferred.
    """

    org_id: str
    version: str
    goal: str
    capability_id: str
    capability_version: str
    decision_hash: str
    reasoning_run_id: str
    candidate_id: str
    context_snapshot_id: str
    config_snapshot_id: str
    actions: tuple[PlannedAction, ...]
    communication: CommunicationPlan
    escalation: tuple[EscalationStep, ...]
    priority_bp: int
    confidence_bp: int
    created_at: datetime
    deadline_at: datetime
    expires_at: datetime
    do_nothing_consequence: str
    success_events: tuple[str, ...] = ()
    subject_ref: str | None = None
    monitored: bool = True
    remindable: bool = True
    autonomy_allowed: bool = False
    metadata: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "org_id", require_identifier(self.org_id, "org id"))
        setattr_(self, "version", require_identifier(self.version, "execution version"))
        setattr_(self, "goal", require_text(self.goal, "goal"))
        setattr_(self, "capability_id", require_identifier(self.capability_id, "capability id"))
        setattr_(self, "capability_version",
                 require_identifier(self.capability_version, "capability version"))
        setattr_(self, "decision_hash", require_hash64(self.decision_hash, "decision hash"))
        setattr_(self, "reasoning_run_id",
                 require_identifier(self.reasoning_run_id, "reasoning run id"))
        setattr_(self, "candidate_id", require_identifier(self.candidate_id, "candidate id"))
        setattr_(self, "context_snapshot_id",
                 require_identifier(self.context_snapshot_id, "context snapshot id"))
        setattr_(self, "config_snapshot_id",
                 require_identifier(self.config_snapshot_id, "config snapshot id"))
        setattr_(self, "actions", tuple(self.actions or ()))
        setattr_(self, "escalation", tuple(self.escalation or ()))
        setattr_(self, "priority_bp", require_bp(self.priority_bp, "priority_bp"))
        setattr_(self, "confidence_bp", require_bp(self.confidence_bp, "confidence_bp"))
        setattr_(self, "created_at", require_aware(self.created_at, "created_at"))
        setattr_(self, "deadline_at", require_aware(self.deadline_at, "deadline_at"))
        setattr_(self, "expires_at", require_aware(self.expires_at, "expires_at"))
        setattr_(self, "do_nothing_consequence",
                 require_text(self.do_nothing_consequence, "do_nothing_consequence"))
        setattr_(self, "success_events",
                 require_sorted_unique(self.success_events, "success event"))
        if self.subject_ref is not None:
            setattr_(self, "subject_ref", require_identifier(self.subject_ref, "subject ref"))
        setattr_(self, "monitored", require_bool(self.monitored, "monitored"))
        setattr_(self, "remindable", require_bool(self.remindable, "remindable"))
        setattr_(self, "autonomy_allowed", require_bool(self.autonomy_allowed, "autonomy_allowed"))
        setattr_(self, "metadata", freeze_mapping(self.metadata))
        self._validate_actions()
        self._validate_clock()
        self._validate_autonomy()

    # ---- invariants -------------------------------------------------------------------

    def _validate_actions(self) -> None:
        if not self.actions:
            raise ValueError("an execution object with no actions is not a commitment")
        if any(not isinstance(action, PlannedAction) for action in self.actions):
            raise TypeError("actions must be PlannedAction instances")
        ordinals = [action.ordinal for action in self.actions]
        if ordinals != list(range(1, len(ordinals) + 1)):
            raise ValueError("action ordinals must be 1..n in order")
        known: set[str] = set()
        for action in self.actions:
            if action.action_id in known:
                raise ValueError(f"duplicate action id {action.action_id}")
            # Dependencies may only point backwards.  A forward reference would describe a plan
            # that can never start, and the cheapest place to catch that is here, once, rather
            # than in a scheduler that deadlocks quietly at 3am.
            unmet = tuple(dep for dep in action.depends_on if dep not in known)
            if unmet:
                raise ValueError(
                    f"action {action.action_id} depends on {unmet} which do not precede it")
            known.add(action.action_id)

    def _validate_clock(self) -> None:
        if self.deadline_at < self.created_at:
            raise ValueError("deadline precedes creation")
        # The decision's own authority window is the hard ceiling.  Committing past it would
        # let Layer 5 keep chasing an outcome Layer 4 has already stopped standing behind.
        if self.deadline_at > self.expires_at:
            raise ValueError("deadline outlives the decision that authorised it")
        offsets = [step.day_offset for step in self.escalation]
        if offsets != sorted(set(offsets)):
            raise ValueError("escalation ladder must be strictly increasing in day offset")
        for step in self.escalation:
            if step.fires_at > self.expires_at:
                raise ValueError(
                    f"escalation day {step.day_offset} fires after the decision expires")

    def _validate_autonomy(self) -> None:
        if not self.autonomy_allowed:
            return
        blocking = tuple(a.action_id for a in self.actions if not a.autonomous_allowed)
        if blocking:
            raise ValueError(
                f"autonomy_allowed is set but {blocking} require a human; "
                "autonomy is granted per action, never per plan")

    # ---- derived ----------------------------------------------------------------------

    @property
    def stage_count(self) -> int:
        return (max(action.stage for action in self.actions) + 1) if self.actions else 0

    @property
    def stages(self) -> tuple[tuple[PlannedAction, ...], ...]:
        """Actions grouped into dependency-free waves — what could legitimately happen at once."""
        grouped: list[list[PlannedAction]] = [[] for _ in range(self.stage_count)]
        for action in self.actions:
            grouped[action.stage].append(action)
        return tuple(tuple(group) for group in grouped)

    @property
    def first_action(self) -> PlannedAction:
        return self.actions[0]

    @property
    def approval_gates(self) -> tuple[PlannedAction, ...]:
        return tuple(a for a in self.actions if a.requires_approval)

    @property
    def read_only(self) -> bool:
        return all(action.read_only for action in self.actions)

    @property
    def monitoring_events(self) -> tuple[str, ...]:
        """Everything whose observation would prove this commitment was honoured."""
        seen = set(self.success_events)
        for action in self.actions:
            seen.update(action.completion_events)
        return tuple(sorted(seen))

    def plan_semantic_dict(self) -> dict[str, Any]:
        """The commitment itself, without routing.

        Deliberately excludes ``communication``: reassignment is a legitimate operation on an
        existing commitment, not the birth of a new one.
        """
        return {"version": self.version, "goal": self.goal,
                "capability_id": self.capability_id,
                "capability_version": self.capability_version,
                "actions": tuple(action.to_semantic_dict() for action in self.actions),
                "escalation": tuple(step.to_semantic_dict() for step in self.escalation),
                "deadline_at": self.deadline_at, "expires_at": self.expires_at,
                "success_events": self.success_events,
                "do_nothing_consequence": self.do_nothing_consequence}

    @property
    def plan_hash(self) -> str:
        return semantic_hash(self.plan_semantic_dict())

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "version": self.version, "goal": self.goal,
                "capability_id": self.capability_id,
                "capability_version": self.capability_version,
                "decision_hash": self.decision_hash,
                "reasoning_run_id": self.reasoning_run_id,
                "candidate_id": self.candidate_id,
                "context_snapshot_id": self.context_snapshot_id,
                "config_snapshot_id": self.config_snapshot_id,
                "actions": tuple(action.to_semantic_dict() for action in self.actions),
                "communication": self.communication.to_semantic_dict(),
                "escalation": tuple(step.to_semantic_dict() for step in self.escalation),
                "priority_bp": self.priority_bp, "confidence_bp": self.confidence_bp,
                "created_at": self.created_at, "deadline_at": self.deadline_at,
                "expires_at": self.expires_at,
                "do_nothing_consequence": self.do_nothing_consequence,
                "success_events": self.success_events, "subject_ref": self.subject_ref,
                "monitored": self.monitored, "remindable": self.remindable,
                "autonomy_allowed": self.autonomy_allowed, "metadata": self.metadata}

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    @property
    def execution_id(self) -> str:
        """Stable across re-planning of the same decision; distinct when the plan differs.

        Routing is excluded on purpose (see ``plan_semantic_dict``).  This is what lets the
        builder be run repeatedly by a sweep without minting duplicate commitments, and what
        lets the database enforce one live execution per decision with a unique index.
        """
        return stable_id("exec", {"org_id": self.org_id, "decision_hash": self.decision_hash,
                                  "plan_hash": self.plan_hash})

    @classmethod
    def from_semantic_dict(cls, payload: Mapping[str, Any]) -> ExecutionObject:
        """Rebuild a stored commitment, re-running every invariant on the way in.

        Storage is not trusted.  The whole object is reconstructed through the same
        ``__post_init__`` validation that built it, so a row corrupted by a bad migration, a
        hand-edited jsonb, or a version skew fails loudly here rather than quietly escalating to
        somebody's manager three days later.

        The round trip is exact by construction: ``semantic_hash`` of the rehydrated object must
        equal the stored one, and ``verify_round_trip`` below is what asserts it.
        """
        data = decanonicalize(dict(payload))
        actions = tuple(
            PlannedAction(
                ordinal=item["ordinal"], stage=item["stage"], action_id=item["action_id"],
                label=item["label"], kind=ActionKind(item["kind"]),
                depends_on=tuple(item.get("depends_on") or ()),
                audience=AudienceClass(item.get("audience", "owner")),
                requires_approval=bool(item.get("requires_approval", False)),
                read_only=bool(item.get("read_only", True)),
                deadline_at=item.get("deadline_at"),
                resources=tuple(item.get("resources") or ()),
                completion_events=tuple(item.get("completion_events") or ()),
                metadata=item.get("metadata") or {})
            for item in data.get("actions") or ())
        comms = data["communication"]
        communication = CommunicationPlan(
            audience=AudienceClass(comms["audience"]),
            channel_class=ChannelClass(comms["channel_class"]),
            channel_id=comms["channel_id"], interrupt=bool(comms["interrupt"]),
            tone=comms["tone"], format_kind=comms["format_kind"],
            reason_code=comms["reason_code"], assignee=comms.get("assignee"),
            cc=tuple(comms.get("cc") or ()))
        escalation = tuple(
            EscalationStep(day_offset=item["day_offset"],
                           action=EscalationAction(item["action"]),
                           audience=AudienceClass(item["audience"]),
                           interrupt=bool(item["interrupt"]), fires_at=item["fires_at"],
                           reason_code=item["reason_code"])
            for item in data.get("escalation") or ())
        return cls(
            org_id=data["org_id"], version=data["version"], goal=data["goal"],
            capability_id=data["capability_id"],
            capability_version=data["capability_version"],
            decision_hash=data["decision_hash"], reasoning_run_id=data["reasoning_run_id"],
            candidate_id=data["candidate_id"],
            context_snapshot_id=data["context_snapshot_id"],
            config_snapshot_id=data["config_snapshot_id"], actions=actions,
            communication=communication, escalation=escalation,
            priority_bp=data["priority_bp"], confidence_bp=data["confidence_bp"],
            created_at=data["created_at"], deadline_at=data["deadline_at"],
            expires_at=data["expires_at"],
            do_nothing_consequence=data["do_nothing_consequence"],
            success_events=tuple(data.get("success_events") or ()),
            subject_ref=data.get("subject_ref"), monitored=bool(data.get("monitored", True)),
            remindable=bool(data.get("remindable", True)),
            autonomy_allowed=bool(data.get("autonomy_allowed", False)),
            metadata=data.get("metadata") or {})

    def verify_round_trip(self) -> None:
        """Assert that this object survives storage byte-identically.

        Called at build time, not only in tests.  A commitment whose stored form does not
        rehydrate to itself would still deliver correctly today and produce an unexplainable
        audit trail forever after; catching it at the moment of writing costs microseconds.
        """
        restored = ExecutionObject.from_semantic_dict(self.to_semantic_dict())
        if restored.semantic_hash != self.semantic_hash:
            raise ValueError(
                f"execution object does not round-trip: {self.execution_id} "
                f"({self.semantic_hash} != {restored.semantic_hash})")

    def describe(self) -> str:
        """One-screen summary for operators and failure diagnostics."""
        who = self.communication.assignee or f"<{self.communication.audience.value}>"
        head = (f"{self.execution_id} · {self.goal} · {len(self.actions)} actions "
                f"· {who} via {self.communication.channel_id} "
                f"· due {self.deadline_at.isoformat()}")
        lines = [head]
        for action in self.actions:
            gate = " [approval]" if action.requires_approval else ""
            due = f" due {action.deadline_at.isoformat()}" if action.deadline_at else ""
            lines.append(f"  {action.ordinal}. [{action.kind.value}] {action.label}{gate}{due}")
        for step in self.escalation:
            lines.append(f"  day {step.day_offset}: {step.action.value} "
                         f"→ {step.audience.value} ({step.reason_code})")
        return "\n".join(lines)


__all__ = ["ALLOWED_TRANSITIONS", "EXECUTION_VERSION", "EXTERNAL_EFFECT_KINDS", "OPEN_STATES",
           "TERMINAL_STATES", "ActionKind", "AudienceClass", "ChannelClass", "CommunicationPlan",
           "EscalationAction", "EscalationStep", "ExecutionObject", "ExecutionState",
           "PlannedAction", "can_transition"]
