r"""L5 · the claim extractor — a fact and a guess must not look alike on the same card.

⛔ WHAT WAS WRONG. A card's rendered copy is one block of text. Inside it, "They wrote four days
ago", "this deal is at risk" and "you should reply today" are three completely different kinds of
statement — one lifted from a source, one concluded, one an instruction — and the reader is given
no way to tell which is which. The validator one file over asks a question about the whole
paragraph, so a paragraph in which every number is grounded passes even when its central assertion
is a guess wearing a fact's grammar.

⛔ THE VOCABULARY ALREADY EXISTS, AND THIS DOES NOT ADD A SECOND ONE. `contracts/claim_state.py`
defines `OBSERVED / INFERRED / HYPOTHESISED / ENVELOPE`, with `_MODEL_MAY_WRITE` deciding who may
propose which. It classifies FIELDS; this classifies SENTENCES. Two spellings of one idea disagree
the first time one is extended — `FEATURE_CARDS_FROM_SITUATIONS` cost this package exactly that,
and `card_source` carries the note: *"Two spellings of one name is how that happens; there is now
one."*

⛔ NO MODEL. §4 of `00-ARCHITECTURE.md`: *"if the output is a number, a route or a permission, no
model produces it."* A claim tag is a classification that decides what the validator will demand of
a sentence, which makes it a permission. It is computed from the sentence and the grounded corpus.

⛔ AND THIS IS NOT A BLUNT GREP. The family rule is *"assert on structure — the AST, the column
list — never on text that happens to sit near a thing."* It forbids inferring a fact about CODE
from words near it. Here the text IS the subject: a sentence's hedging is what makes it a
hypothesis, not a proxy for something else. Applying the rule here would forbid the only honest
method there is.

PURE. No I/O, no clock.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from genios_engine.contracts.claim_state import ClaimState
from genios_engine.deliver.render import _digit_runs, _fold, _haystack, _proper_nouns

#: Words that mark a sentence as proposed rather than concluded. ⛔ `claim_state` requires this
#: distinction to survive to the surface: a hypothesis is *"never rendered as fact"*, and the only
#: thing that stops a sentence reading as fact is its own wording.
#:
#: Whole words, matched with boundaries. A substring match makes "maybe" out of "dismayed".
HEDGES: frozenset[str] = frozenset({
    "likely", "unlikely", "may", "might", "could", "probably", "possibly", "perhaps",
    "appears", "appear", "seems", "seem", "suggests", "suggest", "suggesting",
    "estimated", "estimate", "approximately", "roughly", "around", "about",
    "expect", "expects", "expected", "assume", "assumes", "assumed", "presumably",
    "potentially", "risk of", "signals that", "indicates", "indicating",
})

#: Verbs that make a sentence an INSTRUCTION. An instruction asserts nothing about the world, so it
#: is not a claim at all — which is exactly what `ENVELOPE` is for, and why `claim_state` put a
#: not-a-claim member inside the claim enum: *"so that 'not a claim' never means 'nobody
#: classified it'."*
_IMPERATIVE_OPENERS: frozenset[str] = frozenset({
    "send", "reply", "call", "email", "draft", "ask", "confirm", "follow", "schedule",
    "check", "review", "share", "forward", "remind", "chase", "close", "book", "tell",
    "let", "consider", "offer", "propose", "suggest", "push", "move", "set", "add",
})

#: ⛔ A sentence ends at `.`, `?`, `!` or a newline — NOT at every period. "4.5x" and "nikhil@a.im"
#: carry interior dots, and splitting on them would cut a grounded number in half and then report
#: both halves as ungrounded inventions. Requires whitespace or end-of-string after the mark.
_SENTENCE = re.compile(r"(?<=[.!?])(?=\s)|\n+")

_WORD = re.compile(r"[a-z][a-z']*")


@dataclass(frozen=True, slots=True)
class Claim:
    """One sentence of rendered copy, and what kind of statement it is."""

    text: str
    state: ClaimState
    #: Why it was tagged that way. ⛔ Recorded for the same reason `LaneChoice.reason` is: a claim
    #: in the wrong state with no record of why is undiagnosable, and this decides what the
    #: validator will demand of the sentence.
    reason: str
    #: The tokens this sentence asserts that the corpus does not hold. Empty for a grounded
    #: sentence. Carried rather than recomputed so the validator refuses on the same evidence the
    #: classifier used — two readings of one sentence is how a card passes one check and fails the
    #: other for reasons neither reports.
    ungrounded: tuple[str, ...] = ()

    @property
    def asserts_about_the_world(self) -> bool:
        """False for an instruction or a question. `ENVELOPE` is not a claim — by definition."""
        return self.state is not ClaimState.ENVELOPE


def split_sentences(text: str) -> tuple[str, ...]:
    """Rendered copy into sentences. Empty in, empty out."""
    return tuple(part.strip() for part in _SENTENCE.split(text or "") if part.strip())


def _is_instruction(sentence: str) -> bool:
    """An imperative or a question: it tells the reader to do something or asks them something.

    Both assert nothing about the world, which is what makes them `ENVELOPE` rather than a claim
    that happens to be unverifiable.
    """
    if sentence.rstrip().endswith("?"):
        return True
    first = _WORD.match(sentence.strip().lower())
    return bool(first) and first.group(0) in _IMPERATIVE_OPENERS


def _hedged(sentence: str) -> str | None:
    """The hedge that makes this sentence a proposal, or None. Whole words only."""
    low = sentence.lower()
    for hedge in sorted(HEDGES, key=len, reverse=True):
        if re.search(rf"(?<![a-z]){re.escape(hedge)}(?![a-z])", low):
            return hedge
    return None


def _ungrounded_tokens(sentence: str, corpus_text: str, corpus_nums: set[str]) -> tuple[str, ...]:
    """What this sentence asserts that the corpus does not hold.

    ⛔ THE SAME TWO CHECKS `invention_ok` RUNS, AND DELIBERATELY ITS OWN HELPERS. Reimplementing
    `_digit_runs`, `_fold`, `_haystack` or `_proper_nouns` here would give the card two different
    answers to "is this number in the corpus" the first time one of them was improved — and the
    folding rules in `render.py` exist because of specific measured failures (`V-02:name:Sofa`
    against a graph holding "Sofía Padrón"). Importing them is what keeps the two in step.
    """
    out: list[str] = []
    for num in _digit_runs(sentence):
        if num not in corpus_nums and num not in corpus_text:
            out.append(f"number:{num}")
    folded = _haystack(_fold(corpus_text))
    for name in _proper_nouns(sentence):
        if name.lower() not in folded:
            out.append(f"name:{name}")
    return tuple(out)


def classify(sentence: str, *, corpus_text: str = "", corpus_nums: set[str] | None = None,
             quotes_something: bool = False) -> Claim:
    """One sentence, one `ClaimState`. Total: every sentence gets exactly one, first match wins.

    THE PRECEDENCE, AND WHY IT IS THIS ORDER.

      1. An INSTRUCTION or a QUESTION is `ENVELOPE` before anything else is asked. "Send the deck
         today" contains no assertion to ground, and running it through the evidence rules would
         either refuse a correct instruction or, worse, pass it and record that an instruction was
         *observed* — which would then let the validator demand a citation for a sentence that
         never claimed anything.

      2. ⛔ A HEDGE OUTRANKS GROUNDING. A sentence may be perfectly grounded and still be a
         proposal: "They will probably churn" invents no number and no name, and it is not an
         observation. Letting grounding win here is precisely how a guess acquires a fact's
         authority, which is the failure `claim_state` names when it says a hypothesis is *"never
         rendered as fact"*.

      3. Grounded AND quoting is `OBSERVED` — the strongest thing a card can say, and the only
         state `_MODEL_MAY_WRITE` refuses to a model. Grounded without a quote is `INFERRED`: the
         parts are real, the sentence assembling them is ours.

      4. Anything ungrounded is `INFERRED` and carries WHAT was ungrounded. ⛔ Not `HYPOTHESISED`:
         an unhedged sentence asserting an invented number is not a modest proposal, it is a false
         claim, and tagging it as a hypothesis would let it pass a check designed to be lenient
         with hypotheses. The validator refuses it on the `ungrounded` list.
    """
    sentence = sentence.strip()
    if _is_instruction(sentence):
        return Claim(sentence, ClaimState.ENVELOPE,
                     "an instruction or a question — it asserts nothing about the world")

    hedge = _hedged(sentence)
    ungrounded = _ungrounded_tokens(sentence, corpus_text, corpus_nums or set())

    if hedge is not None:
        return Claim(sentence, ClaimState.HYPOTHESISED,
                     f"hedged on '{hedge}' — proposed, not concluded", ungrounded)
    if ungrounded:
        return Claim(sentence, ClaimState.INFERRED,
                     "asserts something the grounded corpus does not hold", ungrounded)
    if quotes_something:
        return Claim(sentence, ClaimState.OBSERVED,
                     "every number and name is in the corpus, and the card quotes a source")
    return Claim(sentence, ClaimState.INFERRED,
                 "grounded in the corpus, but no source states it outright")


def extract(text: str, *, corpus_text: str = "", corpus_nums: set[str] | None = None,
            quotes_something: bool = False) -> tuple[Claim, ...]:
    """Rendered copy into tagged claims, in the order the reader meets them."""
    return tuple(classify(s, corpus_text=corpus_text, corpus_nums=corpus_nums,
                          quotes_something=quotes_something)
                 for s in split_sentences(text))


def by_state(claims: tuple[Claim, ...]) -> dict[str, int]:
    """The mix, with every state declared — including the states that did not occur.

    A key that appears only when it fires is a key nobody knows exists; `pipeline` prints its zeros
    for the same reason.
    """
    counts = {state.value: 0 for state in ClaimState}
    for claim in claims:
        counts[claim.state.value] += 1
    return counts


__all__ = ["HEDGES", "Claim", "by_state", "classify", "extract", "split_sentences"]
