"""STEP-13 · what the check found is written down in closed words, and reads back as it was stored.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_claim_check_contract.py

Tree `yc2_w27_s13` M35.C1.L-contract.V0.U02 (`contracts/claim_check.py`). A verdict per line — kept,
corrected by one named means, dropped for one closed reason, or noted — and the checked review: the move's
fate, the one question a held file asks, the card's words once checked, the ids its standing facts cite.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from genios_engine.contracts import claim_check as C

pytestmark = pytest.mark.unit

WORDS = C.CardWords(headline="Send Neel the one-page pre-read", situation="A first call with a fund",
                    done_when="Neel has the pre-read before the call", draft="Hi Neel, …", to="Neel",
                    evidence=("evt_a", "loop:l1", "evt_a"), quotes=("could we talk", ""))


def _checked(**over) -> C.CheckedReview:
    base = dict(verdicts=(C.LineVerdict("fact:1", C.KEPT),
                          C.LineVerdict("fact:2", C.DROPPED, C.MISQUOTED, "quote: send the deck"),
                          C.LineVerdict("move", C.CORRECTED, C.BY_CALCULATOR, "number:52 -> 48 (num:gap)"),
                          C.LineVerdict("situation", C.NOTED, C.SPEAKS_OF_YOU, "the founder")),
                fate=C.SHOWN, words=WORDS, cited=("evt_b", "evt_a", "evt_a"))
    base.update(over)
    return C.CheckedReview(**base)


def test_a_checked_review_keeps_a_verdict_per_line_and_what_stands():
    checked = _checked()
    assert checked.cited == ("evt_a", "evt_b"), "sorted, once each"
    assert checked.stands("fact:1") and not checked.stands("fact:2") and checked.stands("move")
    assert [v.line for v in checked.dropped] == ["fact:2"]
    assert checked.reasons == (C.MISQUOTED,)
    assert checked.version == C.CHECK_VERSION


def test_a_checked_review_round_trips_as_stored():
    for checked in (_checked(),
                    _checked(fate=C.HELD, question="Did Neel ask for the deck?", because="misquoted: fact 2",
                             words=C.CardWords(None, "A first call with a fund", None, None, None)),
                    _checked(fate=C.REFUSED, because="nothing_stands", cited=(),
                             verdicts=(C.LineVerdict("fact:1", C.DROPPED, C.UNCITED),))):
        again = C.CheckedReview.from_mapping(checked.as_mapping())
        assert again == checked and again.as_mapping() == checked.as_mapping()


@pytest.mark.parametrize("line, verdict, reason", [
    ("fact:1", "kept", "misquoted"),           # a kept line has no reason
    ("fact:1", "dropped", None),               # a dropped line always has one
    ("fact:1", "dropped", "rude"),             # a reason outside the closed list
    ("fact:1", "corrected", "misquoted"),      # a correction names HOW, not why
    ("fact:1", "noted", "misquoted"),          # a note is a note
    ("fact:1", "fixed", None),                 # a verdict outside the closed list
    ("fact:0", "kept", None),                  # facts count from one
    ("fact", "kept", None),
    ("claim:1", "kept", None),
    ("headline", "kept", None),                # the card's line is the MOVE
])
def test_a_verdict_is_closed_and_names_a_real_line(line, verdict, reason):
    with pytest.raises(ValueError):
        C.LineVerdict(line, verdict, reason)


@pytest.mark.parametrize("over, says", [
    ({"fate": "maybe"}, "fate"),
    ({"fate": C.HELD, "because": "misquoted"}, "asks its question"),
    ({"fate": C.HELD, "question": "Did Neel ask?"}, "says why"),
    ({"fate": C.SUPPRESSED}, "says why"),
    ({"fate": C.REFUSED, "because": "nothing_stands"}, "no standing fact"),
    ({"verdicts": (C.LineVerdict("fact:1", C.KEPT), C.LineVerdict("fact:1", C.DROPPED, C.UNCITED))},
     "one verdict"),
    ({"verdicts": (C.LineVerdict("move", C.NOTED, C.SPEAKS_OF_YOU),
                   C.LineVerdict("move", C.NOTED, C.SPEAKS_OF_YOU))}, "one verdict"),
])
def test_a_fate_that_is_not_shown_says_why_and_a_held_one_asks(over, says):
    with pytest.raises(ValueError, match=says):
        _checked(**over)


def test_a_line_carries_its_verdict_and_its_notes_beside_it():
    checked = _checked(verdicts=(C.LineVerdict("situation", C.KEPT),
                                 C.LineVerdict("situation", C.NOTED, C.SPEAKS_OF_YOU, "the founder"),
                                 C.LineVerdict("prose", C.NOTED, C.UNHELD_NUMBER, "number:3")))
    assert checked.stands("situation") and checked.notes == (C.SPEAKS_OF_YOU, C.UNHELD_NUMBER)
    assert checked.reasons == ()


def test_the_reasons_dropped_are_counted_once_each_in_one_order():
    """What a health check counts: each reason once, in one order whatever order the lines dropped in."""
    reasons = (C.UNSUPPORTED, C.MISQUOTED, C.WRONG_NUMBER, C.UNCITED, C.UNKNOWN_EVIDENCE, C.UNQUOTED)
    verdicts = tuple(C.LineVerdict(f"fact:{n}", C.DROPPED, reason) for n, reason in enumerate(reasons, 1))
    checked = _checked(verdicts=verdicts + (C.LineVerdict("fact:9", C.DROPPED, C.UNSUPPORTED),))
    assert checked.reasons == tuple(sorted(set(reasons)))


def test_every_reason_note_and_fate_is_spelled_once():
    for vocabulary in (C.REASONS, C.NOTES, C.CORRECTIONS, C.FATES, C.VERDICTS):
        assert len(vocabulary) == len(set(vocabulary))
    assert not set(C.REASONS) & set(C.NOTES) and not set(C.REASONS) & set(C.CORRECTIONS)


def test_the_headline_says_where_it_came_from_once_each():
    assert WORDS.evidence == ("evt_a", "loop:l1") and WORDS.quotes == ("could we talk",)
    assert C.CardWords.from_mapping(WORDS.as_mapping()) == WORDS


def test_card_words_withheld_read_back_as_withheld():
    words = C.CardWords(headline="Send Neel the pre-read", situation=None, done_when="", draft=None,
                        to=None)
    assert C.CardWords.from_mapping(words.as_mapping()) == C.CardWords(
        "Send Neel the pre-read", None, None, None, None)


def test_a_checked_review_is_frozen():
    with pytest.raises(FrozenInstanceError):
        _checked().fate = C.HELD                                   # type: ignore[misc]


def test_a_stored_check_that_is_not_an_object_is_a_value_error():
    with pytest.raises(ValueError, match="an object"):
        C.CheckedReview.from_mapping(["shown"])


# ── STEP-14 · the alternative and the stop rule are card words (`yc2_w27_s14` M43.C1.L-contract.V0.U02) ─────────
def test_the_alternative_and_the_stop_rule_are_card_words_kept_as_checked():
    """The gold card shows the review's alternative and when to wait or stop (0221), so the check holds them like the
    situation (s14-F8): `CardWords` carries them — None withheld — and a verdict may name them."""
    words = C.CardWords(**{**{k: v for k, v in WORDS.as_mapping().items() if k not in ("evidence", "quotes")},
                           "evidence": WORDS.evidence, "quotes": WORDS.quotes,
                           "alternative": "Offer Neel a short call instead", "wait_or_stop": "If no reply by Friday, ask once"})
    again = C.CardWords.from_mapping(words.as_mapping())
    assert (again.alternative, again.wait_or_stop) == ("Offer Neel a short call instead", "If no reply by Friday, ask once")
    assert again == words
    assert (WORDS.alternative, WORDS.wait_or_stop) == (None, None), "a check that held none withholds them"
    assert {"alternative", "wait_or_stop", "do_nothing"} <= set(C.CARD_LINES)
    for line in ("alternative", "wait_or_stop"):
        assert C.LineVerdict(line, C.DROPPED, C.UNSUPPORTED, "name:Kunal").line == line
    old = {k: v for k, v in WORDS.as_mapping().items() if k not in ("alternative", "wait_or_stop")}
    assert C.CardWords.from_mapping(old).alternative is None, "a check stored before them reads back withheld"


# =================================================================================================
# STEP-16 · never silently — the check's words for a correction (`yc2_w27_s16` M46.C4.L-contract.V0.U01)
# =================================================================================================
def test_the_check_has_words_for_an_unheeded_correction_and_a_card_you_called_wrong():
    assert (C.CORRECTION_UNHEEDED, C.CALLED_WRONG) == ("correction_unheeded", "called_wrong")
    assert {C.CORRECTION_UNHEEDED, C.CALLED_WRONG} <= set(C.REASONS)
    assert C.UNCITED_CORRECTION in C.NOTES and C.UNCITED_CORRECTION not in C.REASONS
    for why in (C.CORRECTION_UNHEEDED, C.CALLED_WRONG):
        assert C.HELD_BECAUSE[why], "a held move says why in founder words"


def test_a_move_held_over_your_correction_is_one_question_naming_it():
    assert C.correction_question("  she asked for news only on   real milestones ", "12 Oct") == (
        "You said “she asked for news only on real milestones” on 12 Oct; does it still hold?")
    assert C.called_wrong_question("Send Theresa the August update") == (
        "You called “Send Theresa the August update” wrong; should we advise it again?")
    for bad in ("", "   ", None):
        with pytest.raises(ValueError):
            C.correction_question(bad, "12 Oct")
        with pytest.raises(ValueError):
            C.called_wrong_question(bad)


def test_a_held_move_over_a_correction_is_a_verdict_the_contract_keeps():
    held = C.CheckedReview(
        verdicts=(C.LineVerdict("fact:1", C.KEPT),
                  C.LineVerdict("move", C.DROPPED, C.CORRECTION_UNHEEDED, "corr:fc_0123456789abcdef01234567")),
        fate=C.HELD, words=C.CardWords(None, None, None, None, None), cited=("evt_1",),
        question=C.correction_question("news only on milestones", "12 Oct"),
        because=C.HELD_BECAUSE[C.CORRECTION_UNHEEDED])
    assert C.CheckedReview.from_mapping(held.as_mapping()) == held
    assert held.reasons == (C.CORRECTION_UNHEEDED,) and not held.stands("move")
    noted = C.LineVerdict("move", C.NOTED, C.UNCITED_CORRECTION, "corr:fc_0123456789abcdef01234567")
    assert C.LineVerdict.from_mapping(noted.as_mapping()) == noted


def test_a_check_stored_before_reads_as_stored():
    """Additive vocabularies: a check written before STEP-16 reads back exactly as it was."""
    stored = {"version": "check.v3", "fate": "shown", "question": None, "because": None, "cited": ["evt_1"],
              "words": {"headline": "Send the deck"}, "verdicts": [{"line": "fact:1", "verdict": "kept",
                                                                   "reason": None, "detail": ""}]}
    again = C.CheckedReview.from_mapping(stored)
    assert again.as_mapping()["verdicts"] == stored["verdicts"] and again.version == "check.v3"


# =================================================================================================
# STEP-13b · three sources — what the check says of the engine and of the expert's own
# =================================================================================================
def test_the_check_has_words_for_an_engine_cited_as_a_fact_and_for_an_own_line_that_overreaches():
    assert (C.ENGINE_IS_NO_FACT, C.OWN_STATES_A_NUMBER, C.OWN_NAMES_THE_FILE) == (
        "engine_is_no_fact", "own_states_a_number", "own_names_the_file")
    assert {C.ENGINE_IS_NO_FACT, C.OWN_STATES_A_NUMBER, C.OWN_NAMES_THE_FILE} <= set(C.REASONS)
    assert C.OWN_DISAGREES == "own_disagrees" and C.OWN_DISAGREES in C.NOTES and C.OWN_DISAGREES not in C.REASONS
    assert C.HELD_BECAUSE[C.ENGINE_IS_NO_FACT], "a move resting on such a fact is held in founder words"
    assert "own" in C.LINE_KINDS and C.LineVerdict("own:2", C.DROPPED, C.OWN_STATES_A_NUMBER, "number:9").line == "own:2"
    with pytest.raises(ValueError):
        C.LineVerdict("own:0", C.KEPT)


@pytest.mark.parametrize("refs, source", [
    (("evt_1", "fact:1", "num:reply_days", "loop:l1"), C.DATA),
    (("pb:founder_office.pb.x", "cap:a.b.c#q", "rule:r", "cons:r", "sig:s", "frame:f", "org:o", "pat:p",
      "pref:q", "ru:core.risk"), C.ENGINE),
    (("own:1", "own:3"), C.OWN),
    (("evt_1", "pb:founder_office.pb.x"), C.MIXED),
    (("own:1", "pb:founder_office.pb.x"), C.MIXED),
    (("evt_1", "own:1"), C.MIXED),
    ((), C.DATA),
    (("owned_event_1", "ownership:1"), C.DATA),     # a mail whose id merely begins with "own"
])
def test_a_lines_source_is_derived_from_what_it_cites_never_asserted(refs, source):
    assert C.source_of(refs) == source
    assert C.SOURCES == ("data", "engine", "own", "mixed")


def test_a_verdict_may_carry_its_derived_source_and_reads_back():
    v = C.LineVerdict("pattern:1", C.KEPT, source=C.ENGINE)
    assert C.LineVerdict.from_mapping(v.as_mapping()) == v and v.as_mapping()["source"] == "engine"
    assert "source" not in C.LineVerdict("fact:1", C.KEPT).as_mapping(), "a verdict stored before reads as stored"
    with pytest.raises(ValueError):
        C.LineVerdict("fact:1", C.KEPT, source="guess")


def test_a_checked_review_keeps_the_engine_lines_its_standing_lines_cite():
    cite = C.EngineCited("pb:founder_office.pb.x", "Run an investor conversation: ask once", "founder_office.pb.x",
                         reviewed=False)
    checked = _checked(engine=(cite, C.EngineCited("cap:a.b.c#q", "Is it done?", "a.b.c", reviewed=True)))
    assert [c.ref for c in checked.engine] == ["cap:a.b.c#q", "pb:founder_office.pb.x"], "sorted, once each"
    again = C.CheckedReview.from_mapping(checked.as_mapping())
    assert again == checked and again.engine[1].words == cite.words and again.engine[1].reviewed is False
    with pytest.raises(ValueError, match="engine"):
        C.EngineCited("evt_1", "a mail is no engine line", "x", reviewed=False)


def test_a_check_stored_before_has_no_engine_and_reads_as_stored():
    stored = _checked().as_mapping()
    assert "engine" not in stored and C.CheckedReview.from_mapping(stored).engine == ()


def test_the_check_version_moved_for_the_three_sources():
    assert C.CHECK_VERSION == "check.v5"
