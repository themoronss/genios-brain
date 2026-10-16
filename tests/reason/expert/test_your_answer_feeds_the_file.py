"""STEP-13 · your answer feeds the file: its dossier shows it, its fingerprint names it, its next review reads it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_your_answer_feeds_the_file.py

Tree `yc2_w27_s13` M36.C2.L-data.V2.U07 (`reason/expert/dossier`, `fingerprint`, `triggers`; STEP-13 §8.4 item
7). A question a file asked you, answered, is the file's: the dossier prints it in its own section — the id
the expert may cite (`[answer:<question id>]`), your words, when — the fingerprint's inputs name it, and an
answer the last review did not see is new evidence: the next sweep reviews the file with your answer in front
of the expert. ⛔ A file with no answer is printed and fingerprinted byte for byte as before.

⛔ YOUR ANSWER IS YOUR WORDS (M36.C2.L-data.V2.U12, `03` X05). The answer's own line prints its id and your
words, and nothing else: never the question's text — a held review's question IS the claim the check dropped,
so a line carrying it let "No. He asked for the roadmap" ground "Send Neel the deck" — and never its date,
printed on a line of its own, whose digits would ground any small number. A fact citing `answer:` is held to
your words alone, by the check as it stands (`reason/expert/verify`, the cited item is the fact's ground).
"""
from __future__ import annotations

import dataclasses
import os
from datetime import timedelta

import pytest

from genios_engine.context.founder_questions import ANSWERED, Question
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert import fingerprint as F
from genios_engine.reason.expert import triggers as T
from tests.reason.expert.test_the_dossier import FILE, NOW, _parts

ANSWER = Question(question_id="fq_0123456789abcdef01234567", file_id=FILE, fingerprint="ffp-1", run_id="run_1",
                  question="Is it so: “Kunal asked to move the call”? It is not in what it cites.",
                  why="misquoted (fact 1)", asked_at=NOW - timedelta(days=2), state=ANSWERED,
                  answer="Yes — he asked on WhatsApp to move it to Thursday.", answered_by="user_arjun",
                  answered_at=NOW - timedelta(days=1))
CITE = f"answer:{ANSWER.question_id}"


def _answered(*answers):
    return dataclasses.replace(_parts(), answers=tuple(answers))


def test_the_dossier_shows_what_you_told_us_and_the_expert_may_cite_it():
    dossier = D.build_dossier(_answered(ANSWER))
    section = next(s for s in dossier.sections if s.name == "answers")
    names = [s.name for s in dossier.sections]
    assert names[names.index("timeline") + 1] == "answers", "after what happened, before its promises"
    assert f"## {D.TITLES['answers']}" in dossier.text
    assert f"[{CITE}]" in section.text and CITE in dossier.catalogue.evidence_ids
    assert f"“{ANSWER.answer}”" in section.text and "2026-10-09" in section.text, "your words, and when"
    assert D.lines_by_id(dossier.text)[CITE][0].words is None, "your words are no mail's to quote"


def test_the_answers_line_is_your_words_and_its_id_and_nothing_else():
    """⛔ RESTATED by M36.C2.L-data.V2.U12 (`03` X05). U07 printed the question's text on the answer's line, and
    pinned it here (`ANSWER.question in section.text`): a held review's question is the claim its check dropped,
    so the line that grounds a fact citing `answer:` grounded that claim again. The line is the id and your
    words; the question is nowhere in the dossier; the date is a line of its own, no part of what is cited."""
    dossier = D.build_dossier(_answered(ANSWER))
    [place] = D.lines_by_id(dossier.text)[CITE]
    assert place.item == place.line == f"- [{CITE}] “{ANSWER.answer}”"
    assert ANSWER.question not in dossier.text and "Kunal asked to move the call" not in dossier.text
    assert "2026-10-09" not in place.item


def test_a_file_with_no_answer_is_printed_byte_for_byte_as_before():
    plain = D.build_dossier(_parts())
    assert D.build_dossier(_answered()) == plain
    assert "answers" not in {s.name for s in plain.sections} and D.TITLES["answers"] not in plain.text


