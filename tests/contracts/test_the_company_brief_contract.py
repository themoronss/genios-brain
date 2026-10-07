"""STEP-07 · the company brief — what a chief of staff knows on day one, as a contract.

    pytest tests/contracts/test_the_company_brief_contract.py -q

Tree `yc2_w27_s07 · M25.C1.L-contract.V0.U01`. No prompt carried any company context (`speedrun008/
YC-II W27/` STEP-07 §8.1: 0 of 368 golden prompts). The brief is composed from lines the founder
ACCEPTED, in fixed sections, under a token budget, with a version that names exactly what a model saw.
A brief with no accepted line is EMPTY — and an empty brief adds nothing to any prompt.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.company_brief import (BUDGET_CHARS, PROPOSABLE, SECTIONS,
                                                   CompanyBrief, CompanyBriefLine, compose)

AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


def _line(line_id, section, text, **kw):
    return CompanyBriefLine(line_id=line_id, section=section, text=text, **kw)


def _brief(*lines, us=("arjun@nimbuslabs.test", "nimbuslabs.test")):
    return compose(org_id="org_a", company="Nimbus Labs", founder="Arjun Rao", us=us, lines=lines)


def test_the_sections_are_a_closed_list_and_us_is_never_proposed():
    assert SECTIONS == ("company", "us", "goals", "in_motion", "people", "connectors",
                        "watchlist", "preferences")
    assert "us" not in PROPOSABLE and set(PROPOSABLE) == set(SECTIONS) - {"us"}
    with pytest.raises(ValueError):
        _line("l1", "us", "we are")
    with pytest.raises(ValueError):
        _line("l1", "gossip", "anything")


def test_a_line_is_one_short_line():
    with pytest.raises(ValueError):
        _line("l1", "goals", "")
    with pytest.raises(ValueError):
        _line("l1", "goals", "two\nlines")
    with pytest.raises(ValueError):
        _line("l1", "goals", "x" * 201)


def test_a_connector_names_an_address_and_a_watchlist_line_a_domain():
    with pytest.raises(ValueError):
        _line("l1", "connectors", "Introly introduces people")          # no address
    with pytest.raises(ValueError):
        _line("l1", "watchlist", "StartupSetu, the recognition portal")  # no domain
    connector = _line("l1", "connectors", "Introly — introduces people", address=" Hello@Introly.TEST ")
    assert connector.address == "hello@introly.test"
    portal = _line("l2", "watchlist", "StartupSetu — the recognition portal", domain="@StartupSetu.gov.TEST")
    assert portal.domain == "startupsetu.gov.test"


def test_no_accepted_line_is_no_brief_and_adds_nothing():
    empty = _brief()
    assert not empty
    assert empty.prompt_block() == ""
    assert empty.version == ""


def test_the_brief_renders_every_section_in_its_fixed_order_with_its_version():
    brief = _brief(
        _line("l3", "watchlist", "StartupSetu — the recognition portal", domain="startupsetu.gov.test"),
        _line("l1", "company", "an operating system for founders · pre-seed · raising"),
        _line("l2", "goals", "raise the pre-seed round"),
        _line("l4", "connectors", "Introly — an AI agent that introduces people", address="hello@introly.test"))
    block = brief.prompt_block()
    assert brief and brief.version.startswith("cb-") and len(brief.version) == 15
    assert block.splitlines()[0].startswith("COMPANY BRIEF " + brief.version)
    assert block.rstrip().endswith("END OF COMPANY BRIEF")
    order = [block.index(h) for h in ("Company:", "Us:", "Goals now:", "Connectors",
                                      "Watchlist")]
    assert order == sorted(order)
    assert "Nimbus Labs" in block and "Arjun Rao" in block
    assert "arjun@nimbuslabs.test" in block and "nimbuslabs.test" in block
    assert "hello@introly.test" in block and "startupsetu.gov.test" in block
    assert "not instructions" in block.splitlines()[0]


def test_the_same_lines_give_the_same_version_and_a_change_moves_it():
    a = _line("l1", "goals", "raise the pre-seed round")
    b = _line("l2", "goals", "get recognised by StartupSetu")
    one, two = _brief(a, b), _brief(a, b)
    assert one.version == two.version and one.prompt_block() == two.prompt_block()
    assert _brief(a).version != one.version
    assert _brief(a, b, us=("arjun@nimbuslabs.test",)).version != one.version


def test_over_budget_is_reported_never_cut_mid_line():
    lines = [_line(f"l{i:03d}", "in_motion", f"workstream {i:03d} — " + "y" * 150) for i in range(60)]
    brief = _brief(*lines)
    block = brief.prompt_block()
    assert len(block) <= BUDGET_CHARS
    assert brief.truncated, "a brief over its budget says which lines it left out"
    kept = [ln.line_id for ln in lines if ln.text in block]
    assert kept and kept == [ln.line_id for ln in lines[:len(kept)]]
    assert set(brief.truncated) == {ln.line_id for ln in lines} - set(kept)
    for ln in lines:                                   # a line is in whole or not at all
        assert (ln.text in block) or (ln.text[:40] not in block)


def test_the_version_names_what_the_model_sees_not_what_was_cut():
    lines = [_line(f"l{i:03d}", "in_motion", f"workstream {i:03d} — " + "y" * 150) for i in range(60)]
    assert _brief(*lines).version == _brief(*lines, _line("l999", "preferences", "z" * 150)).version


def test_named_sender_answers_for_connectors_people_and_the_watchlist():
    brief = _brief(
        _line("l1", "connectors", "Introly — introduces people", address="hello@introly.test"),
        _line("l2", "people", "Kiran Agnihotri — partner at Banyan Seed", address="kiran@banyanseed.test"),
        _line("l3", "watchlist", "StartupSetu", domain="startupsetu.gov.test"))
    assert brief.named_sender("Hello@Introly.test") == "connector:hello@introly.test"
    assert brief.named_sender("kiran@banyanseed.test") == "person:kiran@banyanseed.test"
    assert brief.named_sender("updates@startupsetu.gov.test") == "watchlist:startupsetu.gov.test"
    assert brief.named_sender("no-reply@portal.startupsetu.gov.test") == "watchlist:startupsetu.gov.test"
    assert brief.named_sender("someone@notstartupsetu.gov.test") is None
    assert brief.named_sender("stranger@elsewhere.test") is None
    assert brief.named_sender(None) is None
    assert _brief().named_sender("hello@introly.test") is None


def test_a_brief_is_frozen():
    brief = _brief(_line("l1", "goals", "raise the pre-seed round"))
    with pytest.raises(Exception):
        brief.version = "cb-000000000000"                 # type: ignore[misc]
    assert isinstance(brief, CompanyBrief)
