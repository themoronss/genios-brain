"""STEP-15 · what changed since your last brief — each review since, with what triggered it in words, and each line of
the last brief gone today, with why.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_what_changed_since_the_last_brief.py

`executive/morning_day.read_changes` (tree `yc2_w27_s15` M44.C3.L-logic.V1.U04). Read against the seat's last kept brief
(`executive/morning_store.last_before`); a first brief reads the day before. A review's triggers (0199) are said in the
brief's words — who wrote (never you: your own mail is no news to you), a quiet crossed once in whole days — and a first
look is no change. A line of the last brief that is gone today says why: answered, no longer asked, done on its card,
closed, no longer open. Measured on golden tenants replayed from their cassettes (no spend), then on a last brief kept
for the day before.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_day as M
from genios_engine.executive import morning_store
from genios_engine.executive.morning_template import template_brief

pytestmark = pytest.mark.pg

CASES = ("F14", "F21", "F30", "F45", "F54")


@pytest.fixture(scope="module")
def world():
    import os
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — what changed is read from golden tenants on Postgres")
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    cases = {c.case_id: c for c in load_cases()}
    runs = {}
    try:
        for cid in CASES:
            # STEP-15 (03 provisional s15-F18): `run_case` composes and keeps a brief by default since
            # M44.C5.L-integration.V0.U03 (06fbb2c8); `brief=False` keeps this suite's own `read_day`/`compose`
            # calls below the first and only composer of each golden tenant's day, as before that default existed
            # — a kept brief at the exact sweep instant would otherwise be read back as "the last brief", and
            # `test_a_first_brief_reads_one_day_back_and_no_review_not_yet_written` would see 0 changes, not 1.
            runs[cid] = engine_runner.run_case(cases[cid], RecordedLLM(cassettes.load(cases[cid])), keep=True,
                                               brief=False)
        yield engine, cases, runs
    finally:
        for run in runs.values():
            engine_runner.remove_tenant(engine, run.org_id)


def _changes(day):
    return [i for i in day.items if i.kind == B.CHANGE]


def _day(world, cid, *, shift=timedelta(0)):
    engine, cases, runs = world
    with engine.connect() as c:
        return M.read_day(c, runs[cid].org_id, "seat_owner", now=cases[cid].sweeps[-1] + shift)


def test_a_first_brief_says_what_triggered_each_review_of_the_day_before(world):
    (f14,) = _changes(_day(world, "F14"))
    assert f14.subject == "Fjord Venture Partners"
    assert f14.material.word("what") == "their move, quiet 25 days — past the file's usual gap of 7 days"
    (f21,) = _changes(_day(world, "F21"))
    assert f21.material.word("what") == "Awadh Enterprise Centre wrote"
    (f45,) = _changes(_day(world, "F45"))
    assert f45.material.word("what").startswith("Meera Shah wrote; their move, quiet 15 days")
    assert "you wrote" not in f45.material.word("what")
    for change in (f14, f21, f45):
        assert [s.kind for s in change.sources] == [B.SOURCE_REVIEW]


def test_a_line_of_the_last_brief_gone_today_says_why(world):
    engine, cases, runs = world
    org, now = runs["F54"].org_id, cases["F54"].sweeps[-1]
    before = _day(world, "F54")
    questions = [i for i in before.items if i.kind == B.QUESTION]
    kavya = next(q for q in questions if q.subject == "Kavya")
    rhea = next(q for q in questions if q.subject == "Rhea")
    rhea_card = next(s.ref for s in rhea.sources if s.kind == B.SOURCE_CARD)
    made = [B.Item(item_id=B.item_id_for(B.DECISION, f"node_{n}"), kind=B.DECISION, about=f"node_{n}",
                   subject=f"File {n}", material=B.Material(words=(("name", f"File {n}"), ("headline", "Write."))),
                   sources=sources) for n, sources in (
                       ("closed", (B.Source(B.SOURCE_CARD, rhea_card),)),
                       ("gone", (B.Source(B.SOURCE_REVIEW, "node_gone@fp"),)))]
    yesterday = template_brief(org_id=org, seat_id="seat_owner", items=before.items + tuple(made),
                               now=now - timedelta(days=1), tz=before.tz)
    with engine.begin() as c:
        morning_store.keep(c, yesterday)
        c.execute(text("update founder_questions set state = 'answered', answer = 'yes, we met', answered_by = "
                       "'seat_owner', answered_at = :at where org_id = :o and file_id = :f and state = 'open'"),
                  {"at": now, "o": org, "f": kavya.about})
        c.execute(text("update cards set state = 'dismissed' where org_id = :o and card_id = :k"),
                  {"o": org, "k": rhea_card})
    try:
        gone = {i.subject: i.material.word("what") for i in _changes(_day(world, "F54"))
                if any(s.kind != B.SOURCE_REVIEW for s in i.sources) or i.subject.startswith("File")}
        assert gone["Kavya"] == "answered — you answered its question"
        assert gone["File closed"] == "closed — its card was dismissed"
        assert gone["File gone"] == "no longer open"
        assert "Rhea" not in gone                                  # still asked today: nothing is gone
    finally:
        with engine.begin() as c:
            c.execute(text("delete from morning_briefs where org_id = :o"), {"o": org})


def test_a_first_brief_reads_one_day_back_and_no_review_not_yet_written(world):
    assert len(_changes(_day(world, "F21", shift=timedelta(hours=3)))) == 1     # the review of three hours ago
    assert _changes(_day(world, "F21", shift=timedelta(hours=25))) == []       # a day and an hour ago: past
    assert _changes(_day(world, "F21", shift=-timedelta(minutes=1))) == []     # the review is not yet written


def test_a_file_on_the_shadow_lane_has_no_change_line(world):
    assert _changes(_day(world, "F30")) == []                    # its review at the last sweep: decided in shadow
    engine, cases, runs = world
    org = runs["F45"].org_id                                     # Meera wrote — on a file moved to the shadow lane
    with engine.begin() as c:
        c.execute(text("update reasoning_fingerprints set outcome = 'shadow' where org_id = :o "
                       "and subject_key like '%|expert.file_review'"), {"o": org})
    try:
        day = _day(world, "F45")
        assert _changes(day) == [] and not [i for i in day.items if i.kind == B.DECISION]
    finally:
        with engine.begin() as c:
            c.execute(text("update reasoning_fingerprints set outcome = 'emitted' where org_id = :o "
                           "and subject_key like '%|expert.file_review'"), {"o": org})


def test_who_wrote_is_never_you_by_name(world):
    engine, cases, runs = world
    org = runs["F21"].org_id
    with engine.begin() as c:
        c.execute(text("update source_events set actor = jsonb_set(jsonb_set(actor, '{name}', '\"Arjun Rao\"'), "
                       "'{email}', '\"arjun.personal@elsewhere.test\"') where org_id = :o "
                       "and actor->>'email' like '%awadhec%'"), {"o": org})
    try:
        assert _changes(_day(world, "F21")) == []                # "Arjun Rao wrote": speaks of you, so unsaid
    finally:
        with engine.begin() as c:
            c.execute(text("update source_events set actor = jsonb_set(jsonb_set(actor, '{name}', "
                           "'\"Awadh Enterprise Centre\"'), '{email}', '\"programs@awadhec.test\"') "
                           "where org_id = :o and actor->>'email' = 'arjun.personal@elsewhere.test'"), {"o": org})


def test_a_review_the_last_brief_already_saw_is_no_change_nor_is_a_change_line_ever_gone(world):
    engine, cases, runs = world
    org, now = runs["F45"].org_id, cases["F45"].sweeps[-1]
    day = _day(world, "F45")
    stale = B.Item(item_id=B.item_id_for(B.CHANGE, "node_x", "review"), kind=B.CHANGE, about="node_x",
                   subject="File X", material=B.Material(words=(("name", "File X"), ("what", "File X wrote"))),
                   sources=(B.Source(B.SOURCE_REVIEW, "node_x@fp"),), at=now - timedelta(days=2))
    yesterday = replace(template_brief(org_id=org, seat_id="seat_owner", items=day.items + (stale,),
                                       now=now - timedelta(days=1), tz=day.tz), as_of=now)
    with engine.begin() as c:
        morning_store.keep(c, yesterday)
    try:
        assert _changes(_day(world, "F45")) == []                # seen at `now` already; a change is never "gone"
    finally:
        with engine.begin() as c:
            c.execute(text("delete from morning_briefs where org_id = :o"), {"o": org})


def test_a_question_you_answered_before_the_review_asked_again_is_asked(world):
    engine, cases, runs = world
    org = runs["F54"].org_id
    before = {q.subject: q for q in _day(world, "F54").items if q.kind == B.QUESTION}
    with engine.begin() as c:
        c.execute(text("update founder_questions set state = 'answered', answer = 'an old answer', "
                       "answered_by = 'seat_owner', answered_at = :at, retired_at = null, retired_why = null "
                       "where org_id = :o and file_id = :f"),
                  {"at": datetime(2026, 8, 1, tzinfo=before["Rhea"].at.tzinfo), "o": org, "f": before["Rhea"].about})
    asked = {q.subject for q in _day(world, "F54").items if q.kind == B.QUESTION}
    assert "Rhea" in asked                                        # her answer predates the review that asks


# ── the words, pure ──────────────────────────────────────────────────────────────────────────────
def test_a_trigger_in_the_briefs_words():
    us = type("Us", (), {})()
    actors = {"evt_a1": "Hub Seventy", "evt_b2": "you", "evt_c3": None}
    said = M._said_triggers([("new_evidence", "new since the last review: evt_a1, evt_b2 and evt_c3")], actors, us)
    assert said == "Hub Seventy wrote"
    assert M._said_triggers([("first_look", "never judged")], actors, us) is None
    assert M._said_triggers([("founder_asked", "x"), ("date_closing_in", "the next meeting: <=72 → <=24")],
                            actors, us) == "you asked about it; a date it holds is closer"
    assert M._said_triggers([("reply_overdue", "their move, quiet 18.4 days — past the 5 days they usually take"),
                             ("past_normal", "quiet 18.4 days — past the longest gap it ever had, 9 days")],
                            actors, us) == "their move, quiet 18 days — past the 5 days they usually take"
    assert M._said_triggers([("new_evidence", "evt_a1"), ("new_evidence", "evt_a1"), ("founder_asked", "x"),
                             ("date_closing_in", "y")], actors, us) == "Hub Seventy wrote; you asked about it"


@pytest.mark.parametrize("kind, sources, questions, cards, why", [
    (B.QUESTION, ((B.SOURCE_QUESTION, "q1"),), {"q1": "retired"}, {}, "no longer asked"),
    (B.DECISION, ((B.SOURCE_CARD, "k1"),), {}, {"k1": "acted"}, "done — you acted on its card"),
    (B.DECISION, ((B.SOURCE_CARD, "k1"),), {}, {"k1": "expired"}, "closed — its card was expired"),
    (B.DECISION, ((B.SOURCE_CARD, "k1"),), {}, {"k1": "surfaced"}, "no longer open"),
    (B.PROMISE, ((B.SOURCE_PROMISE, "c1"),), {}, {}, "no longer due — kept, or no longer open"),
    (B.MEETING, ((B.SOURCE_MEETING, "m1"),), {}, {}, "the meeting has passed"),
])
def test_why_a_line_is_gone(kind, sources, questions, cards, why):
    line = B.Line(line_id="bl_1", item_id="bi_1", section=B.TODAY, words="x.", kind=kind, subject="S",
                  sources=tuple(B.Source(k, r) for k, r in sources))
    assert M._why_gone(line, questions, cards) == why