def test_the_fingerprint_names_the_answer_and_no_answer_moves_nothing():
    kw = dict(prompt_version="expert-review.v3")
    plain, answered = F.fingerprint_inputs(_parts(), **kw), F.fingerprint_inputs(_answered(ANSWER), **kw)
    assert "answers" not in plain and F.fingerprint_inputs(_answered(), **kw) == plain
    assert answered["answers"] == [CITE]
    assert F.file_fingerprint(_answered(ANSWER), **kw) != F.file_fingerprint(_parts(), **kw)


def test_an_answer_the_last_review_did_not_see_brings_the_file_back():
    kw = dict(prompt_version="expert-review.v3")
    then = F.fingerprint_inputs(_parts(), **kw)
    last = type("Last", (), {"inputs": then, "reviewed_at": NOW - timedelta(days=3)})()
    parts = _answered(ANSWER)
    found = T.triggers_for(parts, F.fingerprint_inputs(parts, **kw), last=last)
    assert [t.kind for t in found] == [T.NEW_EVIDENCE] and CITE in found[0].says
    seen = type("Last", (), {"inputs": F.fingerprint_inputs(parts, **kw), "reviewed_at": NOW})()
    assert T.triggers_for(parts, F.fingerprint_inputs(parts, **kw), last=seen) == ()


# ── `03` X05's counter-example, on the check as it stands (`reason/expert/verify.check_review`) ──────────────────
#
# Neel Shah at Sequoia asked for the product roadmap. The expert claimed he asked for "the deck and the 2M SAFE
# terms from Sequoia", misquoting him: the check dropped the claim and the file asked you about it, in its words.
# You answered "No". The next review cites your answer for the very claim you denied.

NEEL, NEEL_MAIL, NEEL_FILE = "neel@sequoia.test", "evt_m1", "node_neel"
DENIED = "Neel asked for the deck and the 2M SAFE terms from Sequoia"
YOUR_NO = "No. He asked for the roadmap, not the deck."


def _neel(*answers, judgments=None) -> tuple:
    """Neel's file — our first mail, his ask for the roadmap — its dossier and its people, as the check reads them
    (`judgments`: what was judged before on it — its cards, M36.C2.L-logic.V2.U12's question card)."""
    from genios_engine.context.file_judgments import FileJudgments
    from genios_engine.context.workstream_numbers import FileNumbers, PersonNumbers
    from genios_engine.context.workstream_timeline import FileTimeline, Touch
    from genios_engine.context.workstreams import Lifecycle, WorkFile
    from genios_engine.contracts.company_brief import CompanyBriefLine, compose
    from genios_engine.contracts.measured import Measured, median_of
    from genios_engine.packs.compiler.playbook_reader import PlaybookAnswer
    from tests.reason.expert import check_world as W

    touches = (
        Touch(at=W.NOW - timedelta(days=15), kind="mail", direction="out", who="arjun@nimbuslabs.test",
              who_name="Arjun Rao", event_id="evt_ours", thread="t_neel",
              words="Hi Neel, good to meet you last week. Happy to share more."),
        Touch(at=W.NOW - timedelta(days=9), kind="mail", direction="in", who=NEEL, who_name="Neel Shah",
              event_id=NEEL_MAIL, thread="t_neel",
              words="Thanks Arjun. Could you send me the product roadmap before our partner meeting?"))
    gaps = (6.0,)
    timeline = FileTimeline(file_id=NEEL_FILE, as_of=W.NOW, touches=touches, upcoming=(), gaps_days=gaps,
                            usual_gap=median_of(gaps, basis="file", unit="days"), longest_gap_days=6.0,
                            days_quiet=9.0, silence_exceeds_prior_gaps=True)
    work = WorkFile(file_id=NEEL_FILE, kind=None, line=None, introduced_by=None, counterparty="Neel Shah",
                    counterparty_key=NEEL, counterparty_type="person", domains=("founder_office",),
                    correlations=("c_neel",), events=("evt_ours", NEEL_MAIL), first_touch=touches[0].at,
                    last_touch=touches[-1].at, days_quiet=9.0, whose_move="ours", open_asks=(),
                    people=(NEEL_FILE,), work_kind="investor")
    numbers = FileNumbers(file_id=NEEL_FILE, as_of=W.NOW, people=(PersonNumbers(
        node_id=NEEL_FILE, key=NEEL, name="Neel Shah", their_reply_time=Measured(value=6, n=1, basis="person",
                                                                                 unit="days"),
        their_normal=None, your_reply_time=Measured(value=None, n=0, basis="person", unit="days"),
        your_normal=None, bounced_at=None),), your_normal_overall=None, mailboxes=(),
        no_reply_since=touches[0].at, no_reply_can_be_said=False)
    parts = D.DossierParts(
        org_id="org_x", file_id=NEEL_FILE, as_of=W.NOW,
        brief=compose(org_id="org_x", company="Nimbus Labs", founder="Arjun Rao", lines=[CompanyBriefLine(
            line_id="cbl_1", section="in_motion", text="Investor · Sequoia", kind="investor",
            domain="sequoia.test")]),
        file=work, timeline=timeline, numbers=numbers, playbook=PlaybookAnswer(kind="investor", playbook=None,
                                                                              reason="no_kind"),
        judgments=judgments or FileJudgments(file_id=NEEL_FILE),
        lifecycle=Lifecycle(file_id=NEEL_FILE, situations=()),
        answers=tuple(answers))
    return D.build_dossier(parts), D.people_of(parts, us=W.US, our_names=W.OUR_NAMES)


