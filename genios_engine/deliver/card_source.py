"""L2-7 · where a card came from — a situation, or a signal whose situation never formed.

⛔ **THE RECALL GUARD, AND IT IS THE UNIT THAT DECIDES WHETHER FEWER CARDS IS A MERGE OR A LOSS.**

`deliver/pipeline` loops over SIGNALS, and signals are emitted per (pack, rule, node), so one
situation that fires three rules becomes three cards. Collapsing them means grouping by
`signals.situation_id` — and the moment a card REQUIRES a situation, a correlator gap becomes a
silent disappearance. That is the exact failure L2-4 exists to end, and this module is what stops
this step from causing it.

**`situation_id IS NULL` is an ANSWER, not a gap.** A signal written before migration 0182, and a
signal whose situation never formed, both read NULL — and both still reach the founder, **marked**
and **counted**. The step says it in one line: *"fewer cards must come from merging, never from
dropping."*

COUNTED, NEVER SILENT — the idiom `_cohort_absorbed` already uses one file over: *"a suppression
nobody can see the size of is indistinguishable from a bug that lost cards."*

PURE. No I/O, no clock. It classifies, labels and tallies; the pipeline reads rows.
"""
from __future__ import annotations

from enum import Enum

from genios_engine.platform.l4_activation import FEATURE_CARDS_FROM_SITUATIONS
from typing import Any, MutableMapping


class CardSource(str, Enum):
    """Two, and closed. A third kind of provenance is a third thing a founder must learn."""

    #: Built from an admitted situation — what Layer 2 concluded.
    SITUATION = "situation"
    #: A signal whose situation never formed. Surfaced anyway, and SAID so.
    UNINTERPRETED = "uninterpreted"

    @property
    def label(self) -> str:
        """⛔ What the CARD says, not what a dashboard counts.

        A number on a dashboard is not a label on a card. The founder has to be able to tell an
        interpretation from a raw measurement, or the two become one undifferentiated feed and
        the interpretation is worth nothing.
        """
        return {
            CardSource.SITUATION: "from a situation GeniOS assembled",
            CardSource.UNINTERPRETED: (
                "uninterpreted — this is a measurement, not a conclusion. No situation formed "
                "around it, so nothing has read it against your domain's doctrine"),
        }[self]


def classify(*, situation_id: Any) -> CardSource:
    """NULL is UNINTERPRETED, never missing."""
    return CardSource.SITUATION if str(situation_id or "").strip() else CardSource.UNINTERPRETED


#: ⛔ The keys both paths are compared on, on ONE sweep, before either is retired — criterion 5.
#: Declared as a set so a path that stops reporting one of them is a path that stopped being
#: comparable, rather than a path that looks like it improved.
COMPARISON_KEYS: frozenset[str] = frozenset({
    "cards_from_situation",      # the new path: one card per situation
    "cards_uninterpreted",       # the recall guard: surfaced, labelled, not lost
    "cards_from_signal",         # the old path: one card per signal
})

#: The per-tenant activation name. A row, not a boolean.
#:
#: ⛔ IMPORTED, NOT SPELT AGAIN. This module held the string as a literal and
#: `platform/l4_activation.L4_FEATURES` did not contain it, so `require_feature` refused the name
#: and the lane below could never be switched on for any tenant — the reader was looking for a
#: word the writer rejected. Two spellings of one name is how that happens; there is now one.
FEATURE = FEATURE_CARDS_FROM_SITUATIONS


def tally_source(counts: MutableMapping[str, Any], *, situation_id: Any) -> None:
    """One card's provenance, counted. Both keys always move, so they sum to the pass."""
    source = classify(situation_id=situation_id)
    key = ("cards_from_situation" if source is CardSource.SITUATION else "cards_uninterpreted")
    counts[key] = int(counts.get(key, 0)) + 1


def cards_from_situations(*, activated: frozenset[str] | set[str] | None) -> bool:
    """⛔ PER TENANT, AND OFF UNTIL A ROW SAYS OTHERWISE.

    `live_lane` recorded what the alternative costs: *"`forced` is one boolean for every tenant at
    once… it only ever turns lanes ON: switching it off does not take an activated tenant off the
    live lane."* The way back has to be deleting a row, not unsetting a flag.
    """
    return FEATURE in (activated or frozenset())


__all__ = ["COMPARISON_KEYS", "FEATURE", "CardSource", "cards_from_situations", "classify",
           "tally_source"]
