"""L2.7.7-U1 step 4b · TWO DETERMINISTIC REFUSALS ALG-08 CANNOT MAKE.

ALG-08 answers exactly one question — *are these words really in this source?* — and it answers
it well. It is silent about two things that decide whether the words mean what the claim says
they mean, and both of them close live threads in real mail:

**WHERE the words are.** A reply carries its own history. `"all sorted, we signed yesterday"` is
genuinely present in a message whose live text reads *"I don't think this ever happened, can you
confirm?"* — it is present in the part someone else wrote three weeks ago. ALG-08 verifies it,
the speaker is our own owner, the band is EXPLICIT_COMPLETION, and the situation closes on a
sentence the sender did not write and was arguing against. This is not an exotic case: quoting
the thread below is the default behaviour of every mail client, so on a real inbox it is the
single most available route to a false close.

**WHETHER THE WORDS ARE NEGATED.** `"we have not signed the MSA yet"` contains the substring
`"signed the MSA"`, and it contains `"we have not signed"` in full. Both verify. Doc 12 case 1
already makes a forward-looking modal a HARD NEGATIVE in deterministic code rather than trusting
the model's band; a negator sitting four words to the left of the quote is the same class of
signal, is cheaper to detect, and is more dangerous, because the sentence it falsifies reads as
a completion report to anything doing substring matching.

WHY HERE AND NOT IN THE PROMPT. Both are already in the prompt — rule 3 asks for a verbatim
quote and rule 4 covers irony. The prompt is where we ask; this is where we check. Every guard in
this unit is written on the assumption that the answer came back wrong, because the whole design
of M-4 is *the model describes, the code decides*, and a rule that exists only in the instruction
spine is a rule the code does not have.

BOTH REFUSALS ARE ONE-DIRECTIONAL, and that is the point. They can turn a close into a rejection
and they can never turn a rejection into a close, so the worst thing either can cost is one
unnecessary nudge — the cheap error, by doc 12's own table. Neither is ever applied to
`CONTRADICTED`: a contradiction is the REOPEN path, its quote is supposed to contain a negator
("actually not yet"), and its whole reason for existing is that a wrong close must be
recoverable. Guarding the reopen would point the cascade backwards, which is the same argument
`judge.py` already makes for not applying a floor to it.

PURE, INTEGER, NO CLOCK, NO MODEL. Both functions take text and offsets and return a receipt.
"""
from __future__ import annotations

import re

__all__ = ["NEGATORS", "in_quoted_history", "negator_in_clause", "quoted_regions"]

#: MOVED, NOT DELETED. `quoted_regions` and `in_quoted_history` now live in
#: `capture/preprocess/quoted.py`, because reply history is a property of the raw message and
#: Layer 1 has to know it BEFORE anything is extracted — see that module's header for the 23
#: signals this file's absence from the capture path was producing. Re-exported here so this
#: module's public surface, `judge.py` and `test_h6_adversarial.py` are all unchanged.
from genios_engine.capture.preprocess.quoted import (        # noqa: E402
    in_quoted_history,
    quoted_regions,
)

#: The negators, lower-cased, matched on WORD BOUNDARIES. English and Hinglish together for the
#: reason doc 12 case 6 gives about the prompt: this corpus is mixed-script, and an English-only
#: list would pass `"abhi tak nahi hua"` straight through the guard that exists to stop it.
#:
#: Deliberately SHORT. Every entry is a word whose presence in the same clause as a completion
#: quote genuinely inverts it; nothing is here on the grounds that it "often" appears near a
#: negative, because a false entry costs a miss on every message that happens to contain it.
#: EVERY ENTRY NEGATES A VERB OF COMPLETION. That restriction is the whole design of the list and
#: it was learned the expensive way: an earlier draft carried "nothing", "none" and "no longer",
#: and it refused `vendor_implied_nothing_pending` — because *"nothing pending from our side"* and
#: *"no longer an issue"* are how English STATES a completion, not how it denies one. A negator
#: that inverts a noun tells you nothing about whether the work was done; only one that inverts
#: the act does. Anything added here must fail that test first.
NEGATORS: tuple[str, ...] = (
    "not", "n't", "never", "cannot", "cant",
    "yet to", "still waiting", "unsigned", "un-signed", "unresolved",
    # Hinglish. `nahi`/`nahin`/`nai` are one word in three transliterations, and a corpus that
    # contains one contains all three. `abhi tak nahi` ("not yet, up to now") is the ordinary way
    # this corpus says a thing is still outstanding — the `nahi` in it is what matches.
    "nahi", "nahin", "nai", "nahee",
)

#: The clause boundaries a negation does NOT reach across. `"the delay is no longer an issue, we
#: signed yesterday"` must not be refused: the negator belongs to the clause before the comma and
#: says nothing about the signing. Sentence enders, the comma, the semicolon, the dash and the
#: newline all end a clause; "but" and "however" do too, and they are the two words English uses
#: precisely to reverse the polarity of what came before.
_CLAUSE_BREAK = re.compile(r"[.!?;,\n\r]|\s[-–—]\s|\b(?:but|however|although|though)\b",
                           re.IGNORECASE)


def negator_in_clause(text: str, start: int, end: int) -> str | None:
    """The negator governing the span at `[start, end)`, or None.

    The window is the span itself plus its own clause-prefix — everything from the last clause
    boundary before `start` up to `end`. Scoped that tightly on purpose: a wider window turns
    every long message containing the word "not" anywhere into a refusal, which would cost real
    resolutions in exchange for guarding a sentence the negator was never about.

    Returns the matched negator so the refusal can name it. Doctrine 3: no claim without a
    receipt, and *"a negator governs this quote"* is a claim.
    """
    if not text or end <= start:
        return None
    start = max(0, min(start, len(text)))
    end = max(start, min(end, len(text)))

    prefix = text[:start]
    breaks = list(_CLAUSE_BREAK.finditer(prefix))
    clause_start = breaks[-1].end() if breaks else 0
    window = text[clause_start:end].lower()

    for negator in NEGATORS:
        # `\b` on both sides where the negator starts and ends with a word character, so "not"
        # does not match inside "notice" and "nai" does not match inside "email". `n't` starts
        # with a non-word character and takes a boundary only on the right.
        left = r"\b" if negator[0].isalnum() else ""
        right = r"\b" if negator[-1].isalnum() else ""
        if re.search(left + re.escape(negator) + right, window):
            return negator
    return None