def _neel_review(fact1: dict):
    from genios_engine.contracts.expert_review import ExpertReview
    return ExpertReview.from_mapping({
        "facts": [{"claim": DENIED, **fact1},
                  {"claim": "Neel has been quiet 9 days", "evidence": ["num:days_quiet"]}],
        "frames": {"primary": "Neel is quiet since his ask", "rivals": ["a busy week"]},
        "expected_vs_actual": {"stage": None, "expected": "a reply", "actual": "nothing yet"},
        "scenarios": {"do_nothing": "the meeting goes ahead without us", "act": "he has it first",
                      "best": "a second meeting", "worst": "a pass", "signals_to_watch": ["his reply"]},
        "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                      "reasons": ["his partner meeting is next"]},
        "mode": "act",
        "next_move": {"who": "you", "what": "Send Neel the deck and the 2M SAFE terms from Sequoia",
                      "for_whom": "Neel Shah", "by_when": None, "rests_on": ["fact:1", "fact:2"],
                      "to": "Neel Shah"},
        "alternative": "Ask Neel what he needs", "wait_or_stop": "if no reply, ask once",
        "done_when": "Neel has what he asked for",
        "draft": "Hi Neel, attaching the deck and the 2M SAFE terms from Sequoia."})


def _check(review, *answers):
    from genios_engine.reason.expert.verify import check_review
    dossier, people = _neel(*answers)
    return check_review(review, dossier.text, people, evidence_ids=dossier.catalogue.evidence_ids)


def _your_no(question: str) -> Question:
    from genios_engine.context.founder_questions import question_id_for
    return Question(question_id=question_id_for("org_x", NEEL_FILE, "ffp-neel-1", question), file_id=NEEL_FILE,
                    fingerprint="ffp-neel-1", run_id="run_1", question=question, why="misquoted (fact 1)",
                    asked_at=NOW - timedelta(days=2), state=ANSWERED, answer=YOUR_NO, answered_by="user_arjun",
                    answered_at=NOW - timedelta(days=1))


def _asked() -> Question:
    """Pass 1: the misquoted claim is dropped, the move held, and the file asks you.

    ⛔ RESTATED by M36.C2.L-logic.V2.U10 (fix, the second crosscheck G2): this pinned the question asking "in the
    claim's words" (`DENIED in held.question`) — the echo X10 names. It never repeats them now."""
    from genios_engine.contracts import claim_check as C
    held = _check(_neel_review({"evidence": [NEEL_MAIL], "quote": "send me the deck and the 2M SAFE terms"}))
    assert held.fate == C.HELD and DENIED not in held.question and "SAFE" not in held.question, held
    return _your_no(held.question)


