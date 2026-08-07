"""Layer 5 · Unit 3 — semantic communication intent for a commitment.

This v1 unit records how important the commitment believes communication to be: business
audience, tone, presentation intent and historical route hints. Layer 5.2 treats those as input
intent, not current send authority. It resolves the live recipient, registered destination,
concrete channel and interruptibility from present context and policy.

The rules encode one principle: **interruption is a budget, not a feature.**  Every channel
here is ordered by how much of a person's attention it spends, and a commitment has to earn its
way up that order with score, not with enthusiasm.  A system that pages on everything is
indistinguishable from a system nobody reads.

The historical channel decision remains frozen and explained so old ExecutionObjects round-trip
and audits can reconstruct upstream intent. The Layer 5.2 orchestrator deliberately ignores its
concrete channel and interrupt fields when selecting an actual route.

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
CHAT_CHANNELS: tuple[str, ...] = ("slack", "teams")

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

#: Tone is a rendering instruction for Layer 5.2's copy step, not prose written here. Layer 5 says
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

    Extracted so the card path can ask the same question.  Layer 5.2 pushes high/critical cards to
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
    """Record business audience, tone and backwards-compatible route/attention hints.

    The returned concrete channel and interrupt values are part of the immutable v1/v2 contract's
    audit shape. Layer 5.2 recomputes the actual route and interrupt decision from current state.

    Ordered most-constrained first.  Each branch is a *refusal to escalate the channel*, and
    they are checked before the branches that would: an unrouted commitment cannot be pushed to
    a person who does not exist, and an autonomous one should not spend human attention at all.
    """
    settings = _config(cfg)
    channels = set(available_channels or ())
    band = band_of(context.priority_bp, settings)

    # 1. Nobody owns it. It lands on the admin surface and waits for a human to claim it. Pushing
    #    an unrouted commitment would mean choosing a recipient at random, which is worse than
    #    the queue: it creates the appearance of ownership without any.
    if not assignment.routed:
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
            assignee=assignment.seat_id)

    tone = "urgent" if band == "critical" else _TONE_BY_TYPE.get(context.execution_type, "direct")
    chat = next((name for name in CHAT_CHANNELS if name in channels), None)
    band_rank = _BAND_RANK[band]

    # 3. Loud enough to interrupt — but only if the reasoner is actually sure. A high score with
    #    low confidence is a hypothesis, and hypotheses do not get to buzz someone's phone.
    if chat and may_interrupt(band, context.confidence_bp, settings):
        return CommunicationPlan(
            audience=assignment.audience, channel_class=ChannelClass.CHAT, channel_id=chat,
            interrupt=True, tone=tone, format_kind="card",
            reason_code=f"band_{band}_interrupt", assignee=assignment.seat_id)

    # 4. Worth pushing, not worth interrupting. Same channel, no urgency framing.
    if chat and band_rank >= _BAND_RANK[str(settings["push_band"])]:
        reason = (f"band_{band}_push" if context.confidence_bp
                  >= int(settings["interrupt_min_confidence_bp"])
                  else f"band_{band}_push_low_confidence")
        return CommunicationPlan(
            audience=assignment.audience, channel_class=ChannelClass.CHAT, channel_id=chat,
            interrupt=False, tone=tone, format_kind="card", reason_code=reason,
            assignee=assignment.seat_id)

    # 5. Routine. It goes in the batch, where routine work belongs.
    if DIGEST_CHANNEL in channels or chat:
        return CommunicationPlan(
            audience=assignment.audience, channel_class=ChannelClass.DIGEST,
            channel_id=DIGEST_CHANNEL, interrupt=False, tone=tone, format_kind="digest_item",
            reason_code=f"band_{band}_digest", assignee=assignment.seat_id)

    # 6. The org has registered nothing. The card surface still works, and the commitment is
    #    still tracked, reminded and escalated — it simply waits to be found rather than sent.
    return CommunicationPlan(
        audience=assignment.audience, channel_class=ChannelClass.IN_APP, channel_id=IN_APP_CHANNEL,
        interrupt=False, tone=tone, format_kind="card", reason_code="no_channel_registered",
        assignee=assignment.seat_id)


def reassign(plan: CommunicationPlan, assignment: Assignment, *,
             reason_code: str = "reassigned") -> CommunicationPlan:
    """Point an existing plan at a different person, keeping everything else.

    Reassignment is an operation on a live commitment, which is precisely why the communication
    plan is excluded from ``ExecutionObject.execution_id``: handing work to a colleague must not
    mint a second copy of the same commitment for the escalation ladder to chase separately.
    """
    if not assignment.routed:
        return CommunicationPlan(
            audience=AudienceClass.ADMIN_QUEUE, channel_class=ChannelClass.IN_APP,
            channel_id=IN_APP_CHANNEL, interrupt=False, tone=plan.tone, format_kind="card",
            reason_code=f"{reason_code}_unrouted", assignee=None)
    return CommunicationPlan(
        audience=assignment.audience, channel_class=plan.channel_class,
        channel_id=plan.channel_id, interrupt=plan.interrupt, tone=plan.tone,
        format_kind=plan.format_kind, reason_code=reason_code, assignee=assignment.seat_id,
        cc=plan.cc)


__all__ = ["AGENT_CHANNEL", "CHAT_CHANNELS", "COMMUNICATION_VERSION", "DEFAULTS",
           "DIGEST_CHANNEL", "IN_APP_CHANNEL", "band_of", "may_interrupt",
           "plan_communication", "projected_score", "reassign"]
