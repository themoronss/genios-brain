"""Category 1 · Situation Understanding — the Context Unit.

Answers one question: *what is actually true right now?*

Every other unit in the plan reasons on top of the situation this one describes.  Before anyone asks
whether a deal is at risk or whether there is headroom to win, somebody has to state, plainly and
without flattery, what the system actually knows: which of the facts this capability declared it
needs are present, which are explicitly absent, how old the freshest piece of evidence is, and how
many genuinely independent sources stand behind it.

That reading has to be produced by a unit rather than assumed, because the most expensive failure in
an intelligence system is not a wrong answer — it is a confident answer drawn from two known fields,
month-old evidence, and a single source that reported itself twice.  The Context Unit makes that
situation visible as numbers other units and the Decision Maker can act on.

**It states what is known; it never judges whether that is good or bad.**  It does not publish
confidence, it does not gate, and it deliberately refuses to blend its readings into a single
"context quality" score — a single number would be read downstream as a verdict on the situation,
and this unit has no authority to render one.  Completeness, freshness and corroboration are three
different facts about the world and they stay three numbers.

The silence rule matters here more than anywhere else: a unit whose job is to report what is known
must never invent a zero.  No dated evidence means *no freshness metric*, not `freshness_bp = 0`.
A fabricated zero would read downstream as "we checked, and it is stale", which is a different and
much stronger claim than "we do not know".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import EvidenceRef, Finding
from genios_engine.platform.canonical import semantic_hash

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, evidence_ids, missing_fields


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Per-capability tuning, validated as integer basis points.

    Tuning is authored in Layer 3 and versioned with the capability. A malformed value is a
    deployment fault, not something to silently round into range — a threshold that quietly became
    zero would make every situation look complete.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_count(view: UnitView, key: str, default: int) -> int:
    """A positive integer count or duration from capability config (not a basis-point value)."""
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{key} must be a positive integer")
    return value


def declared_fields(view: UnitView) -> tuple[str, ...]:
    """The facts *this capability said it cares about* — the denominator of completeness.

    Completeness is meaningless in the absolute: a snapshot with four facts is not 40% of anything
    unless something declared what the full set was.  So the denominator is taken from the
    capability itself — its own `required_fields` plus every field its reasoners declared they need
    — rather than from a list this unit invents.

    Layer 2's `context.missing_fields` is folded in as well.  Those are the fields the selector
    *tried* to supply and could not; they are known absences, and leaving them out of the
    denominator would let a snapshot look complete precisely because retrieval failed.

    A capability may override the whole set via `context_fields` when its reasoner declarations are
    not the right yardstick (e.g. a capability that reasons mostly on neighbour context).
    """
    configured = view.config.get("context_fields")
    if configured is not None:
        if not isinstance(configured, (tuple, list)) or not all(
                isinstance(name, str) and name.strip() for name in configured):
            raise ValueError("context_fields must be a list of non-empty field names")
        return tuple(sorted({name.strip() for name in configured}))
    names: set[str] = set(view.request.capability.required_fields)
    for spec in view.request.capability.reasoners:
        names.update(spec.required_fields)
    names.update(view.request.context.missing_fields)
    return tuple(sorted(names))


def independence_key(item: EvidenceRef) -> str:
    """How many *witnesses* an evidence row represents — one, at most.

    Two rows are one witness when they came from the same place.  A mailbox sync that ingests the
    same thread twice, or two CRM fields written by the same integration, is a single observer
    repeating itself; counting it as two would let the system manufacture corroboration out of
    duplication.  Layer 2 states this explicitly via `independence_group`; where it did not, the
    source reference is the next best proxy, and an unattributed row can only ever speak for itself.

    The namespace prefixes exist so that an independence_group named "crm" and a source_ref_id named
    "crm" are never accidentally treated as the same witness.
    """
    if item.independence_group:
        return f"group:{item.independence_group}"
    if item.source_ref_id:
        return f"source:{item.source_ref_id}"
    return f"evidence:{item.evidence_id}"


class FactCoveragePlugin:
    """Which of the declared facts are actually present, and which are known absences.

    This is the plainest claim the unit makes and the one most often skipped in practice: systems
    tend to reason from whatever arrived and never state what did not.  Recording the absences by
    name is what lets a later human ask "why did it not consider the owner?" and get an answer.
    """

    plugin_id = "fact_coverage"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        declared = declared_fields(view)
        if not declared:
            # Nothing declared what "complete" means here, so no share can be stated. Reporting
            # 100% because zero fields were missing would be the fabrication this unit exists to
            # prevent.
            return ()
        absent = missing_fields(view.request, declared)
        present = tuple(name for name in declared if name not in set(absent))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="context.fact_coverage",
            metrics={
                "completeness_bp": clamp_bp(divide_half_up(len(present) * 10_000, len(declared))),
                "declared_field_count": len(declared),
                "known_field_count": len(present),
                "missing_field_count": len(absent),
            },
            evidence_ids=evidence_ids(view.request, *present),
            reason_codes=("context_fields_absent",) if absent else ("context_fields_all_present",),
        ),)


class EvidenceFreshnessPlugin:
    """How old the newest thing we know is.

    Freshness is measured from the *newest* dated evidence rather than an average, because staleness
    is about whether anything has happened recently: one message yesterday makes a situation current
    no matter how much of the file is a year old.

    Decay is linear to zero across a horizon the capability owns, because "fresh" is domain-specific
    — a week-old touch is current on an enterprise deal and ancient on a live support thread — and a
    straight line is the only decay curve a reviewer can verify by hand from the trace.
    """

    plugin_id = "evidence_freshness"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        horizon = _config_count(view, "freshness_horizon_hours", 168)
        evaluation_time = view.request.evaluation_time
        # Evidence dated after the evaluation instant cannot describe the situation being reasoned
        # about; treating it as "zero hours old" would let a clock skew read as perfect freshness.
        dated = [item for item in view.request.context.evidence
                 if item.occurred_at is not None and item.occurred_at <= evaluation_time]
        if not dated:
            return ()
        newest = max(item.occurred_at for item in dated)
        age_hours = int((evaluation_time - newest).total_seconds()) // 3600
        cited = tuple(sorted(item.evidence_id for item in dated if item.occurred_at == newest))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="context.evidence_freshness",
            metrics={
                "freshness_bp": clamp_bp(
                    10_000 - divide_half_up(min(age_hours, horizon) * 10_000, horizon)),
                "evidence_age_hours": age_hours,
                "dated_evidence_count": len(dated),
            },
            evidence_ids=cited[:1],
            reason_codes=("context_evidence_dated",),
        ),)


class SourceCorroborationPlugin:
    """How many independent witnesses stand behind what we believe — and where they disagree.

    One source saying something and three independent sources saying the same thing are different
    epistemic situations, and the difference is invisible unless somebody counts.  This plugin
    counts witnesses per field (see `independence_key` for why duplicates do not count twice) and
    reports the best-corroborated field, how many fields clear the capability's corroboration bar,
    and how many rest on a single source.

    Conflict is reported, never resolved.  Where independent witnesses cite different values for the
    same field, this unit says so and stops; choosing which witness to believe is a judgement, and
    judgement belongs to the Decision Maker with the full picture in front of it.
    """

    plugin_id = "source_corroboration"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        minimum = _config_count(view, "min_corroboration", 2)
        witnesses: dict[str, dict[str, set[str]]] = {}
        citations: dict[str, list[str]] = {}
        # Sorted so neither the grouping nor the cited evidence depends on snapshot iteration order.
        for item in sorted(view.request.context.evidence, key=lambda ref: ref.evidence_id):
            field_witnesses = witnesses.setdefault(item.field, {})
            field_witnesses.setdefault(independence_key(item), set()).add(semantic_hash(item.value))
            citations.setdefault(item.field, []).append(item.evidence_id)
        if not witnesses:
            return ()
        # Deterministic pick: most witnesses first, field name as the tie-break — never dict order.
        best = min(witnesses, key=lambda name: (-len(witnesses[name]), name))
        # A conflict needs two *independent* witnesses; one source citing two values for a
        # list-valued fact is describing facets of the same fact, not contradicting itself.
        conflicts = sum(1 for groups in witnesses.values()
                        if len(groups) > 1 and len({h for hs in groups.values() for h in hs}) > 1)
        corroborated = sum(1 for groups in witnesses.values() if len(groups) >= minimum)
        single = sum(1 for groups in witnesses.values() if len(groups) == 1)
        return (Observation(
            plugin_id=self.plugin_id,
            kind="context.source_corroboration",
            metrics={
                "corroboration_count": len(witnesses[best]),
                "corroborated_field_count": corroborated,
                "single_sourced_field_count": single,
                "evidenced_field_count": len(witnesses),
                "conflict_count": conflicts,
            },
            evidence_ids=tuple(citations[best]),
            reason_codes=("context_sources_conflict",) if conflicts
            else ("context_sources_agree",),
        ),)


class ContextUnit(ReasoningUnit):
    """Situation Understanding · the stable factual reading of the present moment.

    Publishes nothing that re-scores the system.  In particular it does not publish `confidence_bp`
    — completeness and corroboration are *inputs* a confidence authority may weigh, and letting a
    second unit emit confidence would silently move every decision in the plan.
    """

    unit_id = "core.context"
    version = "1.0.0"
    category = UnitCategory.SITUATION_UNDERSTANDING
    publishes = (
        "completeness_bp", "declared_field_count", "known_field_count", "missing_field_count",
        "freshness_bp", "evidence_age_hours", "dated_evidence_count",
        "corroboration_count", "corroborated_field_count", "single_sourced_field_count",
        "evidenced_field_count", "conflict_count",
    )
    plugins = (FactCoveragePlugin(), EvidenceFreshnessPlugin(), SourceCorroborationPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Publish each plugin's reading as-is; deliberately no composite score.

        Coverage, freshness and corroboration answer three different questions, and averaging them
        would produce a number that means nothing in particular while inviting downstream units to
        treat it as a verdict on the situation.  A situation that is fully known but a month old is
        not "half good" — it is complete and stale, and both halves of that sentence matter to a
        different reader.

        Metric names are disjoint across plugins by construction; iteration is sorted by plugin id
        anyway so that the published mapping can never depend on registration order.
        """
        metrics: dict[str, int] = {}
        for observation in sorted(observations, key=lambda item: item.plugin_id):
            for name in sorted(observation.metrics):
                metrics[name] = int(observation.metrics[name])
        return metrics

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """Name the thresholds the reading crossed — without declaring the situation good or bad.

        `matched` stays `None` on purpose.  A matched verdict is a claim that some condition the
        capability cares about has been met, and "the context is adequate" is exactly the judgement
        this unit is forbidden to make: adequacy depends on what is about to be decided, which only
        the Decision Maker knows.  The reason codes below are threshold crossings authored in
        Layer 3 — statements of fact about a line the capability itself drew, not opinions.
        """
        codes = {code for observation in observations for code in observation.reason_codes}
        completeness = metrics.get("completeness_bp")
        if completeness is not None:
            codes.add("context_incomplete"
                      if completeness < _config_bp(view, "completeness_floor_bp", 6_000)
                      else "context_substantially_known")
        freshness = metrics.get("freshness_bp")
        if freshness is not None:
            codes.add("context_stale" if freshness < _config_bp(view, "freshness_floor_bp", 3_000)
                      else "context_current")
        corroboration = metrics.get("corroboration_count")
        if corroboration is not None:
            codes.add("context_corroborated"
                      if corroboration >= _config_count(view, "min_corroboration", 2)
                      else "context_single_sourced")
        # Every reading is recorded as a finding, matched or not: the value of this unit is the
        # written record of what was known at decision time, which is only useful if it is always
        # there — including, especially, on the runs that turned out badly.
        findings = tuple(Finding(
            finding_id=f"context.{observation.plugin_id}",
            kind="context",
            matched=None,
            metrics=observation.metrics,
            evidence_ids=observation.evidence_ids,
            reason_codes=observation.reason_codes,
        ) for observation in sorted(observations, key=lambda item: item.plugin_id))
        return Verdict(matched=None, metrics=dict(metrics), findings=findings,
                       reason_codes=tuple(sorted(codes)))


__all__ = ["ContextUnit", "EvidenceFreshnessPlugin", "FactCoveragePlugin",
           "SourceCorroborationPlugin", "declared_fields", "independence_key"]
