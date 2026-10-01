r"""L6 · attribution — a wrong card names the layer that failed.

⛔ WHAT WAS MISSING. `grep -rn "layer" genios_engine/feedback/` returns seven hits and every one is
prose in a comment about the import topology. There is no reason-to-layer map, no layer counter, no
layer column. `M14` ships *"a wrong card debits the layer that failed"*; nothing could express it.

⛔ AND THREE REASONS CANNOT EXPRESS IT EITHER. Today a founder may say `not_relevant`, `wrong_facts`
or `bad_timing`. `wrong_facts` alone covers a mis-read email (capture), a fact linked to the wrong
company (context) and a stale value nobody refreshed (capture again) — three different teams, one
word. `feedback/calibrate.TAXONOMY` already routes each reason to a CONSEQUENCE (numerator /
denominator / none); what no map says is **which layer to go and look at**.

⛔ A NEW FILE, AND NOT AN ADDITION TO `contracts/learning.py`. `M14.C1.U01` names that file as its
artifact. It holds `LearningObject` v2, which is content-addressed and round-trip verified: adding a
member to an enum it validates against would change identities already minted. This map hashes
nothing and is purely additive. The departure from the unit's stated artifact is deliberate and the
reason is the hash.

⛔ ONE LAYER PER REASON, AND EXACTLY ONE. A reason that debits two layers debits neither — the next
person to read the number cannot act on it. Where a reason genuinely spans two, the reason is drawn
wrongly and is split instead, which is what having eleven rather than three is FOR.

⛔ THE LAYER NAMES ARE PLAIN STRINGS HERE, AND THE CHECK AGAINST `LAYERS.py` LIVES IN A TEST — AND
THAT IS A CORRECTION. The first version of this module imported `genios_engine.LAYERS` so the guard
could run at import time, and `tests/test_layer_topology.py::test_contracts_import_nothing_above_platform`
failed the build on it: *"contracts/ is the boundary vocabulary — it may depend on platform/stdlib
only."* The gate was right. `contracts/` is what every layer imports, so a dependency added here is a
dependency added everywhere, and `LAYERS.py` exists to be read by the topology TEST, not by shipped
code — nothing else in `genios_engine/` imports it.

So the consistency requirement stands and moves: `DEBITABLE_LAYERS` below is this module's own list,
and `tests/feedback/test_the_right_layer_is_debited.py` asserts it against `LAYERS.py`. A test is a
weaker place than an import guard, and it is the strongest place available without making the boundary
vocabulary depend on the topology it describes.

⛔ AND THE DEBIT IS A DIRECTION TO LOOK, NEVER A WEIGHT. L6 already changes one thing — a rule's
precision, bounded by `calibrate.OFFSET_BOUND = 15`. Wiring an attribution to a weight would let one
founder's misclassification retune a whole layer. See `feedback/attribution.py`.

PURE. No I/O, no clock, no model. §4 of `00-ARCHITECTURE.md`: *"if the output is a number, a route or
a permission, no model produces it"* — an attribution is a route.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

#: ⛔ The packages a founder's complaint may point at. Kept HERE as strings rather than imported
#: from `LAYERS.py` — see the module docstring — and asserted against it by a test.
#:
#: `feedback` IS DELIBERATELY ABSENT, and that is the point of the layer. L6 is what READS these
#: debits; a reason attributing failure to the learner would have the learner grade itself. If
#: learning is wrong, that shows up as every other layer's debits being wrong at once, which is a
#: different investigation and not a button on a card.
DEBITABLE_LAYERS: frozenset[str] = frozenset({
    "capture", "context", "packs", "reason", "executive", "deliver"})

#: The layer number, for ORDERING A REPORT only. ⛔ `LAYERS.py` warns why the digit is never the
#: identity: *"Atlas 5.2 is our `deliver` (6) and Atlas 6 is our `feedback` (7) — so always name the
#: package, never the digit alone."* A test asserts every number here matches `LAYERS.py`.
LAYER_ORDER: dict[str, int] = {"capture": 1, "context": 2, "packs": 3, "reason": 4,
                               "executive": 5, "deliver": 6}


class WrongReason(str, Enum):
    """Why a card was wrong. ⛔ Eleven, closed, and every one names a different thing to fix.

    THE THREE THAT ALREADY EXIST KEEP THEIR EXACT SPELLINGS. `deliver/actions.WRONG_REASONS`,
    `calibrate.TAXONOMY`, `feedback/units` and `context/correlation_history` all hold them, and
    every judgment already recorded must grade the way it graded — renaming one would silently
    re-score the 28-day window.
    """

    # ── the original three, unchanged ────────────────────────────────────────────────────────
    #: The card should not have existed. The situation was real; telling this person was not.
    NOT_RELEVANT = "not_relevant"
    #: A fact on the card is false. ⛔ KEPT AS THE CATCH-ALL rather than deleted in favour of the
    #: finer reasons below: an existing button whose meaning quietly narrows is worse than one
    #: that stays broad, because every judgment recorded under the old meaning would be re-read
    #: under the new one.
    WRONG_FACTS = "wrong_facts"
    #: Right card, wrong moment. ⛔ NEVER a precision failure — see the module note in
    #: `feedback/attribution.py`. Three places already enforce this and a guard now protects it.
    BAD_TIMING = "bad_timing"

    # ── the eight that name a layer ──────────────────────────────────────────────────────────
    #: A number, name or date was read out of a source incorrectly.
    MISREAD_SOURCE = "misread_source"
    #: The source itself was right and is now out of date — nobody refreshed it.
    STALE_DATA = "stale_data"
    #: The fact is real and belongs to a different company, person or deal.
    WRONG_SUBJECT = "wrong_subject"
    #: Two things were treated as one, or one as two.
    BAD_LINK = "bad_link"
    #: The facts are right and the conclusion drawn from them does not follow.
    BAD_REASONING = "bad_reasoning"
    #: The conclusion is right and this is not how this business does it.
    WRONG_PLAYBOOK = "wrong_playbook"
    #: Right card, wrong person. Somebody else answers for this.
    WRONG_PERSON = "wrong_person"
    #: The card is right and unreadable — the copy does not say what it means.
    BADLY_WRITTEN = "badly_written"


#: Whether this reason grades the recommendation's accuracy.
#:
#: ⛔ THE VOCABULARY IS `calibrate.TAXONOMY`'S, DELIBERATELY: `numerator` / `denominator` / `none`.
#: A second word for the same role is how two maps come to disagree.
class PrecisionRole(str, Enum):
    DENOMINATOR = "denominator"   # counts against the rule: it should not have said this
    NONE = "none"                 # the card was right; something else about it was not


@dataclass(frozen=True, slots=True)
class Attribution:
    """One reason, the one layer it debits, and what a reader should go and do about it."""

    layer: str
    precision: PrecisionRole
    #: What changes, in the words of somebody who would have to change it. Never a module path:
    #: a path goes stale on the next refactor and a sentence does not.
    fix: str

    def __post_init__(self) -> None:
        if self.layer not in DEBITABLE_LAYERS:
            raise ValueError(
                f"{self.layer!r} is not a debitable layer. `feedback` is excluded on purpose: the "
                f"learner must not grade itself")
        if not self.fix.strip():
            raise ValueError("an attribution with no stated fix is a number nobody can act on")

    @property
    def layer_number(self) -> int:
        """⛔ From `LAYERS.py`, never written down here. And note its own warning: Atlas 5.2 is our
        `deliver` (6) and Atlas 6 is our `feedback` (7), so *"always name the package, never the
        digit alone."* The number is for ordering a report; the package is the identity."""
        return LAYER_ORDER[self.layer]

    @property
    def grades_accuracy(self) -> bool:
        return self.precision is PrecisionRole.DENOMINATOR


