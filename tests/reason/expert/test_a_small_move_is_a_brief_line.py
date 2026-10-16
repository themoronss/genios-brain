"""STEP-15 · a small move is a line in your brief, never a card (s15-D3, `06` D66).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_small_move_is_a_brief_line.py -q

Tree `yc2_w27_s15` M45.C4.L-integration.V0.U03 (`reason/domain_shadow._decide_covered_files`, `reason/expert/small_move`).
`06` D66, answered 12 Oct: a move the expert appraised LOW stakes and LOW urgency — F20's meetup on 27 Sep, F23's
registration complete; 2 of 94 authored reviews — is a line in the morning brief and no card. It is decided as before:
the audited run is persisted, the file's decision made and remembered (the change gate skips the same review while it
stands). It emits no signal, so delivery has nothing to build a card from; and a file whose earlier, bigger move had a
signal and a card has them cleared, the way any review that no longer names a move clears them (F175). The day's card
budget is a budget for cards: a small move spends none of it and is never held back by it.

The world is STEP-12's (`test_a_covered_file_decides_once`): a founder with a fund's mail, the Founder Office on.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert import small_move
from tests.reason.expert.checks import as_written
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _open_signals, _review, _write, admitted, world)
from tests.reason.expert.test_a_file_hands_its_card_on import _cards, _carded, _signal_status
from tests.reason.expert.test_a_file_keeps_one_decision import expiries  # noqa: F401 — a fixture

SMALL = {"stakes": "low", "urgency": "low", "reversibility": "reversible", "reasons": ["a meetup nothing hangs on"]}
A, B = "ffp-small-a-0000000000000", "ffp-small-b-0000000000000"


def _appraised(stakes: str, urgency: str) -> dict:
    return {**SMALL, "stakes": stakes, "urgency": urgency}


# ── the predicate, pure ─────────────────────────────────────────────────────────────────────────
def _stored(*, check=None, **over):
    from genios_engine.contracts.expert_review import ExpertReview
    from genios_engine.reason.expert import store as R
    review = ExpertReview.from_mapping(_review("evt_small", **over))
    checked = check(as_written(review)) if check is not None else as_written(review)
    return R.StoredReview(file_id="node_f", fingerprint="ffp-0123456789abcdef01234567", model="m", prompt_version="p",
                          dossier_digest="d" * 64, status=R.VALID, reason=None, review=review, raw=None,
                          input_tokens=1, output_tokens=1, cost_micro_usd=1, reviewed_at=NOW, checked=checked)


@pytest.mark.parametrize("stakes, urgency, small", [
    ("low", "low", True), ("low", "medium", False), ("medium", "low", False), ("low", "high", False),
    ("high", "low", False), ("medium", "medium", False), ("high", "high", False)])
def test_a_small_move_is_an_act_appraised_low_stakes_and_low_urgency(stakes, urgency, small):
    assert small_move.is_small_move(_stored(appraisal=_appraised(stakes, urgency))) is small


def test_a_low_low_move_that_writes_to_someone_stays_a_card():
    """03 s15-F24: F61's two silent introductions (STEP-14, replay 02 m02) are appraised low/low and labelled a card
    each — a card puts a draft to a person in front of you, and these have one. D66's words alone took them."""
    writes = {"who": "You", "what": "Write to Omkar Joshi offering a call", "for_whom": "Omkar Joshi at Redfern Labs",
              "by_when": None, "to": "Omkar Joshi"}
    assert small_move.is_small_move(_stored(appraisal=SMALL, next_move=writes)) is False
    assert small_move.is_small_move(_stored(appraisal=SMALL, next_move={**writes, "to": None})) is True


@pytest.mark.parametrize("over", [{"mode": "wait", "next_move": None}, {"mode": "nothing", "next_move": None},
                                  {"mode": "find_out"}, {"mode": "blocked", "next_move": None}],
                         ids=["wait", "nothing", "find_out", "blocked"])
def test_only_an_act_review_is_a_small_move(over):
    assert small_move.is_small_move(_stored(appraisal=SMALL, **over)) is False


@pytest.mark.parametrize("fate", [C.HELD, C.SUPPRESSED])
def test_a_move_the_check_held_or_suppressed_is_not_an_act_so_not_a_small_move(fate):
    check = lambda c: replace(c, fate=fate, because="answered", question="Is it still open?")      # noqa: E731
    assert small_move.is_small_move(_stored(appraisal=SMALL, check=check)) is False


