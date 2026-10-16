"""STEP-15 · the day, read for one seat at one instant — every item with its material and its sources.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_the_day.py

`executive/morning_day.read_day` (tree `yc2_w27_s15` M44.C3.L-logic.V0.U02). Read on golden tenants as the real chain
leaves them after each case's last sweep — replayed from their cassettes, no spend — so the day is measured on what
the engine holds, not on rows a test invented: F45's decision with your reply time (1.5 days, n=6), F14's watched
file with the expert's wait rule, F22's question with its card, F54's two questions and its mixer nobody followed up,
F55's desk (28 days, three waiting), F30's promise in its file — and, s15-D2 = yes, a labelled line for a file
decided on the shadow lane (F30's own, F55's Dev), never a card. Then the day's own rules, case by case.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_day as M

pytestmark = pytest.mark.pg

CASES = ("F14", "F22", "F30", "F45", "F54", "F55")


@pytest.fixture(scope="module")
def days():
    import os
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the day is read from golden tenants on Postgres")
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    cases = {c.case_id: c for c in load_cases()}
    out, orgs = {}, []
    try:
        for cid in CASES:
            case = cases[cid]
            run = engine_runner.run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
            orgs.append(run.org_id)
            with engine.connect() as c:
                out[cid] = M.read_day(c, run.org_id, "seat_owner", now=case.sweeps[-1])
        # Two worlds the replays do not reach, made from them: F45's review suppressed by its check (its ask is
        # answered), and F55's mailbox no longer vouching for its silence (its last sync did not complete).
        at = {cid: cases[cid].sweeps[-1] for cid in CASES}
        with engine.begin() as c:
            c.execute(text("update expert_reviews set checked = jsonb_set(jsonb_set(checked, '{fate}', "
                           "'\"suppressed\"'), '{because}', '\"answered\"') where org_id = 'org_golden_f45'"))
            c.execute(text("update l1_sync_runs set cursor_exhausted = false where org_id = 'org_golden_f55'"))
            c.execute(text("update expert_reviews set checked = jsonb_set(jsonb_set(checked, '{fate}', "
                           "'\"suppressed\"'), '{because}', '\"answered\"') where org_id = 'org_golden_f22'"))
            c.execute(text("update founder_questions set state = 'retired', retired_at = now(), retired_why = 'x' "
                           "where org_id = 'org_golden_f22'"))
        with engine.connect() as c:
            out["F22/suppressed"] = M.read_day(c, "org_golden_f22", "seat_owner", now=at["F22"])
            out["F45/suppressed"] = M.read_day(c, "org_golden_f45", "seat_owner", now=at["F45"])
            out["F55/unsaid"] = M.read_day(c, "org_golden_f55", "seat_owner", now=at["F55"])
        # A third world, for the wait rule that names you: STEP-14 reworded F55's authored Meadow rule from "stop if
        # Arjun decides…" to "stop if you decide…" (M43.C2.L-data.V2.U05, the 16 Oct merge), so the golden tenant no
        # longer holds the rule that speaks of the founder — this puts the founder's name back in the stored review.
        with engine.begin() as c:
            c.execute(text("update expert_reviews set review = jsonb_set(review, '{wait_or_stop}', "
                           "to_jsonb(replace(review->>'wait_or_stop', 'you decide', 'Arjun decides'))) "
                           "where org_id = 'org_golden_f55' and review->>'wait_or_stop' like '%you decide Meadow%'"))
        with engine.connect() as c:
            out["F55/named"] = M.read_day(c, "org_golden_f55", "seat_owner", now=at["F55"])
        # A fourth: F54's two find-out files whose questions were never stored — the day then asks them in the check's
        # own words (`read_day`'s second branch), and says what each is about the same way.
        with engine.begin() as c:
            c.execute(text("delete from founder_questions where org_id = 'org_golden_f54'"))
        with engine.connect() as c:
            out["F54/unasked"] = M.read_day(c, "org_golden_f54", "seat_owner", now=at["F54"])
        yield out
    finally:
        for org in orgs:
            engine_runner.remove_tenant(engine, org)


def _of(day, kind):
    return [i for i in day.items if i.kind == kind]


def test_f45_a_decision_with_your_reply_time_and_its_card(days):
    (d,) = _of(days["F45"], B.DECISION)
    assert d.subject == "Bluepeak" and d.material.word("name") == "Bluepeak"
    assert d.material.word("headline").startswith("Introduce Meera Shah to the two pilot leads")
    reply = d.material.number("your_reply_time")
    assert (reply.value, reply.n, d.material.word("reply_with")) == (1.5, 6, "Meera Shah")
    assert (d.stakes, d.urgency, d.mode, d.lane, d.our_move) == ("high", "high", "act", "live", True)
    assert d.card_id and d.book_score_bp is not None
    kinds = {s.kind for s in d.sources}
    assert {B.SOURCE_REVIEW, B.SOURCE_CARD, B.SOURCE_CALCULATOR} <= kinds
    assert days["F45"].tz == "Asia/Kolkata"


def test_f14_a_watched_file_with_the_wait_rule_the_check_lets_stand(days):
    (w,) = _of(days["F14"], B.WATCHED)
    assert w.subject == "Fjord Venture Partners" and w.quiet_days > 7
    assert w.material.word("wait_rule").startswith("Stop the weekly updates to Tara")
    assert w.material.number("quiet").n == 25 and not _of(days["F14"], B.DECISION)


def test_f22_the_question_your_file_asks_with_the_card_that_asks_it(days):
    (q,) = _of(days["F22"], B.QUESTION)
    assert q.subject == "University Startup Cell"
    assert "incubated on the university's campus" in q.material.word("question")
    assert q.material.date("by") == "2026-09-30" and q.card_id
    assert {B.SOURCE_QUESTION, B.SOURCE_CARD, B.SOURCE_REVIEW} <= {s.kind for s in q.sources}


def test_a_question_says_what_the_file_is_about_and_not_only_what_it_asks(days):
    """03 s15-F19, found on the STEP-14 + STEP-15 merge (16 Oct): STEP-14 made F22's question the plain ask — "Can you
    tell us whether you are a startup incubated on the university's campus?" — and a question line that is only the
    ask no longer says it is about a seed grant. The review's situation is what the file is about (the card's own
    second line, STEP-14): the item carries it beside the question."""
    (q,) = _of(days["F22"], B.QUESTION)
    assert q.material.word("situation").startswith("A university cell's notice of a seed grant closing on the thirtieth")
    assert "seed grant" not in q.material.word("question")            # the ask alone does not say it: the reason for this
    for question in _of(days["F54"], B.QUESTION):                      # every question of a reviewed file carries one
        assert question.material.word("situation")
    # …and a file whose question was never stored is asked in the check's own words, with the same sentence beside it
    unasked = _of(days["F54/unasked"], B.QUESTION)
    assert sorted(q.subject for q in unasked) == ["Kavya", "Rhea"]
    assert all(q.material.word("situation") and q.material.word("question") for q in unasked)
    assert {q.material.word("situation") for q in unasked} == {q.material.word("situation") for q
                                                               in _of(days["F54"], B.QUESTION)}


def test_f54_two_questions_and_the_mixer_nobody_followed_up(days):
    day = days["F54"]
    assert sorted(q.subject for q in _of(day, B.QUESTION)) == ["Kavya", "Rhea"]
    (m,) = _of(day, B.NO_FOLLOW_UP)
    assert m.material.word("title") == "Fintech founders mixer - Bluebay" and m.material.word("when") == "20 Aug"
    assert set(m.material.names) == {"Kavya", "Rhea"} and "events" not in " ".join(m.material.names).lower()
    assert not _of(day, B.WATCHED) and not _of(day, B.DECISION)        # the organiser's mailbox needs nothing


def test_f55_your_desk_and_a_labelled_line_for_the_file_on_the_shadow_lane(days):
    day = days["F55"]
    (desk,) = _of(day, B.DESK)
    assert desk.material.number("since_your_last_mail").n == 28 and desk.material.number("waiting").n == 3
    assert set(desk.material.names) == {"Dev Malhotra", "Rhea Thomas", "Kabir Sethi"}
    decisions = {d.subject: d for d in _of(day, B.DECISION)}
    assert len(decisions) == 3                                 # s15-D2 = yes: the shadow file is a line too
    live = [d for d in decisions.values() if d.lane == "live"]
    assert len(live) == 2 and all(d.card_id for d in live)
    shadow = next(d for d in decisions.values() if d.lane == "shadow")
    assert "Dev" in (shadow.material.word("headline") or "")
    assert shadow.material.word("headline").endswith(M.SHADOW_LABEL)
    assert shadow.card_id is None and shadow.book_score_bp is None and B.SOURCE_CARD not in {
        s.kind for s in shadow.sources}


def test_f30_your_promise_in_its_file_and_a_labelled_line_for_the_shadow_decision(days):
    day = days["F30"]
    (p,) = _of(day, B.PROMISE)
    assert (p.material.word("promise"), p.material.word("to"), p.material.date("due")) == \
        ("send the pilot proposal", "Gaurav", "2026-09-25")
    assert p.material.word("file") == "Stackfield" and p.subject == "Gaurav"
    assert not _of(day, B.QUESTION)
    (d,) = _of(day, B.DECISION)                                # s15-D2 = yes: a line, never a card
    assert d.lane == "shadow" and d.card_id is None
    assert d.material.word("headline").endswith(M.SHADOW_LABEL)


def test_what_the_check_suppressed_is_no_decision_and_a_silence_no_mailbox_vouches_for_is_unsaid(days):
    assert not _of(days["F45/suppressed"], B.DECISION)
    assert not _of(days["F22/suppressed"], B.QUESTION)                # nor a find-out whose ask is answered
    (desk,) = _of(days["F55/unsaid"], B.DESK)
    assert desk.material.number("since_your_last_mail") is None and desk.material.number("waiting").n == 3


def test_a_reply_time_too_sparse_to_be_normal_is_not_said_and_a_wait_rule_naming_you_is_not_kept(days):
    day = days["F55"]
    assert all(d.material.number("your_reply_time") is None for d in _of(day, B.DECISION))
    (meadow,) = _of(day, B.WATCHED)
    # Said to you as "you" the rule stands (STEP-14 reworded it from "stop if Arjun decides…", M43.C2.L-data.V2.U05)…
    assert meadow.material.word("wait_rule").endswith("stop if you decide Meadow VC is not part of this round.")
    assert meadow.material.word("headline")
    (named,) = _of(days["F55/named"], B.WATCHED)
    assert named.material.word("wait_rule") is None                  # …and the same rule naming the founder is unsaid
    assert named.material.word("headline")
    assert not _of(days["F14"], B.DESK)                               # nobody waits on you: no desk line


def test_every_item_names_its_sources_and_no_address(days):
    for cid, day in days.items():
        assert day.items or "/" in cid                                  # a world made from a case may hold none
        for item in day.items:
            assert item.sources
            for text in item.material.texts():
                assert "@" not in text, (item.kind, text)


# ── the day's own rules, pure ────────────────────────────────────────────────────────────────────
def test_what_a_question_is_about_is_the_checked_situation_unless_it_speaks_of_you():
    from types import SimpleNamespace
    checked = lambda said: SimpleNamespace(words=SimpleNamespace(situation=said))        # noqa: E731
    founder = ("Arjun Rao",)
    assert M._about(checked("A grant closes on the thirtieth."), founder) == "A grant closes on the thirtieth."
    assert M._about(checked("Arjun Rao has not answered."), founder) is None            # your name
    assert M._about(checked("The founder has not answered."), founder) is None          # "the founder"
    assert M._about(checked("  "), founder) is None and M._about(checked(None), founder) is None
    assert M._about(None, founder) is None                                              # no check, nothing to say


def test_words_speak_of_you_as_you():
    assert M.speaks_of_you("the founder should write", ("Arjun Rao",))
    assert M.speaks_of_you("a sign from Arjun that he wants it", ("Arjun Rao",))
    assert not M.speaks_of_you("a sign from Arjunpur", ("Arjun Rao",))
    assert not M.speaks_of_you("write to Tara once", ("Arjun Rao",))
    assert not M.speaks_of_you("ask Al", ("Al B",))                      # a word under three letters is no name


def test_unheld_words_join_the_material_only_on_checked_ground_and_speaking_of_you_as_you():
    assert M._holds("Stop the weekly updates to Tara", ["Tara asked for news"], ("Arjun Rao",))
    assert not M._holds("Write to Initech once", ["Tara asked for news"], ("Arjun Rao",))      # an invented name
    assert not M._holds("a sign from Arjun", ["Arjun wrote to Tara"], ("Arjun Rao",))        # names you
    assert not M._holds("  ", ["Tara"], ())
    assert M._holds("File the form with Tara", ["Tara"], ())                                 # an earned word


def test_a_node_of_ours_is_never_a_name_the_brief_gives():
    from types import SimpleNamespace as N
    from genios_engine.platform.self_identity import SelfIdentity
    us = SelfIdentity.of(addresses=["arjun@nimbuslabs.test"], domains=["nimbuslabs.test"])
    rows = [N(node_id="n1", node_type="person", display_name="Arjun Rao", canonical_key="arjun@nimbuslabs.test"),
            N(node_id="n2", node_type="person", display_name="Meera Shah", canonical_key="meera@bluepeak.test"),
            N(node_id="n3", node_type="company", display_name=None, canonical_key="nimbuslabs.test")]
    assert M.spoken_names(rows, us) == {"n2": "Meera Shah"}


def test_a_file_whose_last_touch_is_still_to_come_is_quiet_for_no_days():
    from types import SimpleNamespace
    assert M._quiet(SimpleNamespace(days_quiet=-1.4)).n == 0 and M._quiet(SimpleNamespace(days_quiet=None)) is None
    assert M._quiet(SimpleNamespace(days_quiet=25.12)).says == "25 days"


def test_the_name_a_company_brief_line_gives():
    assert M._line_name("Program · Awadh Enterprise Centre — applied") == "Awadh Enterprise Centre"
    assert M._line_name("StartupSetu — the startup recognition portal") == "StartupSetu"
    assert M._line_name("State Startup Mission") == "State Startup Mission"
