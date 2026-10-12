"""STEP-13 · a held file asks you its one question — and a decision retires it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_a_held_file_asks.py

Tree `yc2_w27_s13` M36.C2.L-integration.V2.U03 (`reason/domain_shadow`; STEP-13 §8.4 item 7, `06` D60, `03`
F184). A covered file decided INSUFFICIENT on its answer — its review's move held by the check, or a review
that must find out first — files its question (`context/founder_questions`, by the run that asked it) and
its question signal: the Investigation lane, bound to that run, no candidate, authorised as a question
(`reason/authority.QUESTION_SIGNAL_PREDICATE`) and never as a decision. The same question asked again is
the one already open — its signal re-bound to the run that asks it now, never rebuilt; a new question
replaces the old one, its card with it; any other decision retires the file's question and its signal.
The shadow lane asks nothing.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import founder_questions as Q
from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.authority import QUESTION_SIGNAL_JOINS, QUESTION_SIGNAL_PREDICATE
from genios_engine.reason.expert import store as R
from tests.reason.expert.checks import as_written
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _authoritative, _compile, _fund, _open_signals, _review, world)
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

pytestmark = pytest.mark.pg

FIND_OUT = "Did Arjun ask for last quarter's metrics or this quarter's?"
HELD_Q = "Is it so: “Arjun asked for the deck and the quarter's metrics”? It is not in what it cites."


def _write(store, org, file_id, fingerprint, events, *, checked=None, **over):
    review = ExpertReview.from_mapping(_review(sorted(events)[0], **over))
    with store.engine.begin() as c:
        assert R.write_review(c, org_id=org, file_id=file_id, fingerprint=fingerprint, model="claude-sonnet-5",
                              prompt_version="expert-review.v3", dossier_digest="d" * 64, status=R.VALID,
                              reason=None, review=review, input_tokens=10, output_tokens=10, cost_micro_usd=1,
                              at=NOW, inputs={"events": sorted(events), "booked": []},
                              triggers=[{"kind": "first_look", "says": "never judged"}],
                              checked=checked or as_written(review))
    return review


def _find_out(store, org, anchor, fp, events, question=FIND_OUT):
    return _write(store, org, anchor, fp, events, mode="find_out", draft=None,
                  next_move={"who": "you", "what": question, "for_whom": "Arjun", "by_when": None})


def _held(review) -> C.CheckedReview:
    shown = as_written(review)
    return C.CheckedReview(verdicts=(C.LineVerdict("fact:1", C.DROPPED, C.MISQUOTED, "the deck"),),
                           fate=C.HELD, cited=(), question=HELD_Q, because="misquoted (fact 1)",
                           words=C.CardWords(None, shown.words.situation, shown.words.done_when, None, None))


def _questions(store, org, file_id):
    with store.engine.connect() as c:
        return c.execute(text("select question_id, question, why, state, run_id, retired_why from "
                              "founder_questions where org_id = :o and file_id = :f order by asked_at, "
                              "question_id"), {"o": org, "f": file_id}).all()


def _asking(store, org, at=NOW) -> list[str]:
    with store.engine.connect() as c:
        return [r[0] for r in c.execute(text(
            "select s.signal_id from signals s " + QUESTION_SIGNAL_JOINS +
            " where s.org_id = :o and s.status = 'open' and " + QUESTION_SIGNAL_PREDICATE),
            {"o": org, "authority_time": at})]


def test_a_file_that_must_find_out_first_asks_you_its_question(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    assert counts.get("expert_question_asked") == 1, counts
    assert counts.get("needs_refused") == 1, "the needs queue is read once a pass — and, unwired, refuses"
    [q] = _questions(store, org, anchor)
    assert (q.question, q.state) == (FIND_OUT, Q.OPEN) and q.run_id
    [signal] = _open_signals(store, org, anchor)
    assert (signal.rule_id, signal.output_lane, signal.reasoning_run_id) == (
        "founder_question", "investigation", q.run_id)
    assert _asking(store, org) == [signal.signal_id]
    assert _authoritative(store, org, NOW) == set(), "never a decision: it selects no move"


def test_a_held_review_asks_the_question_its_check_asked(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    review = ExpertReview.from_mapping(_review(sorted(events)[0]))
    _write(store, org, anchor, "ffp-fund-held-review-00000", events, checked=_held(review))
    _compile(store, org, registry, covered={anchor: "ffp-fund-held-review-00000"})
    [q] = _questions(store, org, anchor)
    assert (q.question, q.why, q.state) == (HELD_Q, "misquoted (fact 1)", Q.OPEN)
    assert len(_asking(store, org)) == 1


def test_the_same_question_asked_again_is_rebound_never_rebuilt(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    covered = {anchor: "ffp-fund-findout-review-000"}
    _compile(store, org, registry, covered=covered)
    [first] = _open_signals(store, org, anchor)
    with store.engine.begin() as c:            # the gate has no memory of it: decided again
        c.execute(text("delete from reasoning_fingerprints where org_id = :o"), {"o": org})
    again = _compile(store, org, registry, covered=covered, at=NOW + timedelta(hours=30))
    assert again.get("expert_question_standing") == 1, again
    [q] = _questions(store, org, anchor)
    [now] = _open_signals(store, org, anchor)
    assert now.signal_id == first.signal_id, "its card is not torn down and rebuilt"
    assert now.reasoning_run_id == q.run_id != first.reasoning_run_id, "re-bound to the run asking now"
    assert _asking(store, org, at=NOW + timedelta(hours=30)) == [first.signal_id]


def test_a_new_question_replaces_the_old_one_and_its_card(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    [old_signal] = _open_signals(store, org, anchor)
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question="Who at the fund decides?")
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"},
             at=NOW + timedelta(hours=1))
    old, new = _questions(store, org, anchor)
    assert (old.state, old.retired_why) == (Q.RETIRED, Q.REPLACED) and new.state == Q.OPEN
    [signal] = _open_signals(store, org, anchor)
    assert signal.signal_id != old_signal.signal_id and _asking(store, org, at=NOW + timedelta(hours=1)) == [
        signal.signal_id]


def test_a_decision_retires_the_files_question(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    _write(store, org, anchor, "ffp-fund-act-review-000000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"},
                      at=NOW + timedelta(hours=1))
    assert counts.get("expert_question_retired") == 1, counts
    [q] = _questions(store, org, anchor)
    assert (q.state, q.retired_why) == (Q.RETIRED, Q.NO_LONGER_ASKED)
    assert [s.rule_id for s in _open_signals(store, org, anchor)] == ["file_review"], "the decision's own"
    assert _asking(store, org, at=NOW + timedelta(hours=1)) == []


def test_on_the_shadow_lane_nothing_is_asked(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"}, live=False)
    assert _questions(store, org, anchor) == [] and _open_signals(store, org, anchor) == []
