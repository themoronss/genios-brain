"""L1.5.x-U1 · CLAIM DIRECTNESS — did the writer witness this, or are they relaying it?

*"I heard Acme is leaving"* and *"Acme is leaving, I spoke to their CFO"* come from the same person,
in the same email, and were **indistinguishable** in this layer. ALG-14 ranks the ARTIFACT — an
email is an email — so both took `EMAIL_PROSE`, and hearsay from a senior actor outranked a
first-hand account from a junior one.

That is backwards, and it is how a rumour becomes a card. `validate/confidence.py` names the
failure in its own words: *"five sources all repeating one weak recollection of a contract value,
composed upward into an 8900 that nothing in the corpus supports... it looks exactly like rigour."*
Directness is the axis that stops the repetition counting.

⛔ **DERIVED, NOT ASKED FOR — and the cost check is what decided that.** Step 9's plan said the
extractor should PROPOSE directness with a span. Asking the model means a closed set in
`semantic/vocabulary._SETS`, which moves `vocabulary_fingerprint()`, which is a component of the
`l1_extraction_results` cache key: **the whole corpus re-extracts, a third full bill after step
4's.** Changing the prompt WITHOUT moving the key is worse still — every cached row then answers a
question it was never asked, which is the recorded *"260 cached extractions survived a prompt fix
and the numbers did not move."*

Deriving it is also simply better:

* **doctrine 1** — hearsay is a property of the WORDS, not a judgement. *"I heard"* is in the text
  or it is not, and a deterministic recogniser cannot hallucinate one;
* **the receipt is free** — the marker sits inside the span the claim already carries, so the
  evidence for *"this is hearsay"* is the quote itself. A model proposing it would need a SECOND
  span to justify the first.

**THE WEAKEST READING PRESENT WINS.** *"I heard they signed, but I confirmed it with their CFO"*
reads REPORTED, not FIRSTHAND. Taking the stronger half would let one hedged clause launder a
rumour into a witnessed fact, which is the whole thing this exists to prevent.

**ABSENCE IS `unknown`, NEVER `firsthand`.** Most business writing states a fact flatly — *"the
renewal is confirmed"* — and reading that as witnessed would make the DEFAULT the strongest value.
That is the one direction this axis may never fail in, and it is also what every extraction already
in storage will report.

PURE: no clock, no I/O, no model.
"""
from __future__ import annotations

import re
from enum import Enum


class Directness(str, Enum):
    """How close the writer was to the thing they are asserting.

    A SEPARATE AXIS FROM ALG-14's AUTHORITY LADDER, and never folded into it (E3). *"What kind of
    artifact is this"* and *"did the writer witness it"* are two questions, and one table answering
    both answers neither.
    """

    #: The writer names their own contact with the fact — they saw it, said it, or were there.
    FIRSTHAND = "firsthand"
    #: The writer is relaying somebody else's account of something that HAPPENED.
    REPORTED = "reported"
    #: The writer is guessing about something that has NOT happened. Separate from `reported`
    #: because a guess is not somebody's account — folding the two would let a guess corroborate
    #: a witness.
    SPECULATIVE = "speculative"
    #: Not stated, and not guessed at. The default, and what every stored extraction reports.
    UNKNOWN = "unknown"


#: Somebody else told the writer. Phrases people actually write, not a thesaurus expansion — a
#: recogniser tuned on invented sentences matches invented sentences.
_REPORTED = re.compile(
    r"\b(i\s+(?:heard|was\s+told|gather|understand)"
    r"|(?:some|any)one\s+(?:said|told|mentioned)"
    r"|(?:they|he|she|people)\s+(?:say|said|tell|told)\s+me"
    r"|word\s+(?:is|has\s+it)|rumou?r(?:\s+has\s+it|\s+is)?"
    r"|apparently|reportedly|supposedly|allegedly"
    r"|according\s+to|second[-\s]?hand)\b", re.I)

#: The writer is guessing. CHECKED FIRST — see `read_directness`.
_SPECULATIVE = re.compile(
    r"\b(i\s+(?:think|believe|suspect|reckon|assume|expect)"
    r"|my\s+(?:guess|sense|hunch)\s+is"
    r"|(?:might|may|could|would)\s+(?:be|have|leave|switch|move|slip|go)"
    r"|it\s+seems|seems?\s+like|looks?\s+like"
    r"|probably|possibly|perhaps|maybe|likely|unclear\s+(?:if|whether))\b", re.I)