def test_a_review_with_no_check_or_no_review_is_not_a_small_move():
    unchecked = replace(_stored(appraisal=SMALL), checked=None)
    refused = replace(_stored(appraisal=SMALL), review=None)
    assert small_move.is_small_move(unchecked) is False and small_move.is_small_move(refused) is False


# ── the pass ────────────────────────────────────────────────────────────────────────────────────
def _runs(store, org):
    with store.engine.connect() as c:
        return c.execute(text(
            "select o.outcome_kind from reasoning_runs r join reasoning_run_outputs o "
            "  on o.org_id = r.org_id and o.run_id = r.run_id "
            " where r.org_id = :o and r.capability_id = 'expert.file_review' order by r.run_id"),
            {"o": org}).scalars().all()


def _remembered(store, org):
    with store.engine.connect() as c:
        return c.execute(text("select outcome from reasoning_fingerprints where org_id = :o "
                              "and subject_key like '%|expert.file_review'"), {"o": org}).scalars().all()


def test_a_small_move_is_decided_as_before_and_emits_no_signal(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, A, events, appraisal=SMALL)
    counts = _compile(store, org, registry, covered={anchor: A})
    assert counts["expert_decided"] == 1 and counts["expert_small_move"] == 1, counts
    assert "expert_emitted" not in counts and _open_signals(store, org, anchor) == []
    assert _runs(store, org) == ["decision"], "decided as before: the audited run stands, an act's outcome a decision"
    assert _remembered(store, org) == ["suppressed"]
    again = _compile(store, org, registry, covered={anchor: A})
    assert again["expert_unchanged"] == 1 and "expert_small_move" not in again, "the same review is not decided twice"


@pytest.mark.parametrize("stakes, urgency", [("medium", "low"), ("low", "medium"), ("high", "low"), ("low", "high")])
def test_a_move_that_is_not_both_low_is_a_card_as_before(world, stakes, urgency):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, A, events, appraisal=_appraised(stakes, urgency))
    counts = _compile(store, org, registry, covered={anchor: A})
    assert counts.get("expert_emitted") == 1 and "expert_small_move" not in counts, counts
    assert len(_open_signals(store, org, anchor)) == 1


@pytest.mark.parametrize("over", [{"mode": "wait", "next_move": None}, {"mode": "nothing", "next_move": None}],
                         ids=["wait", "nothing"])
def test_a_review_that_names_no_move_is_not_counted_a_small_one(world, over):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, A, events, appraisal=SMALL, **over)
    counts = _compile(store, org, registry, covered={anchor: A})
    assert "expert_small_move" not in counts and _open_signals(store, org, anchor) == [], counts


def test_a_small_move_after_a_bigger_one_clears_the_old_decision_and_its_card(world, expiries):
    """The file's earlier move had a signal and a card. The new review names a small one: no signal now, so the
    old decision is cleared (F175) — its card RULE_CLEARED, said — and never left standing beside the brief's line."""
    store, org, registry, _ = world
    anchor, events, first, card = _carded(store, org, registry)
    _write(store, org, anchor, B, events, appraisal=SMALL)
    counts = _compile(store, org, registry, covered={anchor: B}, at=NOW + timedelta(hours=6))
    assert counts.get("expert_small_move") == 1 and counts.get("expert_cleared") == 1, counts
    assert _open_signals(store, org, anchor) == [] and _signal_status(store, org, first.signal_id) == "expired"
    assert expiries == [("rule_cleared", (first.signal_id,))]
    assert [c.state for c in _cards(store, org)] == ["expired"]


def test_a_small_move_spends_none_of_the_card_budget_and_is_never_held_back_by_it(world, monkeypatch):
    from genios_engine.reason import domain_shadow
    store, org, registry, _ = world
    monkeypatch.setattr(domain_shadow, "_daily_allowance", lambda *a, **k: 0)          # today's cards are spent
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, A, events)                                               # high, high: held back
    held = _compile(store, org, registry, covered={anchor: A})
    assert held.get("budget_exhausted") == 1 and "expert_emitted" not in held, held
    _write(store, org, anchor, B, events, appraisal=SMALL)
    small = _compile(store, org, registry, covered={anchor: B}, at=NOW + timedelta(hours=1))
    assert small.get("expert_small_move") == 1 and "budget_exhausted" not in small, small
