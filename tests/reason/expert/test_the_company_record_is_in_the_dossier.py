"""STEP-13b · what the company said of itself in OTHER files is in this file's dossier, citable and quotable.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_company_record_is_in_the_dossier.py

Tree `yc2_w27_s13b` M37.C3.L-interface.V6.U03. Section WHAT YOU SAID OF YOURSELF ELSEWHERE, after WHAT YOU TOLD US: one
line per mail of ours (not this file's own — that is its timeline) with the id `[self:<event>]` and, beneath it, the
statements about us, whole — a quote the check resolves exactly as a touch's. Printed only when there is one.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from genios_engine.context.company_record import CompanyRecord, SelfLine
from genios_engine.reason.expert import dossier as D
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

ELSEWHERE = SelfLine(event_id="evt_elsewhere", at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
                     said="We closed our pre-seed round last month. We have 40 customers.", said_cut=0)
CUT = SelfLine(event_id="evt_cut", at=datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc),
               said="We run a team of nine.", said_cut=120)
OWN = SelfLine(event_id=W.OURS, at=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc), said="We are a small team.")
TITLE = "WHAT YOU SAID OF YOURSELF ELSEWHERE"


def _record(*lines, cut=0):
    return CompanyRecord(org_id="org_x", as_of=W.NOW, lines=tuple(lines), cut=cut)


def _with(record):
    return D.build_dossier(dataclasses.replace(W.parts(), company=record))


def _titles(d):
    return [line[3:] for line in d.text.splitlines() if line.startswith("## ")]


def test_no_record_or_an_empty_one_leaves_the_dossier_as_before():
    plain = D.build_dossier(W.parts())
    assert _with(None).text == plain.text and _with(_record()).text == plain.text


def test_a_mail_of_this_files_own_is_not_repeated_here():
    assert _with(_record(OWN)).text == D.build_dossier(W.parts()).text, "it is already the file's timeline"


def test_the_section_follows_what_happened_and_each_line_carries_its_id_and_its_statements():
    d = _with(_record(ELSEWHERE, OWN))
    titles = _titles(d)
    assert titles.index(TITLE) == titles.index("WHAT HAPPENED") + 1
    assert "[self:evt_elsewhere]" in d.text and "self:evt_elsewhere" in d.catalogue.evidence_ids
    assert "self:" + W.OURS not in d.catalogue.evidence_ids
    [place] = D.lines_by_id(d.text)["self:evt_elsewhere"]
    assert "“We closed our pre-seed round last month. We have 40 customers.”" in d.text
    assert place.line == "- [self:evt_elsewhere] 2026-08-01 09:00 UTC · written by us, to someone else"


def test_it_follows_what_you_told_us_and_precedes_what_you_corrected():
    from genios_engine.context.founder_questions import Question
    from tests.reason.expert.test_your_correction_is_in_the_dossier import _correction
    answered = Question(question_id="fq_1", file_id=W.FILE, fingerprint="ffp-1", run_id="run_1",
                        question="Which quarter?", why="the file asks", asked_at=W.NOW, state="answered",
                        answer="This quarter's.", answered_by="user_arjun", answered_at=W.NOW)
    parts = dataclasses.replace(W.parts(), answers=(answered,), corrections=(_correction(1),),
                                company=_record(ELSEWHERE))
    names = [s.name for s in D.build_dossier(parts).sections]
    start = names.index("timeline")
    assert names[start:start + 4] == ["timeline", "answers", "company", "corrections"]


def test_what_the_record_cut_is_counted_and_a_cut_statement_says_so():
    d = _with(_record(CUT, cut=4))
    assert "(120 characters cut)" in d.text
    assert "… and 4 more mail(s) of ours, not shown." in d.text


def test_a_number_the_company_said_is_in_the_dossiers_numbers():
    d = _with(_record(ELSEWHERE))
    assert "40" in d.catalogue.numbers
