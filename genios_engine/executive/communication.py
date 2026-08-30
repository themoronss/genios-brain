"""Layer 5 · Unit 3 — the Communication Planning Unit.  *Where* and *how loudly*.

Owning the channel choice up here, alongside the owner choice, is a deliberate architectural
call: interrupting someone is part of the commitment, not part of the transport.  "Slack this
person right now" and "let them find it in tomorrow's digest" are two different promises about
how much of their attention this is worth, and that judgement belongs with the layer that
decided the work was worth doing at all.  Layer 6 keeps the adapters, the retries and the
outbox — it executes the plan, it does not author it.

The rules encode one principle: **interruption is a budget, not a feature.**  Every channel
here is ordered by how much of a person's attention it spends, and a commitment has to earn its
way up that order with score, not with enthusiasm.  A system that pages on everything is
indistinguishable from a system nobody reads.

Behaviourally this reproduces exactly what Layer 6 does today — high and critical go to the
org's chat channel, everything else waits for the digest, unrouted work sits on the card
surface — with the difference that the choice is now recorded, explained by a reason code, and
frozen into the execution object rather than recomputed inside a queue drain.

Pure: the org's available channels are passed in, never queried here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genios_engine.contracts.execution import AudienceClass, ChannelClass, CommunicationPlan
from genios_engine.executive.assignment import Assignment
from genios_engine.executive.interpret import ExecutionContext, ExecutionType

COMMUNICATION_VERSION = "comms.v1"

#: The card surface.  Always available, never interrupts, and therefore the floor every other
#: choice falls back to — a commitment that cannot be pushed anywhere still has a home.
IN_APP_CHANNEL = "in_app"
DIGEST_CHANNEL = "digest"
AGENT_CHANNEL = "agent"

#: Concrete adapters that count as an interrupting chat channel.  Matches the adapter registry
#: in ``deliver/channels/`` — v1 ships Slack; adding one is a registry entry plus a line here.
CHAT_CHANNELS: tuple[str, ...] = ("slack",)

DEFAULTS: Mapping[str, Any] = {
    # Band cuts on the 0..100 projected score, matching the pack's own `bands` block so a tenant
    # that retunes what "critical" means retunes interruption at the same time — one dial, not
    # two that can silently disagree.
    "bands": {"high": 70, "critical": 85},
    # The band at which GeniOS is allowed to interrupt. Raising this to "critical" is the
    # single knob a tenant reaches for when they say "too noisy", and it is one config change.
    "interrupt_band": "critical",
    # The band below which work waits for the digest rather than being pushed at all.
    "push_band": "high",
    # Confidence floor for interrupting. A 92-score conclusion the reasoner is 40% sure of is
    # exactly the kind of thing that should reach someone calmly, not urgently.
    "interrupt_min_confidence_bp": 6_000,
}

#: Tone is a rendering instruction for Layer 6's copy step, not prose written here. Layer 5 says
#: *how this should land*; the renderer's validators still refuse any word not grounded in facts.
_TONE_BY_TYPE: Mapping[ExecutionType, str] = {
    ExecutionType.DECISION_REQUIRED: "direct",
    ExecutionType.COMMUNICATION: "direct",
    ExecutionType.TASK: "direct",
    ExecutionType.MONITORING: "informational",
}


def _config(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULTS, **dict(cfg or {})}
    merged["bands"] = {**DEFAULTS["bands"], **dict(merged.get("bands") or {})}
    return merged


def projected_score(priority_bp: int) -> int:
    """Basis points to the historical 0..100 score, half-up.

    The same projection law the authority SQL uses (``AUTHORITATIVE_SCORE_SQL``). Reimplementing
    it with a different rounding rule would make a card that Postgres considers authoritative
    fall one point short of a band here, and the resulting "why didn't this page me?" would be
    unanswerable from either side.
    """
    return (int(priority_bp) + 50) // 100


def band_of(priority_bp: int, cfg: Mapping[str, Any] | None = None) -> str:
    settings = _config(cfg)
    score = projected_score(priority_bp)
    if score >= int(settings["bands"]["critical"]):
        return "critical"
    if score >= int(settings["bands"]["high"]):
        return "high"
    return "standard"


_BAND_RANK: Mapping[str, int] = {"standard": 0, "high": 1, "critical": 2}


def may_interrupt(band: str, confidence_bp: int, cfg: Mapping[str, Any] | None = None) -> bool:
    """Is this loud enough *and* certain enough to be allowed to buzz a phone?

    Extracted so the card path can ask the same question.  Layer 6 pushes high/critical cards to
    chat without ever building a ``CommunicationPlan``, and it still has to mark each one with
    whether it may break through quiet hours.  Deriving that over there would put a second copy
    of ``interrupt_band`` and ``interrupt_min_confidence_bp`` below the real ones — and the
    failure mode of two copies is not that they both exist, it is that a tenant turns the noise
    down in one place and the phone keeps ringing from the other.
    """
    settings = _config(cfg)
    return (_BAND_RANK.get(str(band), 0) >= _BAND_RANK[str(settings["interrupt_band"])]
            and int(confidence_bp) >= int(settings["interrupt_min_confidence_bp"]))


def plan_communication(context: ExecutionContext, assignment: Assignment, *,
                       available_channels: frozenset[str] | set[str] | None = None,
                       autonomous: bool = False,
                       cfg: Mapping[str, Any] | None = None) -> CommunicationPlan:
    """Decide audience, channel, interrupt and tone — and record why.

    Ordered most-constrained first.  Each branch is a *refusal to escalate the channel*, and
    they are checked before the branches that would: an unrouted commitment cannot be pushed to
    a person who does not exist, and an autonomous one should not spend human attention at all.
    """
    settings = _config(cfg)
    channels = set(available_channels or ())
    band = band_of(context.priority_bp, settings)

    # 1. There is NOBODY — not an owner, not even an admin to triage it. It lands on the card
    #    surface and waits. Pushing here would mean choosing a recipient at random, which is
    #    worse than the queue: it creates the appearance of ownership without any.
    #
    #    The test used to be `not assignment.routed` — "nobody OWNS it" — and that is a much
    #    larger set. `deal.owner`, `relationship.owner` and `commitment.actor` have no
    #    `write_fact` producer anywhere in this repo and `graph_nodes.attributes` is never
    #    populated, so `routed` is False for EVERY commitment of EVERY tenant, forever
    #    (production 2026-08-30: 203/203 executions, `routing_rule='rule3_admin_queue'`). This
    #    branch therefore swallowed the whole layer: every commitment came out `in_app`,
    #    `assignee=null`, `remindable=false`, and not one reminder was ever decided.
    #
    #    The honest test is whether anyone can be REACHED. When rule 3 resolves an admin seat
    #    there is a real person on the other end, so the commitment routes by band like any
    #    other. Ownership still stays absent — the audience remains ADMIN_QUEUE and the card
    #    still says "unclaimed" — because being shown work is not the same as owning it.
    if assignment.recipient is None:
        return CommunicationPlan(
            audience=AudienceClass.ADMIN_QUEUE, channel_class=ChannelClass.IN_APP,
            channel_id=IN_APP_CHANNEL, interrupt=False,
            tone=_TONE_BY_TYPE.get(context.execution_type, "direct"),
            format_kind="card", reason_code=f"unrouted_{assignment.reason_code}", assignee=None)

    # 2. A machine can do the whole thing. Send it to the executor, not to a person's attention.
    if autonomous and AGENT_CHANNEL in channels:
        return CommunicationPlan(
            audience=AudienceClass.AGENT, channel_class=ChannelClass.AGENT,
            channel_id=AGENT_CHANNEL, interrupt=False, tone="machine",
            format_kind="agent_task", reason_code="autonomous_agent_executable",
            # No `queue_seat` here, and that is the point: a machine is doing the whole thing,
            # so the plan is deliberately not routable and the commitment is deliberately not
            # remindable. Nudging a person about work a machine already owns is the reminder
            # engine at its worst. (This branch is unreachable on both live orgs today —
            # neither has registered the `agent` channel.)
            assignee=assignment.seat_id)

    tone = "urgent" if band == "critical" else _TONE_BY_TYPE.get(context.execution_type, "direct")
    return _route_by_band(assignment, band=band, confidence_bp=context.confidence_bp, tone=tone,
                          channels=channels, settings=settings)


def _route_by_band(assignment: Assignment, *, band: str, confidence_bp: int, tone: str,
                   channels: set[str], settings: Mapping[str, Any]) -> CommunicationPlan:
    """Branches 3-6: how loudly, given that there IS somebody to reach.

    Extracted so `replan_for_recipient` below can ask the identical question without a second
    copy of the band rules. Two copies would not fail loudly; they would drift, and a tenant who
    turned the noise down would find one of them still shouting.
    """
    chat = next((name for name in CHAT_CHANNELS if name in channels), None)
    band_rank = _BAND_RANK[band]

    # 3. Loud enough to interrupt — but only if the reasoner is actually sure. A high score with
    #    low confidence is a hypothesis, and hypotheses do not get to buzz someone's phone.
    if chat and may_interrupt(band, confidence_bp, settings):
        return CommunicationPlan(
            audience=assignment.audience, channel_class=ChannelClass.CHAT, channel_id=chat,
            interrupt=True, tone=tone, format_kind="card",
            reason_code=f"band_{band}_interrupt", assignee=assignment.seat_id,
            queue_seat=assignment.queue_seat)

    # 4. Worth pushing, not worth interrupting. Same channel, no urgency framing.
    if chat and band_rank >= _BAND_RANK[str(settings["push_band"])]:
        reason = (f"band_{band}_push" if confidence_bp
                  >= int(settings["interrupt_min_confidence_bp"])
                  else f"band_{band}_push_low_confidence")
        return CommunicationPlan(
            audience=assignment.audience, channel_class=ChannelClass.CHAT, channel_id=chat,
            interrupt=False, tone=tone, format_kind="card", reason_code=reason,
            assignee=assignment.seat_id, queue_seat=assignment.queue_seat)

    # 5. Routine. It goes in the batch, where routine work belongs.
    if DIGEST_CHANNEL in channels or chat:
        return CommunicationPlan(
            audience=assignment.audience, channel_class=ChannelClass.DIGEST,
            channel_id=DIGEST_CHANNEL, interrupt=False, tone=tone, format_kind="digest_item",
            reason_code=f"band_{band}_digest", assignee=assignment.seat_id,
            queue_seat=assignment.queue_seat)

    # 6. The org has registered nothing. The card surface still works, and the commitment is
    #    still tracked, reminded and escalated — it simply waits to be found rather than sent.
    return CommunicationPlan(
        audience=assignment.audience, channel_class=ChannelClass.IN_APP, channel_id=IN_APP_CHANNEL,
        interrupt=False, tone=tone, format_kind="card", reason_code="no_channel_registered",
        assignee=assignment.seat_id, queue_seat=assignment.queue_seat)


def replan_for_recipient(plan: CommunicationPlan, assignment: Assignment, *, priority_bp: int,
                         confidence_bp: int,
                         available_channels: frozenset[str] | set[str] | None = None,
                         cfg: Mapping[str, Any] | None = None,
                         reason_code: str = "reachability_restored") -> CommunicationPlan:
    """Re-ask *where and how loudly* for a commitment that had nobody to reach.

    Distinct from ``reassign`` above, which keeps the channel because reassignment changes only
    who does the work. Here the channel itself was mis-decided: branch 1 sends a commitment to
    the card surface *because* there is no recipient, so a plan built while the directory was
    empty says ``in_app`` for a reason that has stopped being true. Leaving it would make the
    heal half a heal — the commitment becomes remindable, and then Layer 6's bridge (which obeys
    Layer 5's recorded ``channel_id``) declines to carry the reminder anywhere.

    Only ever called when the old plan had no recipient and the new assignment does. A plan that
    already names somebody keeps the channel it was given: that one WAS decided on true inputs.
    """
    if plan.routable or assignment.recipient is None:
        return plan
    settings = _config(cfg)
    band = band_of(priority_bp, settings)
    tone = "urgent" if band == "critical" else plan.tone
    replanned = _route_by_band(assignment, band=band, confidence_bp=confidence_bp, tone=tone,
                               channels=set(available_channels or ()), settings=settings)
    return CommunicationPlan(
        audience=replanned.audience, channel_class=replanned.channel_class,
        channel_id=replanned.channel_id, interrupt=replanned.interrupt, tone=replanned.tone,
        format_kind=replanned.format_kind,
        # The band branch's own code is kept as a suffix rather than replaced: "why is this on
        # Slack?" and "why did it start being on Slack?" are different questions and the row has
        # to answer both.
        reason_code=f"{reason_code}_{replanned.reason_code}",
        assignee=replanned.assignee, cc=plan.cc, queue_seat=replanned.queue_seat)


def reassign(plan: CommunicationPlan, assignment: Assignment, *,
             reason_code: str = "reassigned") -> CommunicationPlan:
    """Point an existing plan at a different person, keeping everything else.

    Reassignment is an operation on a live commitment, which is precisely why the communication
    plan is excluded from ``ExecutionObject.execution_id``: handing work to a colleague must not
    mint a second copy of the same commitment for the escalation ladder to chase separately.
    """
    if not assignment.routed:
        # Handing work back to the queue keeps the queue's own seat, so the commitment stays
        # REACHABLE while becoming unowned again. Dropping it here is what made the reroute path
        # a one-way trip to silence: `execution_guard` rule 7 reroutes when an owner goes
        # inactive, and the replacement plan had nobody on it at all.
        return CommunicationPlan(
            audience=AudienceClass.ADMIN_QUEUE, channel_class=ChannelClass.IN_APP,
            channel_id=IN_APP_CHANNEL, interrupt=False, tone=plan.tone, format_kind="card",
            reason_code=f"{reason_code}_unrouted", assignee=None,
            queue_seat=assignment.queue_seat)
    return CommunicationPlan(
        audience=assignment.audience, channel_class=plan.channel_class,
        channel_id=plan.channel_id, interrupt=plan.interrupt, tone=plan.tone,
        format_kind=plan.format_kind, reason_code=reason_code, assignee=assignment.seat_id,
        cc=plan.cc)


__all__ = ["AGENT_CHANNEL", "CHAT_CHANNELS", "COMMUNICATION_VERSION", "DEFAULTS",
           "DIGEST_CHANNEL", "IN_APP_CHANNEL", "band_of", "may_interrupt",
           "plan_communication", "projected_score", "reassign", "replan_for_recipient"]
