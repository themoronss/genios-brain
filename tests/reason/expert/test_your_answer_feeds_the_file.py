"""STEP-13 · your answer feeds the file: its dossier shows it, its fingerprint names it, its next review reads it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_your_answer_feeds_the_file.py

Tree `yc2_w27_s13` M36.C2.L-data.V2.U07 (`reason/expert/dossier`, `fingerprint`, `triggers`; STEP-13 §8.4 item
7). A question a file asked you, answered, is the file's: the dossier prints it in its own section — the id
the expert may cite (`[answer:<question id>]`), what was asked, your words, when — the fingerprint's inputs
name it, and an answer the last review did not see is new evidence: the next sweep reviews the file with your
answer in front of the expert. ⛔ A file with no answer is printed and fingerprinted byte for byte as before.
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
    assert f"[{CITE}]" in section.text and ANSWER.question in section.text
    assert f"“{ANSWER.answer}”" in section.text and "2026-10-09" in section.text
    assert CITE in dossier.catalogue.evidence_ids
    assert D.lines_by_id(dossier.text)[CITE][0].words is None, "your words are no mail's to quote"


def test_a_file_with_no_answer_is_printed_byte_for_byte_as_before():
    plain = D.build_dossier(_parts())
    assert D.build_dossier(_answered()) == plain
    assert "answers" not in {s.name for s in plain.sections} and D.TITLES["answers"] not in plain.text


def test_the_fingerprint_names_the_answer_and_no_answer_moves_nothing():
    kw = dict(model="claude-sonnet-5", prompt_version="expert-review.v3")
    plain, answered = F.fingerprint_inputs(_parts(), **kw), F.fingerprint_inputs(_answered(ANSWER), **kw)
    assert "answers" not in plain and F.fingerprint_inputs(_answered(), **kw) == plain
    assert answered["answers"] == [CITE]
    assert F.file_fingerprint(_answered(ANSWER), **kw) != F.file_fingerprint(_parts(), **kw)


def test_an_answer_the_last_review_did_not_see_brings_the_file_back():
    kw = dict(model="claude-sonnet-5", prompt_version="expert-review.v3")
    then = F.fingerprint_inputs(_parts(), **kw)
    last = type("Last", (), {"inputs": then, "reviewed_at": NOW - timedelta(days=3)})()
    parts = _answered(ANSWER)
    found = T.triggers_for(parts, F.fingerprint_inputs(parts, **kw), last=last)
    assert [t.kind for t in found] == [T.NEW_EVIDENCE] and CITE in found[0].says
    seen = type("Last", (), {"inputs": F.fingerprint_inputs(parts, **kw), "reviewed_at": NOW})()
    assert T.triggers_for(parts, F.fingerprint_inputs(parts, **kw), last=seen) == ()


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