#: The writer was there. Deliberately NARROW: it must name the writer's own contact with the fact,
#: because this is the only value that can RAISE a composition and a loose pattern here is the one
#: mistake with an upside for a wrong answer.
_FIRSTHAND = re.compile(
    r"\b(i\s+(?:spoke|talked|met|saw|read|confirmed|checked|verified|attended|called)"
    r"|we\s+(?:spoke|agreed|met|signed|discussed|confirmed)"
    r"|(?:on|during)\s+(?:the|our)\s+call"
    r"|in\s+(?:the|our)\s+meeting"
    r"|i\s+have\s+(?:the|a)\s+(?:signed|countersigned|executed))\b", re.I)


def read_directness(text: str | None) -> Directness:
    """Read a claim's directness off its own words.

    **THE ORDER IS THE RULE, and it is the weakest reading first.** A sentence carrying two markers
    is read at the lower one:

        "I heard they might be leaving"                       → SPECULATIVE
        "I heard they signed, but I confirmed it with the CFO" → REPORTED

    Taking the stronger half in either case would let one clause launder a weak claim into a strong
    one. That is the failure the whole axis exists to prevent, so the precedence runs
    SPECULATIVE → REPORTED → FIRSTHAND and stops at the first match.

    Anything with no marker is `UNKNOWN` — never `FIRSTHAND`. Most business prose states facts
    flatly, and reading a flat statement as witnessed would make the default the strongest value.
    """
    if not text or not text.strip():
        return Directness.UNKNOWN
    if _SPECULATIVE.search(text):
        return Directness.SPECULATIVE
    if _REPORTED.search(text):
        return Directness.REPORTED
    if _FIRSTHAND.search(text):
        return Directness.FIRSTHAND
    return Directness.UNKNOWN


#: How much each reading is worth as a MULTIPLIER on a source's confidence, in basis points.
#:
#: `FIRSTHAND` IS 10000 — A WITNESS IS NOT PROMOTED, EVERYTHING ELSE IS DISCOUNTED. That direction
#: matters: a multiplier above 10000 would let this axis RAISE a confidence, and Rule 11 says a
#: layer may only raise by adding independent evidence and naming it. Directness names no new
#: evidence — it reads the words already there — so it may only lower.
#:
#: `UNKNOWN` IS NEUTRAL — 10000, the same as `FIRSTHAND` — and that was a CORRECTION, made
#: 2026-09-24 after the existing suite refused the first version.
#:
#: It was 9000 for half an hour, on the reasoning that an unstated directness should "compose
#: conservatively" (E5). **Eight existing tests in `test_confidence.py` went red**, and they were
#: right: every caller in the tree passes the default, so a 9000 multiplier silently discounts
#: EVERY composition in the system by ten percent on the day this ships.
#:
#: The distinction the failure forced, and it is the correct one:
#:
#:   conservative   does not INFLATE on no evidence.       10000 is conservative.
#:   punitive       DEDUCTS on no evidence.                9000 is punitive.
#:
#: This axis lowers a value only on POSITIVE EVIDENCE of hearsay or speculation — a marker that
#: is in the words or is not. `unknown` means no marker was found, which is no evidence either
#: way, and discounting on an absence of evidence is punishing silence. This layer refuses that
#: everywhere else (`unknown` is a real answer, never a worse one), and the composed value of
#: every stored claim is exactly where it would cost the most.
#:
#: The step's T2 still holds and is what the axis is for: a CEO's hearsay (7000) composes below
#: the same CEO's first-hand claim (10000).
DIRECTNESS_MULTIPLIER_BP: dict[Directness, int] = {
    Directness.FIRSTHAND: 10_000,
    Directness.UNKNOWN: 10_000,
    Directness.REPORTED: 7_000,
    Directness.SPECULATIVE: 5_000,
}


def directness_multiplier_bp(directness: Directness) -> int:
    """The multiplier for one reading. Never above 10000 — see the table's note on Rule 11."""
    return DIRECTNESS_MULTIPLIER_BP[directness]


__all__ = ["DIRECTNESS_MULTIPLIER_BP", "Directness", "directness_multiplier_bp",
           "read_directness"]
