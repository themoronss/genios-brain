"""A bare id the model cites is the id the dossier printed (`reason/expert/verify.printed_ids`).

    pytest tests/reason/expert/test_printed_ids.py -q

A dossier prints a reference with its kind — `[sig:sig_3cb1…]`, `[node:node_b40a…]`, `[sit:sit_23c1…]` — and the id
after the colon already names its kind, so a live model cites `sig_3cb1…`. Every such fact dropped as
`unknown_evidence` and held its card: on the design partner's 24 stored judgments (23 Oct) 112 of 182 such drops (62%)
were exactly this. Pure tests here; the two call sites (the L2 judge and the expert review) are pinned beside their own
tests.
"""
from __future__ import annotations

import pytest

from genios_engine.reason.expert.verify import printed_ids

pytestmark = pytest.mark.unit

PRINTED = {"sig:sig_3cb1", "node:node_b40a", "sit:sit_23c1", "loop:loop_73d7", "evt_4b8d", "num:days_quiet"}


def test_a_bare_id_becomes_the_printed_one_wherever_the_answer_cites_it():
    answer = {"facts": [{"claim": "Priya asked for the link", "evidence": ["sig_3cb1", "evt_4b8d"]},
                        {"claim": "Arjun works at Acme", "evidence": ["node_b40a"]}],
              "inferences": [{"claim": "the move is ours", "based_on": ["fact:1", "sit_23c1"]}],
              "next_move": {"who": "you", "what": "book the call", "answers": "loop_73d7", "rests_on": ["fact:1"]}}
    out = printed_ids(answer, PRINTED)
    assert out["facts"][0]["evidence"] == ["sig:sig_3cb1", "evt_4b8d"]
    assert out["facts"][1]["evidence"] == ["node:node_b40a"]
    assert out["inferences"][0]["based_on"] == ["fact:1", "sit:sit_23c1"]
    assert out["next_move"]["answers"] == "loop:loop_73d7"
    assert out["next_move"]["rests_on"] == ["fact:1"]                    # not an id the dossier printed


def test_no_sentence_moves_and_the_answer_given_is_untouched():
    answer = {"facts": [{"claim": "sig_3cb1 was the signal", "quote": "Please resend the link.",
                         "evidence": ["sig_3cb1"]}]}
    out = printed_ids(answer, PRINTED)
    assert out["facts"][0]["claim"] == "sig_3cb1 was the signal"         # only a string that IS an id moves
    assert out["facts"][0]["quote"] == "Please resend the link."
    assert answer["facts"][0]["evidence"] == ["sig_3cb1"]                 # a copy; the model's answer is kept as given


def test_an_id_printed_as_it_is_and_one_printed_twice_are_left_alone():
    printed = {"sig:evt_1", "evt_1", "node:x_9", "card:x_9"}
    answer = {"facts": [{"claim": "c", "evidence": ["evt_1", "x_9"]}]}
    out = printed_ids(answer, printed)
    assert out["facts"][0]["evidence"] == ["evt_1", "x_9"]               # printed bare; ambiguous tail


def test_an_answer_already_in_printed_ids_is_the_same_answer():
    answer = {"facts": [{"claim": "c", "evidence": ["sig:sig_3cb1"]}]}
    assert printed_ids(answer, PRINTED) == answer
    assert printed_ids(printed_ids(answer, PRINTED), PRINTED) == answer
