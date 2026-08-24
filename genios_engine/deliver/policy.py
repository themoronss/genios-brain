"""Layer 5.2 · the Delivery Policy Unit — *is this allowed to travel this way at all?*

The timing unit asks whether the moment is humane.  This one asks the blunter question that has
to be settled first: is this delivery **permitted**.  A tenant on a compliance hold, a channel
somebody disconnected, a person who turned Slack pushes off — none of those are matters of
timing, and none of them get better in an hour.  Keeping the two questions in separate units is
what stops "you opted out" from being expressed as a deferral that quietly retries forever.

**Verdicts here are almost always terminal.**  Policy answers SEND or SUPPRESS.  It has one
deferral — an org-wide hold with a stated end — and that exists precisely because a hold *does*
have a clock, and pretending otherwise would throw away work that becomes legitimate on Monday.

**What is deliberately absent, and why.**

*No daily volume cap.*  There is already one: the pack's ``budget_per_user_day``, enforced in
``deliver/router.py``, which is documented there as "a property of the channel's politeness".
A second daily dial here would be a second answer to one question, and the failure mode is not
that a message gets blocked twice — it is that a support engineer finds one limit, changes it,
and nothing happens.  The timing unit caps the *burst*, which is a dimension the daily budget
genuinely does not cover; that is additive rather than duplicative.

*No "are they already handling it?" check.*  Layer 5 owns that, and already does it:
``executive_bridge.executive_delivery_is_live`` re-validates the commitment against live state
immediately before the send, and the card path re-checks decision authority in the same place.
Re-deriving liveness here would put a second, weaker copy of an authority predicate below the
real one, and two copies of an authority rule is how a revoked recommendation gets delivered.

*No content inspection.*  Policy sees a candidate, never a payload.  A rule that reads the
message is a rule that will eventually be asked to make exceptions for important-sounding ones.

**Purity.**  Like the timing unit: no database handle, no clock beyond what it is handed.  The
caller resolves a ``DeliveryPolicy`` for one (org, recipient, channel) triple and passes it in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.delivery import BAND_ORDER, DeliveryCandidate, DeliveryDecision

POLICY_VERSION = "policy.v1"
UNIT = "policy"


@dataclass(frozen=True, slots=True)
class DeliveryPolicy:
    """The resolved rules for exactly one (org, recipient, channel) triple.

    Not a config file — a *resolution*.  Org defaults, channel registration and the recipient's
    own preferences are merged by the caller into this flat answer, so the unit below never has
    to know which layer of settings a value came from.  That merge order is the store's business
    and is stated where it happens; the decision logic only ever sees the outcome.

    Defaults are permissive on purpose, and that is the opposite of the timing unit's protective
    defaults.  The asymmetry is intended: an *unconfigured* tenant should still receive its
    intelligence (permissive policy), just not at 3am (protective timing).  Silence by default
    would be indistinguishable from the product being broken.
    """

    delivery_enabled: bool = True         # org-level kill switch: compliance hold, trial ended
    hold_until: datetime | None = None    # a hold with a known end, rather than a stop
    channel_enabled: bool = True          # this adapter is registered and active for the org
    channel_min_band: str = "standard"    # the floor this channel accepts
    recipient_active: bool = True         # the seat still exists and is not deactivated
    recipient_opted_out: bool = False     # this person turned this channel off

    def __post_init__(self) -> None:
        if self.channel_min_band not in BAND_ORDER:
            raise ValueError(f"channel_min_band must be one of {BAND_ORDER}")
        # A stop and a pause are different promises; carrying both at once means neither is
        # legible in the audit row that explains a blocked delivery.
        if self.hold_until is not None and self.delivery_enabled is False:
            raise ValueError(
                "delivery_enabled=False is an indefinite stop; hold_until is a pause with an "
                "end — set one or the other, never both")


def evaluate_policy(candidate: DeliveryCandidate, policy: DeliveryPolicy, *,
                    now: datetime) -> DeliveryDecision:
    """Decide whether this delivery is permitted on this channel to this recipient.

    Ordered widest-blast-radius first.  An org on a compliance hold is a stronger fact than one
    person's notification preference, and checking it first means the reason code in the audit
    row names the *real* cause rather than whichever rule happened to be evaluated earliest.
    """
    # 1. The whole tenant is stopped. Nothing below this matters.
    if not policy.delivery_enabled:
        return DeliveryDecision.suppress(UNIT, "org_delivery_disabled")

    # 2. The tenant is paused with a known end — the one deferral policy issues. Work held here
    #    is legitimate again when the hold lifts, so discarding it would be a real loss.
    if policy.hold_until is not None and policy.hold_until > now:
        return DeliveryDecision.defer(UNIT, "org_delivery_held", policy.hold_until)

    # 3. Nobody has connected this channel, or somebody disconnected it. Not a failure to retry:
    #    a disconnected webhook does not reconnect itself, and retrying it burns the ladder that
    #    exists for genuinely transient faults.
    if not policy.channel_enabled:
        return DeliveryDecision.suppress(UNIT, "channel_inactive", channel=candidate.channel)

    # 4. This channel has a floor. Routine work reaching a channel reserved for escalations is
    #    how a channel stops being read, which costs more than the message was worth.
    if not candidate.at_least(policy.channel_min_band):
        return DeliveryDecision.suppress(UNIT, "below_channel_min_band",
                                         band=candidate.band,
                                         min_band=policy.channel_min_band)

    # 5 & 6. The recipient. Both are suppressions rather than reassignments: choosing a different
    #    person at delivery time would invent an owner the commitment never had, and Layer 5's
    #    unrouted path already exists for work with nobody to send it to. The commitment stays
    #    live, keeps escalating, and remains visible on the card surface — only this push stops.
    if not policy.recipient_active:
        return DeliveryDecision.suppress(UNIT, "recipient_inactive",
                                         recipient=candidate.recipient or "")
    if policy.recipient_opted_out:
        return DeliveryDecision.suppress(UNIT, "recipient_opted_out",
                                         recipient=candidate.recipient or "",
                                         channel=candidate.channel)

    return DeliveryDecision.send(UNIT, "permitted")


def describe_policy(policy: DeliveryPolicy) -> dict[str, Any]:
    """Flat, loggable summary — travels into the delivery audit row beside the verdict."""
    return {"delivery_enabled": policy.delivery_enabled,
            "hold_until": policy.hold_until.isoformat() if policy.hold_until else None,
            "channel_enabled": policy.channel_enabled,
            "channel_min_band": policy.channel_min_band,
            "recipient_active": policy.recipient_active,
            "recipient_opted_out": policy.recipient_opted_out}


__all__ = ["POLICY_VERSION", "UNIT", "DeliveryPolicy", "describe_policy", "evaluate_policy"]
