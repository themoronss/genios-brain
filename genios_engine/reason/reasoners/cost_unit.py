"""Category 3 · Optimization — the Cost Unit.

Answers one question: *what does acting here cost, and does that cost look worth paying?*

Every other unit in Part 2 argues for motion. Something is decaying, something is unanswered,
something is at risk — and each of those units is measuring a reason to act. Nothing in that set
measures the other side of the ledger, and a system that only ever prices the upside will act on
everything, which is indistinguishable from acting on nothing.

The Cost Unit prices the other side, in three separable claims:

* **Effort** — what the declared plays actually ask a human to do. Layer 3 authors a play with a
  declared ``effort_bp``; this unit re-derives effort from the steps the play actually contains and
  reports the disagreement, because a play whose declared effort drifted away from its real steps
  will otherwise be scored on a number nobody has checked since it was written.
* **The cost of *not* acting** — waiting is not free. A quiet thread does not stay warm, and the
  headroom another unit found does not stay open. This is the number that makes "expensive" a
  comparison rather than a verdict: an expensive play against a very expensive silence is cheap.
* **Downside exposure** — a play that sends something to an outsider, or that cannot be taken back,
  carries a cost that no amount of effort accounting shows.

Two deliberate asymmetries in how the roster is read, both chosen so the unit errs toward caution:

* Effort is reported as the roster's **floor** — acting means running *one* play, and the cheapest
  route is the least anyone could pay, so anything above it is real.
* Exposure is reported as the roster's **ceiling** — the unit does not know which play Part 3 will
  choose, so the exposure the capability carries is the worst it could incur.

Neither of those is a selection. This unit never picks a play, never ranks one, and never says
"do not act". Where cost clearly outruns benefit it raises a ``cost_benefit`` check with outcome
WARN — a flag on the ledger, deliberately not an elimination, because "expensive" is an input to a
decision and not the decision itself. Part 3 owns the verdict.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import (
    CandidateAdjustment,
    CandidateCheck,
    CheckOutcome,
    Finding,
    PlayDefinition,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, elapsed_hours, evidence_ids, fact_value

# The check stage this unit is allowed to speak on. Stated once so the string that has to match the
# frozen contract's vocabulary lives in exactly one place.
COST_BENEFIT_STAGE = "cost_benefit"


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Read one tuning knob as integer basis points, refusing anything else.

    Tuning is authored in Layer 3 and travels inside the versioned capability, so a bad value is a
    deployment fault that must fail loudly here rather than silently become a plausible-looking
    cost somewhere downstream.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _plays(view: UnitView) -> tuple[PlayDefinition, ...]:
    """The capability's plays in one total order — never manifest order, never set order."""
    return tuple(sorted(view.request.capability.plays, key=lambda play: play.play_id))


def _step_effort(view: UnitView, play: PlayDefinition) -> int:
    """Effort implied by what the play actually asks someone to do.

    Steps are the only honest unit of work a play carries: a three-step play is three things a
    human has to do, whatever number the author typed into ``effort_bp`` last quarter. Costing each
    declared step at a fixed configured rate keeps this arithmetic auditable — a reviewer can count
    the steps in the manifest and reproduce the number by hand.
    """
    return clamp_bp(_config_bp(view, "step_effort_bp", 1_200) * len(play.steps))


def _play_exposure(view: UnitView, play: PlayDefinition) -> int:
    """Downside this play carries if it goes wrong, independent of how hard it is to do.

    Two things dominate: whether the play can be taken back, and whether it puts something in front
    of someone outside the org. A read-only play that turns out to be a mistake costs an apology;
    an irreversible outbound one costs a relationship. The human-approval policy earns relief
    because a person reads the thing before it leaves — the exposure is real but it is caught.
    """
    exposure = 0
    if not play.read_only:
        exposure += _config_bp(view, "irreversible_exposure_bp", 6_000)
    if play.metadata.get("external_recipient_required") is True:
        exposure += _config_bp(view, "external_recipient_exposure_bp", 2_000)
    if "human_approval_required" in view.request.capability.policies:
        exposure -= _config_bp(view, "approval_backstop_relief_bp", 3_000)
    return clamp_bp(exposure)


