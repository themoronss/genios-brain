"""STEP-14 fix · a renewal is never stopped by the day's publication cap — the card it keeps does not lapse.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_renewal_is_never_capped.py -q

Tree `yc2_w27_s14` M42.C2.L-integration.V2.U07 (fix of M42.C2.L-logic.V0.U01 / M42.C2.L-integration.V2.U02; the
STEP-14 crosscheck, finding 11). A standing decision is decided again in its last twelve hours (`FILE_RENEW_MARGIN`)
"so the same advice renews the card instead of a lapse" — and the renewal, a decision WITH a move, was held to the
day's cap (`domain_shadow._decide_covered_files`): on a day whose cap was spent it was `budget_exhausted`, nothing
renewed, and the card lapsed at its window — the lapse the margin exists to prevent. A renewal publishes nothing new
(a quiet version, s14-D1): the same advice re-emitted inside the margin is not held to the cap, and spends none of
this pass's allowance. The bound, declared: its signal is still a signal written today, so `runner._budget_used`
counts it for the passes after — one renewal per file per window.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import pipeline
from genios_engine.deliver.store import CardStore
from genios_engine.reason.change_gate import FILE_RENEW_MARGIN
from genios_engine.reason.expert import decide as expert
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _write, admitted, world)
from tests.reason.expert.test_a_file_keeps_one_decision import FIRST, OTHER_MOVE, SECOND

pytestmark = pytest.mark.pg

INSIDE = NOW + timedelta(hours=expert.EXPIRY_HOURS) - FILE_RENEW_MARGIN + timedelta(hours=6)


def _spend_the_day(store, org, at):
    with store.engine.begin() as c:          # the day's cap already spent by other publications that day
        for n in range(60):
            c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
                           "eval_time, status, created_at) values (:s, :o, 'other_rule', :n, 50, 'other_rule', :t, "
                           "'expired', :t)"), {"s": f"sig_cap_{org}_{n}", "o": org, "n": f"node_other_{n}", "t": at})


def _first(world):
    store, org, registry, _ = world
    cards = CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    return store, org, registry, cards, anchor, events


def _card(store, org):
    with store.engine.connect() as c:
        return c.execute(text("select card_id, state, version from cards where org_id = :o"), {"o": org}).one()


def test_a_renewal_on_a_spent_day_still_renews_its_card(world):
    store, org, registry, cards, anchor, _events = _first(world)
    first = _card(store, org)
    _spend_the_day(store, org, INSIDE)
    counts = _compile(store, org, registry, covered={anchor: FIRST}, at=INSIDE)
    assert counts.get("expert_emitted") == 1 and not counts.get("budget_exhausted"), counts
    built = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=INSIDE)
    assert (built["versioned"], built["renewed"]) == (1, 1), built
    cards.sweep_lifecycle(eval_time=NOW + timedelta(hours=expert.EXPIRY_HOURS, minutes=1))
    assert tuple(_card(store, org)) == (first.card_id, first.state, 2), "renewed: no lapse at the old window"


def test_new_advice_on_a_spent_day_is_still_held_to_the_cap(world):
    """⛔ THE NEGATIVE CONTROL: other advice is a publication — the spent cap holds it, as before."""
    store, org, registry, _cards, anchor, events = _first(world)
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    _spend_the_day(store, org, INSIDE)
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=INSIDE)
    assert counts.get("budget_exhausted") == 1 and not counts.get("expert_emitted"), counts


def test_a_renewal_spends_none_of_the_passs_allowance(world, monkeypatch):
    """The day has room for ONE more publication. The file decided first in the pass (files go in id order) renews;
    the other gives new advice — and both go out: the renewal took none of the room."""
    from genios_engine.reason import domain_shadow
    from tests.reason.expert.test_a_held_file_asks import _other_file
    store, org, registry, _ = world
    cards = CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    anchor, _situations, events = _fund(store, org)
    other, other_events = _other_file(store, org)
    files = {anchor: (FIRST, events), other: ("ffp-programme-review-0000", other_events)}
    for file_id, (fp, evs) in files.items():
        _write(store, org, file_id, fp, evs)
    _compile(store, org, registry, covered={f: fp for f, (fp, _e) in files.items()})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    renews, moves = sorted(files)
    _write(store, org, moves, "ffp-other-advice-review-01", files[moves][1],
           next_move={**OTHER_MOVE, "what": "Ask the programme when its next intake opens"})
    monkeypatch.setattr(domain_shadow, "_daily_allowance", lambda *_a, **_k: 1)
    counts = _compile(store, org, registry, covered={renews: files[renews][0], moves: "ffp-other-advice-review-01"},
                      at=INSIDE)
    assert counts.get("budget_allowance") == 1 and counts.get("expert_emitted") == 2, counts
    assert not counts.get("budget_exhausted"), counts


def test_the_same_advice_in_a_new_review_inside_the_margin_is_a_renewal_too(world):
    store, org, registry, _cards, anchor, events = _first(world)
    _write(store, org, anchor, SECOND, events,
           frames={"primary": "a fund two days from its partner meeting", "rivals": ["a check-in"]})
    _spend_the_day(store, org, INSIDE)
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=INSIDE)
    assert counts.get("expert_emitted") == 1 and not counts.get("budget_exhausted"), counts


def test_the_same_advice_after_its_window_is_a_publication_again(world):
    """⛔ THE NEGATIVE CONTROL for the window: once the decision's authority lapsed, the same advice is published anew —
    held to the cap like any."""
    store, org, registry, _cards, anchor, _events = _first(world)
    after = NOW + timedelta(hours=expert.EXPIRY_HOURS, minutes=30)
    _spend_the_day(store, org, after)
    counts = _compile(store, org, registry, covered={anchor: FIRST}, at=after)
    assert counts.get("budget_exhausted") == 1 and not counts.get("expert_emitted"), counts