#: ⛔ ELEVEN REASONS, EXACTLY ONE LAYER EACH. Closed in both directions below.
ATTRIBUTION: MappingProxyType = MappingProxyType({
    # ── capture · what we read out of the customer's systems ──────────────────────────────────
    WrongReason.MISREAD_SOURCE: Attribution(
        "capture", PrecisionRole.DENOMINATOR,
        "the extractor read this field wrongly — fix the extraction, not the rule"),
    WrongReason.STALE_DATA: Attribution(
        "capture", PrecisionRole.NONE,
        "the source was right when we read it and is not now — shorten the refresh window"),
    # ⛔ `STALE_DATA` IS `NONE`, NOT `DENOMINATOR`, AND THAT IS THE SHARPEST CALL IN THIS MAP.
    # The rule concluded correctly from what it was given. Debiting its precision for the age of
    # the input is the same error `_PRECISION_SQL` already refuses on the abstention axis:
    # *"counting that as a precision failure made answering the system's own question evidence the
    # system was wrong."*

    # ── context · assembling facts into a situation ───────────────────────────────────────────
    WrongReason.WRONG_SUBJECT: Attribution(
        "context", PrecisionRole.DENOMINATOR,
        "this fact belongs to a different company or person — fix identity resolution"),
    WrongReason.BAD_LINK: Attribution(
        "context", PrecisionRole.DENOMINATOR,
        "two things were treated as one, or one as two — fix the correlator that joined them"),

    # ── reason · the conclusion drawn ─────────────────────────────────────────────────────────
    WrongReason.BAD_REASONING: Attribution(
        "reason", PrecisionRole.DENOMINATOR,
        "the facts were right and the conclusion does not follow — fix the reasoner"),
    WrongReason.NOT_RELEVANT: Attribution(
        "reason", PrecisionRole.DENOMINATOR,
        "the situation was real and did not warrant telling anybody — raise the rule's threshold"),
    WrongReason.WRONG_FACTS: Attribution(
        "reason", PrecisionRole.DENOMINATOR,
        "a fact on the card is false and the founder did not say which layer lost it — read the "
        "evidence chain before debiting anything narrower"),
    # ⛔ `WRONG_FACTS` LANDS ON `reason` BECAUSE IT IS THE CATCH-ALL, AND THAT IS AN ADMISSION, NOT
    # A FINDING. A founder choosing it has told us a fact is wrong and nothing about where it was
    # lost. Attributing it to `capture` on a guess would produce a confident number pointing at the
    # wrong team — worse than an honest one pointing at the layer that PUBLISHED the claim. The
    # narrower reasons exist so that this one gets picked less often, and `fix` says so out loud.

    # ── packs · what this business's doctrine says to do ──────────────────────────────────────
    WrongReason.WRONG_PLAYBOOK: Attribution(
        "packs", PrecisionRole.NONE,
        "the conclusion is right and this is not how this business does it — fix the expertise"),

    # ── executive · who answers for it ────────────────────────────────────────────────────────
    WrongReason.WRONG_PERSON: Attribution(
        "executive", PrecisionRole.NONE,
        "right card, wrong person — fix the responsibility or the reporting line"),

    # ── deliver · when it arrived and how it read ─────────────────────────────────────────────
    WrongReason.BAD_TIMING: Attribution(
        "deliver", PrecisionRole.NONE,
        "right card, wrong moment — fix the send window, never the rule's precision"),
    WrongReason.BADLY_WRITTEN: Attribution(
        "deliver", PrecisionRole.NONE,
        "the card is right and does not say what it means — fix the copy"),
})

