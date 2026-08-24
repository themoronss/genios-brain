"""Category 2 · Business Evaluation — the Risk Unit.

Answers one question: *what does it cost us if nobody does anything?*

Risk here is not a mood and not a forecast. It is the downside already visible in the situation,
read off two independent signals that were measured elsewhere and are merely *weighted* here:

* **Momentum decay** — the deal is going quiet. `core.temporal` owns the clock and publishes
  `drop_bp`; this unit does not re-derive it, because two units deriving the same number from the
  same facts is how they drift apart.
* **Relationship health** — the account is thinly held. `core.relationship` owns coverage and
  publishes `relationship_risk_bp`.

Both are exposures of the *do nothing* branch, which is why the single finding this unit emits is
literally named `risk.do_nothing`. The unit has no opinion about what to do instead — it reports
the size of the downside and stops. That is why `matched` is always `None`: risk is a magnitude,
not a gate, and collapsing it into a boolean would make this unit a decision authority.

Three properties are load-bearing and must survive any future edit:

**The blend is fixed, the floor is authored.** Decay carries 60% of the weighted term and
relationship health 40%, over a basis of 100 — integers throughout, half-up rounding, so the same
inputs give the same basis points on every machine. The `base_risk_bp` floor exists because a deal
that looks perfect is still a deal that can be lost; the capability author sets how much of that
irreducible exposure to carry.

**Silence is zero, deliberately.** Unlike the Impact unit, an absent dependency here contributes
0 rather than withholding the metric. `risk_bp` is consumed by the ranking math, and a missing
`risk_bp` would be read downstream as "unknown", not "low" — so the unit reports the risk it can
actually evidence and lets the floor carry the rest. This is a documented asymmetry, not an
oversight.

**It never picks a play.** Where a play reduces the risk it addresses, the reduction is authored in
Layer 3 as `play_risk_reduction_bp: {play_id: bp}` and merely emitted here as a negative `risk`
adjustment. The unit supplies no judgement about which play wins; the Decision Maker does the
choosing. The authored mapping is iterated **sorted**, never in arrival order: adjustment order
reaches this result's semantic hash, and the manifest is re-sorted when it round-trips through the
audit store, so unsorted iteration would report every replayed run as non-reproducible.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import (
    CandidateAdjustment,
    Finding,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import basis_points, clamp_bp, divide_half_up, integer

#: The single reason code this unit publishes. Risk is one claim about the do-nothing branch, so it
#: carries one code — the per-plugin codes below stay inside the observations as provenance.
RISK_REASON_CODE = "deal_momentum_risk"

#: Carried by every adjustment, so an auditor asking "what moved this play's risk component?" gets
#: an answer that names the authored mitigation rather than the unit.
RISK_MITIGATION_REASON = "play_mitigates_detected_risk"

#: The blend: 60/40 over a basis of 100. Decay leads because a deal that has stopped moving is the
#: nearer loss; thin coverage is the slower one. Named rather than inlined so the weighting is
#: reviewable, but *not* configurable — moving these would re-score every shipped decision.
MOMENTUM_WEIGHT = 60
RELATIONSHIP_WEIGHT = 40
WEIGHT_BASIS = 100

#: Plugin ids, referenced by the calculator. Constants rather than literals so a rename cannot
#: silently turn a contribution into a zero.
MOMENTUM_PLUGIN = "momentum_decay"
RELATIONSHIP_PLUGIN = "relationship_health"
MITIGATION_PLUGIN = "risk_mitigation"


def _published(view: UnitView, reasoner_id: str, name: str) -> int:
    """Read one metric a named dependency published, treating "did not run" as zero.

    Deliberately not `UnitView.prior_metric`: that helper substitutes its default whenever the
    prior result is not COMPLETED *or* the value is not an int, whereas this unit has always
    coerced through `integer()` and let a non-integer metric fail loudly. Risk is summed into the
    ranking math, so a metric the system cannot read as an integer is an authoring fault worth
    surfacing, not a value to quietly replace with zero.
    """
    result = view.prior.get(reasoner_id)
    return integer((result.metrics if result else {}).get(name, 0), name)


def _observed(observations: Sequence[Observation], plugin_id: str, name: str) -> int:
    """The value one plugin reported, or zero if it stayed silent."""
    for observation in observations:
        if observation.plugin_id == plugin_id:
            return int(observation.metrics.get(name, 0))
    return 0


class MomentumDecayPlugin:
    """How far the conversation has fallen off, as measured by the temporal unit.

    The plugin reads rather than re-derives. `core.temporal` parsed the timestamps and owns
    `drop_bp`; recomputing it here from the same facts would produce a second number that agrees
    today and diverges the first time either side is tuned.

    Which unit to read is authored (`temporal_reasoner`), because a capability may run a
    domain-specific decay model under a different id and still want its output weighted here.
    """

    plugin_id = MOMENTUM_PLUGIN

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        source = str(view.config.get("temporal_reasoner") or "core.temporal")
        return (Observation(
            plugin_id=self.plugin_id,
            kind="risk.momentum_decay",
            metrics={"drop_bp": _published(view, source, "drop_bp")},
            reason_codes=("momentum_decay_exposure",),
        ),)


class RelationshipHealthPlugin:
    """How thinly the account is held, as measured by the relationship unit.

    A single-threaded deal is one departure away from starting over, and that exposure is
    independent of how recently anyone spoke — which is exactly why it is a separate contribution
    with its own weight rather than a modifier on decay.
    """

    plugin_id = RELATIONSHIP_PLUGIN

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        source = str(view.config.get("relationship_reasoner") or "core.relationship")
        return (Observation(
            plugin_id=self.plugin_id,
            kind="risk.relationship_health",
            metrics={"relationship_risk_bp": _published(view, source, "relationship_risk_bp")},
            reason_codes=("relationship_exposure",),
        ),)


class PlayMitigationPlugin:
    """What the capability author says each play does to the risk it addresses.

    This is authored knowledge, not inference: only the capability knows that "multithread the
    account" attacks coverage risk. The plugin reads the table, validates each entry as basis
    points, and reports it — the sign is applied where the adjustment is built, so this observation
    stays a plain statement of magnitude.

    The scan is `sorted()`, and the consumer sorts again. Adjustment order is inside this result's
    semantic hash while the manifest's key order is not stable across a JSON round trip through the
    audit store, so ordering has to come from the content and nowhere else.
    """

    plugin_id = MITIGATION_PLUGIN

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        authored = dict(view.config.get("play_risk_reduction_bp") or {})
        if not authored:
            return ()                       # nothing authored is not a zero-value mitigation
        reductions = {
            str(play_id): basis_points(reduction, f"{play_id}.risk_reduction_bp")
            for play_id, reduction in sorted(authored.items())
        }
        return (Observation(
            plugin_id=self.plugin_id,
            kind="risk.play_mitigation",
            metrics=reductions,             # keyed by play_id: the whole authored table, validated
            reason_codes=(RISK_MITIGATION_REASON,),
        ),)


class RiskUnit(ReasoningUnit):
    """Business Evaluation · what the do-nothing branch costs."""

    unit_id = "core.risk"
    version = "1.0.0"
    category = UnitCategory.BUSINESS_EVALUATION
    publishes = ("risk_bp",)
    plugins = (MomentumDecayPlugin(), PlayMitigationPlugin(), RelationshipHealthPlugin())

    def validate(self, view: UnitView) -> None:
        """Nothing to refuse: this unit reads no context facts.

        Its inputs are other units' published metrics and the capability's own config, so there is
        no fact whose absence could make it guess. The default validator would raise
        `MissingContextError` for a declared `required_fields` entry and turn a perfectly
        answerable run into INSUFFICIENT_CONTEXT — a status this unit has never returned and which
        would terminate the whole capability at its required failure policy.
        """

    def retrieve(self, request: ReasoningRequest, spec: ReasonerSpec,
                 prior: Mapping[str, ReasonerResult]) -> UnitView:
        """The window is the prior results and the config — no facts, therefore no evidence.

        The unit cites nothing directly: every claim it makes is downstream of a metric another
        unit already evidenced, and re-attaching that unit's evidence ids here would double-count
        them in the audit trail as if risk had observed the facts itself.
        """
        return UnitView(request=request, spec=spec, prior=prior)

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """A floor plus the weighted blend of the two exposures.

            risk_bp = clamp(base + round_half_up((drop*60 + relationship*40) / 100))

        The division happens once, over the summed numerator, rather than per term: rounding each
        contribution separately would let two 50bp halves round to 100bp of risk that neither
        signal actually reported.
        """
        drop = _observed(observations, MOMENTUM_PLUGIN, "drop_bp")
        relationship_risk = _observed(observations, RELATIONSHIP_PLUGIN, "relationship_risk_bp")
        base = basis_points(view.config.get("base_risk_bp", 1_000), "base_risk_bp")
        return {"risk_bp": clamp_bp(base + divide_half_up(
            drop * MOMENTUM_WEIGHT + relationship_risk * RELATIONSHIP_WEIGHT, WEIGHT_BASIS))}

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """One finding about the do-nothing branch, plus the authored mitigations as adjustments.

        `matched` stays `None` on purpose. There is no threshold at which risk becomes "true" —
        the number is the statement, and a boolean would invite a downstream reader to treat this
        unit as a gate.

        The finding carries the single unit-level reason code. The plugins' own codes stay inside
        their observations as provenance rather than being unioned into the result: a reader of a
        `risk` result should see one claim, not three, and the composition of the score is already
        visible in the metric.
        """
        risk_bp = metrics["risk_bp"]
        adjustments: list[CandidateAdjustment] = []
        for observation in observations:
            if observation.plugin_id != MITIGATION_PLUGIN:
                continue
            for play_id in sorted(observation.metrics):
                adjustments.append(CandidateAdjustment(
                    play_id, "risk", -observation.metrics[play_id], RISK_MITIGATION_REASON))
        finding = Finding("risk.do_nothing", "risk", metrics={"risk_bp": risk_bp},
                          reason_codes=(RISK_REASON_CODE,))
        return Verdict(matched=None, metrics=dict(finding.metrics), findings=(finding,),
                       adjustments=tuple(adjustments), reason_codes=finding.reason_codes)


#: The name the roster and every shipped capability import. Kept as an alias so the migration onto
#: the unit framework is invisible to `reasoners/__init__.py` and to any pinned manifest.
RiskReasoner = RiskUnit

__all__ = ["MomentumDecayPlugin", "PlayMitigationPlugin", "RISK_MITIGATION_REASON",
           "RISK_REASON_CODE", "RelationshipHealthPlugin", "RiskReasoner", "RiskUnit"]
