"""STEP-01's promise, held: every founder case says what must never appear.

    pytest tests/replays/test_every_case_forbids_something.py -q

`yc2_w27_align` M34.C1.L-data.V0.U04. STEP-01 §3.1 wrote that a case carries "forbidden names and
phrases"; 25 of the 47 cases carried none (`10-BEFORE-STEP-12.md` §2), and three new ones would have
joined them. A case that forbids nothing passes whatever a card says beside the subject it expects —
an invented number, the connector as the person to reply to, a chase for something already sent. Each
case now names what its own shape makes wrong, and a new case cannot ship without it.
"""
from __future__ import annotations

import pytest

from tests.replays.founder_case import load_cases

CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_every_case_forbids_something(case):
    assert case.forbidden_names or case.forbidden_phrases, (
        f"{case.case_id} ({case.title}) forbids nothing: name what its own shape makes wrong — a wrong "
        "subject, an invented number, a state the evidence contradicts")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_a_forbidden_term_is_never_what_the_case_expects(case):
    """A term a card must carry, or the subject a card must be about, cannot also be forbidden — the
    case would fail on its own right answer."""
    wanted = {t.lower() for e in case.cards for t in e.mentions}
    wanted |= {t.lower() for e in case.cards if e.min >= 1 for t in e.about}
    clash = [t for t in (*case.forbidden_names, *case.forbidden_phrases) if t.lower() in wanted]
    assert not clash, f"{case.case_id}: {clash} is both expected and forbidden"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_a_forbidden_term_says_something(case):
    """Blank or one-letter terms match everything or nothing — either way they hold no claim."""
    short = [t for t in (*case.forbidden_names, *case.forbidden_phrases) if len(t.strip()) < 3]
    assert not short, f"{case.case_id}: forbidden terms too short to be a claim: {short}"
