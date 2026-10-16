"""STEP-16 · your own numbers for a kind of work — how far your files got, how long each stage took you, what ended verified.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_your_numbers_for_a_kind_of_work.py

Tree `yc2_w27_s16` M47.C2.L-logic.V3.U01 (`context/kind_numbers`; STEP-16 §3.4, §8.4 item 4). Across the tenant's files of
one kind: how many reached each stage their reviews named (a count), the days from the first review naming a stage to
the first naming the next (a median with its n), and of the decisions that ended, how many ended verified (a rate with
its n) — each a `Measured`, never a habit below five (`06` D37). Observe-only; org-level.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.context import kind_numbers as K
from genios_engine.reason.expert import store as R
from tests.reason.expert.checks import as_written

ORG = "org_s16_kind_numbers"
AT = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


def _row(file_id, days, stage):
    return SimpleNamespace(file_id=file_id, reviewed_at=AT + timedelta(days=days), stage=stage)


def test_how_far_your_files_got_and_how_long_each_stage_took():
    rows = [_row("f1", 0, "first_call"), _row("f1", 4, "first_call"), _row("f1", 10, "partner_meeting"),
            _row("f2", 0, "first_call"), _row("f2", 6, "partner_meeting"),
            _row("f3", 0, "first_call"), _row("f3", 2, None)]
    reached, days_in = K.stage_numbers(rows)
    assert {s: (m.value, m.n) for s, m in reached.items()} == {"first_call": (3, 3), "partner_meeting": (2, 2)}
    assert (days_in["first_call"].value, days_in["first_call"].n) == (8.0, 2), "10 and 6 days: a median of 8, n=2"
    assert "partner_meeting" not in days_in, "no file moved on from it yet"
    assert "usually" not in days_in["first_call"].says() and days_in["first_call"].sparse


def test_a_stage_named_again_after_another_is_its_first_naming_that_counts():
    rows = [_row("f1", 0, "first_call"), _row("f1", 5, "partner_meeting"), _row("f1", 9, "first_call")]
    reached, days_in = K.stage_numbers(rows)
    assert reached["first_call"].value == 1 and days_in["first_call"].value == 5.0


def test_at_five_files_a_stage_time_is_a_habit():
    rows = [r for i in range(5) for r in (_row(f"f{i}", 0, "first_call"), _row(f"f{i}", 7, "partner_meeting"))]
    _reached, days_in = K.stage_numbers(rows)
    assert days_in["first_call"].normal and "usually" in days_in["first_call"].says()


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the reviews and the cards are read from Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _review(engine, file_id, n, days, stage):
    raw = {"facts": [{"claim": "they wrote", "evidence": ["evt_1"]}],
           "frames": {"primary": "a fund", "rivals": ["a pass"]},
           "expected_vs_actual": {"stage": stage, "expected": "a call", "actual": "a call"},
           "scenarios": {"do_nothing": "cools", "act": "moves", "best": "a term sheet", "worst": "a pass",
                         "signals_to_watch": ["a reply"]},
           "appraisal": {"stakes": "high", "urgency": "low", "reversibility": "reversible", "reasons": ["warm"]},
           "mode": "wait", "wait_or_stop": "wait", "done_when": "they reply"}
    review = ExpertReview.from_mapping(raw)
    with engine.begin() as c:
        R.write_review(c, org_id=ORG, file_id=file_id, fingerprint=f"ffp-{file_id}-{n}", model="claude-sonnet-5",
                       prompt_version="expert-review.v4", dossier_digest="d" * 64, status=R.VALID, reason=None,
                       review=review, input_tokens=1, output_tokens=1, cost_micro_usd=1, at=AT + timedelta(days=days),
                       inputs={"events": ["evt_1"]}, triggers=[{"kind": "first_look", "says": "never judged"}],
                       checked=as_written(review))


def _ended_card(engine, card_id, file_id, *, verified: bool):
    import json
    with engine.begin() as c:
        c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                       "score, expires_at, state, file_id) values (:c, :s, :o, 'prescriptive', 'standard', 'h', 's', "
                       "10, :exp, :st, :f)"), {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "f": file_id,
                                              "exp": AT + timedelta(days=60),
                                              "st": "resolved" if verified else "expired"})
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) values "
                       "(:i, :c, :o, :k, :cause, 'system', cast(:d as jsonb))"),
                  {"i": f"cev_{card_id}", "c": card_id, "o": ORG,
                   "k": "card.resolved" if verified else "window.lapsed", "cause": "verified" if verified else "expired",
                   "d": json.dumps({"event_id": "evt_nda", "loop_id": "l1", "basis": "answered"} if verified else {})})


@pytest.mark.pg
def test_your_numbers_for_investor_work_are_read_from_your_files(engine):
    _review(engine, "node_f1", 0, 0, "first_call")
    _review(engine, "node_f1", 1, 9, "partner_meeting")
    _review(engine, "node_f2", 0, 0, "first_call")
    _ended_card(engine, "k1", "node_f1", verified=True)
    _ended_card(engine, "k2", "node_f2", verified=False)
    with engine.begin() as c:                  # a decision still open is in no denominator
        c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                       "score, expires_at, state, file_id) values ('k3', 'sig_k3', :o, 'prescriptive', 'standard', "
                       "'h', 's', 10, :exp, 'queued', 'node_f1')"), {"o": ORG, "exp": AT + timedelta(days=60)})
    with engine.connect() as c:
        numbers = K.numbers_for_kind(c, ORG, "investor", now=AT + timedelta(days=30), files=("node_f1", "node_f2"))
    assert numbers.files == 2
    assert {s: m.value for s, m in numbers.reached.items()} == {"first_call": 2, "partner_meeting": 1}
    assert (numbers.days_in["first_call"].value, numbers.days_in["first_call"].n) == (9.0, 1)
    assert (numbers.verified.value, numbers.verified.n, numbers.verified.k) == (0.5, 2, 1)
    assert numbers.as_dict()["verified"]["n"] == 2


@pytest.mark.pg
def test_a_kind_with_no_files_says_nothing_was_measured(engine):
    with engine.connect() as c:
        numbers = K.numbers_for_kind(c, ORG, "hiring", now=AT, files=())
    assert numbers.files == 0 and numbers.reached == {} and numbers.verified.value is None
