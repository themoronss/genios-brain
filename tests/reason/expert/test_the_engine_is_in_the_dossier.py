"""STEP-13b · the dossier prints what the engine knows, and what the units measured, each line citable.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_engine_is_in_the_dossier.py

Tree `yc2_w27_s13b` M37.C3.L-interface.V5.U02. Two optional sections: WHAT THE ENGINE KNOWS ABOUT ITS SITUATIONS
(after the playbook) and WHAT THE REASONING UNITS MEASURED (after the numbers). Printed only when there is something to
say — a file the engine read nothing for reads byte for byte as before. Every printed id is in the catalogue.
"""
from __future__ import annotations

import dataclasses

import pytest

from genios_engine.contracts import engine_read as E
from genios_engine.reason.expert import dossier as D
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

CAP = E.EngineLine(ref="cap:a.b.c#q", family=E.CAPABILITY, words="Who holds the next move?", source="a.b.c",
                   source_version="v", reviewed=False)
RULE = E.EngineLine(ref="rule:r1", family=E.RULE, words="Follow up within a week.", source="fundraising.rules",
                    source_version="v", reviewed=True)
UNIT = E.EngineLine(ref="ru:core.risk", family=E.UNIT, words="Risk reads high: quiet 21 days.", source="core.risk",
                    source_version="v", reviewed=False)


def _with(**over):
    p = W.parts()
    return D.build_dossier(dataclasses.replace(p, **over))


def _titles(d):
    return [line[3:] for line in d.text.splitlines() if line.startswith("## ")]


def test_a_file_the_engine_read_nothing_for_reads_as_before():
    plain = D.build_dossier(W.parts())
    assert _with(engine=E.EngineRead(), units=E.EngineRead()).text == plain.text
    assert _with(engine=None, units=None).text == plain.text


def test_the_engine_section_follows_the_playbook_and_prints_every_line_with_its_id_and_source():
    d = _with(engine=E.EngineRead(lines=(CAP, RULE)))
    titles = _titles(d)
    assert titles.index("WHAT THE ENGINE KNOWS ABOUT ITS SITUATIONS") == titles.index(
        "WHAT A PROFESSIONAL KNOWS ABOUT THIS WORK") + 1
    assert "- [cap:a.b.c#q] Who holds the next move? — a.b.c, not yet reviewed" in d.text
    assert "- [rule:r1] Follow up within a week. — fundraising.rules\n" in d.text
    assert {"cap:a.b.c#q", "rule:r1"} <= d.catalogue.evidence_ids


def test_a_situation_that_may_apply_and_one_not_read_are_named_with_why():
    read = E.EngineRead(
        lines=(RULE,),
        may_apply=(E.MayApply(situation="stalled_intro", capability="a.b.c", missing=("exists:thing",)),),
        not_read=(E.NotRead(situation_type="investor_relationship", domain="fundraising", reason="switched_off",
                            corpora=("fundraising",)),))
    text = _with(engine=read).text
    assert "May apply, not shown — stalled_intro (a.b.c)" in text and "exists:thing" in text
    assert ("Not read — a investor_relationship situation (fundraising): its corpus is switched off for your "
            "company (fundraising)") in text


def test_a_read_with_only_a_not_read_still_prints_the_section():
    read = E.EngineRead(not_read=(E.NotRead(situation_type="x", domain="y", reason="no_route"),))
    assert "Not read" in _with(engine=read).text


def test_cuts_are_counted():
    d = _with(engine=E.EngineRead(lines=(RULE,), cut={E.RULE: 3}))
    assert "… and 3 more of its rules, not shown." in d.text
    assert d.cut["engine"] == 3, "the dossier's own cut count carries the engine's"


def test_the_units_section_follows_the_numbers_and_every_reading_is_citable():
    d = _with(units=E.EngineRead(lines=(UNIT,)))
    titles = _titles(d)
    assert titles.index("WHAT THE REASONING UNITS MEASURED") == titles.index(
        "ITS NUMBERS") + 1
    assert "- [ru:core.risk] Risk reads high: quiet 21 days." in d.text
    assert "ru:core.risk" in d.catalogue.evidence_ids


def test_the_dossier_stays_deterministic_with_the_engine():
    read = E.EngineRead(lines=(CAP, RULE))
    assert _with(engine=read).digest == _with(engine=read).digest
    assert _with(engine=read).digest != D.build_dossier(W.parts()).digest


def test_an_engine_that_could_not_be_read_is_said_so_and_a_file_without_one_is_not_told():
    d = _with(engine=None, engine_error="the engine could not be read for this file")
    assert "Not read — the engine could not be read for this file." in d.text
    assert "WHAT THE ENGINE KNOWS ABOUT ITS SITUATIONS" in d.text
    assert _with(engine=None, engine_error=None).text == D.build_dossier(W.parts()).text
