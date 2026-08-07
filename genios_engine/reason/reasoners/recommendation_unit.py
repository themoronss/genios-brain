"""Category 4 · Decision Support — the Recommendation Unit.

Answers one question: *for each thing we could do here, what is the case for it?*

Everything before this unit reasons about the **situation**. Temporal knows the clock, risk knows
the downside, opportunity knows the headroom, dependency knows what is in the way. None of them
know what the capability is actually able to *do*, and none of them connect their claim to it. So
by the time Part 3 ranks the declared plays, it holds a pile of findings on one side and a pile of
plays on the other, with nothing joining them — and a card that says "reply to the buyer" cannot
then explain which observation made that the sensible move.

This unit builds that join, and only that join. For every play the capability declares it assembles:

  * **which findings support it** — the units whose published claims match the linkage the
    capability author declared for that play,
  * **which evidence stands behind that support** — the actual snapshot rows, so a well-supported
    play backed by nothing citable is visibly different from one backed by three sources,
  * **whether the preconditions for acting are present** — a strong case for work that cannot be
    started is a different situation from a strong case for work that can.

The boundary here is the subtlest in Layer 4, so it is drawn explicitly:

**It assembles a case; it never argues one.** The unit reports the support behind *every* declared
play, including the plays with none. It emits its findings in play-id order — deliberately not in
support order — publishes no play id in any metric, and names no winner in any reason code.
Selecting is `reason/decision_maker.py`'s job and nothing here may pre-empt it. The most it does to
a candidate is scale a *capability-authored* nudge on `success`: the author says which play a
well-evidenced case should favour, this unit supplies only the measured magnitude.

**Linkage is declared, never inferred.** A finding supports a play because Layer 3 said so — via
the play's own `tags` or an explicit `play_support_codes` map — not because this unit guessed that
"inbound_awaiting_reply" sounds like it goes with "send a reply". Guessing the join would make the
explanation confident and wrong, which is worse than absent. Where a capability declares no linkage
at all the support plugins stay silent and the unit publishes no support metrics, so a reader gets
"we never wired this up" rather than a manufactured "nothing supports anything".

**A supporting unit that says nothing matched is not support.** A finding the publishing unit
itself marked `matched=False` is a claim it declined to make; counting it would let a unit's
*absence* of a finding argue for a play.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from genios_engine.contracts.reasoning import (
    CandidateAdjustment,
    CandidateCheck,
    CheckOutcome,
    Finding,
    ResultStatus,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, evidence_ids

#: Every observation this unit emits names the play whose case it belongs to, in its reason codes.
#: Colons are legal in the contract's identifier grammar, so this survives Finding validation and a
#: trace reader can recover the join without a second lookup table.
PLAY_PREFIX = "play:"

#: Reason code carried by every adjustment and check this unit emits, so an auditor asking "what
#: moved this play's success score?" gets an answer that names the *case*, not the unit.
SUPPORT_ADJUSTMENT_REASON = "play_case_is_well_supported"

#: Basis points are 0..10000 by law, so a negative sentinel can never collide with a published
#: value. It is how the readiness plugin tells "the dependency unit reported total blockage" apart
#: from "the dependency unit never ran" — the second is a blind spot, not a green light.
_ABSENT = -1


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Read one basis-point tuning value, refusing anything that is not integer bp.

    A silently coerced float would change the decision hash on a different machine, so a malformed
    capability is a loud authoring fault rather than a quiet rescore.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _delta_bp(value: Any, label: str) -> int:
    """An authored nudge may be negative — evidence can also argue a play is the wrong shape."""
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


def _config_price(prices: Mapping[str, Any], code: str, default: int) -> int:
    """Validate one authored per-code support weight (`support_weight_bp.<reason_code>`)."""
    value = prices.get(code, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"support_weight_bp.{code} must be integer basis points")
    return value


def _config_id(view: UnitView, key: str, default: str) -> str:
    """Which unit supplies an input, so a capability can appoint its own authority."""
    value = view.config.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must name a reasoning unit")
    return value.strip()


@dataclass(frozen=True, slots=True)
class _Support:
    """One published claim that argues for one play.

    Kept as a record rather than a running total because the *identity* of the supporting unit is
    the point: two claims from one unit are one unit's opinion, and an explanation that cannot say
    who spoke cannot be checked by the person reading it.
    """

    unit_id: str
    codes: tuple[str, ...]
    weight_bp: int
    evidence_ids: tuple[str, ...]


def _linkage(view: UnitView) -> Mapping[str, tuple[str, ...]]:
    """play_id → the reason codes Layer 3 declared as arguments for that play.

    Two authoring routes, unioned. A play's own `tags` are the lightweight route — a play tagged
    `inbound_awaiting_reply` is claiming that observation as its trigger — and `play_support_codes`
    is the explicit route for capabilities that keep tags for other purposes. Unioning rather than
    overriding means adding an explicit map never silently drops a linkage a tag already declared.

    Sorted output, because this table's iteration order reaches the reason codes on a finding.
    """
    authored = _mapping_config(view, "play_support_codes")
    table: dict[str, tuple[str, ...]] = {}
    for play in view.request.capability.plays:
        codes = {str(tag).strip() for tag in play.tags}
        raw = authored.get(play.play_id)
        if raw is not None:
            if isinstance(raw, str) or not isinstance(raw, (tuple, list)):
                raise ValueError(
                    f"play_support_codes.{play.play_id} must be a list of reason codes")
            codes.update(str(item).strip() for item in raw)
        table[play.play_id] = tuple(sorted(code for code in codes if code))
    return table


def _claims(view: UnitView) -> tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]:
    """Every claim a completed prior unit actually made: (unit_id, reason codes, evidence).

    Findings are preferred over the result-level roll-up because a result's `reason_codes` are
    usually the union of its findings' codes (see `opportunity.py`), and counting both would let
    one observation support a play twice. The roll-up is the fallback for the older reasoners that
    publish codes without findings — dropping those would silently un-support half the corpus.

    Iterated over sorted unit ids so the support order — and every hash downstream of it — is a
    property of the run, not of dict insertion order.
    """
    claims: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for unit_id in sorted(view.prior):
        result = view.prior[unit_id]
        if result.status != ResultStatus.COMPLETED:
            continue                      # a unit that did not complete has no opinion
        matched_findings = tuple(item for item in result.findings if item.matched is not False)
        if result.findings:
            claims.extend((unit_id, item.reason_codes, item.evidence_ids)
                          for item in matched_findings)
        elif result.matched is not False and result.reason_codes:
            claims.append((unit_id, result.reason_codes, result.evidence_ids))
    return tuple(claims)


def _support_for(view: UnitView, codes: tuple[str, ...]) -> tuple[_Support, ...]:
    """Which published claims match one play's declared linkage, and how much each is worth.

    A claim's weight is authored per reason code (`support_weight_bp`), because "the buyer replied
    and nobody answered" is not the same size of argument as "the account has no owner". Where the
    author never priced a code it takes `default_support_bp` — a neutral half, so an unpriced
    linkage still counts as support without pretending to be a strong one.
    """
    if not codes:
        return ()
    prices = _mapping_config(view, "support_weight_bp")
    default = _config_bp(view, "default_support_bp", 5_000)
    wanted = set(codes)
    supports: list[_Support] = []
    for unit_id, claim_codes, claim_evidence in _claims(view):
        matched = tuple(sorted(wanted & set(claim_codes)))
        if not matched:
            continue
        # The strongest matching code sets the claim's weight. A claim that happens to carry three
        # linked codes is still one unit saying one thing, so the weights are not summed here.
        weight = max(_config_price(prices, code, default) for code in matched)
        supports.append(_Support(unit_id=unit_id, codes=matched, weight_bp=weight,
                                 evidence_ids=tuple(sorted(set(claim_evidence)))))
    return tuple(supports)


class PlaySupportPlugin:
    """Which units argue for this play, and how strongly.

    This is the aggregation the Decision Maker cannot do for itself: it sees findings and plays but
    not the join between them, and inventing that join at ranking time would bury the reasoning
    inside the ranker where nobody can audit it.

    Every declared play gets an observation, including plays nothing supports. That is deliberate.
    "Three plays were considered and two had no case" is a materially different report from "one
    play was considered", and only the first lets a reader see that the field was not quietly
    narrowed before ranking. Where the capability declared no linkage for *any* play the plugin
    stays silent instead: with no vocabulary to match, zero support is a statement about our wiring
    rather than about the situation.
    """

    plugin_id = "play_support"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        linkage = _linkage(view)
        if not any(linkage.values()):
            return ()                     # no declared join exists; we have nothing to report
        observations: list[Observation] = []
        for play_id in sorted(linkage):
            supports = _support_for(view, linkage[play_id])
            # A unit that matched several codes is still one voice: take its strongest claim, so
            # breadth of *sources* is what raises the case, not verbosity of one source.
            by_unit: dict[str, int] = {}
            for item in supports:
                by_unit[item.unit_id] = max(by_unit.get(item.unit_id, 0), item.weight_bp)
            weights = sorted(by_unit.values(), reverse=True)
            # Same shape as `opportunity.py`, for the same reason: the strongest argument sets the
            # level and corroboration adds a bounded lift. Summing would let four weak, correlated
            # observations out-argue one decisive one; averaging would let a weak corroborator drag
            # a decisive case down.
            strength = clamp_bp(weights[0] + divide_half_up(sum(weights[1:]), 4)) if weights else 0
            codes = [f"{PLAY_PREFIX}{play_id}"]
            codes.extend(code for item in supports for code in item.codes)
            if not linkage[play_id]:
                # Wired for nothing at all. Reported apart from "wired and unsupported" because one
                # is an authoring gap and the other is a fact about the situation, and an operator
                # who cannot tell them apart will go looking for the wrong problem.
                codes.append("support.unlinked")
            elif not supports:
                codes.append("support.absent")
            elif len(by_unit) > 1:
                codes.append("support.corroborated")
            else:
                codes.append("support.single_source")
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="recommendation.play_support",
                metrics={"support_bp": strength,
                         "supporting_unit_count": len(by_unit),
                         "supporting_claim_count": len(supports)},
                reason_codes=tuple(codes),
            ))
        return tuple(observations)


class EvidenceLinkagePlugin:
    """What the case for this play actually stands on.

    Support strength and evidential grounding are different properties and they fail apart. Two
    units can agree loudly about a deal while both reading the same single stale CRM row; one unit
    can make a modest claim that cites three independent sources. A capability under an
    `evidence_required` policy needs to see which of those it has *before* the constraint unit
    eliminates on it, and a human reading the card needs the citations to check the reasoning at
    all.

    So this reports the distinct snapshot rows behind a play's support, and — the part that matters
    — how much of that support cited nothing. An unevidenced claim is not disallowed here; it is
    disclosed, and the disclosure travels with the play into Part 3.

    Silent for a play with no support: there is no linkage to trace, and reporting "0 evidence"
    would double-count the absence the support plugin already reported.
    """

    plugin_id = "evidence_linkage"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        linkage = _linkage(view)
        if not any(linkage.values()):
            return ()
        observations: list[Observation] = []
        for play_id in sorted(linkage):
            supports = _support_for(view, linkage[play_id])
            if not supports:
                continue
            linked = sorted({item for support in supports for item in support.evidence_ids})
            bare = sum(1 for support in supports if not support.evidence_ids)
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="recommendation.evidence_linkage",
                metrics={"evidence_count": len(linked), "unevidenced_support_count": bare},
                evidence_ids=tuple(linked),
                reason_codes=(f"{PLAY_PREFIX}{play_id}",)
                + (("evidence_linked",) if linked else ())
                + (("support_without_evidence",) if bare else ()),
            ))
        return tuple(observations)


class ActionReadinessPlugin:
    """Could this play actually be started, with what is in hand right now?

    A case for work that cannot begin is not the same as a case for work that can, and until this
    unit nothing carried that distinction to the ranker: the constraint reasoner *eliminates* on a
    failed precondition, which is a verdict, but it says nothing about the plays that survive with
    half their inputs missing.

    Readiness here is observability, not permission. A precondition is observable when the fact it
    names is present in the scope it names — we can evaluate it, whatever it then says. An `absent`
    precondition is observable by construction, since absence is exactly what it asserts. A play
    that declares no preconditions at all is fully ready: the play itself is the authority on what
    it needs, and second-guessing that would be inventing requirements.

    Two other inputs fold in, both read from units that already spoke. An upstream ELIMINATE check
    drops readiness to zero — something has already ruled this play out, and presenting it as ready
    would put a contradiction in front of a human. And where a dependency authority published how
    free the work is to proceed, readiness cannot exceed it: preconditions being *readable* is no
    comfort when a named blocker sits in front of the work.
    """

    plugin_id = "action_readiness"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        blocked_plays = self._eliminated(view)
        unblocked = view.prior_metric(
            _config_id(view, "dependency_source", "core.dependency"), "unblocked_bp", _ABSENT)
        observations: list[Observation] = []
        for play in sorted(view.request.capability.plays, key=lambda item: item.play_id):
            fields: list[str] = []
            observable = 0
            for condition in play.preconditions:
                field = str(condition.get("field") or "")
                if not field:
                    continue              # a malformed precondition is not evidence of readiness
                neighbor = bool(condition.get("neighbor", False))
                source = view.request.context.neighbor_facts if neighbor \
                    else view.request.context.facts
                present = field in source
                if present:
                    fields.append(field)
                if present or str(condition.get("op") or "exists") == "absent":
                    observable += 1
            declared = sum(1 for condition in play.preconditions
                           if str(condition.get("field") or ""))
            # No declared preconditions means nothing must be in place, so nothing is missing.
            ratio = 10_000 if declared == 0 \
                else clamp_bp(divide_half_up(observable * 10_000, declared))
            eliminated = play.play_id in blocked_plays
            readiness = 0 if eliminated else (
                ratio if unblocked == _ABSENT else min(ratio, clamp_bp(unblocked)))
            codes = [f"{PLAY_PREFIX}{play.play_id}"]
            if eliminated:
                codes.append("readiness.blocked_upstream")
            elif declared == 0:
                codes.append("readiness.unconditional")
            elif observable == declared:
                codes.append("readiness.inputs_present")
            else:
                codes.append("readiness.inputs_missing")
            if unblocked != _ABSENT and not eliminated and clamp_bp(unblocked) < ratio:
                codes.append("readiness.limited_by_dependency")
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="recommendation.action_readiness",
                metrics={"readiness_bp": readiness, "precondition_count": declared,
                         "observable_precondition_count": observable,
                         "blocked": 1 if eliminated else 0},
                evidence_ids=evidence_ids(view.request, *fields),
                reason_codes=tuple(codes),
            ))
        return tuple(observations)

    @staticmethod
    def _eliminated(view: UnitView) -> frozenset[str]:
        """Plays some earlier unit has already ruled out, read from its typed checks."""
        return frozenset(check.play_id
                         for unit_id in sorted(view.prior)
                         for check in view.prior[unit_id].checks
                         if view.prior[unit_id].status == ResultStatus.COMPLETED
                         and check.outcome == CheckOutcome.ELIMINATE)


def _play_of(observation: Observation) -> str:
    """Recover the play an observation belongs to. Every plugin here tags one; '' means malformed."""
    for code in observation.reason_codes:
        if code.startswith(PLAY_PREFIX):
            return code[len(PLAY_PREFIX):]
    return ""


class RecommendationUnit(ReasoningUnit):
    """Decision Support · the assembled case for each declared play.

    Publishes the *shape* of the field — how many plays were assembled, how many have a case, how
    strong the strongest case in the field is, how much of the field is evidenced, how many could
    actually be started. No metric names a play, because a metric that named one would be a
    recommendation wearing a number's clothes.

    It publishes none of the reserved shared metrics. Support changes how *well argued* a play is;
    letting a second unit move `confidence_bp` or `urgency_bp` would silently re-score every
    decision in the system.
    """

    unit_id = "core.recommendation"
    version = "1.0.0"
    category = UnitCategory.DECISION_SUPPORT
    publishes = ("declared_play_count", "supported_play_count", "support_strength_bp",
                 "support_coverage_bp", "evidence_linked_count", "ready_play_count")
    plugins = (ActionReadinessPlugin(), EvidenceLinkagePlugin(), PlaySupportPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Describe the field, never order it.

        `support_strength_bp` is the strongest case *available*, deliberately reported without the
        play it belongs to: it tells Part 3 and the explanation layer what quality of argument this
        run managed to assemble at all, which is the difference between "we picked the best of three
        strong cases" and "we picked the least bad of three thin ones". Naming which play holds it
        would be selection, so it is not named here and the per-play numbers live on the findings.

        Every derived metric is omitted rather than zeroed when its plugin had nothing to observe.
        A published `support_strength_bp = 0` from a capability that never declared any linkage
        would be indistinguishable from a situation where nothing genuinely supports anything — the
        exact fabrication this layer exists to prevent.
        """
        threshold = _config_bp(view, "support_threshold_bp", 3_000)
        ready_at = _config_bp(view, "readiness_threshold_bp", 10_000)
        grouped = self._by_play(observations)
        metrics: dict[str, int] = {"declared_play_count": len(grouped)}
        if not grouped:
            return metrics

        supported = [item for item in grouped.values() if "support_bp" in item]
        if supported:
            metrics["supported_play_count"] = sum(1 for item in supported
                                                  if item["support_bp"] >= threshold)
            metrics["support_strength_bp"] = max(item["support_bp"] for item in supported)
            # How much of the field was argued for at all — the guard against a run that looks
            # decisive because only one play was ever wired up.
            metrics["support_coverage_bp"] = clamp_bp(divide_half_up(
                sum(1 for item in supported if item["support_bp"] > 0) * 10_000, len(grouped)))

        # Distinct rows across the whole field, so three plays citing one email do not read as
        # three sources. Published only when the linkage plugin actually spoke: an unwired
        # capability has an unknown evidential base, not an empty one.
        traced = [observation for observation in observations
                  if observation.plugin_id == EvidenceLinkagePlugin.plugin_id]
        if traced:
            metrics["evidence_linked_count"] = len(
                {item for observation in traced for item in observation.evidence_ids})

        readiness = [item for item in grouped.values() if "readiness_bp" in item]
        if readiness:
            metrics["ready_play_count"] = sum(1 for item in readiness
                                              if item["readiness_bp"] >= ready_at)
        return metrics

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """`matched` means "at least one declared play has a real case", and nothing stronger.

        It is not "act", and it is certainly not "act on the best one". A finding is emitted for
        every assembled play in **play-id order** — never support order — so that neither this
        unit's output nor its ordering can be mistaken for a ranking. The unsupported plays keep
        their findings too: what was considered and found wanting is part of an honest explanation.

        `matched` is None when no support was observable at all, because "no capability linkage was
        declared" is a statement about our wiring and must not collapse into "nothing supports
        anything here".
        """
        grouped = self._by_play(observations)
        threshold = _config_bp(view, "support_threshold_bp", 3_000)
        codes_by_play = self._codes_by_play(observations)
        findings = tuple(Finding(
            finding_id=f"recommendation.{play_id}",
            kind="recommendation",
            matched=(None if "support_bp" not in grouped[play_id]
                     else grouped[play_id]["support_bp"] >= threshold),
            metrics=grouped[play_id],
            evidence_ids=tuple(sorted({item for observation in observations
                                       if _play_of(observation) == play_id
                                       for item in observation.evidence_ids})),
            reason_codes=codes_by_play[play_id],
        ) for play_id in sorted(grouped))

        supported = "supported_play_count" in metrics
        matched = None if not supported else metrics["supported_play_count"] > 0
        adjustments, checks = self._tilt(view, grouped, threshold)

        # Unit-level vocabulary stays categorical: the `play:` codes belong on their findings, where
        # they name one case, rather than at the top level where they would read as a shortlist.
        codes = {code for observation in observations for code in observation.reason_codes
                 if not code.startswith(PLAY_PREFIX)}
        if supported:
            codes.add("play_case_assembled" if matched else "no_play_case_assembled")
        return Verdict(
            matched=matched,
            metrics=dict(metrics),
            findings=findings,
            adjustments=adjustments,
            checks=checks,
            reason_codes=tuple(sorted(codes)),
        )

    def _tilt(self, view: UnitView, grouped: Mapping[str, Mapping[str, int]], threshold: int
              ) -> tuple[tuple[CandidateAdjustment, ...], tuple[CandidateCheck, ...]]:
        """Scale the capability's authored nudge on `success` by the measured strength of the case.

        The judgement — *which* play a well-evidenced case should favour, and by how much at full
        strength — is authored in Layer 3 as `play_success_bp: {play_id: delta}`. This unit supplies
        only the magnitude, so the author's delta is a ceiling reached by a maximal case rather than
        a flat bonus handed to anything over the line. Hardcoding play names here would make this
        unit a decision authority by the back door.

        Nothing is emitted for a play some earlier unit already eliminated: raising the success
        score of a play that is out of the contest adds a contradiction to the audit trail and
        cannot change any outcome.
        """
        authored = _mapping_config(view, "play_success_bp")
        adjustments: list[CandidateAdjustment] = []
        checks: list[CandidateCheck] = []
        for play_id in sorted(str(key) for key in authored):
            case = grouped.get(play_id)
            if case is None or case.get("support_bp", 0) < threshold or case.get("blocked", 0) == 1:
                continue
            delta = _delta_bp(authored[play_id], f"play_success_bp.{play_id}")
            scaled = divide_half_up(delta * case["support_bp"], 10_000)
            if scaled == 0:
                continue                  # a tilt that rounds away is noise in the audit trail
            adjustments.append(CandidateAdjustment(
                play_id=play_id, component="success", delta_bp=scaled,
                reason_code=SUPPORT_ADJUSTMENT_REASON))
            checks.append(CandidateCheck(
                play_id=play_id, stage="cost_benefit", outcome=CheckOutcome.ADJUST,
                reason_code=SUPPORT_ADJUSTMENT_REASON, evaluator_id=self.unit_id,
                evaluator_version=self.version,
                detail={"support_bp": case["support_bp"], "delta_bp": scaled,
                        "supporting_unit_count": case.get("supporting_unit_count", 0)}))
        return tuple(adjustments), tuple(checks)

    @staticmethod
    def _by_play(observations: Sequence[Observation]) -> Mapping[str, Mapping[str, int]]:
        """Merge every plugin's observation about one play into that play's case file.

        Plugins publish disjoint metric names on purpose, so the merge is total and no plugin can
        overwrite another's claim. Returned as a plain dict whose keys are always read in sorted
        order by the callers — the ordering is applied where it reaches output, not left to chance.
        """
        cases: dict[str, dict[str, int]] = {}
        for observation in observations:
            play_id = _play_of(observation)
            if not play_id:
                continue
            case = cases.setdefault(play_id, {})
            for name, value in sorted(observation.metrics.items()):
                case[name] = int(value)
        return cases

    @staticmethod
    def _codes_by_play(observations: Sequence[Observation]) -> Mapping[str, tuple[str, ...]]:
        """Every reason code observed about one play, sorted — this is the *why* on the card."""
        codes: dict[str, set[str]] = {}
        for observation in observations:
            play_id = _play_of(observation)
            if not play_id:
                continue
            codes.setdefault(play_id, set()).update(observation.reason_codes)
        return {play_id: tuple(sorted(values)) for play_id, values in codes.items()}


__all__ = ["ActionReadinessPlugin", "EvidenceLinkagePlugin", "PLAY_PREFIX", "PlaySupportPlugin",
           "RecommendationUnit", "SUPPORT_ADJUSTMENT_REASON"]
