"""Category 2 · Business Evaluation — the Impact Unit.

Answers one question: *if this goes one way or the other, how much actually changes?*

Impact is the size of the swing, not the direction of it and never the choice about it. A deal
worth twelve thousand and a deal worth twelve million can sit in exactly the same state, with the
same risk and the same urgency, and still deserve very different amounts of human attention. That
difference is what this unit measures, and nothing else in Layer 4 measures it: temporal knows the
clock, relationship knows the coverage, risk knows the downside — none of them know the stake.

The stake is read across three independent dimensions, because they fail independently and are
evidenced independently:

* **Revenue exposure** — the money on the table, scaled against what "big" means for this
  capability. A number is only large relative to a declared reference.
* **Account importance** — how much relationship sits behind the entity. A named strategic account
  is a bigger loss than an equal-sized deal with a one-thread stranger.
* **Strategic linkage** — whether this entity is attached to something the business has said it is
  trying to do. Work that advances a declared goal is worth more than equally-sized work that
  does not.

Three rules keep the unit honest:

**Silence is not zero.** A dimension with no evidence contributes no observation *and publishes no
metric*. Emitting `revenue_exposure_bp = 0` because Layer 2 never supplied a deal value would be a
fabricated fact — downstream it is indistinguishable from a genuinely worthless deal. An absent
metric lets the reader supply their own default; a fabricated zero silently lies.

**The blend renormalises over what was actually seen.** Impact is a weighted mean of the present
dimensions only. Averaging a known 9,000bp revenue exposure against two unknowns would report a
3,000bp stake for a deal we know to be enormous.

**It never picks a play.** Where large stakes should make a play more attractive, the tilt is
authored in Layer 3 as `play_impact_bp: {play_id: delta}` and merely *scaled* here by the measured
impact. The unit supplies the magnitude; the capability author supplies the judgement about which
play the magnitude favours; the Decision Maker does the actual choosing. Hardcoding play names here
would make this unit a decision authority by the back door.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.contracts.reasoning import (
    CandidateAdjustment,
    CandidateCheck,
    CheckOutcome,
    Finding,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, evidence_ids, fact_value, integer

#: Reason code carried by every adjustment and check this unit emits, so an auditor can ask "what
#: moved this play?" and get an answer that names the stake rather than the unit.
IMPACT_ADJUSTMENT_REASON = "impact_magnitude_at_stake"


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Read one basis-point tuning value, refusing anything that is not integer bp.

    A silently coerced float here would change the decision hash on a different machine, so a
    malformed capability is a loud authoring fault rather than a quiet rescore.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_positive(view: UnitView, key: str, default: int) -> int:
    """Read a positive integer scale (a money reference, not a ratio)."""
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _delta_bp(value: Any, label: str) -> int:
    """An adjustment delta may be negative — a large stake can also make a cheap play look worse."""
    if isinstance(value, bool) or not isinstance(value, int) or not -10_000 <= value <= 10_000:
        raise ValueError(f"{label} must be an integer between -10000 and 10000")
    return value


def _mapping_config(view: UnitView, key: str) -> Mapping[str, Any]:
    value = view.config.get(key)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be a mapping")
    return value


class RevenueExposurePlugin:
    """The money at stake, expressed against what this capability calls a large deal.

    Absolute currency amounts are meaningless across tenants: 50,000 is a rounding error to an
    enterprise team and a record quarter to a two-person agency. So the plugin reports a *ratio*
    against `reference_value` — the amount Layer 3 declares as "fully material here" — and saturates
    at that point. Beyond the reference the stake is already maximal for attention purposes; a deal
    ten times the reference does not deserve ten times the priority, it deserves the top of the
    scale.
    """

    plugin_id = "revenue_exposure"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        field = str(view.config.get("value_field") or "deal.value")
        raw = fact_value(view.request, field)
        if raw is None:
            return ()                       # no amount recorded — that is unknown, not small
        try:
            amount = integer(raw, field)
        except ValueError:
            # A malformed amount is not a small amount. Reporting 0 would understate a live deal;
            # staying silent lets the missing-evidence path handle it honestly.
            return ()
        if amount <= 0:
            # A zero or negative recorded value carries no information about the stake (it is how
            # CRMs represent "not filled in yet" and how they represent credits), so we say nothing.
            return ()
        reference = _config_positive(view, "reference_value", 100_000)
        strength = clamp_bp(divide_half_up(amount * 10_000, reference))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="impact.revenue_exposure",
            metrics={"strength_bp": strength, "exposure_value": amount},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=("revenue_at_stake",),
        ),)


class AccountImportancePlugin:
    """How much relationship is riding on the outcome.

    Two readings, in order of authority. If the capability names a tier fact and a tier→weight map,
    that explicit business classification wins: a company that has been designated strategic is
    strategic regardless of how many threads happen to be open today.

    Failing that, the unit falls back to the breadth already measured by the relationship reasoner.
    Breadth is a defensible proxy for stake because a well-multithreaded account represents more
    accumulated relationship capital — more people, more history, more to lose in either direction.
    It is a weaker claim than an explicit tier, which is why it is the fallback and not the primary.

    The fallback uses a negative sentinel rather than the usual 0 default, because "the relationship
    reasoner did not run" and "coverage is genuinely zero" are different facts and only one of them
    justifies an observation.
    """

    plugin_id = "account_importance"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        tier_field = str(view.config.get("account_tier_field") or "").strip()
        weights = _mapping_config(view, "account_tier_bp")
        if tier_field and weights:
            tier = fact_value(view.request, tier_field)
            if tier is not None:
                # Tier labels arrive from CRMs with arbitrary casing and padding; normalise both
                # sides. Sorted iteration makes a key collision after normalisation resolve the
                # same way on every machine instead of by dict order.
                table = {str(key).strip().lower(): weights[key] for key in sorted(weights)}
                label = str(tier).strip().lower()
                if label in table:
                    strength = _delta_bp(table[label], f"account_tier_bp.{label}")
                    if strength >= 0:
                        return (Observation(
                            plugin_id=self.plugin_id,
                            kind="impact.account_importance",
                            metrics={"strength_bp": clamp_bp(strength)},
                            evidence_ids=evidence_ids(view.request, tier_field),
                            reason_codes=("named_account_tier",),
                        ),)
        source = str(view.config.get("relationship_reasoner") or "core.relationship")
        coverage_bp = view.prior_metric(source, "coverage_bp", -1)
        if coverage_bp < 0:
            return ()                       # the dependency did not run; we have nothing to say
        return (Observation(
            plugin_id=self.plugin_id,
            kind="impact.account_importance",
            metrics={"strength_bp": clamp_bp(coverage_bp)},
            reason_codes=("relationship_footprint",),
        ),)


class StrategicLinkagePlugin:
    """Whether this entity is attached to something the business declared it is trying to do.

    Strategic weight is not inferable from the entity itself — it is a statement of intent that
    lives in the capability. So the plugin reads a fact the capability names (a list of initiative
    or goal ids the entity is tagged with) and scores it against a weight table the capability
    authors. Without both halves it contributes nothing rather than guessing that untagged work is
    unimportant.

    Linkage to the capability's *own* declared goal is treated as strategic by definition — the
    capability exists to move that goal — so it carries a configured default even when the author
    never listed the goal in the weight table.

    The strongest single linkage sets the level. A deal attached to five minor initiatives is not
    more strategic than one attached to the company's stated priority; summing would say otherwise.
    """

    plugin_id = "strategic_linkage"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        field = str(view.config.get("strategic_link_field") or "").strip()
        if not field:
            return ()
        raw = fact_value(view.request, field)
        if raw is None:
            return ()
        items = raw if isinstance(raw, (tuple, list)) else (raw,)
        links = tuple(sorted({str(item).strip() for item in items if str(item).strip()}))
        if not links:
            return ()
        weights = _mapping_config(view, "strategic_goal_bp")
        table = {str(key).strip(): weights[key] for key in sorted(weights)}
        goal_id = view.request.capability.goal.goal_id
        scores: list[int] = []
        codes: list[str] = []
        for link in links:                  # links are sorted, so the scan is order-independent
            if link == goal_id:
                strength = _config_bp(view, "goal_alignment_bp", 6_000) if link not in table \
                    else clamp_bp(_delta_bp(table[link], f"strategic_goal_bp.{link}"))
                codes.append("linked_to_capability_goal")
            elif link in table:
                strength = clamp_bp(_delta_bp(table[link], f"strategic_goal_bp.{link}"))
                codes.append("linked_to_strategic_initiative")
            else:
                continue                    # an untagged initiative is unweighted, not zero-weight
            scores.append(strength)
        if not scores:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="impact.strategic_linkage",
            metrics={"strength_bp": max(scores), "linked_goal_count": len(scores)},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=tuple(codes),
        ),)


#: The dimensions of the stake, in a fixed order: (plugin, published metric, weight key, default).
#: Declared as data rather than branching code so that the published metric names, the tuning keys,
#: and the blend can never drift apart. Default weights say revenue dominates, relationship matters,
#: and strategy is a tie-breaker — the ordering most capabilities start from and then re-author.
_DIMENSIONS: tuple[tuple[str, str, str, int], ...] = (
    ("revenue_exposure", "revenue_exposure_bp", "revenue_weight_bp", 5_000),
    ("account_importance", "relationship_exposure_bp", "relationship_weight_bp", 3_000),
    ("strategic_linkage", "strategic_bp", "strategic_weight_bp", 2_000),
)


class ImpactUnit(ReasoningUnit):
    """Business Evaluation · how much is at stake if this goes one way or the other."""

    unit_id = "core.impact"
    version = "1.0.0"
    category = UnitCategory.BUSINESS_EVALUATION
    publishes = ("impact_bp", "revenue_exposure_bp", "relationship_exposure_bp",
                 "strategic_bp", "impact_signal_count")
    plugins = (AccountImportancePlugin(), RevenueExposurePlugin(), StrategicLinkagePlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Weighted mean over the dimensions that actually reported.

        Deliberately *not* a mean over all three dimensions: an unmeasured dimension has no value,
        and treating it as zero would report a small stake for a large deal whose account tier
        simply was not synced. Renormalising over the observed weights keeps the number meaning
        "how big is this, given what we know" instead of "how complete is our data".

        `impact_bp` is omitted entirely when nothing reported, so a reader gets their own default
        rather than a manufactured 0.
        """
        strengths: dict[str, int] = {}
        for item in observations:
            value = clamp_bp(int(item.metrics.get("strength_bp", 0)))
            # A plugin emits at most one observation today; taking the max keeps the arithmetic
            # total and order-free if one ever emits several.
            strengths[item.plugin_id] = max(strengths.get(item.plugin_id, 0), value)

        metrics: dict[str, int] = {}
        weighted_sum = 0
        total_weight = 0
        present: list[int] = []
        for plugin_id, metric_name, weight_key, default_weight in _DIMENSIONS:
            if plugin_id not in strengths:
                continue
            strength = strengths[plugin_id]
            metrics[metric_name] = strength
            weight = _config_bp(view, weight_key, default_weight)
            weighted_sum += strength * weight
            total_weight += weight
            present.append(strength)

        metrics["impact_signal_count"] = len(present)
        if present:
            # An author who zeroes every weight has not asked for a zero impact — they have removed
            # the weighting, so fall back to an unweighted mean rather than dividing by zero.
            metrics["impact_bp"] = clamp_bp(divide_half_up(weighted_sum, total_weight)) \
                if total_weight > 0 else clamp_bp(divide_half_up(sum(present), len(present)))
        return metrics

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """Is the stake material, and if so how far should it tilt the declared plays?

        `matched` is None when no dimension reported — the unit has no opinion, which is a different
        statement from "this is immaterial" and must not be collapsed into False.

        Adjustments are scaled by the measured impact, so the author's delta is the ceiling reached
        at a maximal stake rather than a flat bonus applied to anything that clears the threshold.
        Each adjustment is mirrored by a `cost_benefit` check so the tilt shows up in the audit
        trail next to the score it moved, instead of appearing as an unexplained component delta.
        """
        impact_bp = metrics.get("impact_bp")
        if impact_bp is None:
            return Verdict(matched=None, metrics=dict(metrics))

        threshold = _config_bp(view, "impact_threshold_bp", 5_000)
        material = impact_bp >= threshold
        evidence = tuple(sorted({item for observation in observations
                                 for item in observation.evidence_ids}))
        findings = tuple(Finding(
            finding_id=f"impact.{observation.plugin_id}",
            kind="impact",
            matched=True,
            metrics=observation.metrics,
            evidence_ids=observation.evidence_ids,
            reason_codes=observation.reason_codes,
        ) for observation in observations)

        adjustments: list[CandidateAdjustment] = []
        checks: list[CandidateCheck] = []
        if material:
            authored = _mapping_config(view, "play_impact_bp")
            for play_id in sorted(str(key) for key in authored):
                delta = _delta_bp(authored[play_id], f"play_impact_bp.{play_id}")
                scaled = divide_half_up(delta * impact_bp, 10_000)
                if scaled == 0:
                    continue                # a tilt that rounds away is noise in the audit trail
                adjustments.append(CandidateAdjustment(
                    play_id=play_id, component="impact", delta_bp=scaled,
                    reason_code=IMPACT_ADJUSTMENT_REASON, evidence_ids=evidence))
                checks.append(CandidateCheck(
                    play_id=play_id, stage="cost_benefit", outcome=CheckOutcome.ADJUST,
                    reason_code=IMPACT_ADJUSTMENT_REASON, evaluator_id=self.unit_id,
                    evaluator_version=self.version,
                    detail={"impact_bp": impact_bp, "delta_bp": scaled}))

        codes = {code for observation in observations for code in observation.reason_codes}
        codes.add("material_impact" if material else "immaterial_impact")
        return Verdict(
            matched=material,
            metrics=dict(metrics),
            findings=findings,
            adjustments=tuple(adjustments),
            checks=tuple(checks),
            reason_codes=tuple(sorted(codes)),
        )


__all__ = ["AccountImportancePlugin", "IMPACT_ADJUSTMENT_REASON", "ImpactUnit",
           "RevenueExposurePlugin", "StrategicLinkagePlugin"]
