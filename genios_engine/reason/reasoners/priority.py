"""Category 2 · Business Evaluation — the Priority Unit.

Answers one question: *how much does the clock matter here, and did anything overrule it?*

This unit is deliberately the smallest in the roster, and deliberately the only one allowed to
speak about urgency at all.  `urgency_bp` and `priority_override_bp` are resolved by the Decision
Maker through a named authority (`reason/decision_maker.py::PRIORITY_AUTHORITY`), which means
exactly one unit may publish them.  If a second unit ever published `urgency_bp`, the winner would
become "whichever reasoner happened to run last" and every ranked decision in the system would
silently re-score the day that unit joined a capability.  So the value is not computed here from
scratch: it is *sourced*, from a unit that already measured the thing urgency is made of.

There are two ways to source it, and they are mutually exclusive:

* **Declared.**  The capability names a `source_reasoner` — for `sales.deal_cooling` that is
  `core.temporal`, the unit that actually watched the silence grow.  Its reading is taken as the
  urgency, and its `priority_bp`, if it published one, is carried forward as an explicit override.
  Naming the source in Layer 3 is what keeps the judgement ("decay is what makes this urgent")
  with the capability author rather than hardcoded in a shared unit.
* **Derived.**  No source is named, or the named source did not run.  Then the loudest prior
  reading wins: urgency is the maximum `urgency_bp` any prior unit reported.  Maximum rather than
  mean, because urgency does not average — one genuinely burning input is not made cool by three
  calm ones sitting next to it.

Three rules keep the unit honest:

**It never invents urgency.**  Every number it publishes was measured by something else.  The unit
selects and normalises; it does not add a term of its own.

**Absence of an opinion is 5,000bp, absence of a reading is 0.**  With no prior results at all the
unit has nothing to source from and reports the neutral midpoint rather than a fabricated extreme.
But a prior unit that ran and reported no urgency contributes a genuine 0 to the maximum — it was
asked and it answered.  Those are different facts and the arithmetic keeps them different.

**It analyses, it does not rank.**  The unit publishes priority *inputs*.  The orchestrator's math
stage is what ranks actual candidates with them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import (Finding, ReasonerResult, ReasonerSpec,
                                               ReasoningRequest)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, integer

#: Reported when neither a declared source nor any prior reading is available.  The neutral
#: midpoint is a statement that the unit has no information, not that the situation is half urgent.
NEUTRAL_URGENCY_BP = 5_000

#: The single reason code this unit publishes.  It says "the priority inputs are ready", not
#: "this is urgent" — the reading itself lives in the metrics, and the Decision Maker judges it.
PRIORITY_READY_REASON = "priority_inputs_ready"


def _source_reasoner(view: UnitView) -> str:
    """The unit whose reading Layer 3 declared to be the urgency for this capability.

    Falsy config (absent, empty, ``None``) means "no source declared" and routes to the derived
    path.  A single accessor so the two urgency plugins can never disagree about which branch they
    are in — they are mutually exclusive by construction, not by coincidence.
    """
    return str(view.config.get("source_reasoner") or "")


def _declared_source(view: UnitView) -> ReasonerResult | None:
    """The declared source's result, or None if none was declared or it did not run.

    Deliberately *not* filtered by status: the contract already forbids a non-completed result
    from carrying metrics, so a skipped source reads as an empty metric map and falls back to the
    neutral midpoint through the same code path as a source that completed without an opinion.
    Re-checking status here would be a second, divergent definition of the same rule.
    """
    source = _source_reasoner(view)
    if not source:
        return None
    return view.prior.get(source)


class DeclaredUrgencyPlugin:
    """The urgency the capability's named source reasoner reported.

    The authoritative path.  A capability that names `core.temporal` as its source is asserting
    that time-decay *is* what urgency means for this situation, and that assertion outranks any
    louder number some other unit happened to publish.
    """

    plugin_id = "declared_urgency"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        result = _declared_source(view)
        if result is None:
            return ()
        raw = result.metrics.get("urgency_bp", NEUTRAL_URGENCY_BP)
        return (Observation(
            plugin_id=self.plugin_id,
            kind="priority.declared_urgency",
            metrics={"urgency_bp": integer(raw, "urgency_bp")},
            reason_codes=("urgency_from_declared_source",),
        ),)


class MaximumUrgencyPlugin:
    """The loudest urgency any prior unit reported, when no source was declared.

    Maximum, not mean: urgency is a claim that something is about to be lost, and a claim like
    that is not weakened by other units having nothing to say.  Averaging would let a quiet
    relationship reading dilute a deal that is one day from close.

    A prior unit that ran and published no `urgency_bp` contributes 0 rather than being skipped —
    it was in scope and reported no time pressure, which is information.  Only the case of *no
    prior results at all* falls back to the neutral midpoint.
    """

    plugin_id = "maximum_urgency"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        if _declared_source(view) is not None:
            return ()                       # the declared path owns this situation
        # Sorted so that a malformed prior reading raises against a deterministic result rather
        # than against whichever key the runtime mapping happened to yield first.  The maximum
        # itself is order-free, so sorting cannot move the published number.
        readings = [integer(view.prior[key].metrics.get("urgency_bp", 0), "urgency_bp")
                    for key in sorted(view.prior)]
        return (Observation(
            plugin_id=self.plugin_id,
            kind="priority.maximum_urgency",
            metrics={"urgency_bp": max(readings, default=NEUTRAL_URGENCY_BP),
                     "prior_reading_count": len(readings)},
            reason_codes=("urgency_from_prior_maximum",),
        ),)


class DeclaredOverridePlugin:
    """An explicit priority the declared source asked to be carried forward.

    Some sources do not merely measure pressure, they have already resolved it into a priority —
    a rule corpus that fired, a gate that ranked.  When the declared source publishes
    `priority_bp`, that reading travels intact to the Decision Maker as `priority_override_bp`
    instead of being re-derived from urgency, which would lose the source's judgement.

    Only the declared path can produce an override.  The derived maximum is an aggregation across
    units with no single author, so there is nobody whose override it would be.
    """

    plugin_id = "override_priority"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        result = _declared_source(view)
        if result is None:
            return ()
        raw = result.metrics.get("priority_bp")
        if raw is None:
            return ()                       # the source measured pressure but did not rule on it
        return (Observation(
            plugin_id=self.plugin_id,
            kind="priority.declared_override",
            metrics={"priority_override_bp": integer(raw, "priority_override_bp")},
            reason_codes=("priority_override_declared",),
        ),)


class AuthoredPriorityPlugin:
    """The priority the SITUATION AUTHOR declared, carried on the compiled capability's config.

    `DeclaredOverridePlugin` covers a source that ruled at runtime. This covers the case where the
    ruling was made in the corpus and compiled in — which is every compiled capability, because
    `core.risk` measures pressure and never rules on priority. With neither present the Decision
    Maker's formula ran on neutral components, returned 5,000bp, and `domain_shadow` turned that
    into `score = (5000 + 50) / 100 = 50` for every compiled signal alike: 193 of 223 signals and
    104 of 115 cards at the same score on the design partner's org, all in one urgency band.

    The corpus is not short of opinions about this — 48 situations carry `priority_bp` and they
    take 30 distinct values from 3,000 to 9,600. The number was read at compile time, used to
    rank which situation's card copy won, and then dropped. Everything needed to rank was already
    written down; nothing carried it.

    Published only when the compiler put one there. An absent authored priority stays absent
    rather than becoming a neutral 5,000, for the same reason the override never becomes a zero:
    "the author said nothing" and "the author said middling" are different claims, and only the
    second should outrank the formula.
    """

    plugin_id = "authored_priority"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        raw = view.config.get("authored_priority_bp")
        if raw is None:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="priority.authored",
            metrics={"priority_override_bp": integer(raw, "authored_priority_bp")},
            reason_codes=("priority_authored_by_situation",),
        ),)


class PriorityReasoner(ReasoningUnit):
    """Business Evaluation · the priority inputs; the orchestrator's math stage ranks candidates.

    Kept under its original class name because `reasoners/__init__.py`, the capability packs, and
    the registry all resolve it by that name, and the unit id `core.priority` is wired into the
    Decision Maker's authority table.
    """

    unit_id = "core.priority"
    version = "1.0.0"
    category = UnitCategory.BUSINESS_EVALUATION
    #: The reserved pair.  `tests/test_unit_roster.py` asserts that no other unit in the roster
    #: declares either of these, and that this one declares both.
    publishes = ("urgency_bp", "priority_override_bp")
    # ORDER IS THE PRECEDENCE RULE. `evaluate_metrics` keeps the LAST override observation it
    # sees, so the authored priority is offered first and a source that ruled at RUNTIME overrides
    # it — a live ruling about THIS node beats a general one about its situation type. The two
    # are rarely both present today (nothing on the compiled path publishes `priority_bp` at
    # runtime), which is exactly why the order has to be decided now rather than discovered later.
    plugins = (DeclaredUrgencyPlugin(), MaximumUrgencyPlugin(), AuthoredPriorityPlugin(),
               DeclaredOverridePlugin())

    def retrieve(self, request: ReasoningRequest, spec: ReasonerSpec,
                 prior: Mapping[str, ReasonerResult]) -> UnitView:
        """This unit reads prior results and config — never a context fact.

        The base retriever would select facts and attach their evidence ids to the result.  That
        would be a false claim here: no fact was consulted, so no fact evidences the number.  The
        window is deliberately empty and the evidence chain stays with the source reasoner that
        actually measured something.
        """
        return UnitView(request=request, spec=spec, prior=prior)

    def validate(self, view: UnitView) -> None:
        """Nothing to validate: with no prior results this unit still has a defined answer.

        The base validator enforces `required_fields`, which would turn a capability that declared
        fields on this spec into an insufficient-context result.  This unit never reads a fact, so
        a missing one cannot undermine its conclusion — refusing to answer would be a fabricated
        objection, and it would strip the Decision Maker of the urgency authority it resolves
        against.
        """

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Clamp the sourced readings into publishable basis points.

        There is no blending here on purpose.  Exactly one urgency observation exists — the two
        urgency plugins are mutually exclusive — so this stage selects and bounds rather than
        combines.  The override is published only when the declared source produced one; an
        absent override must stay absent rather than become a zero, because a zero override is a
        live instruction to deprioritise and "no opinion" is not that.
        """
        metrics: dict[str, int] = {}
        for observation in observations:
            if "urgency_bp" in observation.metrics:
                metrics["urgency_bp"] = clamp_bp(observation.metrics["urgency_bp"])
        for observation in observations:
            if "priority_override_bp" in observation.metrics:
                metrics["priority_override_bp"] = clamp_bp(
                    observation.metrics["priority_override_bp"])
        return metrics

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """Report the inputs as ready; refuse to say whether they are high.

        `matched` stays None because this unit has no gate to match.  "Is 7,200bp urgent enough to
        act?" is a ranking question, and answering it here would make the priority unit a decision
        authority by the back door — the one thing a unit that owns a reserved metric must never
        become.  The single finding carries the same metrics as the result so an auditor reading
        the findings alone sees the whole contribution.
        """
        finding = Finding(finding_id="priority.inputs", kind="priority", metrics=metrics,
                          reason_codes=(PRIORITY_READY_REASON,))
        return Verdict(metrics=dict(metrics), findings=(finding,),
                       reason_codes=finding.reason_codes)


__all__ = ["DeclaredOverridePlugin", "DeclaredUrgencyPlugin", "MaximumUrgencyPlugin",
           "NEUTRAL_URGENCY_BP", "PRIORITY_READY_REASON", "PriorityReasoner"]
