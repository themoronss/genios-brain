"""STEP-12 · the expert's review has a shape code can check, and it refuses what its dossier does not hold.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_review_contract.py

Tree `yc2_w27_s12` M32.C1.L-contract.V0.U01 (`contracts/expert_review.py`). Plane R had no result
contract (STEP-12 §8.3 N5); the review is the Atlas's `reasoning_result`: facts that cite, inferences
and patterns that rest on something, hypotheses and unknowns, a frame and its rivals, expected vs actual
against the playbook's stage, scenarios, an appraisal in levels with reasons, a mode, a next move, an
alternative, when to wait or stop, done-when and a draft. `validate` refuses an uncited fact, a citation
the dossier never showed, an inference or a pattern resting on nothing it holds, a stage the playbook
lacks, a moving mode with no next move — and any number, anywhere in the review, that the dossier does
not hold. A malformed answer is a ValueError that names the field: the one thing a caller may repair.

M32.C1.L-contract.V0.U09: a review may PROPOSE the file's kind of work (`03` F132, F151) — one of the
brief's kinds, why, and the dossier ids that show it, validated like a fact; null when the kind is right.

STEP-13 `yc2_w27_s13` M35.C1.L-contract.V0.U01: the second version carries what the check reads — a fact's
quote, the facts a move rests on, whom its draft goes to, the ask it answers — each optional, so a
first-version answer reads, validates and is stored exactly as before.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from genios_engine.contracts.expert_review import (
    MODES, NO_NEXT_MOVE, OWN_KINDS, NUMBER_NOT_IN_DOSSIER, REFUSALS, UNCITED_FACT, UNGROUNDED_INFERENCE,
    UNGROUNDED_MOVE, UNGROUNDED_PATTERN, UNKNOWN_EVIDENCE, UNKNOWN_STAGE, DossierCatalogue, ExpertReview,
    number_tokens, validate)

pytestmark = pytest.mark.unit

CATALOGUE = DossierCatalogue(
    evidence_ids=frozenset({"evt_neel_0927", "evt_invite_1008", "pb:first_call", "num:reply_days"}),
    numbers=number_tokens("27 Sep Neel wrote · the call on 8 Oct · last mail to any investor 40 days ago"
                          " · Neel replies in 3 days (n=6)"),
    stages=("first_contact", "first_call", "partner_meeting"))


def _raw(**over) -> dict:
    raw = {
        "facts": [{"claim": "Neel wrote on 27 Sep asking for a first call", "evidence": ["evt_neel_0927"]},
                  {"claim": "The call is booked for 8 Oct", "evidence": ["evt_invite_1008"]}],
        "inferences": [{"claim": "This is a first call with a fund", "based_on": ["fact:1", "fact:2"]}],
        "patterns": [{"kind": "pattern", "claim": "Neel answers within 3 days",
                      "based_on": ["num:reply_days"]},
                     {"kind": "counter_pattern", "claim": "a fund that books the call itself rarely ghosts",
                      "based_on": ["pb:first_call"]}],
        "hypotheses": [{"proposition": "Neel leads deals at this stage", "needs": "his last deals"}],
        "unknowns": [{"question": "Does the fund invest pre-seed?", "relevance": "decides the pitch"}],
        "frames": {"primary": "a first call with a top-tier fund", "rivals": ["an exploratory chat"]},
        "expected_vs_actual": {"stage": "first_call", "expected": "a pre-read before the call",
                               "actual": "nothing sent yet"},
        "scenarios": {"do_nothing": "the call runs cold", "act": "a pre-read frames the call",
                      "best": "a partner meeting follows", "worst": "a polite pass",
                      "signals_to_watch": ["a reply to the pre-read"]},
        "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                      "reasons": ["the call is close and the fund is the founder's best lead"]},
        "mode": "act",
        "next_move": {"who": "the founder", "what": "send a one-page pre-read",
                      "for_whom": "Neel", "by_when": "2026-10-07"},
        "alternative": "send it after the call",
        "wait_or_stop": "if no reply by the call, raise it on the call",
        "done_when": "the call happens and its next step is logged",
        "draft": "Hi Neel, ahead of our call on 8 Oct, a one-page note on where we are."}
    raw.update(over)
    return raw


def test_a_whole_review_parses_and_validates():
    review = ExpertReview.from_mapping(_raw())
    assert review.mode == "act" and review.next_move.by_when == date(2026, 10, 7)
    assert [p.kind for p in review.patterns] == ["pattern", "counter_pattern"]
    result = validate(review, CATALOGUE)
    assert result.ok and result.reasons == () and result.problems == ()


@pytest.mark.parametrize("over, refusal", [
    ({"facts": [{"claim": "Neel wrote", "evidence": ["evt_made_up"]}]}, UNKNOWN_EVIDENCE),
    ({"inferences": [{"claim": "a fund", "based_on": ["fact:9"]}]}, UNGROUNDED_INFERENCE),
    ({"inferences": [{"claim": "a fund", "based_on": ["fact:0"]}]}, UNGROUNDED_INFERENCE),
    ({"inferences": [{"claim": "a fund", "based_on": []}]}, UNGROUNDED_INFERENCE),
    ({"inferences": [{"claim": "a fund", "based_on": ["evt_made_up"]}]}, UNKNOWN_EVIDENCE),
    ({"patterns": [{"kind": "base_rate", "claim": "most first calls lead nowhere", "based_on": []}]},
     UNGROUNDED_PATTERN),
    ({"patterns": [{"kind": "pattern", "claim": "Neel is quick", "based_on": ["num:made_up"]}]},
     UNKNOWN_EVIDENCE),
    ({"patterns": [{"kind": "pattern", "claim": "Neel is quick", "based_on": ["fact:3"]}]},
     UNGROUNDED_PATTERN),
    ({"expected_vs_actual": {"stage": "term_sheet", "expected": "x", "actual": "y"}}, UNKNOWN_STAGE),
    ({"mode": "find_out", "next_move": None}, NO_NEXT_MOVE),
    ({"mode": "act", "next_move": None}, NO_NEXT_MOVE),
    ({"draft": "Hi Neel, we grew 32% last month."}, NUMBER_NOT_IN_DOSSIER),
    ({"facts": [{"claim": "Neel wrote 12 days ago", "evidence": ["evt_neel_0927"]}]},
     NUMBER_NOT_IN_DOSSIER),
    ({"appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                    "reasons": ["a $2m round rides on it"]}}, NUMBER_NOT_IN_DOSSIER),
    ({"next_move": {"who": "the founder", "what": "send 5 slides", "for_whom": "Neel"}},
     NUMBER_NOT_IN_DOSSIER),
])
def test_what_the_dossier_does_not_hold_is_refused_by_name(over, refusal):
    result = validate(ExpertReview.from_mapping(_raw(**over)), CATALOGUE)
    assert not result.ok and refusal in result.reasons, result.problems


def test_a_fact_with_no_citation_is_refused():
    result = validate(ExpertReview.from_mapping(_raw(facts=[{"claim": "Neel is keen",
                                                              "evidence": []}])), CATALOGUE)
    assert UNCITED_FACT in result.reasons, result.problems


def test_every_refusal_is_named_and_counted_once_per_kind():
    review = ExpertReview.from_mapping(_raw(
        facts=[{"claim": "Neel wrote 12 days ago", "evidence": ["evt_made_up"]},
               {"claim": "it is 99 percent sure", "evidence": []}],
        mode="find_out", next_move=None))
    result = validate(review, CATALOGUE)
    assert set(result.reasons) == {UNKNOWN_EVIDENCE, UNCITED_FACT, NO_NEXT_MOVE, NUMBER_NOT_IN_DOSSIER}
    assert result.reasons == tuple(sorted(result.reasons))
    assert set(result.reasons) <= set(REFUSALS)
    assert (NUMBER_NOT_IN_DOSSIER, "12") in result.problems and (NUMBER_NOT_IN_DOSSIER, "99") in result.problems


@pytest.mark.parametrize("mode", ["wait", "nothing", "blocked"])
def test_a_mode_that_does_not_move_needs_no_next_move(mode):
    review = ExpertReview.from_mapping(_raw(mode=mode, next_move=None, draft=None))
    assert review.next_move is None and review.draft is None
    assert validate(review, CATALOGUE).ok


@pytest.mark.parametrize("over, says", [
    ({"facts": []}, "at least one fact"),
    ({"mode": "panic"}, "mode"),
    ({"appraisal": {"stakes": "very", "urgency": "high", "reversibility": "reversible",
                    "reasons": ["r"]}}, "stakes"),
    ({"appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                    "reasons": []}}, "reasons"),
    ({"frames": {"primary": "a first call", "rivals": []}}, "rival frames"),
    ({"scenarios": {"do_nothing": "a", "act": "b", "best": "c", "worst": "d",
                    "signals_to_watch": []}}, "signals to watch"),
    ({"done_when": ""}, "what done looks like"),
    ({"wait_or_stop": None}, "when to wait or stop"),
    ({"facts": "Neel wrote"}, "facts"),
    ({"facts": ["Neel wrote"]}, "a fact"),
    ({"facts": [{"claim": "Neel wrote", "evidence": "evt_neel_0927"}]}, "a fact's evidence"),
    ({"facts": [{"claim": "Neel wrote", "evidence": [{"id": "evt_neel_0927"}]}]},
     "a fact's evidence must be words"),
    ({"inferences": "a fund"}, "inferences"),
    ({"patterns": [{"kind": "rumour", "claim": "x", "based_on": ["pb:first_call"]}]}, "kind"),
    ({"next_move": {"who": "the founder", "what": "x", "for_whom": "Neel", "by_when": "soon"}},
     "by_when"),
    ({"next_move": "send a pre-read"}, "next move"),
    ({"frames": ["a first call"]}, "frames"),
])
def test_a_malformed_answer_is_a_value_error_that_says_what(over, says):
    with pytest.raises(ValueError, match=says):
        ExpertReview.from_mapping(_raw(**over))


def test_an_answer_that_is_not_an_object_is_a_value_error():
    with pytest.raises(ValueError, match="an object"):
        ExpertReview.from_mapping(["facts"])


def test_the_closed_words_are_read_as_a_reader_spells_them():
    review = ExpertReview.from_mapping(_raw(
        mode="Find out", appraisal={"stakes": " Medium", "urgency": "LOW",
                                    "reversibility": "costly to reverse", "reasons": ["r"]},
        patterns=[{"kind": "counter-pattern", "claim": "x", "based_on": ["pb:first_call"]}]))
    assert review.mode == "find_out" and "find_out" in MODES
    assert (review.appraisal.stakes, review.appraisal.urgency) == ("medium", "low")
    assert review.appraisal.reversibility == "costly_to_reverse"
    assert review.patterns[0].kind == "counter_pattern"


def test_a_review_round_trips_through_its_mapping():
    review = ExpertReview.from_mapping(_raw())
    again = ExpertReview.from_mapping(review.as_mapping())
    assert again == review
    assert again.as_mapping()["next_move"]["by_when"] == "2026-10-07"
    bare = ExpertReview.from_mapping(_raw(mode="wait", next_move=None, draft=None, patterns=[]))
    assert ExpertReview.from_mapping(bare.as_mapping()) == bare


def test_a_review_is_frozen():
    review = ExpertReview.from_mapping(_raw())
    with pytest.raises(FrozenInstanceError):
        review.mode = "nothing"                                   # type: ignore[misc]


def test_every_text_the_review_writes_is_read_for_numbers():
    review = ExpertReview.from_mapping(_raw())
    texts = review.texts()
    for expected in ("Neel answers within 3 days", "send a one-page pre-read", "a polite pass",
                     "his last deals", "decides the pitch", "an exploratory chat", "nothing sent yet",
                     "send it after the call", "Hi Neel, ahead of our call on 8 Oct, a one-page note"
                     " on where we are."):
        assert expected in texts, expected


PROPOSED = {"kind": "investor", "why": "the programme writes cheques like the fund behind it",
            "evidence": ["evt_neel_0927"]}


def test_a_review_may_propose_the_files_kind_of_work():
    review = ExpertReview.from_mapping(_raw(proposed_kind=PROPOSED))
    assert (review.proposed_kind.kind, review.proposed_kind.evidence) == ("investor", ("evt_neel_0927",))
    assert ExpertReview.from_mapping(review.as_mapping()) == review
    assert review.proposed_kind.why in review.texts()                 # its words are read for numbers
    assert validate(review, CATALOGUE).ok
    assert ExpertReview.from_mapping(_raw()).proposed_kind is None
    assert ExpertReview.from_mapping(_raw()).as_mapping()["proposed_kind"] is None
    assert ExpertReview.from_mapping(_raw(proposed_kind={"kind": "Investor", "why": "w",
                                                         "evidence": ["evt_neel_0927"]})
                                     ).proposed_kind.kind == "investor"


@pytest.mark.parametrize("over, says", [
    ({"kind": "customer"}, "kind of work"),                          # not one of the brief's kinds
    ({"why": ""}, "why"),
    ({"evidence": []}, "proposed kind's evidence"),
])
def test_a_proposed_kind_says_which_why_and_from_what(over, says):
    with pytest.raises(ValueError, match=says):
        ExpertReview.from_mapping(_raw(proposed_kind={**PROPOSED, **over}))


def test_a_proposed_kind_cites_only_what_the_dossier_showed():
    review = ExpertReview.from_mapping(_raw(proposed_kind={**PROPOSED, "evidence": ["evt_unseen"]}))
    assert UNKNOWN_EVIDENCE in validate(review, CATALOGUE).reasons
    counted = ExpertReview.from_mapping(_raw(proposed_kind={**PROPOSED,
                                                            "why": "it wrote 17 cheques"}))
    assert NUMBER_NOT_IN_DOSSIER in validate(counted, CATALOGUE).reasons


def test_numbers_compare_by_value_not_spelling():
    assert number_tokens("1,400 calls, 2.50 days, on 07 Oct 2026") == {"1400", "2.5", "7", "2026"}
    assert number_tokens("version 1.5.1") == {"1", "5"}
    assert number_tokens("0.50 of it") == {"0.5"}
    assert number_tokens("on 7,8 and 9 Oct, 1,400.50 in all") == {"7", "8", "9", "1400.5"}
    assert number_tokens("forty days") == frozenset()            # words are not read — digits are
    assert number_tokens(None) == frozenset()


def test_a_number_the_dossier_holds_passes_whatever_its_spelling():
    review = ExpertReview.from_mapping(_raw(draft="Hi Neel — our call on 08 Oct; it has been 40.0 days."))
    assert validate(review, CATALOGUE).ok


def test_no_stage_is_fine_when_the_file_has_no_playbook():
    review = ExpertReview.from_mapping(_raw(expected_vs_actual={"expected": "a reply", "actual": "none"}))
    assert review.expected_vs_actual.stage is None
    assert validate(review, DossierCatalogue(CATALOGUE.evidence_ids, CATALOGUE.numbers, ())).ok


def test_a_stage_is_refused_when_the_file_has_no_playbook():
    review = ExpertReview.from_mapping(_raw())
    result = validate(review, DossierCatalogue(CATALOGUE.evidence_ids, CATALOGUE.numbers, ()))
    assert result.reasons == (UNKNOWN_STAGE,)


# ── STEP-13 · the second version: what the check reads ───────────────────────────────────────────
ASKED = DossierCatalogue(evidence_ids=CATALOGUE.evidence_ids | {"loop:ask_deck"},
                         numbers=CATALOGUE.numbers, stages=CATALOGUE.stages)
SECOND = {"rests_on": ["fact:1"], "to": "Neel", "answers": "loop:ask_deck"}


def _second(**move) -> dict:
    facts = [{"claim": "Neel wrote on 27 Sep asking for a first call", "evidence": ["evt_neel_0927"],
              "quote": "Could we find thirty minutes for a first call?"},
             {"claim": "The call is booked for 8 Oct", "evidence": ["evt_invite_1008"]}]
    return _raw(facts=facts, next_move={"who": "you", "what": "send a one-page pre-read",
                                        "for_whom": "Neel", "by_when": "2026-10-07",
                                        **SECOND, **move})


def test_a_move_names_what_it_rests_on_whom_its_draft_goes_to_and_the_ask_it_answers():
    review = ExpertReview.from_mapping(_second())
    move = review.next_move
    assert (move.rests_on, move.to, move.answers) == (("fact:1",), "Neel", "loop:ask_deck")
    assert review.facts[0].quote == "Could we find thirty minutes for a first call?"
    assert review.facts[1].quote is None
    assert validate(review, ASKED).ok
    again = ExpertReview.from_mapping(review.as_mapping())
    assert again == review and again.as_mapping() == review.as_mapping()


def test_a_first_version_answer_reads_validates_and_is_stored_as_before():
    review = ExpertReview.from_mapping(_raw())
    move = review.next_move
    assert (move.rests_on, move.to, move.answers) == ((), None, None)
    assert all(f.quote is None for f in review.facts)
    assert validate(review, CATALOGUE).ok
    stored = review.as_mapping()
    assert set(stored["next_move"]) == {"who", "what", "for_whom", "by_when"}
    assert all(set(f) == {"claim", "evidence"} for f in stored["facts"])


@pytest.mark.parametrize("move, refusal", [
    ({"rests_on": ["fact:3"]}, UNGROUNDED_MOVE),                 # the review has two facts
    ({"rests_on": ["fact:0"]}, UNGROUNDED_MOVE),
    ({"rests_on": ["evt_neel_0927"]}, UNGROUNDED_MOVE),          # a mail is no fact of the review
    ({"rests_on": ["inference:9"]}, UNGROUNDED_MOVE),            # the review has one inference
    ({"rests_on": ["inference:0"]}, UNGROUNDED_MOVE),
    ({"answers": "loop:never_shown"}, UNKNOWN_EVIDENCE),
    # ⛔ RESTATED by M35.C1.L-contract.V0.U04 (crosscheck X15): an `answers` that is no ask — a mail, a
    # promise — was `ungrounded_move`, which the review run refuses WHOLE (`verify.STRUCTURAL`) over one
    # optional field. It is named as an unshown ask is, and the check drops only that line.
    ({"answers": "evt_neel_0927"}, UNKNOWN_EVIDENCE),            # a mail is no ask
    ({"answers": "promise:p1"}, UNKNOWN_EVIDENCE),
    ({"rests_on": ["fact:1", "evt_neel_0927"]}, UNKNOWN_EVIDENCE),   # a stray beside a fact it names
])
def test_a_move_resting_on_nothing_or_answering_no_ask_is_named(move, refusal):
    result = validate(ExpertReview.from_mapping(_second(**move)), ASKED)
    assert not result.ok and result.reasons == (refusal,), result.problems


def test_an_ask_named_by_a_move_is_held_to_the_dossier_shown():
    review = ExpertReview.from_mapping(_second())
    assert validate(review, CATALOGUE).reasons == (UNKNOWN_EVIDENCE,)


def test_a_quote_and_a_recipient_are_not_read_for_numbers():
    """The check holds a quote and a recipient to the mail itself; neither is a text the review writes."""
    review = ExpertReview.from_mapping(_second(to="neel2@fund.test"))
    facts = [{"claim": "Neel wrote", "evidence": ["evt_neel_0927"], "quote": "we closed 14 deals in 2025"},
             {"claim": "The call is booked for 8 Oct", "evidence": ["evt_invite_1008"]}]
    quoted = ExpertReview.from_mapping({**_second(), "facts": facts})
    for r in (review, quoted):
        assert validate(r, ASKED).ok
        assert not {"neel2@fund.test", "we closed 14 deals in 2025"} & set(r.texts())


@pytest.mark.parametrize("move, says", [
    ({"rests_on": "fact:1"}, "what the next move rests on"),
    ({"to": ["Neel"]}, "whom the draft goes to"),
    ({"answers": {"loop": "ask_deck"}}, "the ask the next move answers"),
])
def test_a_malformed_second_version_field_is_a_value_error_that_says_what(move, says):
    with pytest.raises(ValueError, match=says):
        ExpertReview.from_mapping(_second(**move))


def test_a_malformed_quote_is_a_value_error():
    with pytest.raises(ValueError, match="a fact's quote"):
        ExpertReview.from_mapping(_raw(facts=[{"claim": "Neel wrote", "evidence": ["evt_neel_0927"],
                                               "quote": ["could we"]}]))


# ── STEP-13b · the third version: the expert's own, what a move is guided by ─────────────────────
ENGINE = DossierCatalogue(evidence_ids=ASKED.evidence_ids | {"pb:founder_office.heu.investors_do_not_chase",
                                                              "cap:founder_office.fundraising.investor_relations#f2"},
                          numbers=CATALOGUE.numbers, stages=CATALOGUE.stages)
OWN = [{"kind": "practice", "claim": "A fund that likes a first call and goes quiet has usually decided",
        "why": "funds say yes quickly and no by silence"},
       {"kind": "base_rate", "claim": "Most first calls with a fund lead nowhere", "why": "selection"}]


def _third(**over) -> dict:
    raw = _second(**{k: over.pop(k) for k in ("rests_on", "guided_by") if k in over})
    raw.update({"own": OWN}, **over)
    return raw


def test_an_own_line_is_a_kind_a_claim_and_why():
    review = ExpertReview.from_mapping(_third())
    assert [(o.kind, o.claim, o.why) for o in review.own] == [
        ("practice", OWN[0]["claim"], OWN[0]["why"]), ("base_rate", OWN[1]["claim"], OWN[1]["why"])]
    assert OWN_KINDS == ("practice", "base_rate", "counter_pattern", "benchmark")


@pytest.mark.parametrize("own, says", [
    ([{"kind": "folklore", "claim": "x", "why": "y"}], "an own line's kind"),
    ([{"kind": "practice", "claim": "", "why": "y"}], "an own line's claim"),
    ([{"kind": "practice", "claim": "x", "why": ""}], "why an own line holds"),
    ("practice", "own"),
])
def test_a_malformed_own_line_is_a_value_error_that_says_what(own, says):
    with pytest.raises(ValueError, match=says):
        ExpertReview.from_mapping(_third(own=own))


def test_an_inference_or_pattern_may_rest_on_an_engine_id_and_an_own_line():
    over = {"inferences": [{"claim": "a fund goes quiet when it decides",
                            "based_on": ["fact:1", "own:1", "pb:founder_office.heu.investors_do_not_chase"]}],
            "patterns": [{"kind": "pattern", "claim": "investors do not chase",
                          "based_on": ["cap:founder_office.fundraising.investor_relations#f2", "own:2"]}]}
    assert validate(ExpertReview.from_mapping(_third(**over)), ENGINE).ok


@pytest.mark.parametrize("based_on, refusal", [
    (["own:3"], UNKNOWN_EVIDENCE),                    # the review has two own lines
    (["own:0"], UNKNOWN_EVIDENCE),
    (["pb:never_printed"], UNKNOWN_EVIDENCE),         # an engine id the dossier never showed
    (["cap:x.y.z#q"], UNKNOWN_EVIDENCE),
])
def test_an_own_line_past_the_list_and_an_unprinted_engine_id_are_named_as_an_unprinted_id_is(
        based_on, refusal):
    over = {"inferences": [{"claim": "a fund goes quiet", "based_on": ["fact:1", *based_on]}]}
    result = validate(ExpertReview.from_mapping(_third(**over)), ENGINE)
    assert result.reasons == (refusal,), result.problems


def test_a_move_may_rest_on_an_inference_and_is_guided_by_engine_or_own_lines():
    over = {"inferences": [{"claim": "a fund goes quiet when it decides", "based_on": ["fact:1"]}],
            "rests_on": ["fact:1", "inference:1"],
            "guided_by": ["pb:founder_office.heu.investors_do_not_chase", "own:1"]}
    review = ExpertReview.from_mapping(_third(**over))
    assert review.next_move.guided_by == ("pb:founder_office.heu.investors_do_not_chase", "own:1")
    assert validate(review, ENGINE).ok
    assert ExpertReview.from_mapping(review.as_mapping()) == review


@pytest.mark.parametrize("guided_by", [["own:5"], ["pb:never_printed"], ["fact:1"]])
def test_a_move_guided_by_what_is_not_there_is_named_not_refused_whole(guided_by):
    result = validate(ExpertReview.from_mapping(_third(guided_by=guided_by)), ENGINE)
    assert result.reasons == (UNKNOWN_EVIDENCE,), result.problems


def test_a_move_resting_only_on_an_inference_that_does_not_exist_is_still_no_move():
    result = validate(ExpertReview.from_mapping(_third(rests_on=["inference:2"])), ENGINE)
    assert result.reasons == (UNGROUNDED_MOVE,)


def test_what_an_own_line_writes_is_read_for_numbers():
    own = [{"kind": "base_rate", "claim": "9 in 10 first calls lead nowhere", "why": "selection"}]
    review = ExpertReview.from_mapping(_third(own=own))
    assert "9 in 10 first calls lead nowhere" in review.texts() and "selection" in review.texts()
    assert validate(review, ENGINE).reasons == (NUMBER_NOT_IN_DOSSIER,)


def test_a_second_version_answer_reads_validates_and_is_stored_as_before():
    review = ExpertReview.from_mapping(_second())
    assert review.own == () and review.next_move.guided_by == ()
    stored = review.as_mapping()
    assert "own" not in stored and "guided_by" not in stored["next_move"]
    assert validate(review, ASKED).ok
