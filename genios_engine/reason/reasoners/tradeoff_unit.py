"""Category 3 · Optimization — the Tradeoff Unit.

Answers one question: *which competing objective is winning here, and what is being given up?*

Every real business decision is contested. Closing this week protects the quarter but concedes
margin. Sending now protects momentum but concedes certainty. Chasing the upside concedes caution.
The rest of Layer 4 is built out of units that each look at one side of that argument — risk looks
at downside, opportunity at upside, temporal at time pressure — and each one is honest inside its
own frame. Nobody, until this unit, holds two of those frames against each other and says *these
two are pulling in opposite directions, and this is how hard*.

That is what makes this the first genuinely executive unit. An operator asks "is this risky?"; an
executive asks "risky compared to what am I giving up by waiting?" This unit does the comparison
and nothing more.

Three properties are deliberate:

**It compares, it never chooses.** The unit reports a *lean* — which side the already-published
evidence favours — and the size of the margin behind that lean. Selecting a play, ranking plays,
or emitting a score adjustment would make it a second decision authority, and GeniOS has exactly
one (`reason/decision_maker.py`). So this unit emits no adjustments and no checks at all.

**It names the loser.** A recommendation nobody can argue with is a recommendation nobody can
audit. Every axis publishes a `concedes.*` reason code alongside its `favours.*` code, so the
delivered explanation can say "we leaned to speed and gave up certainty" rather than presenting a
contested call as if it were obvious.

**It is silent unless both sides spoke.** A tradeoff needs two pressures. If only one of the pair
was published — the risk unit ran and the opportunity unit did not — there is no tension to
measure, and inventing the missing side as zero would fabricate a landslide out of a blind spot.

It reads only metrics other units already published, so it adds no new fact dependency and can be
scheduled last in any capability without changing what Layer 2 must supply.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import Finding

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up

# Basis points are 0..10000 by law, so a negative sentinel can never collide with a real published
# value. It is how a plugin distinguishes "the unit said zero" from "the unit never ran" — the
# difference between a measured absence of pressure and a blind spot.
_ABSENT = -1


def _config_bp(view: UnitView, key: str, default: int) -> int:
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_id(view: UnitView, key: str, default: str) -> str:
    """Which unit supplies one side of an axis, so a capability can substitute its own authority."""
    value = view.config.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must name a reasoning unit")
    return value.strip()


def _prior_bp(view: UnitView, key: str, default_unit: str, metric: str) -> int | None:
    """One side of a tradeoff, or None when the unit that owns it did not complete."""
    value = view.prior_metric(_config_id(view, key, default_unit), metric, _ABSENT)
    return None if value == _ABSENT else clamp_bp(value)


def _weigh(view: UnitView, plugin_id: str, axis: str,
           first_side: str, first_bp: int, second_side: str, second_bp: int
           ) -> tuple[Observation, ...]:
    """Score one contested axis: how tight the contest is, and which way it leans.

    `tension_bp = weaker × (10000 − margin) / 10000`

    Two judgements are encoded there, and both matter:

    * **The weaker side sets the ceiling.** A tradeoff is only as real as its weakest pressure.
      Enormous upside against no downside is not a dilemma, it is a free move, and reporting it as
      maximum tension would make every strong opportunity look agonising.
    * **Distance discounts it.** Two pressures that are both strong *and* close is the situation a
      human actually has to think about; a four-thousand-point gap has already been settled by the
      evidence, whatever its absolute level.

    Below `decisive_margin_bp` no side is named. A lean the width of rounding noise is not a lean,
    and letting one basis point decide which objective "won" would produce explanations that flip
    between runs on immaterial input drift.
    """
    margin = abs(first_bp - second_bp)
    tension = divide_half_up(min(first_bp, second_bp) * (10_000 - margin), 10_000)
    codes = [f"tradeoff.{axis}"]
    if margin < _config_bp(view, "decisive_margin_bp", 500):
        codes.append(f"balanced.{axis}")
    elif first_bp > second_bp:
        codes.extend((f"favours.{first_side}", f"concedes.{second_side}"))
    else:
        codes.extend((f"favours.{second_side}", f"concedes.{first_side}"))
    return (Observation(
        plugin_id=plugin_id,
        kind=f"tradeoff.{axis}",
        metrics={"tension_bp": clamp_bp(tension), "margin_bp": clamp_bp(margin),
                 "leading_bp": max(first_bp, second_bp),
                 "trailing_bp": min(first_bp, second_bp)},
        reason_codes=tuple(codes),
    ),)


class SpeedVersusCertaintyPlugin:
    """Move now, or wait until we are surer?

    The oldest argument in any commercial operation. Time pressure is what the temporal unit
    measured; the pull in the other direction is *doubt*, which is the complement of published
    confidence — the less well evidenced we are, the more a delay is worth. Reading confidence and
    inverting it here is the whole point of the axis: acting fast is only cheap when we are sure.

    This unit reads `confidence_bp`; it must never publish it. `core.confidence` is its sole
    authority, and a second publisher would silently re-score every decision in the system.
    """

    plugin_id = "speed_vs_certainty"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        speed = _prior_bp(view, "speed_source", "core.temporal", "urgency_bp")
        confidence = _prior_bp(view, "certainty_source", "core.confidence", "confidence_bp")
        if speed is None or confidence is None:
            return ()
        # The case for waiting is exactly as strong as our remaining doubt.
        return _weigh(view, self.plugin_id, "speed_vs_certainty",
                      "speed", speed, "certainty", clamp_bp(10_000 - confidence))


class RiskVersusRewardPlugin:
    """Chase the upside, or protect the downside?

    Both sides already exist as audited units, and until now they were only ever summed into a
    score. Holding them apart is what lets an explanation say "the upside is worth more than the
    exposure, and here is the exposure we accepted" — which is the sentence an executive needs and
    a weighted average destroys.
    """

    plugin_id = "risk_vs_reward"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        reward = _prior_bp(view, "reward_source", "core.opportunity", "opportunity_bp")
        risk = _prior_bp(view, "risk_source", "core.risk", "risk_bp")
        if reward is None or risk is None:
            return ()
        return _weigh(view, self.plugin_id, "risk_vs_reward",
                      "reward", reward, "caution", risk)


class CostVersusBenefitPlugin:
    """Is the prize worth the work?

    Effort is the one cost that never appears on an invoice and is therefore the one most often
    ignored. A modest benefit that consumes a week of a senior person is a worse call than a
    smaller benefit that costs an hour, and a system that only ever reported benefit would keep
    recommending the first.

    Both sides come from whichever units a capability appoints; where neither has been deployed the
    plugin stays silent rather than treating unmeasured effort as free.
    """

    plugin_id = "cost_vs_benefit"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        benefit = _prior_bp(view, "benefit_source", "core.impact", "impact_bp")
        cost = _prior_bp(view, "cost_source", "core.effort", "effort_bp")
        if benefit is None or cost is None:
            return ()
        return _weigh(view, self.plugin_id, "cost_vs_benefit",
                      "benefit", benefit, "restraint", cost)


class TradeoffUnit(ReasoningUnit):
    """Optimization · which competing objective the evidence favours, and what it costs.

    Publishes the sharpest contested axis rather than a blend. It reports; the Decision Maker
    still chooses, and nothing here touches a candidate.
    """

    unit_id = "core.tradeoff"
    version = "1.0.0"
    category = UnitCategory.OPTIMIZATION
    publishes = ("tension_bp", "margin_bp", "axis_count", "contested_count")
    plugins = (CostVersusBenefitPlugin(), RiskVersusRewardPlugin(), SpeedVersusCertaintyPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """The hardest dilemma sets the headline; the settled ones are still counted.

        Deliberately a maximum, not a mean. A situation containing one genuinely contested axis and
        two settled ones is a hard situation — averaging would report it as easy and hide the exact
        thing a human is needed for. `axis_count` says how many comparisons were possible at all,
        which is how a reviewer tells "nothing was contested" apart from "nothing was measurable".
        """
        threshold = _config_bp(view, "tension_threshold_bp", 3_000)
        ranked = self._ranked(observations)
        if not ranked:
            return {"tension_bp": 0, "margin_bp": 0, "axis_count": 0, "contested_count": 0}
        sharpest = ranked[0]
        return {
            "tension_bp": int(sharpest.metrics["tension_bp"]),
            "margin_bp": int(sharpest.metrics["margin_bp"]),
            "axis_count": len(ranked),
            "contested_count": sum(1 for item in ranked
                                   if int(item.metrics["tension_bp"]) >= threshold),
        }

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """`matched` means "a real dilemma exists here", not "do the leading thing".

        Every axis becomes a finding whether or not it was close, because what was given up is part
        of the explanation even when the call was easy. The sharpest axis's lean is repeated under a
        `headline.` prefix so a renderer can name one tension without re-deriving the ranking.
        """
        ranked = self._ranked(observations)
        contested = metrics["tension_bp"] >= _config_bp(view, "tension_threshold_bp", 3_000)
        findings = tuple(Finding(
            finding_id=f"tradeoff.{item.plugin_id}",
            kind="tradeoff",
            matched=int(item.metrics["tension_bp"]) >= _config_bp(
                view, "tension_threshold_bp", 3_000),
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in ranked)
        codes = {code for item in ranked for code in item.reason_codes}
        if ranked:
            codes.update(f"headline.{code}" for code in ranked[0].reason_codes
                         if not code.startswith("tradeoff."))
            codes.add("tradeoff_contested" if contested else "tradeoff_settled")
        return Verdict(
            matched=contested,
            metrics=dict(metrics),
            findings=findings,
            reason_codes=tuple(sorted(codes)),
        )

    @staticmethod
    def _ranked(observations: Sequence[Observation]) -> tuple[Observation, ...]:
        """Total order over axes: tightest contest first, then the narrower margin, then plugin id.

        The final key is not decoration. Two axes can tie on both numbers, and if the winner were
        then decided by iteration order the headline — and every hash downstream of it — would
        depend on registration order rather than on the evidence.
        """
        return tuple(sorted(observations, key=lambda item: (
            -int(item.metrics["tension_bp"]),
            int(item.metrics["margin_bp"]),
            item.plugin_id,
        )))


__all__ = ["CostVersusBenefitPlugin", "RiskVersusRewardPlugin", "SpeedVersusCertaintyPlugin",
           "TradeoffUnit"]
