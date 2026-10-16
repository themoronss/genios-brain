"""STEP-13b · every line the expert leans on carries an id the check can hold it to.

    .venv/bin/python -m pytest -q tests/reason/expert/test_every_dossier_line_is_citable.py

Tree `yc2_w27_s13b` M37.C3.L-interface.V4.U01 (`dossier.v2`). Measured on Haiku's pass of 12 Oct: it cited the file's
head, the brief, what was checked and a section's "none" by their WORDS 288 times — they had no id — and 42 of its 68
held reviews fell on one. So the head is `[file:kind]`, `[file:role]`, `[file:whose_move]`, `[file:introduced_by]`,
`[file:first_touch]`, `[file:last_touch]`, `[file:domains]`; the brief `[brief:<line id>]` and `[brief:company]`; what was
checked `[cov:<mailbox>]` and `[cov:last_mail]`; each section's "none" `[none:promises]`, `[none:playbook]`,
`[none:we_wrote]`, `[none:touch]`. The catalogue holds them; `lines_by_id` reads them back.
"""
from __future__ import annotations

import dataclasses
import re
from datetime import timedelta

import pytest

from genios_engine.context.coverage_receipt import MailboxReceipt
from genios_engine.contracts.company_brief import CompanyBriefLine, compose
from genios_engine.reason.expert import dossier as D
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

def _mailbox(n: int = 0) -> MailboxReceipt:
    return MailboxReceipt(connection_id=f"con_{n}", address=f"box{n}@nimbuslabs.test", window_days=365,
                          window_start=W.NOW - timedelta(days=365), last_finished_at=W.NOW - timedelta(hours=1),
                          last_completed=True)


def _with_mailbox(**numbers):
    p = W.parts()
    return dataclasses.replace(p, numbers=dataclasses.replace(p.numbers, mailboxes=(_mailbox(),), **numbers))


HEAD = ("file:kind", "file:role", "file:whose_move", "file:first_touch", "file:last_touch", "file:domains")


def _line(text: str, ident: str) -> str:
    [place] = D.lines_by_id(text)[ident]
    return place.line


def test_the_dossier_is_the_second_version():
    assert D.DOSSIER_VERSION == "dossier.v2"
    dossier, _ = W.world()
    assert dossier.version == "dossier.v2" and "dossier.v2" in dossier.text.splitlines()[0]


@pytest.mark.parametrize("ident, starts", [
    ("file:kind", "Kind of work: "), ("file:role", "Its role in the brief: "),
    ("file:whose_move", "Whose move: "), ("file:domains", "Domains: "),
    ("file:introduced_by", "Introduced by: ")])
def test_each_line_of_the_files_head_carries_its_id_at_the_end_of_its_line(ident, starts):
    dossier, _ = W.world()
    line = _line(dossier.text, ident)
    assert line.startswith(starts) and line.endswith(f"[{ident}]"), line
    assert ident in dossier.catalogue.evidence_ids


def test_the_first_and_last_touch_are_two_ids_on_their_one_line():
    dossier, _ = W.world()
    first, last = _line(dossier.text, "file:first_touch"), _line(dossier.text, "file:last_touch")
    assert first == last and re.fullmatch(
        r"First touch \d{4}-\d\d-\d\d \d\d:\d\d UTC \[file:first_touch\]; last touch \d{4}-\d\d-\d\d \d\d:\d\d UTC "
        r"\[file:last_touch\]", first), first


def test_a_file_nobody_introduced_prints_no_introduced_by_id():
    dossier, _ = W.world(introduced_by=None)
    assert "file:introduced_by" not in dossier.catalogue.evidence_ids
    assert "Introduced by" not in dossier.text


def test_the_company_and_each_accepted_line_of_the_brief_carry_theirs():
    dossier, _ = W.world()
    parts = W.parts()
    block = next(s for s in dossier.sections if s.name == "brief").text
    assert re.search(r"^Company: .+ \[brief:company\]$", block, re.M)
    for line in parts.brief.lines:
        assert f"[brief:{line.line_id}]" in block and f"brief:{line.line_id}" in dossier.catalogue.evidence_ids
    tagged = [row for row in block.splitlines() if "[brief:" in row]
    assert len(tagged) == len(parts.brief.lines) + 1
    assert block.splitlines()[0].startswith("COMPANY BRIEF") and "[brief:" not in block.splitlines()[0]
    assert block.splitlines()[-1] == "END OF COMPANY BRIEF"


