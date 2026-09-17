"""V-02 judged every non-ASCII name an invention, unconditionally, and threw the card away.

`_proper_nouns` builds its token with ``re.sub(r"[^A-Za-z0-9]", "", ...)``, which DELETES a
diacritic rather than folding it. So `Sofía` became `Sofa` and `TÜV` became `TUV`-minus-the-U —
`TV`. Neither string can appear in any corpus, so the guard rejected the name however faithfully
the model had copied it out of the tenant's own graph.

MEASURED ON THE PILOT, 17 Sep 2026, over all 25 live V-02 rejections:

    V-02:name:Sofa             x2   the graph holds "Sofía Padrón" verbatim
    V-02:name:TV               x2   both cards are about TÜV Austria
    V-02:name:SwerashiGeniOS   x3   `Swerashi:GeniOS` welded by the interior colon
    V-02:name:CentreITC        x1   `Centre(ITC)` welded by the interior parenthesis
    V-02:name:SpA              x1   an Italian corporate suffix

The second class is the same failure the hyphen rule already documents — `AI-guided` became
`AIguided` — reached through a mark nobody had added to the split. Deleting an interior
separator does not separate two words, it welds them.

WHAT MUST STILL BE REJECTED, and the two tests that hold it. `V-02:name:INSERT` was a template
placeholder leaking into a draft body: the guard doing exactly its job, and exempting the word
would ship "[INSERT NAME]" to a customer. `V-02:name:Three` is pinned by
`test_a_spelled_number_is_still_a_claim` so the guard cannot depend on whether the model wrote
"3" or "Three". Neither is touched here.
"""
from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from genios_engine.deliver.render import (  # noqa: E402
    _GRAMMAR_WORDS,
    _proper_nouns,
    invention_ok,
)


# =============================================================================================
# (a) the accent
# =============================================================================================
def test_a_name_the_graph_holds_verbatim_is_not_an_invention():
    """The exact live rejection: the pilot's graph carries "Sofía Padrón" and the card was
    discarded for saying it."""
    ok, why = invention_ok("Sofía Padrón has not confirmed", "meeting with sofía padrón", set())

    assert ok, f"a name copied out of the tenant's own graph was rejected as {why}"


def test_the_letter_survives_the_fold():
    """Folding, not deleting. `Sofía` -> `Sofia` keeps a token that can match; the old
    `[^A-Za-z0-9]` strip produced `Sofa`, which matches nothing in any language."""
    assert _proper_nouns("Sofía Padrón wrote") == ["Sofia", "Padron"]
    assert _proper_nouns("TÜV Austria replied") == ["TUV", "Austria"]


def test_an_accented_name_nobody_mentioned_is_still_rejected():
    """The fold must not become an amnesty: an ungrounded name is ungrounded however it is
    spelled, and a guard that stopped rejecting those would be worth nothing."""
    ok, why = invention_ok("Sofía has not replied", "acme is in negotiation", set())

    assert not ok and why == "name:Sofia"


def test_both_sides_are_folded_or_neither_matches():
    """Folding the token and not the corpus just moves which spelling can never match. The
    corpus here is UNfolded, exactly as a caller building one by hand would leave it."""
    assert invention_ok("TÜV Austria replied", "tüv austria is the counterparty", set())[0]
    assert invention_ok("TUV Austria replied", "tüv austria is the counterparty", set())[0]


# =============================================================================================
# (b) the welded token
# =============================================================================================
@pytest.mark.parametrize("text,expected", [
    ("Swerashi:GeniOS pitch is open", ["Swerashi", "GeniOS"]),
    ("Centre(ITC) has not replied", ["Centre", "ITC"]),
    ("Ben&Jerry replied", ["Ben", "Jerry"]),
    ("Acme;Initech both replied", ["Acme", "Initech"]),
    ("Acme[Corp] replied", ["Acme", "Corp"]),
])
def test_an_interior_mark_separates_two_words_rather_than_welding_them(text, expected):
    """`AI-guided` -> `AIguided` is the same bug this file's docstring names, and the hyphen was
    the only mark anybody had fixed."""
    assert _proper_nouns(text) == expected


def test_each_half_of_a_welded_token_is_judged_on_its_own():
    """Splitting must not become an amnesty either: the guard now asks a real question about
    each part instead of an unanswerable one about the weld."""
    grounded = "rohit swerashi pitched genios"
    assert invention_ok("Swerashi:GeniOS pitch is open", grounded, set())[0]

    ok, why = invention_ok("Swerashi:GeniOS pitch is open", "rohit swerashi only", set())
    assert not ok and why == "name:GeniOS"


def test_an_address_is_one_token_and_stays_whole():
    """`.` and `@` are deliberately NOT separators. Splitting `nikhil@addis.im` would ask the
    guard about `im` instead of about the address — the opposite mistake, made the same way."""
    assert _proper_nouns("Nikhil@Addis.im asked about pricing") == ["NikhilAddisim"]
    assert invention_ok("Nikhil@Addis.im asked about pricing",
                        "nikhil@addis.im asked about pricing", set())[0]


# =============================================================================================
# (c) the words, and the two that must never join them
# =============================================================================================
@pytest.mark.parametrize("word", ["address", "reschedule", "clarify", "specifically",
                                  "repeating", "differentiation", "measured", "vcs"])
def test_each_added_word_was_earned_by_a_live_rejection(word):
    """The list's own law: "each entry has to be earned by an observed failure". Every one of
    these rejected a real draft on the pilot on 17 Sep 2026."""
    assert word in _GRAMMAR_WORDS
    assert invention_ok(f"{word.capitalize()} the scope with them", "acme scope", set())[0]


def test_a_template_placeholder_is_not_grammar():
    """`V-02:name:INSERT` was the guard catching "[INSERT NAME]" on its way to a customer."""
    assert "insert" not in _GRAMMAR_WORDS

    ok, why = invention_ok("Send the deck to INSERT NAME", "acme scope", set())
    assert not ok and why == "name:INSERT"


def test_a_spelled_number_did_not_quietly_join_the_list():
    """Pinned by `test_a_spelled_number_is_still_a_claim` for a stated reason: the guard must not
    depend on whether the model wrote "3" or "Three"."""
    assert "three" not in _GRAMMAR_WORDS


def test_the_alias_does_not_weld_the_corpus_into_one_word():
    """The kind fix and the weak fix look identical until this test. Collapsing the WHOLE corpus
    would turn "acme scope" into "acmescope" and ground the invented name "Mesco" as a substring
    — the guard getting kinder by getting worthless. Aliases are per token and joined by spaces."""
    ok, why = invention_ok("Mesco has not replied", "acme scope is open", set())

    assert not ok and why == "name:Mesco"


def test_only_a_token_with_interior_punctuation_gains_an_alias():
    """A plain word is already its own alias. Adding one for every token would double the
    haystack for nothing and widen the substring match for free."""
    from genios_engine.deliver.render import _haystack

    assert _haystack("acme scope is open") == "acme scope is open"
    assert _haystack("nikhil@addis.im wrote") == "nikhil@addis.im wrote nikhiladdisim"
