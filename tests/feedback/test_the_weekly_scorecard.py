"""STEP-16 · the week, measured — usefulness per lane, what was held back and why, coverage, outcomes, your corrections.

    .venv/bin/python -m pytest -q tests/feedback/test_the_weekly_scorecard.py
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (the week read from memory)

Tree `yc2_w27_s16` M47.C3.L-logic.V5.U01 (`feedback/scorecard`; STEP-16 §8.4 item 9, `09` G6, `06` D18). Pure
composition over reads, no model: the week's cards by lane and what came of each — called wrong by reason and the
layer each reason debits (`feedback/attribution.route`, read by nothing until now); the check's fates and why, the
questions asked, answered and called wrong; STEP-10's coverage receipt; the verified-outcome rate with its n, by
kind; each correction you made and what it changed. A week with nothing says so; a part with nothing is empty,
never missing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import file_outcomes as O
from genios_engine.context.coverage_receipt import MailboxReceipt
from genios_engine.context.founder_corrections import Correction
from genios_engine.contracts import claim_check as K
from genios_engine.contracts.learning_attribution import attribute
from genios_engine.feedback import scorecard as S
from genios_engine.reason.expert.correction_delta import CorrectionDelta, Decided, FileDelta

ORG = "org_s16_scorecard"
WEEK = S.Week.of("2026-W42")
MONDAY = datetime(2026, 10, 12, tzinfo=timezone.utc)


def _ended(card: str, end: str, *, lane: str = "decision", file: str | None = "node_a", reason: str | None = None,
           by: str | None = None) -> O.Ended:
    return O.Ended(card_id=card, file_id=file, lane=lane, ended=end, by=by, reason=reason, at=MONDAY)


def _words() -> K.CardWords:
    return K.CardWords(headline="Send the deck", situation=None, done_when=None, draft=None, to=None)


def _checked(fate: str, *, because: str | None = None, dropped: tuple[str, ...] = (), notes: tuple[str, ...] = ()):
    verdicts = tuple(K.LineVerdict(line=f"fact:{i + 1}", verdict=K.DROPPED, reason=r) for i, r in enumerate(dropped))
    verdicts += tuple(K.LineVerdict(line="prose", verdict=K.NOTED, reason=n) for n in notes)
    return K.CheckedReview(verdicts=verdicts, fate=fate, words=_words(), cited=() if fate == K.REFUSED else ("e1",),
                           because=because, question="Does it still hold?" if fate == K.HELD else None)


def _compose(**over):
    parts = {"org_id": ORG, "week": WEEK, "endings": (), "kinds": {}, "checks": (), "questions": {},
             "coverage": (), "corrections": (), "deltas": ()}
    return S.compose(**{**parts, **over})


# =================================================================================================
# the week
# =================================================================================================
def test_a_week_is_its_iso_week_in_utc():
    assert (WEEK.since, WEEK.until) == (MONDAY, MONDAY + timedelta(days=7))
    assert WEEK.label == "2026-W42" and S.Week.containing(MONDAY + timedelta(days=6, hours=23)) == WEEK
    assert S.Week.containing(MONDAY - timedelta(seconds=1)).label == "2026-W41"


@pytest.mark.parametrize("label", ["2026-42", "2026-W4", "W42", "", "2026-W54", "2026-W00"])
def test_a_week_that_is_no_iso_week_is_refused(label):
    with pytest.raises(ValueError):
        S.Week.of(label)


# =================================================================================================
# a week with nothing says so — every part there, and empty
# =================================================================================================
def test_a_week_with_nothing_says_so():
    card = _compose()
    assert card.nothing and card.says == ("Nothing happened in 2026-W42: no card, no review, no question, "
                                          "no correction.")
    out = card.as_dict()
    assert (out["usefulness"], out["wrong_reasons"], out["debits"], out["coverage"], out["corrections"]) == (
        {}, {}, [], [], [])
    assert out["held_back"]["reviews"] == 0 and set(out["held_back"]["fates"].values()) == {0}
    assert out["questions"] == {"asked": 0, "answered": 0, "called_wrong": 0}
    assert out["outcomes"]["all"]["verified"]["n"] == 0 and out["outcomes"]["by_kind"] == {}


@pytest.mark.parametrize("what", ["card", "review", "question", "correction"])
def test_any_one_thing_is_something(what):
    delta = CorrectionDelta(correction_id="fc_1", scope="file", files=())
    over = {"card": {"endings": (_ended("k1", O.OPEN),)}, "review": {"checks": (_checked(K.SHOWN),)},
            "question": {"questions": {"asked": 1}},
            "correction": {"corrections": (_correction(),), "deltas": (delta,)}}[what]
    assert not _compose(**over).nothing


# =================================================================================================
# usefulness per lane — and the layer each reason debits
# =================================================================================================
def test_usefulness_per_lane_says_what_came_of_the_weeks_cards():
    endings = (_ended("k1", O.TAKEN, reason="run_play"), _ended("k2", O.CALLED_WRONG, reason="wrong_facts"),
               _ended("k3", O.LAPSED, reason="expired"), _ended("k4", O.REPLACED, lane="monitor"),
               _ended("k5", O.OPEN, lane="monitor"))
    card = _compose(endings=endings)
    assert card.usefulness["decision"][O.TAKEN] == 1 and card.usefulness["decision"][O.CALLED_WRONG] == 1
    assert card.usefulness["decision"][O.LAPSED] == 1 and card.usefulness["monitor"][O.REPLACED] == 1
    assert set(card.usefulness["monitor"]) == set(O.ENDS), "every end counted, none left out"
    assert card.cards == 5


def test_a_reason_you_gave_debits_the_layer_it_names():
    reasons = ("wrong_facts", "wrong_facts", "bad_timing", "not_relevant")
    endings = tuple(_ended(f"k{i}", O.CALLED_WRONG, reason=r) for i, r in enumerate(reasons))
    endings += (_ended("k_taken", O.TAKEN, reason="do_it_myself"), _ended("k_odd", O.CALLED_WRONG, reason="no_such"))
    card = _compose(endings=endings)
    assert card.wrong_reasons == {"bad_timing": 1, "no_such": 1, "not_relevant": 1, "wrong_facts": 2}
    expected: dict[str, int] = {}
    for r in reasons:
        expected[attribute(r).layer] = expected.get(attribute(r).layer, 0) + 1
    assert {d["layer"]: d["debits"] for d in card.debits} == expected
    assert card.unattributed == 1, "a reason this build does not know is counted, never dropped"
    assert all(d["fixes"] for d in card.debits)


# =================================================================================================
# held back, and why
# =================================================================================================
def test_held_back_counts_each_fate_and_why():
    checks = (_checked(K.SHOWN, notes=(K.UNCITED_CORRECTION,)),
              _checked(K.HELD, because=K.CORRECTION_UNHEEDED, dropped=(K.CORRECTION_UNHEEDED,)),
              _checked(K.HELD, because=K.CALLED_WRONG),
              _checked(K.REFUSED, because=K.NOTHING_STANDS, dropped=(K.UNCITED, K.UNCITED)))
    held = _compose(checks=checks).held_back
    assert held["reviews"] == 4
    assert held["fates"] == {K.SHOWN: 1, K.HELD: 2, K.SUPPRESSED: 0, K.REFUSED: 1}
    assert held["because"] == {"held: called_wrong": 1, "held: correction_unheeded": 1, "refused: nothing_stands": 1}
    assert held["dropped"] == {K.CORRECTION_UNHEEDED: 1, K.UNCITED: 1}, "a reason once per review"
    assert held["notes"] == {K.UNCITED_CORRECTION: 1}


def test_the_questions_asked_answered_and_called_wrong():
    card = _compose(questions={"asked": 3, "answered": 1, "called_wrong": 1})
    assert card.questions == {"asked": 3, "answered": 1, "called_wrong": 1}


# =================================================================================================
# coverage, outcomes, corrections
# =================================================================================================
def test_coverage_is_each_mailboxs_receipt():
    receipt = MailboxReceipt(connection_id="conn_1", address="founder@nimbus.test", window_days=60,
                             window_start=MONDAY - timedelta(days=60), last_finished_at=MONDAY, last_completed=True)
    [mailbox] = _compose(coverage=(receipt,)).coverage
    assert mailbox == {"connection_id": "conn_1", "address": "founder@nimbus.test", "window_days": 60,
                       "window_start": (MONDAY - timedelta(days=60)).isoformat(),
                       "last_finished_at": MONDAY.isoformat(), "last_completed": True}


def test_outcomes_say_the_verified_rate_by_kind_with_its_n():
    endings = (_ended("k1", O.VERIFIED, by="evt_nda"), _ended("k2", O.REPLIED, by="evt_thanks"),
               _ended("k3", O.OPEN), _ended("k4", O.TAKEN, file="node_b", reason="run_play"))
    out = _compose(endings=endings, kinds={"node_a": "investor", "node_b": "vendor"}).outcomes
    assert out["all"]["verified"] == {"value": 0.333, "n": 3, "says": "1 of 3"}, "open cards in no denominator"
    assert out["by_kind"]["investor"]["counts"][O.VERIFIED] == 1 and out["by_kind"]["investor"]["verified"]["n"] == 2
    assert out["by_kind"]["vendor"]["verified"]["says"] == "0 of 1"


def _correction(n: int = 1, scope: str = "file") -> Correction:
    return Correction(correction_id=f"fc_{n}", file_id="node_a", card_id="k2", feedback_id=None, reason="not_relevant",
                      words="She wants news only on real milestones.", scope=scope, kind=None, brief_line_id=None,
                      corrected_by="user_arjun", corrected_at=MONDAY + timedelta(days=1), state="standing")


def test_each_correction_says_what_it_changed():
    before = Decided(fingerprint="ffp-0", reviewed_at=MONDAY, mode="act", move="Send the update", cited=False,
                     fate="shown")
    after = Decided(fingerprint="ffp-1", reviewed_at=MONDAY + timedelta(days=2), mode="wait", move=None, cited=True,
                    fate="shown")
    delta = CorrectionDelta(correction_id="fc_1", scope="file", files=(FileDelta("node_a", before, after),))
    [said] = _compose(corrections=(_correction(),), deltas=(delta,)).corrections
    assert (said["correction_id"], said["reviewed"], said["changed"], said["cited"]) == ("fc_1", 1, 1, 1)
    assert said["words"] == "She wants news only on real milestones." and said["reason"] == "not_relevant"
    assert said["files"] == [{"file_id": "node_a", "changed": True, "before": {"mode": "act", "move": "Send the update"},
                              "after": {"mode": "wait", "move": None, "cited": True, "fate": "shown"}}]


def test_the_same_reads_are_the_same_scorecard():
    endings = (_ended("k1", O.VERIFIED, by="evt_nda"), _ended("k2", O.CALLED_WRONG, reason="bad_timing"))
    one = _compose(endings=endings, checks=(_checked(K.SHOWN),)).as_dict()
    assert one == _compose(endings=endings, checks=(_checked(K.SHOWN),)).as_dict()
    assert one["says"] == "2026-W42: 2 card(s); 1 review(s) checked; 0 correction(s); verified outcomes: 1 of 2"


# =================================================================================================
# the week read from memory
# =================================================================================================
@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the week is read from Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'scorecard@s16.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _card(c, card_id, *, state, at, file, events=(), verdict=None):
    import json
    c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
                   "expires_at, state, file_id, output_lane, lane_reason, created_at) values (:c, :s, :o, "
                   "'prescriptive', 'standard', 'h', 's', 10, :exp, :st, :f, 'decision', 'a test lane', :at)"),
              {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "exp": at + timedelta(days=7), "st": state, "f": file,
               "at": at})
    for i, (kind, cause, detail) in enumerate(events):
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, occurred_at) "
                       "values (:id, :c, :o, :k, :cause, 'system', cast(:d as jsonb), :at)"),
                  {"id": f"cev_{card_id}_{i}", "c": card_id, "o": ORG, "k": kind, "cause": cause,
                   "d": json.dumps(detail or {}), "at": at + timedelta(hours=1 + i)})
    if verdict:
        c.execute(text("insert into card_feedback_verdicts (feedback_id, org_id, card_id, pack_id, pack_version, "
                       "authority_pack_revision, capability_id, capability_version, rule_id, cause, reason, detail, "
                       "actor_id, occurred_at) values (:fb, :o, :c, 'founder_office', '0.1.0', 1, 'expert.file_review', "
                       "'1.0.0', 'file_review', :cause, :reason, '{}'::jsonb, 'founder', :at)"),
                  {"fb": f"fb_{card_id}", "o": ORG, "c": card_id, "cause": verdict[0], "reason": verdict[1],
                   "at": at + timedelta(hours=5)})


def _review(c, file_id, fingerprint, *, at, fate):
    from genios_engine.contracts.expert_review import ExpertReview
    from genios_engine.reason.expert import store as R
    from tests.reason.expert.checks import as_written
    review = ExpertReview.from_mapping({
        "facts": [{"claim": "they wrote", "evidence": ["evt_1"]}], "frames": {"primary": "a fund", "rivals": ["a pass"]},
        "expected_vs_actual": {"stage": None, "expected": "a call", "actual": "a call"},
        "scenarios": {"do_nothing": "cools", "act": "moves", "best": "a term sheet", "worst": "a pass",
                      "signals_to_watch": ["a reply"]},
        "appraisal": {"stakes": "high", "urgency": "low", "reversibility": "reversible", "reasons": ["warm"]},
        "mode": "wait", "wait_or_stop": "wait", "done_when": "they reply"})
    checked = as_written(review)
    if fate == K.HELD:
        checked = K.CheckedReview(verdicts=checked.verdicts, fate=K.HELD, words=checked.words, cited=checked.cited,
                                  because=K.CORRECTION_UNHEEDED, question="You said “x” on 13 Oct; does it still hold?")
    R.write_review(c, org_id=ORG, file_id=file_id, fingerprint=fingerprint, model="claude-sonnet-5",
                   prompt_version="expert-review.v4", dossier_digest="d" * 64, status=R.VALID, reason=None,
                   review=review, input_tokens=1, output_tokens=1, cost_micro_usd=1, at=at,
                   inputs={"events": ["evt_1"]}, triggers=[{"kind": "first_look", "says": "never judged"}],
                   checked=checked)


@pytest.mark.pg
def test_the_week_is_read_from_memory_and_only_the_week(engine):
    from genios_engine.context import founder_corrections as C
    from genios_engine.context import founder_questions as Q
    inside, before = MONDAY + timedelta(days=1), MONDAY - timedelta(days=1)
    with engine.begin() as c:
        _card(c, "k_verified", state="resolved", at=inside, file="node_a", events=[
            ("card.resolved", "verified", {"event_id": "evt_nda", "loop_id": "loop_nda", "basis": "answered"})])
        _card(c, "k_wrong", state="acted", at=inside + timedelta(hours=1), file="node_b",
              events=[("human.card_action", "wrong", {})], verdict=("wrong", "bad_timing"))
        _card(c, "k_last_week", state="acted", at=before, file="node_c",
              events=[("human.card_action", "run_play", {})], verdict=("run_play", None))
        _review(c, "node_a", "ffp-a-0", at=inside, fate=K.SHOWN)
        _review(c, "node_b", "ffp-b-0", at=inside, fate=K.HELD)
        _review(c, "node_c", "ffp-c-0", at=before, fate=K.SHOWN)
        Q.ask(c, org_id=ORG, file_id="node_b", fingerprint="ffp-b-0", run_id=None,
              question="Does Theresa still want news only on milestones?", why="the move rests on it", at=inside)
        Q.retire(c, org_id=ORG, file_id="node_b", why=Q.CALLED_WRONG, at=inside + timedelta(hours=2))
        Q.ask(c, org_id=ORG, file_id="node_a", fingerprint="ffp-a-0", run_id=None,
              question="Has the deck gone?", why="the move rests on it", at=inside)
        Q.retire(c, org_id=ORG, file_id="node_a", why=Q.NO_LONGER_ASKED, at=inside + timedelta(hours=3))
        kept = C.correct(c, org_id=ORG, file_id="node_b", words="Theresa wants news only on real milestones.",
                         scope=C.FILE, by="user_arjun", at=inside + timedelta(hours=2), card_id="k_wrong",
                         reason="not_relevant")
        C.correct(c, org_id=ORG, file_id="node_c", words="Last week's word.", scope=C.FILE, by="user_arjun", at=before)
    with engine.connect() as c:
        card = S.scorecard_for(c, ORG, WEEK, now=MONDAY + timedelta(days=8))
    assert not card.nothing and card.cards == 2, "last week's card is last week's"
    assert card.usefulness["decision"][O.VERIFIED] == 1 and card.usefulness["decision"][O.CALLED_WRONG] == 1
    assert card.wrong_reasons == {"bad_timing": 1} and card.debits[0]["layer"] == attribute("bad_timing").layer
    assert card.held_back["reviews"] == 2 and card.held_back["fates"][K.HELD] == 1
    assert card.questions == {"asked": 2, "answered": 0, "called_wrong": 1}, "a question no longer asked is no wrong"
    assert [c_["correction_id"] for c_ in card.corrections] == [kept.correction_id]
    assert card.outcomes["all"]["verified"]["says"] == "1 of 2"
    assert card.coverage == (), "a tenant with no mailbox: an empty receipt"


@pytest.mark.pg
def test_a_week_not_over_is_read_so_far(engine):
    with engine.begin() as c:
        _card(c, "k_monday", state="queued", at=MONDAY + timedelta(hours=1), file="node_a")
        _card(c, "k_friday", state="queued", at=MONDAY + timedelta(days=4), file="node_b")
    with engine.connect() as c:
        card = S.scorecard_for(c, ORG, WEEK, now=MONDAY + timedelta(days=2))
    assert card.cards == 1 and card.usefulness["decision"][O.OPEN] == 1


@pytest.mark.pg
def test_an_empty_week_read_from_memory_says_so(engine):
    with engine.connect() as c:
        card = S.scorecard_for(c, ORG, S.Week.of("2026-W01"), now=MONDAY)
    assert card.nothing and card.says.startswith("Nothing happened in 2026-W01")
