"""Category 2 · Business Evaluation — the Confidence Unit.

Answers one question: *how much should anyone trust the rest of this reasoning?*

Every other unit reports what it found. This one reports how much of that finding rests on solid
ground, and it is the only unit in the roster permitted to publish `confidence_bp` (see
`reason/decision_maker.py`, `CONFIDENCE_AUTHORITY`). A second publisher would silently re-score
every decision in the system, which is why the number has a single named owner rather than a
convention.

Confidence here is never a feeling about the answer. It is a measurement of the *inputs*, taken
along four independent axes that fail independently:

* **Source quality** — what the facts themselves claim about their own reliability.
* **Completeness** — how much of what the capability asked for actually arrived.
* **Corroboration** — whether each fact was seen once or seen repeatedly.
* **Evidence coverage** — how many genuinely independent sources stand behind the snapshot at all.

Two branches, one output. When a capability names a `source_reasoner` in config, this unit
*bridges* that reasoner's confidence instead of recomputing it — that is how the legacy strangler
packs keep one confidence authority while the old scoring still owns the number. Otherwise it
computes the blend from the frozen snapshot. The bridge is not a fallback; it is a declaration by
the capability author about where confidence comes from, so it wins outright and the decomposition
axes are not even evaluated.

The unit analyses; it never decides. It reports one blended figure plus every component that went
into it, so a reader can see *why* a decision was 42% confident rather than being asked to accept
it. `matched` is always None: "how sure are we" is not a gate that can be passed or failed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import Finding, ReasonerResult, ResultStatus

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import basis_points, clamp_bp, divide_half_up, fact_record, integer, ratio_bp

#: The single reason code every confidence result carries, in both branches. Confidence is always
#: produced — there is no "confidence unknown" outcome — so the code states that the number exists,
#: not what it turned out to be.
CONFIDENCE_REASON = "confidence_computed"

#: The blend, as whole percentages summing to 100. What the facts claim about themselves dominates,
#: how much of the picture arrived is next, and independent corroboration is the tie-breaker.
#: Expressed as data so the weights and the metric names cannot drift apart.
_SOURCE_WEIGHT = 40
_COMPLETENESS_WEIGHT = 30
_CORROBORATION_WEIGHT = 20
_COVERAGE_WEIGHT = 10
_WEIGHT_TOTAL = 100

#: Used where an axis has nothing to measure. Deliberately the midpoint rather than 0: a fact that
#: never stated its own confidence is unknown, not untrustworthy, and scoring it 0 would turn a
#: silent CRM field into a reason to distrust the whole decision.
_NEUTRAL_BP = 5_000

#: Corroboration ladder by distinct source count: three or more independent sightings is as good as
#: it gets, two is strong, one is the floor. A step function rather than a curve because the
#: business meaning is discrete — "one system says so" versus "three systems agree".
_CORROBORATION_MANY_BP = 10_000
_CORROBORATION_PAIR_BP = 8_500
_CORROBORATION_SINGLE_BP = 6_000

#: Each independent evidence group buys this much coverage, saturating at four groups.
_GROUP_COVERAGE_BP = 2_500

#: Missing independence metadata is one unknown group, not proof that every field came from an
#: independent source.
_UNATTRIBUTED_GROUP = "unattributed"

#: Metrics this unit emits into its result and finding but deliberately does *not* declare in
#: `publishes`. `completeness_bp` is already owned by `core.context`, and the roster invariant
#: (tests/test_unit_roster.py) allows exactly one declared publisher per metric name. The value is
#: preserved byte-for-byte because removing or renaming it would change every decision hash; the
#: name collision is recorded here rather than fixed. See the module concerns in the migration
#: notes.
UNDECLARED_METRICS = ("completeness_bp",)


def _bridged_confidence_bp(view: UnitView) -> int | None:
    """The confidence a capability-named source reasoner already published, if any.

    Read from `view.prior` directly rather than through `prior_metric`, because the legacy contract
    is stricter than the framework helper: a malformed or out-of-range bridged value is an authoring
    fault that must surface loudly, not be quietly replaced by a default.

    Every plugin consults this, so the two decomposition plugins stay silent whenever the bridge
    applies — that keeps the branch exclusive exactly as the pre-framework unit had it, including
    the fact that a malformed *fact* is never even looked at when a bridge is configured.
    """
    source = str(view.config.get("source_reasoner") or "")
    if not source:
        return None
    prior = view.prior.get(source)
    if prior is None or "confidence_bp" not in prior.metrics:
        return None
    return basis_points(prior.metrics["confidence_bp"], "confidence_bp")


def _declared_fields(view: UnitView) -> tuple[str, ...]:
    """What this run was supposed to know: the unit's own required fields, else the capability's.

    Both sources are sorted de-duplicated tuples at construction time, so the scan order below is a
    property of the manifest rather than of dict insertion.
    """
    return tuple(view.spec.required_fields or view.request.capability.required_fields)


def _present_fields(view: UnitView) -> tuple[str, ...]:
    """The declared fields that actually arrived, in declared order."""
    facts = view.request.context.facts
    return tuple(field for field in _declared_fields(view) if field in facts)


class LegacyBridgePlugin:
    """The capability says confidence belongs to another reasoner — so take it from there.

    Used by the strangler packs, where the old rule engine still owns the number and this unit
    exists only to be its single, auditable publisher. The bridge carries the value through
    unchanged; re-deriving it here would mean two different confidences for one decision.
    """

    plugin_id = "legacy_bridge"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        bridged = _bridged_confidence_bp(view)
        if bridged is None:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="confidence.legacy_bridge",
            metrics={"confidence_bp": bridged},
        ),)


class FactSourceQualityPlugin:
    """What the facts say about themselves, and how many sources said it.

    Two readings of the same records, kept in one plugin because they come from one pass over one
    structure: a fact record states its own confidence (as basis points, or as a 0..1 ratio from
    older producers) and how many distinct sources contributed it.

    A record that never stated a confidence contributes nothing to the source-quality mean — it is
    unknown, not weak. But it still contributes to corroboration, because "how many systems saw
    this" is knowable even when "how sure is the system" is not; an absent `src_count` reads as one
    sighting, which is the floor of the ladder rather than a hole in it.

    Only mapping-shaped records participate. A bare scalar fact carries no metadata to read, so it
    is counted for completeness and silent everywhere else.
    """

    plugin_id = "fact_source_quality"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        if _bridged_confidence_bp(view) is not None:
            return ()                       # the capability delegated confidence; say nothing
        confidences: list[int] = []
        corroborations: list[int] = []
        for field in _present_fields(view):
            record = fact_record(view.request, field)
            if not isinstance(record, Mapping):
                continue
            if "confidence_bp" in record:
                confidences.append(basis_points(
                    record["confidence_bp"], f"{field}.confidence_bp"))
            elif "confidence" in record:
                confidences.append(ratio_bp(record["confidence"], f"{field}.confidence"))
            groups = integer(record.get("src_count", 1), f"{field}.src_count")
            corroborations.append(
                _CORROBORATION_MANY_BP if groups >= 3
                else (_CORROBORATION_PAIR_BP if groups == 2 else _CORROBORATION_SINGLE_BP))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="confidence.fact_source_quality",
            metrics={
                "source_quality_bp": divide_half_up(sum(confidences), len(confidences))
                if confidences else _NEUTRAL_BP,
                "corroboration_bp": divide_half_up(sum(corroborations), len(corroborations))
                if corroborations else _NEUTRAL_BP,
                "self_reported_fact_count": len(confidences),
                "described_fact_count": len(corroborations),
            },
        ),)


class CoverageCompletenessPlugin:
    """How much of the asked-for picture arrived, and from how many independent places.

    Completeness is a structural claim about the *request*: of the fields this capability declared
    it needs, what fraction is in the snapshot. It is measured even when no fact carries metadata,
    which is why it is the axis that keeps a thin snapshot from scoring as a confident one.

    Coverage is a claim about the *evidence*: how many independent source groups stand behind the
    snapshot as a whole. It counts every evidence item in the frozen context rather than only the
    items backing this unit's fields, because independence is a property of where the picture came
    from, not of which field is being read right now.
    """

    plugin_id = "coverage_completeness"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        if _bridged_confidence_bp(view) is not None:
            return ()
        declared = _declared_fields(view)
        present = _present_fields(view)
        # A capability that declared no required fields asked for nothing and got all of it.
        completeness_bp = divide_half_up(len(present) * 10_000, len(declared)) if declared \
            else 10_000
        groups = {item.independence_group or _UNATTRIBUTED_GROUP
                  for item in view.request.context.evidence}
        return (Observation(
            plugin_id=self.plugin_id,
            kind="confidence.coverage_completeness",
            metrics={
                "completeness_bp": completeness_bp,
                "evidence_coverage_bp": min(10_000, len(groups) * _GROUP_COVERAGE_BP),
                "independent_evidence_groups": len(groups),
                "declared_field_count": len(declared),
                "present_field_count": len(present),
            },
        ),)


class ConfidenceReasoner(ReasoningUnit):
    """Business Evaluation · how much the rest of this reasoning can be trusted.

    Named `ConfidenceReasoner` rather than `ConfidenceUnit` because the roster imports it by this
    name and a capability resolves it by `core.confidence` at version 1.0.0; both are part of the
    shipped contract and neither may move.
    """

    unit_id = "core.confidence"
    version = "1.0.0"
    category = UnitCategory.BUSINESS_EVALUATION
    #: `completeness_bp` is emitted too — see UNDECLARED_METRICS for why it cannot be listed here.
    publishes = ("confidence_bp", "source", "source_quality_bp", "corroboration_bp",
                 "evidence_coverage_bp", "independent_evidence_groups")
    plugins = (LegacyBridgePlugin(), FactSourceQualityPlugin(), CoverageCompletenessPlugin())

    def validate(self, view: UnitView) -> None:
        """Never refuse. A missing field is this unit's subject matter, not an obstacle to it.

        The default validator raises `MissingContextError` when a declared field is absent, which
        the orchestrator turns into an insufficient-context result. That would be exactly backwards
        here: the whole point of the completeness axis is to answer a thin snapshot with a low
        confidence rather than with silence, and downstream units read `confidence_bp` to decide how
        much to lean on everything else. A confidence unit that declined to run on incomplete input
        would remove the only signal that the input was incomplete.
        """

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """One weighted blend, or the bridged number passed straight through.

        The blend is a percentage-weighted mean over all four axes with no renormalisation: each
        axis always reports (using its neutral midpoint where it had nothing to measure), so the
        divisor is the constant 100 and the arithmetic stays integral end to end.
        """
        by_plugin = {item.plugin_id: item for item in observations}
        bridged = by_plugin.get(LegacyBridgePlugin.plugin_id)
        if bridged is not None:
            return {"confidence_bp": bridged.metrics["confidence_bp"]}

        quality = by_plugin.get(FactSourceQualityPlugin.plugin_id)
        coverage = by_plugin.get(CoverageCompletenessPlugin.plugin_id)
        source_bp = quality.metrics["source_quality_bp"] if quality else _NEUTRAL_BP
        corroboration_bp = quality.metrics["corroboration_bp"] if quality else _NEUTRAL_BP
        completeness_bp = coverage.metrics["completeness_bp"] if coverage else 10_000
        evidence_coverage_bp = coverage.metrics["evidence_coverage_bp"] if coverage else 0
        groups = coverage.metrics["independent_evidence_groups"] if coverage else 0
        return {
            "confidence_bp": clamp_bp(divide_half_up(
                source_bp * _SOURCE_WEIGHT + completeness_bp * _COMPLETENESS_WEIGHT
                + corroboration_bp * _CORROBORATION_WEIGHT
                + evidence_coverage_bp * _COVERAGE_WEIGHT, _WEIGHT_TOTAL)),
            "source_quality_bp": source_bp,
            "completeness_bp": completeness_bp,
            "corroboration_bp": corroboration_bp,
            "evidence_coverage_bp": evidence_coverage_bp,
            "independent_evidence_groups": groups,
        }

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """Publish the decomposition, not just the score.

        A bare `confidence_bp` is an assertion; the decomposition beside it is an explanation, and
        it is what lets a reviewer say "this was 42% because half the fields never arrived" instead
        of arguing with a number. So every component travels in one `confidence.decomposition`
        finding alongside the blend.

        `matched` stays None on purpose: confidence is a reading, not a gate, and a False here would
        read downstream as "the confidence check failed".
        """
        published: dict[str, object] = dict(metrics)
        if any(item.plugin_id == LegacyBridgePlugin.plugin_id for item in observations):
            # Marks the number as somebody else's, so an auditor reading the result can tell a
            # bridged confidence from a computed one without re-deriving the branch. A deliberately
            # non-integer metric — the only one in the roster — kept because changing it would
            # change the result hash of every legacy strangler decision ever replayed.
            published["source"] = "legacy"
        finding = Finding("confidence.decomposition", "confidence", metrics=published,
                          reason_codes=(CONFIDENCE_REASON,))
        return Verdict(
            matched=None,
            metrics={name: value for name, value in published.items()
                     if name not in UNDECLARED_METRICS},
            findings=(finding,),
            reason_codes=finding.reason_codes,
        )

    def build(self, view: UnitView, verdict: Verdict,
              observations: Sequence[Observation]) -> ReasonerResult:
        """Assemble the result from the decomposition finding rather than from the verdict.

        Two departures from the base builder, both required to keep the published contract stable:

        * **Metrics come from the finding.** The finding carries the full decomposition, including
          `completeness_bp`, which cannot appear in `verdict.metrics` because it is not declarable
          in `publishes` (see UNDECLARED_METRICS). The result and the finding therefore carry
          identical metric maps, exactly as they always have.
        * **No evidence ids.** This unit reasons *about* the evidence in aggregate — how many
          independent groups exist — rather than *from* any particular item, so attaching the ids
          of every field it counted would assert a provenance it does not actually claim.
        """
        decomposition = verdict.findings[0]
        return ReasonerResult(
            reasoner_id=self.unit_id,
            reasoner_version=self.version,
            status=ResultStatus.COMPLETED,
            matched=verdict.matched,
            metrics=decomposition.metrics,
            findings=verdict.findings,
            adjustments=verdict.adjustments,
            checks=verdict.checks,
            reason_codes=verdict.reason_codes,
        )


__all__ = ["CONFIDENCE_REASON", "ConfidenceReasoner", "CoverageCompletenessPlugin",
           "FactSourceQualityPlugin", "LegacyBridgePlugin", "UNDECLARED_METRICS"]