# ⛔ TOTALITY, BOTH DIRECTIONS, AT IMPORT TIME. One direction alone is half a check: every reason
# must have an attribution, AND every attribution must belong to a real reason. A reason with no
# attribution is a button whose click goes nowhere; a key that is not a reason is a row nothing can
# ever reach.
_unattributed = set(WrongReason) - set(ATTRIBUTION)
if _unattributed:                                                 # pragma: no cover - import guard
    raise RuntimeError(f"reasons with no attribution: {sorted(r.value for r in _unattributed)}")
_phantom = set(ATTRIBUTION) - set(WrongReason)
if _phantom:                                                      # pragma: no cover - import guard
    raise RuntimeError(f"attributions for things that are not reasons: {_phantom}")
# ⛔ AND EVERY DEBITED LAYER MUST BE REACHABLE. A layer nothing can debit is a layer this map
# cannot report on, and the fix somebody eventually applies is to widen a reason until it is
# reachable — at which point the widening, not the design, decides who gets blamed.
_unreachable = DEBITABLE_LAYERS - {a.layer for a in ATTRIBUTION.values()}
if _unreachable:                                                  # pragma: no cover - import guard
    raise RuntimeError(f"layers no reason can debit: {sorted(_unreachable)}")
del _unattributed, _phantom, _unreachable

#: The three spellings that existed before this file. ⛔ Held so a test can prove they survived
#: rather than trusting that they did: every judgment already recorded grades on these words.
LEGACY_REASONS: frozenset[str] = frozenset({"not_relevant", "wrong_facts", "bad_timing"})

#: Every reason, as the strings the API and the card exchange.
ALL_REASONS: tuple[str, ...] = tuple(r.value for r in WrongReason)


def attribute(reason: str | WrongReason) -> Attribution | None:
    """The layer this reason debits, or `None` for a word we do not know.

    ⛔ `None`, NOT A RAISE, AND NOT A DEFAULT. A judgment row is written by a client; a reason we do
    not recognise must not crash a calibration pass over a whole tenant, and must not be silently
    filed against a layer nobody chose. `feedback/attribution.py` counts the unknowns.
    """
    try:
        return ATTRIBUTION[WrongReason(getattr(reason, "value", reason))]
    except ValueError:
        return None


def reasons_for_layer(layer: str) -> tuple[str, ...]:
    """Every reason that debits one layer — the list a team owns."""
    return tuple(r.value for r, a in ATTRIBUTION.items() if a.layer == layer)


__all__ = ["ALL_REASONS", "ATTRIBUTION", "DEBITABLE_LAYERS", "LAYER_ORDER",
           "LEGACY_REASONS", "Attribution", "PrecisionRole", "WrongReason", "attribute",
           "reasons_for_layer"]
