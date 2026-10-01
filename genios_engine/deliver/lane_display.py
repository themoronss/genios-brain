r"""L5 · the lane on the card — what the reader is being handed, said in the reader's words.

⛔ WHAT WAS WRONG, AND WE DID IT OURSELVES. `layer-2-reasoning/STEP-05` added `OutputLane`, routed
every decision through `reason/output_lane.route`, migrated `signals.output_lane` + `lane_reason`
(`0189`) and wrote both onto the row in `domain_shadow`. Then:

    grep -rn "output_lane\|lane_reason" genios_engine/deliver/   →   nothing

Built, tested, green, and called by nothing — the sixth-times defect, in a vocabulary added one step
earlier to fix a different instance of it. That step's own document promised *"the card layer can
group by lane directly"*. It could. It did not. This module is that reader.

⛔ NULL IS AN ANSWER, AND IT IS THE WHOLE RISK HERE. Every signal written before `0189`, and every
signal from a path that does not route, has no lane. Such a card is labelled `unrouted` and COUNTED.
It is never defaulted to `decision`: a default would have the card assert the authority of a routed
decision that no router granted it, which is the exact failure the lane vocabulary was added to end.
`card_source` states the same law about a missing `situation_id` one file over — *"`situation_id IS
NULL` is an ANSWER, not a gap"* — and the reason is the same both times.

⛔ THIS MODULE DOES NOT GATE DELIVERY. A `suppress` lane is DISPLAYED and COUNTED, not hidden. Hiding
would change what reaches a founder on the strength of a column that, because of the API spend limit
since 2026-09-25, has never once been written in production. Carry first, measure, then decide — the
order `card_source.COMPARISON_KEYS` already established for the other cutover in this package.

PURE. No I/O, no clock, no model. §4 of `00-ARCHITECTURE.md`: *"if the output is a number, a route or
a permission, no model produces it."* A lane is a route, and this only reads one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from genios_engine.contracts.reasoning import OUTPUT_LANES, OutputLane

#: ⛔ The label for a card whose signal carries no lane. A WORD, not `None`, because every reader
#: downstream — a count, a filter, a group-by — treats a missing key differently from a present one,
#: and "nobody routed this" must survive all three the same way.
UNROUTED = "unrouted"

#: What the CARD says, per lane. The reader's words, not the engine's: `OutputLane`'s own docstrings
#: explain each lane to an engineer, and a founder reading a card is not the same audience.
#:
#: ⛔ Closed and total against `OUTPUT_LANES` at import time (see below). A lane with no copy would
#: render as a bare enum value on a surface a founder reads.
LANE_COPY: dict[str, str] = {
    OutputLane.DECISION.value:
        "a decision — GeniOS has a move and the standing to assert it",
    OutputLane.INVESTIGATION.value:
        "an investigation — something is missing, and naming it is the point of this card",
    OutputLane.CONFLICT.value:
        "a conflict — two sources disagree, and that is settled by a ruling, not by more evidence",
    OutputLane.MONITOR.value:
        "watch this — real, and not yet certain enough to act on",
    OutputLane.SUPPRESS.value:
        "recorded, not recommended — GeniOS deliberately has nothing for you to do here",
    UNROUTED:
        "unrouted — nothing decided which kind of output this is, so it is shown as it arrived",
}

# ⛔ TOTALITY, BOTH DIRECTIONS, AT IMPORT TIME. The same guard `claim_state` and `output_lane` use.
# One direction alone is half a check: every lane must have copy, AND every key must be a real lane,
# or a typo becomes a label no card can ever reach.
_missing = set(OUTPUT_LANES) - set(LANE_COPY)
if _missing:                                                      # pragma: no cover - import guard
    raise RuntimeError(f"lanes with no card copy: {sorted(_missing)}")
_unknown = set(LANE_COPY) - set(OUTPUT_LANES) - {UNROUTED}
if _unknown:                                                      # pragma: no cover - import guard
    raise RuntimeError(f"card copy for things that are not lanes: {sorted(_unknown)}")
del _missing, _unknown


@dataclass(frozen=True, slots=True)
class LaneOnCard:
    """What one card carries about its own lane: the value, the label, and why it was routed there."""

    #: The lane's own value, or `UNROUTED`. Never `None` — see the module docstring.
    lane: str
    #: The founder-facing sentence from `LANE_COPY`.
    label: str
    #: The router's recorded reason, verbatim. `None` when there was no routing to explain.
    reason: str | None

    @property
    def routed(self) -> bool:
        return self.lane != UNROUTED

    @property
    def suppressed(self) -> bool:
        """⛔ A QUESTION, NEVER AN ACTION. Nothing in this package acts on the answer yet, on
        purpose. Exposed so the eventual gate reads one definition rather than re-deriving it, and
        so a test can prove a suppressed card is still counted."""
        return self.lane == OutputLane.SUPPRESS.value


def describe(output_lane: Any, lane_reason: Any = None) -> LaneOnCard:
    """Read a signal row's two columns into what the card shows. Total over any input.

    An unrecognised value is treated as `UNROUTED` rather than raised on: a card is a read of a row
    somebody else wrote, and refusing to render one because a writer used a word we do not know
    would lose the card entirely. The unknown value is not silently kept either — it would claim a
    lane's authority under a name nothing can group by.
    """
    # ⛔ AN `OutputLane` MEMBER, NOT ONLY ITS STRING. A caller holding the enum is the most
    # natural caller there is, and `str()` on a `(str, Enum)` member yields
    # "OutputLane.DECISION" — which is in no vocabulary, so every in-process caller would
    # have been labelled `unrouted`. Found by a test that passed the members themselves; the
    # database path (plain text) would have kept working and hidden it indefinitely.
    value = str(getattr(output_lane, "value", output_lane) or "").strip()
    if value not in OUTPUT_LANES:
        # ⛔ Do NOT carry the reason of a lane we refused to honour. A reason explaining a route we
        # did not accept reads on the card as though we had.
        return LaneOnCard(lane=UNROUTED, label=LANE_COPY[UNROUTED], reason=None)
    reason = str(lane_reason).strip() if lane_reason is not None else ""
    if not reason:
        # ⛔ HALF A PAIR IS NOT HALF A ROUTE — IT IS NO ROUTE. `0189` makes the pair atomic in the
        # database (`signals_lane_has_a_reason`) precisely because *"a card in the wrong lane with
        # no recorded reason is undiagnosable"*. A caller that hands us a lane without one is
        # therefore handing us something the writer was not allowed to write, and honouring it here
        # would both display an unexplainable lane and violate `cards_lane_has_a_reason` on the way
        # in — a constraint error at write time for a value we could have refused at read time.
        return LaneOnCard(lane=UNROUTED, label=LANE_COPY[UNROUTED], reason=None)
    return LaneOnCard(lane=value, label=LANE_COPY[value], reason=reason)


#: The per-lane tally keys, declared so a reader can prove the counts sum to the pass rather than
#: trusting that they do — `lane_recall.recall_verdict` does exactly that.
#:
#: ⛔ `cards_output_lane_*`, NOT `cards_lane_*`. `deliver/pipeline` already writes a key
#: called `cards_lane`, and it means something else entirely — which CODE PATH built the
#: card, `"situation"` or `"signal"`. Two nearly identical prefixes over two unrelated
#: vocabularies is how somebody later reads a path name as a lane name and reports the
#: wrong number with total confidence.
TALLY_KEYS: frozenset[str] = frozenset(f"cards_output_lane_{name}" for name in LANE_COPY)


def tally_lane(counts: MutableMapping[str, Any], *, lane: "LaneOnCard | str") -> None:
    """One card's lane, counted. ⛔ Including `suppress` and including `unrouted`.

    `card_source` wrote the rule this follows: *"a suppression nobody can see the size of is
    indistinguishable from a bug that lost cards."*

    ⛔ TAKES THE RESOLVED LANE, NEVER THE RAW COLUMN — AND THAT IS NOT A CONVENIENCE. An earlier
    version took `output_lane=` and called `describe(output_lane)` itself, with no reason to hand.
    `describe` treats a lane without its reason as no route at all (the pair is atomic), so every
    routed card was DISPLAYED as `decision` and COUNTED as `unrouted` at the same time — two
    answers to one question, from one card, in one pass. Resolving once and counting the result is
    the only shape in which the label and the tally cannot disagree.
    """
    name = lane.lane if isinstance(lane, LaneOnCard) else str(lane or "").strip()
    key = f"cards_output_lane_{name}"
    if key not in TALLY_KEYS:
        # ⛔ Not silently dropped and not silently invented. A card counted under a key no reader
        # declared is a card missing from every total that matters, which is the shape of loss this
        # whole module exists to prevent.
        key = f"cards_output_lane_{UNROUTED}"
    counts[key] = int(counts.get(key, 0)) + 1


__all__ = ["LANE_COPY", "TALLY_KEYS", "UNROUTED", "LaneOnCard", "describe", "tally_lane"]
