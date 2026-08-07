"""Category 4 · Decision Support — the Validation Unit.

Answers one question: *is this reasoning safe to act on?*

Every other unit in the plan reasons about the world. This one reasons about **the reasoning** —
it is the last thing that runs before synthesis, and the only place in Layer 4 that inspects what
the other units actually produced rather than what the situation actually is.

That job exists because the failure mode of an intelligence system is not usually a bad rule. It is
a plausible-looking answer assembled out of parts that never agreed with each other, or that cited
nothing, or that rested on evidence old enough to describe a different world. None of those are
visible from inside the unit that caused them: a unit that asserts `risk_bp = 9,200` has no idea
that another unit in the same run asserted `risk_bp = 1,000`, and the Decision Maker will happily
score a play on whichever value it reads last. Somebody has to look across the whole run, and that
is this unit.

Three families of integrity fault, one per plugin, because they are resolved three different ways:

  * **Contradiction** — two units in the same run asserting incompatible things. Nothing downstream
    reconciles this; it is not a close call between two opinions, it is a run whose own basis does
    not hold together. Chasing the disagreement is an engineering fix, not a business one.
  * **Insufficient evidence** — a unit that asserted a claim while citing no evidence this snapshot
    can produce. This is the closest thing to hallucination risk a deterministic engine has: the
    claim may well be right, but nothing in the record shows *why*, so a human cannot check it and
    a later replay cannot defend it.
  * **Staleness** — the freshest thing the run stood on is old enough that acting now means acting
    on a description of the past.

Four numbers describe the result, deliberately kept apart:

  ``contradiction_count``      how many incompatible pairs were found across the run.
  ``evidence_sufficiency_bp``  the share of asserted claims that cited producible evidence.
  ``staleness_bp``             how far past the acceptable age the *freshest* evidence is.
  ``safe_bp``                  the one composite: how sound the basis is overall.

And ``inspected_result_count`` states how much was looked at, because ``safe_bp = 10,000`` from
nothing inspected and ``safe_bp = 10,000`` from a clean run are entirely different claims, and a
consumer that cannot tell them apart will eventually act on silence.

**What it may and may not do.** This unit reports integrity; it never ranks a play, never selects
one, and never adjusts anyone's score. It does hold one authority the analytical units do not: when
the basis fails validation it emits a `safety`-stage `ELIMINATE` check. That is a veto, not a
choice — it is applied identically to every play the capability exposes, because reasoning that is
unsafe is unsafe for all of them. This unit can stop the run; it can never pick its winner.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CheckOutcome,
    Finding,
    ResultStatus,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up

# Reason codes carry the specific thing at fault so a trace names the disagreement rather than just
# its species. Colons are legal in the contract's identifier grammar, so these survive validation.
METRIC_PREFIX = "metric:"
KIND_PREFIX = "kind:"
PUBLISHER_PREFIX = "publisher:"
CLAIMANT_PREFIX = "claimant:"
_DETAIL_PREFIXES = (METRIC_PREFIX, KIND_PREFIX, PUBLISHER_PREFIX, CLAIMANT_PREFIX)

# The three metrics that have a *declared authority* in Part 3: several units are expected to
# observe them and exactly one publishes the value the decision uses. Disagreement there is resolved
# by design, so flagging it as a contradiction would report the system working as intended as a
# fault — and drown the genuine ones in noise.
AUTHORITY_RESOLVED_METRICS = frozenset({"confidence_bp", "urgency_bp", "priority_override_bp"})


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Per-capability tuning, validated as integer basis points.

    Tuning is authored in Layer 3 and versioned with the capability. A malformed value is a
    deployment fault rather than something to quietly round into range: a safety floor that
    silently became zero would mean this unit never stopped anything again.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_hours(view: UnitView, key: str, default: int) -> int:
    """A positive whole number of hours from capability config (a duration, not a bp value)."""
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{key} must be a positive integer number of hours")
    return value


def completed_results(view: UnitView) -> tuple[tuple[str, Any], ...]:
    """Every prior result that actually finished, in a total order.

    Sorted by reasoner id so that nothing about this unit's output depends on the order the
    orchestrator happened to fill the mapping in. Results that did not complete are excluded
    entirely: a unit that failed or skipped has no opinion, and reading its absence as agreement is
    exactly the mistake this unit exists to catch.
    """
    return tuple(sorted(
        ((reasoner_id, result) for reasoner_id, result in view.prior.items()
         if result.status == ResultStatus.COMPLETED),
        key=lambda item: item[0],
    ))


def producible_evidence(view: UnitView) -> frozenset[str]:
    """The evidence ids this exact snapshot can produce.

    A citation to something outside the snapshot is not grounding. It may be a stale id from an
    earlier run or a typo in a hand-authored fixture; either way a reviewer following the citation
    finds nothing, which is indistinguishable from no citation at all.
    """
    return frozenset(item.evidence_id for item in view.request.context.evidence)


def _cited(result: Any, producible: frozenset[str]) -> tuple[str, ...]:
    """Every producible evidence id a result stands on, including via its findings."""
    cited = set(result.evidence_ids)
    for finding in result.findings:
        cited.update(finding.evidence_ids)
    return tuple(sorted(cited & producible))


def _asserts_a_claim(result: Any) -> bool:
    """Did this result actually assert something, or merely report numbers?

    Only assertions can be ungrounded. A unit that publishes `elapsed_hours = 31` and matches
    nothing has made an observation about the snapshot, not a claim about the world, and demanding
    a citation for it would turn the evidence metric into noise. `matched is True`, or a finding
    that is not an explicit negative, is where a unit puts its neck out.
    """
    if result.matched is True:
        return True
    return any(finding.matched is not False for finding in result.findings)


class ContradictionPlugin:
    """Two units in the same run asserting incompatible things.

    This is the fault with no downstream remedy. When one unit says the deal is cold and another
    says it is warm, the Decision Maker does not adjudicate — it consumes whatever it finds, and the
    resulting recommendation is confident for reasons that are not true. The point of detecting it
    here is that a contradictory run should stop, be looked at, and be fixed, rather than quietly
    producing a decision whose basis nobody could reconstruct.

    Two structurally detectable forms, both of which can be judged without knowing any domain
    meaning — which matters, because a validator that needed to understand every metric it policed
    would need updating every time a unit was added:

      * **Divergent duplicate metric.** Two units publish the same `_bp` metric name with values far
        apart. Comparison is restricted to basis-point metrics because those share one scale, so a
        gap is meaningful; a gap of "31" between two `elapsed_hours` metrics is not comparable to
        anything. Metrics with a declared authority are exempt, since disagreement there is resolved
        by design rather than left dangling.
      * **Opposed verdicts.** Two different units emit findings of the same kind, one matched and
        one explicitly not matched. Same subject, opposite polarity. The "different units" condition
        is deliberate: one unit reporting several findings of mixed polarity is describing a mixed
        situation, which is honest work, not self-contradiction.
    """

    plugin_id = "contradiction"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        results = completed_results(view)
        if len(results) < 2:
            return ()                        # a single voice cannot disagree with anybody
        producible = producible_evidence(view)
        observations: list[Observation] = []
        observations.extend(self._divergent_metrics(view, results, producible))
        observations.extend(self._opposed_verdicts(view, results, producible))
        return tuple(observations)

    def _divergent_metrics(self, view: UnitView, results, producible) -> list[Observation]:
        tolerance = _config_bp(view, "contradiction_gap_bp", 5_000)
        publishers: dict[str, list[tuple[int, str]]] = {}
        for reasoner_id, result in results:
            for name, value in sorted(result.metrics.items()):
                if not name.endswith("_bp") or name in AUTHORITY_RESOLVED_METRICS:
                    continue
                if isinstance(value, bool) or not isinstance(value, int):
                    continue
                publishers.setdefault(name, []).append((value, reasoner_id))
        observations: list[Observation] = []
        for name in sorted(publishers):
            entries = sorted(publishers[name])       # (value, reasoner_id) — a total order
            if len(entries) < 2:
                continue
            gap = entries[-1][0] - entries[0][0]
            if gap < tolerance:
                continue                              # two readings of one quantity, not a clash
            lowest, highest = entries[0][1], entries[-1][1]
            cited = set()
            for reasoner_id, result in results:
                if reasoner_id in {lowest, highest}:
                    cited.update(_cited(result, producible))
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="validation.metric_divergence",
                # Severity *is* the gap: two units 9,000bp apart on the same quantity have a worse
                # disagreement than two units 5,000bp apart, and the number is already in the right
                # units to say so.
                metrics={"contradiction": 1, "severity_bp": clamp_bp(gap), "gap_bp": clamp_bp(gap),
                         "publisher_count": len(entries)},
                evidence_ids=tuple(sorted(cited)),
                reason_codes=("units_disagree_on_metric", f"{METRIC_PREFIX}{name}",
                              f"{PUBLISHER_PREFIX}{lowest}", f"{PUBLISHER_PREFIX}{highest}"),
            ))
        return observations

    def _opposed_verdicts(self, view: UnitView, results, producible) -> list[Observation]:
        severity = _config_bp(view, "verdict_clash_severity_bp", 8_000)
        polarity: dict[str, dict[bool, set[str]]] = {}
        for reasoner_id, result in results:
            for finding in result.findings:
                if finding.matched is None:
                    continue
                bucket = polarity.setdefault(finding.kind, {True: set(), False: set()})
                bucket[finding.matched].add(reasoner_id)
        observations: list[Observation] = []
        for kind in sorted(polarity):
            affirmed, denied = polarity[kind][True], polarity[kind][False]
            if not affirmed or not denied or len(affirmed | denied) < 2:
                continue
            cited = set()
            for reasoner_id, result in results:
                if reasoner_id in affirmed | denied:
                    cited.update(_cited(result, producible))
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="validation.verdict_clash",
                # Flat severity: a straight yes/no clash has no magnitude to read. It is either
                # present or it is not, and its weight is a business judgement Layer 3 may tune.
                metrics={"contradiction": 1, "severity_bp": severity,
                         "publisher_count": len(affirmed | denied)},
                evidence_ids=tuple(sorted(cited)),
                reason_codes=("units_disagree_on_verdict", f"{KIND_PREFIX}{kind}")
                + tuple(f"{PUBLISHER_PREFIX}{item}"
                        for item in (sorted(affirmed)[0], sorted(denied)[0])),
            ))
        return observations


class EvidenceSufficiencyPlugin:
    """Which claims in this run can actually be checked by a human.

    GeniOS's whole promise is that a recommendation can be traced back to the specific facts it came
    from. A unit that asserts something while citing no evidence the snapshot can produce breaks
    that promise silently — the claim reads exactly like a grounded one, right up until somebody
    asks why. That is this engine's equivalent of a hallucination: not an invented fact, but an
    assertion nobody can retrace.

    Each ungrounded claim is reported by name, because "3 of 5 claims are ungrounded" is an
    engineering metric while "core.opportunity asserted an opportunity and cited nothing" is
    something a reviewer can act on. The share is reported alongside, and only when at least one
    claim was actually asserted: a run in which nobody claimed anything has no sufficiency to
    measure, and printing 0 there would read as "everything is ungrounded", which is a much stronger
    and quite different statement.
    """

    plugin_id = "evidence_sufficiency"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        results = completed_results(view)
        if not results:
            return ()                        # nothing ran; there is nothing to say about it
        producible = producible_evidence(view)
        observations: list[Observation] = []
        claims = grounded = 0
        for reasoner_id, result in results:
            if not _asserts_a_claim(result):
                continue
            claims += 1
            cited = _cited(result, producible)
            if cited:
                grounded += 1
                continue
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="validation.ungrounded_claim",
                metrics={"ungrounded": 1},
                reason_codes=("claim_without_evidence", f"{CLAIMANT_PREFIX}{reasoner_id}"),
            ))
        summary = {"inspected_results": len(results), "claims": claims, "grounded": grounded}
        observations.append(Observation(
            plugin_id=self.plugin_id,
            kind="validation.evidence_sufficiency",
            metrics=summary,
            reason_codes=("evidence_inspected",),
        ))
        return tuple(observations)


class StalenessPlugin:
    """How old the newest thing this run stood on is.

    Age is judged against the *freshest* dated evidence rather than the average or the oldest,
    because one recent observation is enough to say the picture is current: a thread with a message
    from this morning is live regardless of how many year-old attachments hang off it. The reverse
    is the dangerous case, and the one this measures — when even the newest thing we have is old,
    every conclusion in the run describes a world that has had time to move on.

    Only evidence that carries an `occurred_at` is considered. Undated evidence is not assumed
    fresh and is not assumed stale; it is not evidence about time at all, and a run with no dated
    evidence produces no staleness reading rather than a fabricated zero.
    """

    plugin_id = "staleness"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        limit_hours = _config_hours(view, "max_evidence_age_hours", 168)
        evaluation_time = view.request.evaluation_time
        ages: list[tuple[int, str]] = []
        for item in view.request.context.evidence:
            if item.occurred_at is None:
                continue
            seconds = int((evaluation_time - item.occurred_at).total_seconds())
            # Evidence dated after the evaluation time cannot be stale; it is treated as age zero
            # rather than as a negative age, which would otherwise make a clock-skewed row look
            # like the freshest thing in the run by an arbitrary margin.
            ages.append((max(seconds, 0) // 3600, item.evidence_id))
        if not ages:
            return ()
        ages.sort()
        freshest, freshest_id = ages[0]
        stale = tuple(sorted(evidence_id for hours, evidence_id in ages if hours > limit_hours))
        # Linear past the limit and fully stale at twice it: a day past a one-week limit is a mild
        # concern, two weeks on a one-week limit means nobody has looked at this since it mattered.
        overshoot = clamp_bp(divide_half_up((freshest - limit_hours) * 10_000, limit_hours)) \
            if freshest > limit_hours else 0
        return (Observation(
            plugin_id=self.plugin_id,
            kind="validation.evidence_stale" if overshoot else "validation.evidence_fresh",
            metrics={"staleness_bp": overshoot, "stale_count": len(stale),
                     "freshest_age_hours": freshest, "inspected_evidence": len(ages)},
            evidence_ids=(freshest_id,) + stale,
            reason_codes=("evidence_older_than_limit",) if overshoot else ("evidence_current",),
        ),)


class ValidationUnit(ReasoningUnit):
    """Decision Support · is this reasoning safe to act on?

    Reads the accumulated output of the run rather than the situation, and reports where that output
    fails to hold together. It publishes none of the reserved shared metrics: validation says
    whether the basis is sound, not how confident or how urgent the decision is, and letting a
    second writer move those would silently re-score every decision in the system.
    """

    unit_id = "core.validation"
    version = "1.0.0"
    category = UnitCategory.DECISION_SUPPORT
    publishes = ("contradiction_count", "evidence_sufficiency_bp", "ungrounded_claim_count",
                 "staleness_bp", "stale_evidence_count", "inspected_result_count", "safe_bp")
    plugins = (ContradictionPlugin(), EvidenceSufficiencyPlugin(), StalenessPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Worst contradiction governs; weaker faults degrade rather than destroy.

        Deliberately not a sum of complaints. Three mild faults do not make a run three times more
        unsafe than one outright contradiction — a basis that contradicts itself is broken on its
        own, and the sharpest break sets the level. Further contradictions still count, because each
        is another thing that has to be reconciled before anybody can trust the output, so they
        contribute a quarter of their weight.

        Missing citations and age are weighted below contradictions on purpose. A claim with no
        citation may still be perfectly true and a week-old fact may still be current; both make the
        basis weaker without making it incoherent. A contradiction is the only fault here that
        guarantees something in the run is actually wrong.
        """
        metrics: dict[str, int] = {}
        contradictions = sorted((clamp_bp(int(item.metrics.get("severity_bp", 0)))
                                 for item in observations
                                 if int(item.metrics.get("contradiction", 0)) == 1), reverse=True)
        metrics["contradiction_count"] = len(contradictions)
        metrics["ungrounded_claim_count"] = sum(int(item.metrics.get("ungrounded", 0))
                                                for item in observations)

        summary = next((item for item in observations
                        if item.kind == "validation.evidence_sufficiency"), None)
        inspected = int(summary.metrics["inspected_results"]) if summary else 0
        metrics["inspected_result_count"] = inspected
        grounding_gap = 0
        if summary is not None and int(summary.metrics["claims"]) > 0:
            claims, grounded = int(summary.metrics["claims"]), int(summary.metrics["grounded"])
            sufficiency = clamp_bp(divide_half_up(grounded * 10_000, claims))
            metrics["evidence_sufficiency_bp"] = sufficiency
            grounding_gap = 10_000 - sufficiency

        staleness = next((item for item in observations
                          if item.kind in {"validation.evidence_stale",
                                           "validation.evidence_fresh"}), None)
        staleness_bp = 0
        if staleness is not None:
            staleness_bp = clamp_bp(int(staleness.metrics["staleness_bp"]))
            metrics["staleness_bp"] = staleness_bp
            metrics["stale_evidence_count"] = int(staleness.metrics["stale_count"])

        if inspected == 0:
            # Nothing was inspected, so no fault was demonstrated. `inspected_result_count` is what
            # tells a consumer this is an empty room rather than a clean bill of health — this unit
            # will not manufacture a danger it has no evidence for, nor an all-clear it has not
            # earned. The Evaluator refuses to eliminate anything on this basis.
            metrics["safe_bp"] = 10_000
            return metrics

        contradiction_penalty = 0
        if contradictions:
            contradiction_penalty = contradictions[0] + divide_half_up(sum(contradictions[1:]), 4)
        grounding_penalty = divide_half_up(
            grounding_gap * _config_bp(view, "grounding_weight_bp", 6_000), 10_000)
        staleness_penalty = divide_half_up(
            staleness_bp * _config_bp(view, "staleness_weight_bp", 4_000), 10_000)
        metrics["safe_bp"] = clamp_bp(
            10_000 - contradiction_penalty - grounding_penalty - staleness_penalty)
        return metrics

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """`matched` means "an integrity fault was found", and the check says what follows from it.

        The elimination is the one authority this unit holds, and it is bounded in two ways that
        matter. It is applied to *every* play identically, so it can never function as a preference
        for one play over another — this unit stops the run or it does not, it never picks. And it
        is never issued from an uninspected run: eliminating on the grounds of having looked at
        nothing would veto every plan in which validation happens to be scheduled first, which
        would be a bug wearing the costume of caution.

        The passing case emits a check too. A candidate whose trace shows `safety: PASS` was
        genuinely validated; one with no safety check at all never was, and those must not look
        alike weeks later in an audit.
        """
        faults = tuple(item for item in observations
                       if int(item.metrics.get("contradiction", 0)) == 1
                       or int(item.metrics.get("ungrounded", 0)) == 1
                       or item.kind == "validation.evidence_stale")
        if metrics["inspected_result_count"] == 0:
            return Verdict(matched=False, metrics=dict(metrics),
                           reason_codes=("validation_not_observable",))

        floor = _config_bp(view, "safety_floor_bp", 4_000)
        unsafe = metrics["safe_bp"] < floor
        detail = {"safe_bp": metrics["safe_bp"], "safety_floor_bp": floor,
                  "contradiction_count": metrics["contradiction_count"],
                  "ungrounded_claim_count": metrics["ungrounded_claim_count"]}
        checks = tuple(CandidateCheck(
            play_id=play.play_id,
            stage="safety",
            outcome=CheckOutcome.ELIMINATE if unsafe else CheckOutcome.PASS,
            reason_code="unsafe_reasoning_basis" if unsafe else "reasoning_basis_validated",
            evaluator_id=self.unit_id,
            evaluator_version=self.version,
            detail=detail,
        ) for play in sorted(view.request.capability.plays, key=lambda item: item.play_id))

        findings = tuple(Finding(
            finding_id=_finding_id(item),
            kind="validation",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in faults)
        # Per-fault `metric:`/`kind:`/`publisher:`/`claimant:` codes stay on their findings; the
        # unit-level vocabulary is kept categorical so consumers can match on it without parsing
        # reasoner and field names out of a string.
        codes = tuple(sorted({code for item in faults for code in item.reason_codes
                              if not code.startswith(_DETAIL_PREFIXES)}))
        if not faults:
            codes = ("reasoning_basis_validated",)
        return Verdict(matched=bool(faults), metrics=dict(metrics), findings=findings,
                       checks=checks, reason_codes=codes)


def _finding_id(observation: Observation) -> str:
    """Name a fault by what it is *about* so its finding keeps a stable identity across runs.

    Findings are compared between runs to see what changed. A positional id would make a repaired
    contradiction and a newly appeared one indistinguishable — everything after the repair would
    shift up one place and read as churn.
    """
    for prefix in _DETAIL_PREFIXES:
        for code in observation.reason_codes:
            if code.startswith(prefix):
                return f"validation.{observation.plugin_id}.{code[len(prefix):]}"
    return f"validation.{observation.plugin_id}"


__all__ = ["ContradictionPlugin", "EvidenceSufficiencyPlugin", "StalenessPlugin", "ValidationUnit"]