def _expected_benefit(play: PlayDefinition) -> int:
    """What the play is worth *in expectation* — its impact discounted by its odds.

    A 10,000bp impact that lands one time in five is not a big prize, and comparing raw impact
    against cost is how a system talks itself into long-shot work.
    """
    return clamp_bp(divide_half_up(play.impact_bp * play.success_probability_bp, 10_000))


class StepEffortPlugin:
    """What the declared plays cost to actually carry out.

    Reports the roster's cheapest route as the floor of acting: whatever Part 3 chooses, someone
    pays at least this much. The ceiling travels alongside it because a roster whose cheapest and
    dearest routes are far apart is a roster where the choice of play matters to cost — a fact the
    Decision Maker should be able to see rather than infer.
    """

    plugin_id = "step_effort"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        plays = _plays(view)
        if not plays:
            return ()                       # nothing declared to do; no effort claim to make
        estimates = tuple(_step_effort(view, play) for play in plays)
        return (Observation(
            plugin_id=self.plugin_id,
            kind="cost.step_effort",
            metrics={"effort_bp": min(estimates),
                     "effort_ceiling_bp": max(estimates),
                     "play_count": len(plays)},
            reason_codes=("effort_estimated_from_declared_steps",),
        ),)


class DelayCostPlugin:
    """What waiting costs — the opportunity cost of not acting yet.

    Two independent readings of the same silence, and either alone is enough to speak. Elapsed time
    since the last inbound signal prices the wait directly; the Temporal unit's momentum drop
    prices it as loss of warmth. Where both exist the stronger one leads, because they measure the
    same decay and adding them would double-count it.

    Silent when neither exists. An unknown cost of waiting must stay unknown — reporting it as zero
    would tell the Decision Maker that delay is free, which is the single most expensive thing this
    unit could get wrong.
    """

    plugin_id = "delay_cost"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        field = str(view.config.get("delay_field") or "deal.last_inbound")
        per_day = _config_bp(view, "delay_cost_per_day_bp", 400)
        hours: int | None = None
        if fact_value(view.request, field) is not None:
            try:
                hours = elapsed_hours(view.request, field)
            except ValueError:
                hours = None                # unparseable or future-dated: no claim, not a zero
        elapsed_cost = clamp_bp((hours // 24) * per_day) if hours is not None else 0
        momentum_bp = clamp_bp(view.prior_metric("core.temporal", "drop_bp", 0))
        if hours is None and momentum_bp <= 0:
            return ()
        metrics = {"delay_cost_bp": max(elapsed_cost, momentum_bp),
                   "momentum_drop_bp": momentum_bp}
        if hours is not None:
            metrics["waiting_hours"] = hours
        return (Observation(
            plugin_id=self.plugin_id,
            kind="cost.delay",
            metrics=metrics,
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=("waiting_has_a_price",),
        ),)


class ReversibilityPlugin:
    """What acting exposes the org to if it turns out to be the wrong call.

    Deliberately reports the roster's worst case rather than an average: this unit does not know
    which play will be chosen, so the exposure the capability carries is the exposure of the most
    dangerous thing it is allowed to do. Averaging would let two harmless read-only plays hide one
    irreversible outbound one.
    """

    plugin_id = "reversibility_exposure"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        plays = _plays(view)
        if not plays:
            return ()
        exposures = tuple(_play_exposure(view, play) for play in plays)
        irreversible = sum(1 for play in plays if not play.read_only)
        external = sum(1 for play in plays
                       if play.metadata.get("external_recipient_required") is True)
        code = "irreversible_action_available" if irreversible else "roster_is_reversible"
        return (Observation(
            plugin_id=self.plugin_id,
            kind="cost.exposure",
            metrics={"exposure_bp": max(exposures),
                     "irreversible_play_count": irreversible,
                     "external_recipient_play_count": external},
            reason_codes=(code,),
        ),)


class CostUnit(ReasoningUnit):
    """Optimization · what acting costs, and whether that cost looks worth paying.

    Publishes a cost ledger and nothing else. It does not choose a play, does not rank the roster,
    and does not eliminate anything — a play it considers expensive stays fully in contention with
    a WARN on its record, because a capability whose upside is large enough should be free to pay.
    """

    unit_id = "core.cost"
    version = "1.0.0"
    category = UnitCategory.OPTIMIZATION
    publishes = ("cost_bp", "effort_bp", "exposure_bp", "delay_cost_bp",
                 "do_nothing_cost_bp", "cost_benefit_gap_bp")
    plugins = (StepEffortPlugin(), DelayCostPlugin(), ReversibilityPlugin())

    def _observation(self, observations: Sequence[Observation], kind: str) -> Observation | None:
        for item in observations:
            if item.kind == kind:
                return item
        return None

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Fold the three claims into one ledger.

        ``cost_bp`` is a weighted blend rather than a sum because effort and exposure are paid in
        different currencies — an hour of work and a burnt relationship do not add up, they trade
        off, and the ratio between them is a business choice that belongs in capability config.

        ``do_nothing_cost_bp`` follows the same shape the Opportunity Unit uses for corroboration:
        the stronger reading leads and the weaker one adds a bounded lift, because delay cost and
        untaken headroom are two views of one silence, not two separate silences.

        ``cost_benefit_gap_bp`` saturates at zero on purpose. How *comfortably* worth it something
        is is a ranking question, and ranking is Part 3's.
        """
        effort_obs = self._observation(observations, "cost.step_effort")
        exposure_obs = self._observation(observations, "cost.exposure")
        delay_obs = self._observation(observations, "cost.delay")

        effort_bp = int(effort_obs.metrics["effort_bp"]) if effort_obs else 0
        exposure_bp = int(exposure_obs.metrics["exposure_bp"]) if exposure_obs else 0
        delay_bp = int(delay_obs.metrics["delay_cost_bp"]) if delay_obs else 0

        weight = _config_bp(view, "cost_weight_effort_bp", 6_000)
        cost_bp = clamp_bp(divide_half_up(
            effort_bp * weight + exposure_bp * (10_000 - weight), 10_000))

        # Untaken headroom is a cost of inaction too: the Opportunity Unit already priced it, so
        # read it rather than re-deriving a second, disagreeing estimate of the same thing.
        headroom_bp = clamp_bp(view.prior_metric("core.opportunity", "opportunity_bp", 0))
        leading, trailing = max(delay_bp, headroom_bp), min(delay_bp, headroom_bp)
        do_nothing_bp = clamp_bp(leading + divide_half_up(trailing, 4))

        return {"cost_bp": cost_bp,
                "effort_bp": effort_bp,
                "exposure_bp": exposure_bp,
                "delay_cost_bp": delay_bp,
                "do_nothing_cost_bp": do_nothing_bp,
                "cost_benefit_gap_bp": clamp_bp(cost_bp - do_nothing_bp)}

    def _effort_adjustments(self, view: UnitView) -> tuple[CandidateAdjustment, ...]:
        """Correct plays whose declared effort no longer matches the work they describe.

        Layer 3 authors ``effort_bp`` by hand and steps get added to a play long after that number
        was agreed. Where the two have drifted past a tolerance, this reports the correction on the
        ``effort`` component so the play is scored on what it now asks for. The correction is
        capped: this unit is auditing a declaration, not replacing the author's judgement.
        """
        tolerance = _config_bp(view, "effort_mismatch_tolerance_bp", 2_500)
        ceiling = _config_bp(view, "max_effort_adjustment_bp", 3_000)
        adjustments: list[CandidateAdjustment] = []
        for play in _plays(view):
            drift = _step_effort(view, play) - play.effort_bp
            if abs(drift) < tolerance:
                continue
            delta = max(-ceiling, min(ceiling, drift))
            adjustments.append(CandidateAdjustment(
                play_id=play.play_id,
                component="effort",
                delta_bp=delta,
                reason_code=("declared_effort_understated" if delta > 0
                             else "declared_effort_overstated"),
            ))
        return tuple(adjustments)

    def _cost_benefit_checks(self, view: UnitView, do_nothing_bp: int) -> tuple[CandidateCheck, ...]:
        """Flag plays whose price outruns what they can be expected to return.

        Expected benefit is compared against the play's own cost — its effort plus its exposure —
        and against the cost of leaving the situation alone. A play only earns a WARN when it is
        expensive *and* the silence it would break is cheap, because an expensive play is exactly
        the right call when doing nothing is worse.

        The outcome is WARN, never ELIMINATE. Cost is one voice at the table; a unit that could
        eliminate on price alone would quietly become the decision authority.
        """
        gap_threshold = _config_bp(view, "cost_benefit_warn_gap_bp", 2_000)
        weight = _config_bp(view, "cost_weight_effort_bp", 6_000)
        checks: list[CandidateCheck] = []
        for play in _plays(view):
            effort = _step_effort(view, play)
            exposure = _play_exposure(view, play)
            play_cost = clamp_bp(divide_half_up(
                effort * weight + exposure * (10_000 - weight), 10_000))
            benefit = clamp_bp(max(_expected_benefit(play), do_nothing_bp))
            gap = play_cost - benefit
            if gap < gap_threshold:
                continue
            checks.append(CandidateCheck(
                play_id=play.play_id,
                stage=COST_BENEFIT_STAGE,
                outcome=CheckOutcome.WARN,
                reason_code="cost_exceeds_expected_benefit",
                evaluator_id=self.unit_id,
                evaluator_version=self.version,
                detail={"estimated_cost_bp": play_cost,
                        "expected_benefit_bp": benefit,
                        "gap_bp": clamp_bp(gap)},
            ))
        return tuple(checks)

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """``matched`` means "acting here is materially more expensive than sitting still".

        It is a reading of the ledger, not an instruction. A matched cost unit alongside a matched
        opportunity unit is a perfectly normal situation — it says the call is a real trade-off,
        which is precisely when a human wants to see the numbers.
        """
        gap_threshold = _config_bp(view, "cost_benefit_warn_gap_bp", 2_000)
        expensive = metrics["cost_benefit_gap_bp"] >= gap_threshold

        codes = {code for item in observations for code in item.reason_codes}
        codes.add("cost_exceeds_inaction" if expensive else "cost_within_tolerance")
        if metrics["do_nothing_cost_bp"] == 0:
            # No evidence that waiting costs anything. Say so, rather than letting a zero read as a
            # measured finding that inaction is free.
            codes.add("do_nothing_cost_unknown")

        findings = [Finding(
            finding_id=f"cost.{item.plugin_id}",
            kind="cost",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations]
        findings.append(Finding(
            finding_id="cost.ledger",
            kind="cost",
            matched=expensive,
            metrics=dict(metrics),
            reason_codes=tuple(sorted(codes)),
        ))

        return Verdict(
            matched=expensive,
            metrics=dict(metrics),
            findings=tuple(findings),
            adjustments=self._effort_adjustments(view),
            checks=self._cost_benefit_checks(view, metrics["do_nothing_cost_bp"]),
            reason_codes=tuple(sorted(codes)),
        )


__all__ = ["COST_BENEFIT_STAGE", "CostUnit", "DelayCostPlugin", "ReversibilityPlugin",
           "StepEffortPlugin"]
