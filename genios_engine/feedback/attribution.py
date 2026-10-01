r"""L6 · the router — a founder's "this was wrong" becomes a layer to go and look at.

⛔ THIS UNIT WAS NARROWED, AND THE REASON IS A CORRECTION TO THE PLAN. `tree.yaml`'s `M14.C1.U03`
reads *"the router — reason to layer to the thing that changes, and `bad_timing` reaches L5 timing
rather than the rule's precision."* **The second clause is already true in three independent
places:**

    calibrate.TAXONOMY["wrong:bad_timing"]  ->  {"label": "timing", "precision": "none"}
    feedback/units.py:135                   ->  judged = acted + wrong   # bad_timing does not
                                                                         # grade accuracy
    calibrate._PRECISION_SQL                ->  in ('not_relevant','wrong_facts')

and `packs/brains/adaptive_lease.py` documents the same rule from the consuming side. Building it
would have meant building it twice. What is genuinely absent is the LAYER attribution: nothing in
`feedback/` names a layer at all.

⛔ SO THIS FILE DOES TWO THINGS, AND THE SECOND IS THE MORE VALUABLE ONE. It routes a judgment to a
layer, and it GUARDS the property that already works — because a property enforced in three places
can be broken in three places, and none of them currently fails a build if it is.

⛔ A DEBIT IS A DIRECTION TO LOOK, NEVER A WEIGHT. L6 already changes exactly one thing — a rule's
precision offset, bounded by `calibrate.OFFSET_BOUND = 15` so learning cannot run away. An
attribution deliberately changes nothing. Wiring it to a weight would let one founder's
misclassification retune a whole layer, and a founder classifying OUR failure for us is the least
reliable input in the system: presented with eleven options they will pick the first plausible one.
What this produces is a ranked answer to *"where is this tenant's pipeline actually failing?"* —
the question `0188`'s funnel counters were built to ask and currently answer only by volume.

⛔ AND AN UNKNOWN REASON IS COUNTED, NEVER DROPPED AND NEVER DEFAULTED. A judgment row is written by
a client. Filing an unrecognised word against a layer nobody chose would produce a confident number
pointing at the wrong team; dropping it would make a client sending garbage indistinguishable from a
quiet week. `card_source` states the rule one layer over: *"a suppression nobody can see the size of
is indistinguishable from a bug that lost cards."*

PURE. No I/O, no clock, no model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from genios_engine.contracts.learning_attribution import (ATTRIBUTION, PrecisionRole, WrongReason,
                                                          attribute)

#: The key an unrecognised reason is counted under. ⛔ A WORD, not a dropped row: see the module
#: docstring. Distinct from any layer name so it can never be read as a debit.
UNATTRIBUTED = "unattributed"


@dataclass(frozen=True, slots=True)
class LayerDebit:
    """One layer, how often it was named, and what its owners should go and do."""

    layer: str
    layer_number: int
    debits: int
    #: The distinct fixes named, in the order the reasons are declared. Deduplicated, because one
    #: sentence repeated forty times is one thing to do, not forty.
    fixes: tuple[str, ...]
    #: ⛔ How many of those debits actually count against a rule's precision. Carried SEPARATELY
    #: from `debits` because they answer different questions: "which layer is failing" and "which
    #: rule should get quieter" have different answers, and a single number cannot give both.
    accuracy_debits: int = 0

    @property
    def timing_or_fit_debits(self) -> int:
        """The debits that say the card was RIGHT and something else about it was not."""
        return self.debits - self.accuracy_debits


@dataclass(frozen=True, slots=True)
class AttributionReport:
    """Where a tenant's pipeline is failing, in the order somebody should look."""

    by_layer: tuple[LayerDebit, ...]
    #: ⛔ Reasons no vocabulary knows, counted. Not an error and not zero — a number.
    unattributed: int = 0
    #: Judgments that were not `wrong` at all (a click, a snooze). Counted so the totals close.
    not_a_complaint: int = 0

    @property
    def total(self) -> int:
        return sum(d.debits for d in self.by_layer) + self.unattributed + self.not_a_complaint

    @property
    def worst(self) -> LayerDebit | None:
        """The layer named most often. `None` when nothing was named — which is an answer."""
        return self.by_layer[0] if self.by_layer else None

    def explain(self) -> str:
        if not self.by_layer:
            base = "no layer was named"
        else:
            worst = self.by_layer[0]
            base = (f"{worst.layer} (L{worst.layer_number}) named {worst.debits} times — "
                    f"{worst.fixes[0]}")
        if self.unattributed:
            # ⛔ SAID OUT LOUD. An unrecognised reason means a client and this vocabulary disagree,
            # which is the `FEATURE_CARDS_FROM_SITUATIONS` failure — "the reader was looking for a
            # word the writer rejected" — and it is invisible unless the report says so.
            base += f"; {self.unattributed} judgment(s) used a reason this build does not know"
        return base


