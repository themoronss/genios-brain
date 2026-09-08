"""Category 2 · Business Evaluation — the Risk Unit.

Answers one question: *what does it cost us if nobody does anything?*

Risk here is not a mood and not a forecast. It is the downside already visible in the situation,
read off two independent signals that were measured elsewhere and are merely *weighted* here:

* **Momentum decay** — the engagement is going quiet. `core.temporal` owns the clock and
  publishes `drop_bp`; this unit does not re-derive it, because two units deriving the same number
  from the same facts is how they drift apart.
* **Relationship health** — the account is thinly held. `core.relationship` owns coverage and
  publishes `relationship_risk_bp`.

Both are exposures of the *do nothing* branch, which is why the single finding this unit emits is
literally named `risk.do_nothing`. The unit has no opinion about what to do instead — it reports
the size of the downside and stops. That is why `matched` is always `None`: risk is a magnitude,
not a gate, and collapsing it into a boolean would make this unit a decision authority.

Three properties are load-bearing and must survive any future edit:

**The blend is fixed, the floor is authored.** Decay carries 60% of the weighted term and
relationship health 40%, over a basis of 100 — integers throughout, half-up rounding, so the same
inputs give the same basis points on every machine. The `base_risk_bp` floor exists because work
that looks perfect is still work that can be lost; the capability author sets how much of that
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
    ResultStatus,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import basis_points, clamp_bp, divide_half_up, integer

#: The single unit-level reason code. Risk is one claim about the do-nothing branch, so the result
#: carries one code — the per-plugin codes stay on their own findings as provenance.
#:
#: **THIS SPELLING CHANGED, AND THE OLD FREEZE WAS THE WRONG TRADE.** The argument for keeping the
#: previous code was real: `core.risk` is one of the six units that has actually been running on
#: the compiled lane, so the old string is already written into audit rows and into the reasons
#: attached to shipped signals, and renaming it orphans them. But the cost of keeping it was paid
#: on every run, not once — this unit emits its code on EVERY situation it scores, including
#: `account_admin` and support situations that one vertical's vocabulary has no business
#: describing, so a founder reading an admin card's reasons saw that vertical's word on it. A
#: frozen string that keeps being WRITTEN is not a legacy row; it is an ongoing emission, and
#: Law 5 is about what the unit says today.
#:
#: So the emission moves and the history keeps its name: `LEGACY_RISK_REASON_CODE` below is the
#: read-side alias, exported and documented, so anything interpreting stored rows resolves both
#: spellings to one meaning. Nothing is orphaned, and nothing new carries the old vocabulary.
#:
#: The new spelling is the finding's own name (`risk.do_nothing`) rather than a fresh coinage: the
#: unit has always answered "what does it cost us if nobody does anything", and the code now says
#: exactly that in the vocabulary the unit actually uses.
RISK_REASON_CODE = "do_nothing_exposure"

#: What `RISK_REASON_CODE` was before this wave. **NEVER EMITTED** — it exists so a reader of
#: stored `reasoning_run_outputs`, audit bundles and shipped signal reasons can resolve the old
#: spelling to the current meaning. `RISK_REASON_CODES` is the pair, for exactly that lookup.
#:
#: This is the one line in this file that carries domain vocabulary, and
#: `tests/reason/test_units_domain_free.py` pins it as the single permitted occurrence — now as a
#: HISTORICAL alias rather than as a live emission, which is the whole of the change.
LEGACY_RISK_REASON_CODE = "deal_momentum_risk"

#: Every spelling this unit's headline code has ever had, newest first. A consumer filtering stored
#: rows for "the risk unit's verdict" must match on this, not on either string alone: matching only
#: the new one loses every row written before this wave, and matching only the old one loses every
#: row written after it.
RISK_REASON_CODES = (RISK_REASON_CODE, LEGACY_RISK_REASON_CODE)

#: Carried by every adjustment, so an auditor asking "what moved this play's risk component?" gets
#: an answer that names the authored mitigation rather than the unit.
RISK_MITIGATION_REASON = "play_mitigates_detected_risk"

#: The blend: 60/40 over a basis of 100. Decay leads because work that has stopped moving is the
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

#: The units that own the two exposures. Defaults, overridable per capability, and enumerated here
#: so the registration check can prove they name units that exist — a source unit that was never
#: registered reads exactly like a source unit that did not run.
DEFAULT_TEMPORAL_SOURCE = "core.temporal"
DEFAULT_RELATIONSHIP_SOURCE = "core.relationship"

#: Named when an exposure's source unit did not run. This is the difference between "we measured
#: the decay and there is none" and "nothing measured the decay" — two situations that produce the
#: identical `risk_bp` and mean entirely different things. Until these codes existed, a risk
#: reading taken with both eyes shut was indistinguishable from a calm one, which is precisely the
#: state `core.risk` has been in on the compiled lane: it schedules neither source, so two of its
#: three plugins have never contributed a number, and the result never said so.
MOMENTUM_UNMEASURED_REASON = "momentum_unmeasured"
RELATIONSHIP_UNMEASURED_REASON = "relationship_unmeasured"


def _published(view: UnitView, reasoner_id: str, name: str) -> int | None:
    """Read one metric a named dependency published, or None when nothing published it.

    Deliberately not `UnitView.prior_metric`: that helper substitutes its default whenever the
    prior result is not COMPLETED *or* the value is not an int, whereas this unit has always
    coerced through `integer()` and let a non-integer metric fail loudly. Risk is summed into the
    ranking math, so a metric the system cannot read as an integer is an authoring fault worth
    surfacing, not a value to quietly replace with zero.

    The None is new and it is the whole of K1a: the caller now knows whether it is looking at a
    measurement or at a blind spot. What it does with that is unchanged — an unmeasured exposure
    still contributes nothing to `risk_bp`, because this unit's documented asymmetry is that
    silence is zero here, and the floor carries the rest.
    """
    result = view.prior.get(reasoner_id)
    if result is None or result.status != ResultStatus.COMPLETED or name not in result.metrics:
        return None
    return integer(result.metrics[name], name)


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
        source = str(view.config.get("temporal_reasoner") or DEFAULT_TEMPORAL_SOURCE)
        drop = _published(view, source, "drop_bp")
        if drop is None:
            # No metric, because there is no measurement. An observation carrying `drop_bp: 0`
            # would be a claim that the engagement is intact, made by a plugin that never saw it.
            return (Observation(
                plugin_id=self.plugin_id,
                kind="risk.momentum_decay",
                reason_codes=(MOMENTUM_UNMEASURED_REASON,),
            ),)
        return (Observation(
            plugin_id=self.plugin_id,
            kind="risk.momentum_decay",
            metrics={"drop_bp": drop},
            reason_codes=("momentum_decay_exposure",),
        ),)


class RelationshipHealthPlugin:
    """How thinly the account is held, as measured by the relationship unit.

    A single-threaded relationship is one departure away from starting over, and that exposure is
    independent of how recently anyone spoke — which is exactly why it is a separate contribution
    with its own weight rather than a modifier on decay.
    """

    plugin_id = RELATIONSHIP_PLUGIN

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        source = str(view.config.get("relationship_reasoner") or DEFAULT_RELATIONSHIP_SOURCE)
        concentration = _published(view, source, "relationship_risk_bp")
        if concentration is None:
            return (Observation(
                plugin_id=self.plugin_id,
                kind="risk.relationship_health",
                reason_codes=(RELATIONSHIP_UNMEASURED_REASON,),
            ),)
        return (Observation(
            plugin_id=self.plugin_id,
            kind="risk.relationship_health",
            metrics={"relationship_risk_bp": concentration},
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

        The headline finding carries the single unit-level reason code, and each exposure carries
        its own provenance on its own finding: a reader of a `risk` result sees one claim, and an
        auditor reading the findings sees what it was built from.

        The one thing that IS unioned into the result's reason codes is an exposure that could not
        be measured. That is not provenance, it is a limit on the claim — a `risk_bp` computed
        with the decay source absent is a narrower statement than the same number computed with it
        present, and the result has to say which one it is.
        """
        risk_bp = metrics["risk_bp"]
        adjustments: list[CandidateAdjustment] = []
        for observation in observations:
            if observation.plugin_id != MITIGATION_PLUGIN:
                continue
            for play_id in sorted(observation.metrics):
                adjustments.append(CandidateAdjustment(
                    play_id, "risk", -observation.metrics[play_id], RISK_MITIGATION_REASON))
        headline = Finding("risk.do_nothing", "risk", metrics={"risk_bp": risk_bp},
                           reason_codes=(RISK_REASON_CODE,))
        # Both exposures reach the evidence layer as their own findings — including the ones that
        # could not be measured. A blend is not an explanation: `risk_bp` alone cannot tell a
        # reader whether the number came from decay, from thin coverage, from the floor, or from
        # two units that never ran, and the last of those is a fact about the reasoning that has
        # to travel with it.
        exposures = tuple(Finding(
            finding_id=f"risk.{item.plugin_id}",
            kind="risk",
            matched=None,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations if item.plugin_id != MITIGATION_PLUGIN)
        blind = tuple(sorted({code for item in observations for code in item.reason_codes}
                             & {MOMENTUM_UNMEASURED_REASON, RELATIONSHIP_UNMEASURED_REASON}))
        return Verdict(matched=None, metrics=dict(headline.metrics),
                       findings=(headline,) + exposures,
                       adjustments=tuple(adjustments),
                       reason_codes=(RISK_REASON_CODE,) + blind)


#: The name the roster and every shipped capability import. Kept as an alias so the migration onto
#: the unit framework is invisible to `reasoners/__init__.py` and to any pinned manifest.
RiskReasoner = RiskUnit

__all__ = ["DEFAULT_RELATIONSHIP_SOURCE", "DEFAULT_TEMPORAL_SOURCE",
           "LEGACY_RISK_REASON_CODE", "MOMENTUM_UNMEASURED_REASON", "MomentumDecayPlugin",
           "PlayMitigationPlugin", "RELATIONSHIP_UNMEASURED_REASON", "RISK_MITIGATION_REASON",
           "RISK_REASON_CODE", "RISK_REASON_CODES", "RelationshipHealthPlugin", "RiskReasoner",
           "RiskUnit"]
