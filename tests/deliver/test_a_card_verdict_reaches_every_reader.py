"""STEP-16 · the verdict you press on a card reaches every reader the extension's verdict always reached.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_a_card_verdict_reaches_every_reader.py

Tree `yc2_w27_s16` M46.C2.L-integration.V2.U03 (`deliver/actions.ingest_action`; `s16-F1`). ⛔ WHY. The dashboard's
button wrote `card_events` only, and eight of the nine verdict readers read the ledger the extension writes —
so the reason you gave on a card never reached the expert's dossier, its file fingerprint, the change gate,
the learning batch, the adaptive lease, a file's history facts, the counterfactual ledger or the receipt "a
human verdict has reached the loop". Now `run_play`, `do_it_myself` and `wrong` with its reason are recorded
through the one writer (`deliver/verdicts.record`), bound to the card's own authority, at the press's instant,
in the press's transaction — beside the card event, which stays. A deferral is no verdict; a card no
authority binds (a team or verify situation card) keeps its press and writes none.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import actions
from genios_engine.deliver import verdicts as V
from tests.reason.expert.test_a_covered_file_decides_once import NOW, world  # noqa: F401 — fixtures
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

pytestmark = pytest.mark.pg

AT = NOW + timedelta(minutes=5)
FOUNDER = "founder@meridian.test"


@pytest.fixture
def decided(world):
    """A covered file, decided by the expert: its one card, through the decision's own door."""
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the ledger and the authority it binds are Postgres's")
    from genios_engine.deliver.store import CardStore
    from tests.deliver.test_a_question_card import _build, _cards
    from tests.reason.expert.test_a_covered_file_decides_once import _compile, _fund
    from tests.reason.expert.test_a_covered_file_decides_once import _write as _write_act
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write_act(store, org, anchor, "ffp-fund-act-review-000000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"})
    _build(store, CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]), org)
    [card] = _cards(store, org)
    return store, org, anchor, card


def _press(store, org, card, action, **kw):
    return actions.ingest_action(card_store=None, graph=store, org_id=org, card_id=card.card_id, actor=FOUNDER,
                                 action=action, eval_time=AT, allow_any_assignee=True, **kw)


def _ledger(store, org, card_id):
    with store.engine.connect() as c:
        verdict = c.execute(text(
            "select feedback_id, capability_id, rule_id, cause, reason, detail, actor_id, verdict_version, "
            "occurred_at from card_feedback_verdicts where org_id = :o and card_id = :k"),
            {"o": org, "k": card_id}).first()
        revisions = [tuple(r) for r in c.execute(text(
            "select verdict_version, cause, reason from card_feedback_revisions where org_id = :o and card_id = :k "
            "order by verdict_version"), {"o": org, "k": card_id})]
        events = [tuple(r) for r in c.execute(text(
            "select kind, cause from card_events where org_id = :o and card_id = :k and kind = 'human.card_action'"),
            {"o": org, "k": card_id})]
    return verdict, revisions, events


def test_your_wrong_with_its_reason_is_in_the_ledger_bound_to_the_decision(decided):
    store, org, _anchor, card = decided
    out = _press(store, org, card, "wrong", reason="misread_source", surface="web")
    assert out["ok"] is True and out["state"] == "acted", out
    verdict, revisions, events = _ledger(store, org, card.card_id)
    assert verdict is not None, "the dashboard's door wrote no verdict"
    assert (verdict.feedback_id, verdict.capability_id, verdict.rule_id) == (
        V.feedback_id_of(org, card.card_id), "expert.file_review", "file_review")
    assert (verdict.cause, verdict.reason, verdict.actor_id, verdict.verdict_version, verdict.occurred_at) == (
        "wrong", "misread_source", FOUNDER, 1, AT), "the press's one instant"
    assert verdict.detail == {"reason": "misread_source", "surface": "web"}
    assert revisions == [(1, "wrong", "misread_source")]
    assert events == [("human.card_action", "wrong")], "the card's own event stays"


@pytest.mark.parametrize("action", ["run_play", "do_it_myself"])
def test_taking_a_card_is_a_verdict_with_no_reason(decided, action):
    store, org, _anchor, card = decided
    assert _press(store, org, card, action)["ok"] is True
    verdict, revisions, _events = _ledger(store, org, card.card_id)
    assert (verdict.cause, verdict.reason) == (action, None) and revisions == [(1, action, None)]


def test_a_deferral_of_the_card_writes_no_verdict(decided):
    store, org, _anchor, card = decided
    assert _press(store, org, card, "snooze", snooze_option="4h")["ok"] is True
    verdict, revisions, _events = _ledger(store, org, card.card_id)
    assert verdict is None and revisions == []


def test_the_expert_reads_your_reason_in_the_files_dossier(decided):
    from genios_engine.reason.expert import dossier as D
    store, org, anchor, card = decided
    _press(store, org, card, "wrong", reason="wrong_person")
    with store.engine.connect() as c:
        parts = D.read_parts(c, org, anchor, now=AT + timedelta(hours=1))
    said = D.build_dossier(parts).text
    assert "the founder's verdict: wrong — wrong_person" in said


def test_the_change_gate_and_the_receipt_read_it(decided):
    from genios_engine.platform import receipts
    from genios_engine.reason.fingerprint_inputs import read_inputs
    store, org, _anchor, card = decided
    with store.engine.connect() as c:
        before = read_inputs(c, org)
    _press(store, org, card, "wrong", reason="not_relevant")
    with store.engine.connect() as c:
        after = read_inputs(c, org)
        subject = c.execute(text("select s.subject_node_id from cards k join signals s on s.org_id = k.org_id "
                                 "and s.signal_id = k.signal_id where k.org_id = :o and k.card_id = :c"),
                            {"o": org, "c": card.card_id}).scalar()
    assert before.by_rule.get(("file_review", subject), ()) == ()
    assert len(after.by_rule[("file_review", subject)]) == 1, "the verdict is one of the change gate's inputs"
    [receipt] = [r for r in receipts.evaluate(store.engine, org) if r["claim"] == "a human verdict has reached the loop"]
    assert receipt["status"] == "PASS", receipt


def test_a_card_no_authority_binds_keeps_its_press_and_writes_no_verdict(decided, monkeypatch):
    """The negative control, and a team or verify situation card's road: no binding, no verdict — the press
    stands, its card event with it."""
    store, org, _anchor, card = decided
    monkeypatch.setattr(V, "binding_of", lambda *_a, **_k: None)
    assert _press(store, org, card, "wrong", reason="not_relevant")["ok"] is True
    verdict, revisions, events = _ledger(store, org, card.card_id)
    assert verdict is None and revisions == [] and events == [("human.card_action", "wrong")]


def test_a_reason_sent_with_a_taken_card_is_no_part_of_its_verdict(decided):
    """A client that sends a reason with `run_play` is not refused its press: the reason belongs to a `wrong`."""
    store, org, _anchor, card = decided
    assert _press(store, org, card, "run_play", reason="not_relevant")["ok"] is True
    verdict, _revisions, _events = _ledger(store, org, card.card_id)
    assert (verdict.cause, verdict.reason) == ("run_play", None)