def route(judgments: Iterable[Mapping[str, object]]) -> AttributionReport:
    """Judgment rows to a ranked layer report. Total over any input.

    Each row is read for `cause` and `reason`, the pair `correlation_history` already carries whole:
    *"`bad_timing` invites a later retry, `not_relevant` does not."* A row whose cause is not
    `wrong` is counted apart rather than skipped, so the totals close and a report over a quiet
    week is distinguishable from a report that lost rows.

    Ordered by debits descending, then by layer number ascending. ⛔ The tie-break is EARLIEST
    LAYER, not alphabetical: when capture and deliver are named equally often, capture is where to
    look first, because a bad input reaches the reader through every layer after it and fixing the
    last one fixes one symptom.
    """
    counts: dict[str, int] = {}
    accuracy: dict[str, int] = {}
    fixes: dict[str, list[str]] = {}
    unattributed = 0
    not_a_complaint = 0

    for row in judgments:
        if str(row.get("cause") or "") != "wrong":
            not_a_complaint += 1
            continue
        found = attribute(str(row.get("reason") or ""))
        if found is None:
            unattributed += 1
            continue
        counts[found.layer] = counts.get(found.layer, 0) + 1
        if found.precision is PrecisionRole.DENOMINATOR:
            accuracy[found.layer] = accuracy.get(found.layer, 0) + 1
        bucket = fixes.setdefault(found.layer, [])
        if found.fix not in bucket:
            bucket.append(found.fix)

    numbers = {a.layer: a.layer_number for a in ATTRIBUTION.values()}
    ordered = sorted(counts, key=lambda layer: (-counts[layer], numbers[layer]))
    return AttributionReport(
        by_layer=tuple(LayerDebit(layer=layer, layer_number=numbers[layer], debits=counts[layer],
                                  fixes=tuple(fixes[layer]),
                                  accuracy_debits=accuracy.get(layer, 0))
                       for layer in ordered),
        unattributed=unattributed, not_a_complaint=not_a_complaint)


# ── the guard over what already works ─────────────────────────────────────────────────────────

def timing_never_grades_accuracy() -> tuple[str, ...]:
    """⛔ Every reason this map calls a timing-or-fit complaint must be absent from the precision
    denominator, in BOTH vocabularies. Returns the violations; empty is the passing answer.

    THE PROPERTY IS ENFORCED IN THREE PLACES AND GUARDED IN NONE, which is why this exists. The
    check reads `calibrate.TAXONOMY` directly rather than restating its contents: a copy of a rule
    passes forever while the rule drifts.
    """
    from genios_engine.feedback.calibrate import TAXONOMY

    bad: list[str] = []
    for reason, attribution in ATTRIBUTION.items():
        if attribution.precision is not PrecisionRole.NONE:
            continue
        entry = TAXONOMY.get(f"wrong:{reason.value}")
        if entry is None:
            # ⛔ Not a violation. `TAXONOMY` predates this map and holds only the original three;
            # a reason it has never heard of cannot be in its denominator. Reporting it here would
            # make the guard fail on the day the vocabulary widened, which is when the guard is
            # most needed to be trustworthy.
            continue
        if entry.get("precision") != "none":
            bad.append(f"{reason.value}:{entry.get('precision')}")
    return tuple(bad)


def every_legacy_reason_still_grades_the_way_it_did() -> tuple[str, ...]:
    """⛔ The three original reasons must keep their precision roles exactly.

    Every judgment already recorded grades on these words. A change here silently re-scores the
    28-day window — a rule that was fine on Monday gets muted on Tuesday with no event to point at.
    """
    expected = {"not_relevant": PrecisionRole.DENOMINATOR,
                "wrong_facts": PrecisionRole.DENOMINATOR,
                "bad_timing": PrecisionRole.NONE}
    bad: list[str] = []
    for name, role in expected.items():
        actual = ATTRIBUTION[WrongReason(name)].precision
        if actual is not role:
            bad.append(f"{name}: {actual.value}, was {role.value}")
    return tuple(bad)


__all__ = ["UNATTRIBUTED", "AttributionReport", "LayerDebit",
           "every_legacy_reason_still_grades_the_way_it_did", "route",
           "timing_never_grades_accuracy"]
