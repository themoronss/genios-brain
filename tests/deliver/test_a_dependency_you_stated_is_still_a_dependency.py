""""I am waiting on X" is the finding — whoever happened to type the sentence.

    pytest tests/deliver/test_a_dependency_you_stated_is_still_a_dependency.py -q

⛔ WHY THIS FILE EXISTS. Measured on the design partner's org, 2026-10-04: the account held
SIXTEEN live cards and the owner saw THREE. Nine of the missing thirteen were `dependency_stated`,
every one of them stamped *"nothing this account said is on record, so there is no way to say what
they asked for"*, every one of them dropped from the `app` surface by `_surfaces`, and nothing
anywhere told the owner they existed:

    Needs a decision — ESOP allocation
    Needs a decision — Get Khushi's acceptance of the offer
    Needs a decision — Confirm fundraising completion
    Needs a decision — GeniOS funding from Bharat                 … and five more

The quotes were there the whole time — three to seven per node. Every one was authored by
`mrrohitswerashi@gmail.com`, the founder himself, so `quotable()` — which keeps only
`from_counterparty is True` — returned nothing.

⛔ AND THAT IS THE WRONG QUESTION FOR THIS REASON CODE. The corpus defines the situation as
*"anchored on a STATED DEPENDENCY — one sentence in which something was said to wait on something
else"* (`_schema/vocabulary.yaml`), named "Waiting On Something Named". THE SENTENCE IS THE
SITUATION. Who uttered it is not in the definition and cannot be: "I am waiting on Khushi's
acceptance of the offer" is the entire finding whether Khushi wrote it or the founder did.

This is the identical error `_GROUNDED_BY_OUR_OWN_WORDS` already corrects for four other codes, in
that module's own words: *"Requiring their words there is requiring the silence to speak."*

⛔ WHAT THIS DOES NOT DO. It does not weaken `quotable()`, and `test_the_counterparty_filter_is_not
_weakened` is why. The attribution rule stands for every other reason code — 161 of 526 observations
on this org are the founder's own outgoing sentences, and presenting one of those as something the
other side asked is the misattribution the filter exists to prevent. Only this one reason code's
GROUNDING question changes; the honesty rule does not.
"""

from __future__ import annotations

import pytest

from genios_engine.deliver.card_builder import (
    _GROUNDED_BY_OUR_OWN_WORDS,
    _NAMING_ONLY_KINDS,
    quotable,
)

pytestmark = pytest.mark.unit

#: One of the nine, as production held it: the founder's own offer mail, three observations,
#: not one syllable from the other side.
_FOUNDER = "mrrohitswerashi@gmail.com"
_REAL_ROWS = [
    {"kind": "received:commitment_due", "author": _FOUNDER, "from_counterparty": False,
     "quote": "I am pleased to formally invite you to join as Founding AI Engineer."},
    {"kind": "received:commitment_made", "author": _FOUNDER, "from_counterparty": False,
     "quote": "I am pleased to formally invite you to join as Founding AI Engineer."},
    {"kind": "received:deadline_stated", "author": _FOUNDER, "from_counterparty": False,
     "quote": "I am pleased to formally invite you to join as Founding AI Engineer."},
]


def _grounding(quotes, reason_code):
    """The builder's two-step grounding decision, as `build_draft` makes it."""
    grounding = quotable(quotes)
    if not grounding and reason_code in _GROUNDED_BY_OUR_OWN_WORDS:
        grounding = [q for q in (quotes or ())
                     if str(q.get("kind") or "") not in _NAMING_ONLY_KINDS
                     and str(q.get("quote") or "").strip()]
    return grounding


def test_a_dependency_the_founder_stated_is_grounded():
    """⛔ THE MUTATION THIS FILE REJECTS: dropping `dependency_stated` from the set. Nine live
    cards go dark again, and the owner is told nothing was found."""
    assert "dependency_stated" in _GROUNDED_BY_OUR_OWN_WORDS, (
        "dependency_stated needs the counterparty's words again — but the situation IS the "
        "sentence, and the founder is allowed to be the one who wrote it")
    assert _grounding(_REAL_ROWS, "dependency_stated"), (
        "the nine cards abstain again: three quotes on the node and the card still says "
        "'nothing this account said is on record'")


def test_the_counterparty_filter_is_not_weakened():
    """⛔ The fix must be the REASON CODE's, never `quotable()`'s. Weakening the attribution rule
    would let the founder's own outgoing sentence be printed as something the other side asked —
    161 of 526 observations on this org are exactly that."""
    assert quotable(_REAL_ROWS) == [], (
        "quotable() now accepts the account holder's own words — that is misattribution, and it "
        "is a different bug from the one this file fixes")


def test_another_reason_code_still_needs_their_words():
    """The exemption is per reason code, not a new default. A code outside the set that cannot
    quote the counterparty must still abstain."""
    assert _grounding(_REAL_ROWS, "unanswered_email") == []
    assert "unanswered_email" not in _GROUNDED_BY_OUR_OWN_WORDS


def test_the_counterpartys_own_words_still_win_when_they_exist():
    """The fallback is a FALLBACK: when the other side did speak, that is the grounding, and the
    founder's sentences do not displace it."""
    theirs = {"kind": "question_asked", "author": "khushi@example.com",
              "from_counterparty": True, "quote": "What is the vesting schedule?"}
    assert _grounding(_REAL_ROWS + [theirs], "dependency_stated") == [theirs]


def test_a_name_is_not_a_dependency():
    """`_NAMING_ONLY_KINDS` still applies on the fallback path: an extracted name is not a
    statement, so a node that yields only mentions grounds nothing and must still abstain."""
    names = [{"kind": k, "author": _FOUNDER, "from_counterparty": False, "quote": "Khushi"}
             for k in sorted(_NAMING_ONLY_KINDS)]
    assert _grounding(names, "dependency_stated") == []


def test_an_empty_sentence_grounds_nothing():
    """A row with a blank quote is not evidence; it was the fallback's one way to 'succeed'
    while saying nothing."""
    blanks = [{"kind": "received:commitment_made", "author": _FOUNDER,
               "from_counterparty": False, "quote": "   "}]
    assert _grounding(blanks, "dependency_stated") == []


def test_the_four_original_members_are_still_there():
    """The regression this set was built for is not undone by adding to it."""
    for code in ("awaiting_response", "first_touch_unanswered",
                 "outbound_prospect", "cohort_outreach_gap"):
        assert code in _GROUNDED_BY_OUR_OWN_WORDS
