"""Category 2 · Business Evaluation — the Opportunity Unit.

Answers one question: *where is there value to gain here that nobody has taken?*

An opportunity in GeniOS is never "this looks promising". It is a specific, evidenced gap between
what the situation makes possible and what has actually happened — an investor who replied and was
never answered, a buyer who went quiet while the deal is still open, an account with room to grow
and no one working it. Each of those is a separate plugin, because they are separate claims with
separate evidence, and folding them into one score would make the reasoning unexplainable.

The unit never proposes an action. It reports that headroom exists and how strongly; the Decision
Maker weighs that against risk, effort, and policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import Finding

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, elapsed_hours, fact_value


def _config_bp(view: UnitView, key: str, default: int) -> int:
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


class UnansweredInboundPlugin:
    """They reached out and nobody replied.

    The strongest opportunity signal in the system, because the counterparty already spent the
    effort — the cost of capture is one reply, and the window closes on its own.
    """

    plugin_id = "unanswered_inbound"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        inbound = fact_value(view.request, "deal.last_inbound")
        outbound = fact_value(view.request, "deal.last_outbound")
        if inbound is None:
            return ()
        try:
            inbound_hours = elapsed_hours(view.request, "deal.last_inbound")
        except ValueError:
            return ()
        if outbound is not None:
            try:
                if elapsed_hours(view.request, "deal.last_outbound") <= inbound_hours:
                    return ()               # we already answered; no gap remains
            except ValueError:
                return ()
        # Ripe by roughly a day, decaying in value thereafter — an answer tomorrow is worth much
        # less than an answer today, and after a week the moment has mostly passed.
        strength = clamp_bp(divide_half_up(min(inbound_hours, 168) * 10_000, 24)) \
            if inbound_hours <= 24 else clamp_bp(10_000 - divide_half_up(
                (min(inbound_hours, 336) - 24) * 6_000, 312))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="opportunity.unanswered_inbound",
            metrics={"strength_bp": strength, "waiting_hours": inbound_hours},
            reason_codes=("inbound_awaiting_reply",),
        ),)


class StalledButOpenPlugin:
    """The deal is still winnable and nothing is happening to win it."""

    plugin_id = "stalled_but_open"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        status = str(fact_value(view.request, "deal.status") or "").lower()
        if status not in {"open", "active", "in_progress", "negotiation"}:
            return ()
        quiet_bp = view.prior_metric("core.temporal", "drop_bp", 0)
        if quiet_bp <= 0:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="opportunity.stalled_but_open",
            metrics={"strength_bp": clamp_bp(quiet_bp)},
            reason_codes=("open_deal_without_momentum",),
        ),)


class UnworkedRelationshipPlugin:
    """A live relationship with no one currently working it."""

    plugin_id = "unworked_relationship"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        owner = fact_value(view.request, "deal.owner")
        if owner:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="opportunity.unowned",
            metrics={"strength_bp": _config_bp(view, "unowned_strength_bp", 4_000)},
            reason_codes=("no_owner_assigned",),
        ),)


class OpportunityUnit(ReasoningUnit):
    """Business Evaluation · where value can be gained."""

    unit_id = "core.opportunity"
    version = "1.0.0"
    category = UnitCategory.BUSINESS_EVALUATION
    publishes = ("opportunity_bp", "opportunity_count")
    plugins = (UnansweredInboundPlugin(), StalledButOpenPlugin(), UnworkedRelationshipPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Strongest signal leads, others contribute diminishing support.

        Deliberately not a sum: three weak hints are not a strong opportunity, and averaging would
        let one weak plugin drag down a genuinely ripe one. The strongest claim sets the level and
        corroboration adds a bounded lift.
        """
        strengths = sorted((int(item.metrics.get("strength_bp", 0)) for item in observations),
                           reverse=True)
        if not strengths:
            return {"opportunity_bp": 0, "opportunity_count": 0}
        lift = divide_half_up(sum(strengths[1:]), 4)
        return {"opportunity_bp": clamp_bp(strengths[0] + lift),
                "opportunity_count": len(strengths)}

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        threshold = _config_bp(view, "opportunity_threshold_bp", 3_000)
        present = metrics["opportunity_bp"] >= threshold
        findings = tuple(Finding(
            finding_id=f"opportunity.{item.plugin_id}",
            kind="opportunity",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations) if present else ()
        return Verdict(
            matched=present,
            metrics=dict(metrics),
            findings=findings,
            reason_codes=tuple(sorted({code for item in observations
                                       for code in item.reason_codes})) if present else (),
        )


__all__ = ["OpportunityUnit", "StalledButOpenPlugin", "UnansweredInboundPlugin",
           "UnworkedRelationshipPlugin"]