@pytest.mark.parametrize("fact1", [
    {"evidence": ["ANSWER"]},
    {"evidence": ["ANSWER", NEEL_MAIL], "quote": "Could you send me the product roadmap"}],
    ids=["your-answer-alone", "your-answer-and-his-mail"])
def test_your_no_never_grounds_the_claim_you_denied(fact1):
    """⛔ `03` X05: pass 2 was SHOWN — "Send Neel the deck and the 2M SAFE terms from Sequoia", a draft to Neel
    Shah, your answer listed as its source. Now the claim you denied falls on your words, and the move with it."""
    from genios_engine.contracts import claim_check as C
    answered = _asked()
    cite = f"answer:{answered.question_id}"
    fact1 = {**fact1, "evidence": [cite if e == "ANSWER" else e for e in fact1["evidence"]]}
    checked = _check(_neel_review(fact1), answered)
    fact = next(v for v in checked.verdicts if v.line == "fact:1")
    assert fact.verdict == C.DROPPED, checked.verdicts
    assert checked.fate != C.SHOWN and checked.words.headline is None and checked.words.draft is None
    said = " ".join(str(w) for w in (checked.words.headline, checked.words.situation, checked.words.draft,
                                     checked.words.done_when))
    assert "deck" not in said and "SAFE" not in said


def test_without_your_answer_it_was_held_too():
    """The control: the same review with no answer line is held (its cited answer is no item of the dossier)."""
    from genios_engine.contracts import claim_check as C
    answered = _asked()
    checked = _check(_neel_review({"evidence": [f"answer:{answered.question_id}"]}))
    assert checked.fate == C.HELD


def test_your_words_still_ground_what_they_say():
    """⛔ THE NEGATIVE CONTROL: an answer is evidence of what YOU said — a fact restating it stands on it."""
    from genios_engine.contracts import claim_check as C
    answered = _asked()
    review = _neel_review({"evidence": [f"answer:{answered.question_id}"]})
    review = review.__class__.from_mapping({**review.as_mapping(), "facts": [
        {"claim": "You told us he asked for the roadmap, not the deck",
         "evidence": [f"answer:{answered.question_id}"]},
        {"claim": "Neel has been quiet 9 days", "evidence": ["num:days_quiet"]}]})
    checked = _check(review, answered)
    assert next(v for v in checked.verdicts if v.line == "fact:1").verdict == C.KEPT, checked.verdicts


@pytest.mark.pg
def test_the_file_reads_its_answers_from_the_questions_it_asked(pg_store):
    from sqlalchemy import text

    from genios_engine.context import founder_questions as Q
    from tests.context.workstream_world import FOUNDER, process, reset, tenant
    org = "org_s13_answer_feeds"
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("needs GENIOS_TEST_DATABASE_URL")
    tenant(pg_store, org)
    try:
        process(pg_store, org, event_id="evt_kunal_in", sender="kunal@meridianvc.test", thread="t_k",
                at=NOW - timedelta(days=5))
        with pg_store.engine.connect() as c:
            file_id = c.execute(text(
                "select k.anchor_node_id from context_correlations k join context_correlation_members m "
                "on m.org_id = k.org_id and m.correlation_id = k.correlation_id "
                "where k.org_id = :o and m.event_id = 'evt_kunal_in'"), {"o": org}).scalar()
        with pg_store.engine.begin() as c:
            asked = Q.ask(c, org_id=org, file_id=file_id, fingerprint="ffp-1", run_id=None,
                          question="Did Kunal ask to move the call?", why="misquoted (fact 1)",
                          at=NOW - timedelta(days=2))
            assert D.read_parts(c, org, file_id, now=NOW).answers == (), "asked is not answered"
            Q.answer(c, org_id=org, question_id=asked.question_id, words="Yes, to Thursday.",
                     by=FOUNDER, at=NOW - timedelta(days=1))
            parts = D.read_parts(c, org, file_id, now=NOW)
        assert [a.answer for a in parts.answers] == ["Yes, to Thursday."]
    finally:
        reset(pg_store, org)
