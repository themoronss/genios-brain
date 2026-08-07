"""Category 4 · Decision Support — the Alternative Unit.

Answers one question: *what else could be done here, and what does doing nothing actually cost?*

Every other unit in Part 2 examines the situation. This one examines the **option set** — the thing
an executive is actually handed. A recommendation with no visible alternatives is not a
recommendation, it is an instruction, and an instruction cannot be argued with. The difference
between "reply to the buyer" and "reply to the buyer, escalate to their sponsor, or accept that the
deal cools for another week — and here is what that week costs" is the entire difference between a
tool and an advisor.

Three separable claims, one per plugin:

* **Viability** — which declared plays are genuinely available *given what the other units already
  found*. A play another unit eliminated is not an option, however good it looks on paper. A play
  whose expected value rounds to nothing is not an option either; it is a placeholder someone left
  in the manifest.
* **Distinctness** — whether two "options" are actually the same move wearing different labels. A
  roster of five plays that is really two moves offers a false choice, and a false choice is worse
  than an honest single option because it manufactures a feeling of deliberation nobody did.
* **The do-nothing baseline** — the null option is always available, so it is always on the table
  and it always has a price. Pricing it is what turns "should we act?" into a comparison.

Two boundaries hold this unit to analysis:

**It counts options; it never orders them.** No adjustment, no check, no candidate ever leaves this
unit. Reporting that three genuinely different moves survive screening is an observation. Saying
which of the three to take is synthesis, and GeniOS has exactly one synthesis authority
(``reason/decision_maker.py``).

**It defers to the units that already ruled.** It does not re-evaluate preconditions or policies —
``core.constraint`` owns that — it reads the eliminations those units published. Where nobody
screened the roster at all it says so out loud (``viability_unscreened``) rather than reporting an
unchecked roster as a clean bill of health. Likewise it defers to a deployed cost unit's price of
inaction instead of deriving a second, disagreeing number for the same silence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import (
    CheckOutcome,
    Finding,
    PlayDefinition,
    ResultStatus,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up

# Basis points are 0..10000 by law, so a negative sentinel can never collide with a published
# value. It is how a plugin tells "the unit measured zero" apart from "the unit never ran" — the
# difference between a priced silence and a blind spot.
_ABSENT = -1

# Observations are claims, not candidates, so the framework gives them no play field. Where a claim
# is about one specific play, its identity travels in the observation `kind` after a colon — which
# is also what the finding is named after, so the audit trail says which option it is talking about.
_VIABILITY_PREFIX = "alternative.viability:"
_SIGNATURE_PREFIX = "alternative.signature:"
_BASELINE_KIND = "alternative.do_nothing"


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Read one tuning knob as integer basis points, refusing anything else.

    Tuning is authored in Layer 3 and ships inside the versioned capability, so a malformed value is
    a deployment fault. It must fail loudly here rather than quietly become a plausible-looking
    option count somewhere downstream.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_id(view: UnitView, key: str, default: str) -> str:
    """Which unit supplies a signal, so a capability can appoint its own authority for it."""
    value = view.config.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must name a reasoning unit")
    return value.strip()


def _prior_bp(view: UnitView, key: str, default_unit: str, metric: str) -> int | None:
    """One published signal, or None when the unit that owns it did not complete."""
    value = view.prior_metric(_config_id(view, key, default_unit), metric, _ABSENT)
    return None if value == _ABSENT else clamp_bp(value)


def _plays(view: UnitView) -> tuple[PlayDefinition, ...]:
    """The declared roster in one total order — never manifest order, never set order."""
    return tuple(sorted(view.request.capability.plays, key=lambda play: play.play_id))


def _suffix(kind: str) -> str:
    return kind.split(":", 1)[1] if ":" in kind else ""


def _rulings(view: UnitView) -> tuple[Mapping[str, tuple[str, ...]], frozenset[str]]:
    """What earlier units already decided about each play.

    Returns the eliminations by play id, and the set of plays anyone ruled on at all. The second
    value is what lets this unit distinguish "screened and clean" from "nobody looked" — reporting
    an unscreened roster as fully viable would be exactly the fabrication Layer 4 exists to prevent.

    Only completed results are read: a unit that crashed has no opinion, and the frozen contract
    already forbids a non-completed result from carrying checks at all.
    """
    eliminated: dict[str, set[str]] = {}
    ruled: set[str] = set()
    for _, result in sorted(view.prior.items()):
        if result.status != ResultStatus.COMPLETED:
            continue
        for check in result.checks:
            ruled.add(check.play_id)
            if check.outcome == CheckOutcome.ELIMINATE:
                eliminated.setdefault(check.play_id, set()).add(check.reason_code)
    return ({play_id: tuple(sorted(codes)) for play_id, codes in eliminated.items()},
            frozenset(ruled))


def _expected_value(play: PlayDefinition) -> int:
    """What the play is worth *in expectation* — its impact discounted by its odds.

    A large prize that lands one time in fifty is not an option a human would recognise as one, and
    counting it as such is how an option set gets padded with things nobody would ever take.
    """
    return clamp_bp(divide_half_up(play.impact_bp * play.success_probability_bp, 10_000))


def _move_signature(play: PlayDefinition) -> tuple[object, ...]:
    """What actually makes two plays the same move.

    The steps are the move. A different label, a different author's impact estimate, or a different
    tag does not change what a human is being asked to do, so none of those enter the signature —
    otherwise renaming a play would silently manufacture a second "option".

    Steps are lowercased, whitespace-collapsed and sorted: "Draft a reply" and "draft  a reply" are
    the same instruction, and two plays that list the same instructions in a different order are the
    same work in a different write-up.

    Reversibility and whether the play reaches someone outside the org *do* enter it. A read-only
    draft and an auto-send of the same text are genuinely different moves with genuinely different
    consequences, and collapsing them would hide the only choice that matters between them.
    """
    steps = tuple(sorted(" ".join(str(step).lower().split()) for step in play.steps))
    return (steps, play.read_only,
            play.metadata.get("external_recipient_required") is True)


class PlayViabilityPlugin:
    """Which declared plays are genuinely still on the table.

    Two screens, and neither is a ranking. The first defers entirely to units that already ruled:
    a play eliminated on policy or precondition is unavailable, and this unit reports that fact
    rather than re-deriving it. The second is a floor, not an order — a play whose expected value
    sits below the configured floor is nominally available but is not something a person would
    recognise as an option, and presenting it as one inflates the apparent breadth of choice.

    Where no earlier unit ruled on the roster at all, every play is reported as available *and* the
    observation carries ``viability_unscreened``, because an unchecked roster is not a clean one.
    """

    plugin_id = "play_viability"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        plays = _plays(view)
        if not plays:
            return ()                       # nothing declared; no claim about availability to make
        floor = _config_bp(view, "viable_value_floor_bp", 500)
        eliminated, ruled = _rulings(view)
        observations: list[Observation] = []
        for play in plays:
            blocking = eliminated.get(play.play_id, ())
            value = _expected_value(play)
            codes: list[str] = []
            if blocking:
                codes.append("option_eliminated_upstream")
                codes.extend(blocking)
            elif value < floor:
                codes.append("option_below_value_floor")
            else:
                codes.append("option_available")
            if not ruled:
                codes.append("viability_unscreened")
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind=f"{_VIABILITY_PREFIX}{play.play_id}",
                metrics={"viable": 0 if (blocking or value < floor) else 1,
                         "expected_value_bp": value,
                         "elimination_count": len(blocking)},
                reason_codes=tuple(codes),
            ))
        return tuple(observations)


class MoveDistinctnessPlugin:
    """Whether the roster offers different moves or the same move several times.

    Layer 3 capabilities accumulate plays. Two authors solve the same problem, a variant is added
    for a segment that no longer exists, and the roster quietly grows to five entries that are three
    moves. Counting entries would then report a rich set of alternatives that does not exist.

    Each play is assigned a group index over the roster in play-id order, so plays that are the same
    move share an index. The index is what the unit later counts, which is what makes "how many
    genuinely different things could we do?" answerable without re-deriving the comparison.
    """

    plugin_id = "move_distinctness"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        plays = _plays(view)
        if not plays:
            return ()
        # Assignment order follows the sorted roster, so a group index is a property of the
        # capability's content and identical on every replay.
        groups: dict[tuple[object, ...], int] = {}
        assigned: list[tuple[PlayDefinition, int]] = []
        for play in plays:
            signature = _move_signature(play)
            if signature not in groups:
                groups[signature] = len(groups)
            assigned.append((play, groups[signature]))
        sizes: dict[int, int] = {}
        for _, index in assigned:
            sizes[index] = sizes.get(index, 0) + 1
        return tuple(Observation(
            plugin_id=self.plugin_id,
            kind=f"{_SIGNATURE_PREFIX}{play.play_id}",
            metrics={"group": index, "group_size": sizes[index]},
            reason_codes=(("plays_share_one_move",) if sizes[index] > 1
                          else ("play_is_a_distinct_move",)),
        ) for play, index in assigned)


class DoNothingBaselinePlugin:
    """What the null option costs — the one alternative that is always available.

    Doing nothing is never off the table, so an option set that does not price it is incomplete.
    The price is not this unit's to invent: every input is a number another unit already published.

    Where a cost unit is deployed it owns the price of inaction outright, and this plugin reports
    that figure rather than deriving a second one that would disagree with it in the same card.
    Otherwise it composes the three ways a silence costs something — headroom that lapses, momentum
    that decays, exposure that compounds — with the strongest reading leading and the others adding
    a bounded lift, because they are three views of one silence rather than three separate silences.

    Silent when none of them was published. An unknown cost of waiting must stay unknown: reporting
    it as zero would tell a human that doing nothing is free, which is the single most expensive
    thing this unit could get wrong.
    """

    plugin_id = "do_nothing_baseline"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        priced = _prior_bp(view, "inaction_cost_source", "core.cost", "do_nothing_cost_bp")
        if priced is not None:
            return (Observation(
                plugin_id=self.plugin_id,
                kind=_BASELINE_KIND,
                metrics={"do_nothing_baseline_bp": priced, "signal_count": 1},
                reason_codes=("inaction_priced_upstream",),
            ),)
        signals: list[tuple[int, str]] = []
        for key, default_unit, metric, code in (
            ("headroom_source", "core.opportunity", "opportunity_bp", "headroom_lapses"),
            ("momentum_source", "core.temporal", "drop_bp", "momentum_decays"),
            ("exposure_source", "core.risk", "risk_bp", "exposure_compounds"),
        ):
            value = _prior_bp(view, key, default_unit, metric)
            if value is not None:
                signals.append((value, code))
        if not signals:
            return ()
        # Strongest reading first, then by code: a total order, so the leading signal never depends
        # on which unit happened to be scheduled first.
        ordered = sorted(signals, key=lambda item: (-item[0], item[1]))
        cost = clamp_bp(ordered[0][0] + divide_half_up(sum(v for v, _ in ordered[1:]), 4))
        codes = [code for value, code in ordered if value > 0]
        # A measured zero is a real finding and must not read like a blind spot: the signals were
        # published, they simply said the silence costs nothing.
        codes.append("inaction_has_a_price" if cost > 0 else "inaction_appears_costless")
        return (Observation(
            plugin_id=self.plugin_id,
            kind=_BASELINE_KIND,
            metrics={"do_nothing_baseline_bp": cost, "signal_count": len(ordered)},
            reason_codes=tuple(codes),
        ),)


class AlternativeUnit(ReasoningUnit):
    """Decision Support · the option set, and the honest price of the null option.

    Publishes how many genuinely different moves survive screening and what standing still costs.
    It emits no adjustment and no check: counting the options a human should see is analysis, and
    choosing between them is the Decision Maker's alone.
    """

    unit_id = "core.alternative"
    version = "1.0.0"
    category = UnitCategory.DECISION_SUPPORT
    publishes = ("declared_count", "viable_count", "distinct_count", "duplicate_count",
                 "option_count", "has_alternative", "do_nothing_baseline_bp")
    plugins = (DoNothingBaselinePlugin(), MoveDistinctnessPlugin(), PlayViabilityPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Fold three claims into the shape of the choice a human is being handed.

        ``distinct_count`` counts *moves*, not manifest entries: duplicates collapse into their
        group, so five plays that are two moves report two. ``option_count`` is that plus one,
        because the null option never leaves the table and an option set that omitted it would
        overstate how forced the situation is.

        ``has_alternative`` is deliberately strict — it is 1 only when at least two genuinely
        different moves survive. Act-or-do-nothing is a decision, but it is not a choice *between
        courses of action*, and conflating the two is how a forced move gets presented as if it had
        been deliberated.
        """
        viability = {_suffix(item.kind): item for item in observations
                     if item.kind.startswith(_VIABILITY_PREFIX)}
        groups = {_suffix(item.kind): int(item.metrics["group"]) for item in observations
                  if item.kind.startswith(_SIGNATURE_PREFIX)}
        baseline = next((item for item in observations if item.kind == _BASELINE_KIND), None)

        viable_ids = sorted(play_id for play_id, item in viability.items()
                            if int(item.metrics["viable"]) == 1)
        # A play with no published grouping stands alone rather than being folded into group zero;
        # the negative sentinel cannot collide with a real group index.
        distinct = {groups.get(play_id, -1 - index) for index, play_id in enumerate(viable_ids)}
        distinct_count = len(distinct)
        return {"declared_count": len(viability),
                "viable_count": len(viable_ids),
                "distinct_count": distinct_count,
                "duplicate_count": len(viable_ids) - distinct_count,
                "option_count": distinct_count + 1,
                "has_alternative": 1 if distinct_count >= 2 else 0,
                "do_nothing_baseline_bp": int(baseline.metrics["do_nothing_baseline_bp"]) if baseline
                else 0}

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """``matched`` means "this situation offers a real choice" — never "take one of them".

        The negative readings carry as much information as the positive one and are named
        explicitly, because each demands something different from the reader:

        * ``no_viable_option`` — everything was screened out. The only thing left is the null
          option, and its price is the whole story.
        * ``single_course_of_action`` — one move survives. A human should see that it was not
          chosen from a field, it was the field.
        * ``false_choice_in_roster`` — the roster looks broader than it is. Said out loud so nobody
          reads breadth into a duplicate.
        * ``do_nothing_cost_unknown`` — nothing priced the silence. A zero here is an absence of
          measurement, and it must never be read as a measurement of zero.
        """
        codes = {code for item in observations for code in item.reason_codes}
        if metrics["viable_count"] == 0:
            codes.add("no_viable_option")
        elif metrics["has_alternative"] == 1:
            codes.add("genuine_choice_available")
        else:
            codes.add("single_course_of_action")
        if metrics["duplicate_count"] > 0:
            codes.add("false_choice_in_roster")
        if not any(item.kind == _BASELINE_KIND for item in observations):
            codes.add("do_nothing_cost_unknown")

        # Every option's screening is on the record whether it survived or not: an option set is
        # only auditable if the things that were ruled out are visible alongside the things that
        # were not. Duplicates are surfaced too, since a collapsed pair is why a count looks small.
        findings = [Finding(
            finding_id=item.kind,
            kind="alternative",
            matched=int(item.metrics["viable"]) == 1,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations if item.kind.startswith(_VIABILITY_PREFIX)]
        findings.extend(Finding(
            finding_id=item.kind,
            kind="alternative",
            matched=False,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations
            if item.kind.startswith(_SIGNATURE_PREFIX) and int(item.metrics["group_size"]) > 1)
        findings.extend(Finding(
            finding_id=item.kind,
            kind="alternative",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations if item.kind == _BASELINE_KIND)
        findings.append(Finding(
            finding_id="alternative.option_set",
            kind="alternative",
            matched=metrics["has_alternative"] == 1,
            metrics=dict(metrics),
            reason_codes=tuple(sorted(codes)),
        ))

        return Verdict(
            matched=metrics["has_alternative"] == 1,
            metrics=dict(metrics),
            findings=tuple(findings),
            reason_codes=tuple(sorted(codes)),
        )


__all__ = ["AlternativeUnit", "DoNothingBaselinePlugin", "MoveDistinctnessPlugin",
           "PlayViabilityPlugin"]