def test_two_brief_lines_with_the_same_words_keep_their_own_ids():
    lines = [CompanyBriefLine(line_id=f"cbl_{n}", section="goals", text="Close the round") for n in "ab"]
    brief = compose(org_id="o", company="Nimbus Labs", founder="Arjun Rao", lines=lines)
    block = D._brief_ids(brief, brief.prompt_block().strip(), D._Ids())
    assert block.count("Close the round [brief:cbl_a]") == 1 and block.count("Close the round [brief:cbl_b]") == 1


def test_the_brief_text_a_line_is_found_by_is_untouched_when_no_brief_is_accepted():
    dossier = D.build_dossier(dataclasses.replace(W.parts(), brief=None))
    assert next(s for s in dossier.sections if s.name == "brief").text == "No company brief is accepted for this tenant."


def test_each_mailbox_checked_and_the_last_mail_carry_theirs():
    dossier = D.build_dossier(_with_mailbox())
    text = next(s for s in dossier.sections if s.name == "coverage").text
    assert re.search(r"^- box0@nimbuslabs.test: reads .* \[cov:box0@nimbuslabs.test\]$", text, re.M)
    assert "cov:box0@nimbuslabs.test" in dossier.catalogue.evidence_ids
    assert "cov:last_mail" in dossier.catalogue.evidence_ids
    assert re.search(r"^Our last mail in the file: .* \[cov:last_mail\] — ", text, re.M)


def test_every_variant_of_the_last_mail_line_carries_its_id():
    answered = _line(D.build_dossier(_with_mailbox()).text, "cov:last_mail")
    assert "they wrote after it" in answered                                  # the file's reply, in the timeline
    p = _with_mailbox(no_reply_can_be_said=True)
    quiet = dataclasses.replace(p, timeline=dataclasses.replace(
        p.timeline, touches=tuple(t for t in p.timeline.touches if t.direction != "in")))
    assert "may be said up to" in _line(D.build_dossier(quiet).text, "cov:last_mail")
    unread = dataclasses.replace(quiet, numbers=dataclasses.replace(quiet.numbers, no_reply_can_be_said=False))
    assert "may NOT be said" in _line(D.build_dossier(unread).text, "cov:last_mail")


def test_a_section_with_nothing_to_say_says_none_and_the_none_has_an_id():
    p = W.parts()
    bare = dataclasses.replace(p, promises=(), timeline=dataclasses.replace(p.timeline, touches=(), upcoming=()),
                               playbook=dataclasses.replace(p.playbook, playbook=None, reason="no_kind"))
    text = D.build_dossier(bare).text
    assert _line(text, "none:promises") == "No promise was found in its mail. [none:promises]"
    assert _line(text, "none:touch").startswith("No touch yet. [none:touch]")
    assert _line(text, "none:playbook") == "No playbook for this file: the brief names no kind of work for it. [none:playbook]"


def test_we_have_not_written_says_none_we_wrote():
    text = D.build_dossier(_with_mailbox(no_reply_since=None)).text
    assert _line(text, "none:we_wrote") == "We have not written in this file. [none:we_wrote]"
    p = W.parts()
    mute = D.build_dossier(dataclasses.replace(p, numbers=dataclasses.replace(p.numbers, no_reply_since=None))).text
    assert "none:we_wrote" not in D.lines_by_id(mute) and "cov:last_mail" in D.lines_by_id(mute)


def test_every_id_the_dossier_prints_is_in_the_catalogue_and_read_back():
    dossier, _ = W.world()
    printed = set(D.lines_by_id(dossier.text))
    assert printed == set(dossier.catalogue.evidence_ids)
    assert set(HEAD) <= printed and {"brief:company", "cov:last_mail"} <= printed


def test_a_maximal_dossier_stays_under_its_bound_with_the_new_ids():
    p = W.parts(older=30)
    assert len(D.build_dossier(p).text) < D.DOSSIER_CHARS
