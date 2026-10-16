"""The narrator is shown a card's facts in one order, whatever order they were loaded in.

    pytest tests/deliver/test_the_narrator_sees_its_facts_in_one_order.py -q

⛔ WHAT WAS WRONG. `render._prompt` wrote the card's facts — and its known values — with
`json.dumps` in dict insertion order, which is the order the rows came back from the database and
the order the history facts were merged in. The same situation therefore built a different prompt
from one run to the next: a model asked twice about one thing was asked two different questions,
and a golden case's recorded answer could not be replayed (found driving F13, yc2_w27/M19). The
keys are sorted now; what the model is told is unchanged.
"""
from __future__ import annotations

from genios_engine.deliver.render import _prompt

FACTS = {"thread.ball_in_court": {"value": "us"},
         "derived.history.times_seen": {"value": 1},
         "deal.last_inbound": {"value": "2026-08-08T06:30:00+00:00"},
         "derived.anomaly.x": {"value": {"series": {"unit": "count", "metric": "x"}, "flagged": False}}}
SLOTS = {"who": "tuskercap.test", "entity": "tuskercap.test", "ball": "us"}
TEMPLATE = {"artifact_kind": "draft"}


def test_two_insertion_orders_build_one_prompt():
    forward = _prompt("account_admin", TEMPLATE, dict(FACTS), dict(SLOTS))
    backward = _prompt("account_admin", TEMPLATE, dict(reversed(list(FACTS.items()))),
                       dict(reversed(list(SLOTS.items()))))
    assert forward == backward


def test_every_fact_is_still_shown():
    prompt = _prompt("account_admin", TEMPLATE, dict(FACTS), dict(SLOTS))
    for key in FACTS:
        assert f'"{key}"' in prompt, key


# ── STEP-14 · the narrator writes as the founder's chief of staff (`yc2_w27_s14` M43.C5.L-interface.V0.U01, s14-F17) ──
#
# Only a card no review wrote is narrated (an expert's card speaks its review, `render.review_copy`). The narrator was
# told it wrote *"for a salesperson"*, and its headline examples were the founder's real investors and contacts —
# Titan Capital, Divyanshu, Leslie — in a prompt sent for every tenant. It writes to the founder, as "you", and its
# examples are the golden set's invented names.

def _narrator_prompt(absence: bool = False) -> str:
    template = {"artifact_kind": "draft", "fallback": {"states_absence": absence}}
    return _prompt("account_admin", template, dict(FACTS), dict(SLOTS))


def test_the_narrator_is_the_founders_chief_of_staff_writing_to_you():
    prompt = _narrator_prompt()
    assert prompt.startswith("You are the founder's chief of staff, writing ONE card"), prompt[:80]
    assert 'as "you"' in prompt
    assert "salesperson" not in prompt.lower()


def test_no_real_name_reaches_the_narrator():
    from tests.replays.founder_case import real_names_in
    for absence in (False, True):
        assert real_names_in(_narrator_prompt(absence)) == [], absence


def test_its_examples_are_the_golden_sets_invented_names():
    prompt = _narrator_prompt()
    for example in ("Send Kestrel Capital the data-room link", "Answer Meera Shah's question on the pilot fee",
                    "Get Divya Raman's free slots for Thursday"):
        assert example in prompt, example
