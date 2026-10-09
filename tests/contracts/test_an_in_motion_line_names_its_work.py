"""STEP-11 · an in-motion line of the brief names its kind of work and its counterparty (`06` D31).

    pytest tests/contracts/test_an_in_motion_line_names_its_work.py -q

`contracts/company_brief.py` (tree `yc2_w27_s11 · M30.C4.L-contract.V0.U02`). A founder's file knew only
its ROLE — connector, watched, person, intro — so no file could say what kind of WORK it is, and the
next step's expert could not pick the playbook for it (`speedrun008/YC-II W27/` STEP-11 §8.3 N1). Now
an in-motion line may name its kind, one of `WORK_KINDS`, and its counterparty through the line's own
`address` (a person) or `domain` (a fund, a program, a portal, a company) — each checked as a
connector's address and a watchlist's domain are. No other section names a kind.

THE MODEL NEVER SEES THE KIND. The prompt a brief renders is unchanged. A brief whose lines name no kind
has exactly the version it had before kinds existed — recorded cassettes carry it — and setting or
correcting a kind moves the version: the brief the founder accepted is then a different brief.
"""
from __future__ import annotations

import hashlib
from dataclasses import fields, replace

import pytest

from genios_engine.contracts.company_brief import (PROPOSABLE, WORK_KINDS, CompanyBriefLine,
                                                   compose)


def _line(line_id, section, text, **kw):
    return CompanyBriefLine(line_id=line_id, section=section, text=text, **kw)


def _brief(*lines):
    return compose(org_id="org_a", company="Nimbus Labs", founder="Arjun Rao",
                   us=("arjun@nimbuslabs.test", "nimbuslabs.test"), lines=lines)


# ── the kind ────────────────────────────────────────────────────────────────────────────────────

def test_the_kinds_of_work_are_a_closed_list():
    assert WORK_KINDS == ("investor", "program", "compliance", "hiring", "intro", "partner")


def test_the_kind_is_the_lines_last_field_and_no_kind_is_the_default():
    """The frozen contract the next units read: `kind` comes last, so every line built before it —
    by keyword or by position — is built exactly as before, with no kind."""
    assert [f.name for f in fields(CompanyBriefLine)] == ["line_id", "section", "text", "address",
                                                          "domain", "kind"]
    assert CompanyBriefLine("l1", "goals", "Raise the seed round").kind is None
    assert _line("l1", "in_motion", "Banyan Seed").kind is None


@pytest.mark.parametrize("kind", WORK_KINDS)
def test_an_in_motion_line_may_name_each_kind(kind):
    assert _line("l1", "in_motion", "Banyan Seed — first call held", kind=kind).kind == kind


def test_a_kind_is_read_as_its_word_whatever_its_case():
    assert _line("l1", "in_motion", "Banyan Seed", kind=" Investor ").kind == "investor"


@pytest.mark.parametrize("kind", ["fundraising", "investors", "accelerator", "", " ",
                                  "connector", "watched", "person"])
def test_a_kind_not_on_the_list_is_refused(kind):
    """`connector`, `watched` and `person` are a file's ROLES (`context/workstreams.KINDS`), not
    kinds of work — the two vocabularies stay apart. (`intro` is both: a connector's introduction is
    a role, introducing two people is work.)"""
    with pytest.raises(ValueError, match="not a kind of work"):
        _line("l1", "in_motion", "Banyan Seed", kind=kind)


_NAMES = {"people": {"address": "kiran@banyanseed.test"},
          "connectors": {"address": "hello@introly.test"},
          "watchlist": {"domain": "startupsetu.gov.test"}}


@pytest.mark.parametrize("section", [s for s in PROPOSABLE if s != "in_motion"])
def test_no_other_section_names_a_kind(section):
    extra = _NAMES.get(section, {})
    assert _line("l1", section, "A line of the brief", **extra).kind is None
    with pytest.raises(ValueError, match="only an in-motion line"):
        _line("l1", section, "A line of the brief", kind="investor", **extra)


# ── the counterparty ────────────────────────────────────────────────────────────────────────────

def test_the_counterparty_is_read_as_a_connectors_address_and_a_watchlists_domain_are():
    by_address = _line("l1", "in_motion", "Kiran — partner call booked", kind="investor",
                       address=" Kiran@BanyanSeed.TEST ")
    by_domain = _line("l2", "in_motion", "Banyan Seed — data room asked", kind="investor",
                      domain="@BanyanSeed.test.")
    assert (by_address.address, by_domain.domain) == ("kiran@banyanseed.test", "banyanseed.test")


@pytest.mark.parametrize("bad", [{"address": "not-an-address"}, {"address": "two@@at.test"},
                                 {"domain": "localhost"}, {"domain": "kiran@banyanseed.test"}])
def test_a_counterparty_that_is_neither_an_address_nor_a_domain_is_refused(bad):
    with pytest.raises(ValueError, match="is not a"):
        _line("l1", "in_motion", "Banyan Seed", kind="investor", **bad)


def test_a_kind_and_a_counterparty_are_each_optional():
    hire = _line("l1", "in_motion", "Hiring a founding AI engineer", kind="hiring")
    fund = _line("l2", "in_motion", "Banyan Seed — first call held", domain="banyanseed.test")
    assert (hire.kind, hire.address, hire.domain) == ("hiring", None, None)
    assert (fund.kind, fund.domain) == (None, "banyanseed.test")


def test_naming_a_counterparty_does_not_make_it_a_named_sender():
    """The gate's W-07 reads `named_sender` — connectors, people, the watchlist. D31 gives an in-motion
    line a counterparty for its FILE; who the gate keeps does not move with it, and moving it would be
    its own decision."""
    brief = _brief(_line("l1", "in_motion", "Banyan Seed — data room asked", kind="investor",
                         domain="banyanseed.test"),
                   _line("l2", "in_motion", "Kiran — partner call booked", kind="investor",
                         address="kiran@banyanseed.test"))
    assert brief.named_sender("kiran@banyanseed.test") is None
    assert brief.named_sender("deals@banyanseed.test") is None


# ── the version, and the words a model reads ────────────────────────────────────────────────────

#: A brief with every section, two in-motion lines naming a counterparty, and its version and text
#: as `compose` gave them BEFORE kinds existed — measured at `c63bd079`. Recorded cassettes carry
#: versions like it, so a brief that names no kind must not move by one byte.
PINNED_VERSION = "cb-4eebe8437f0a"
PINNED_TEXT_SHA256 = "9eb9ce1b1d2b698445904530a6761cc9230f41d1802a898d487284c61a59dcb7"


def _every_section(**kinds: str):
    """The pinned brief; `kinds` names a kind for an in-motion line by its id (`l3`, `l4`, `l5`)."""
    lines = [
        _line("l1", "company", "An AI chief of staff for founders · seed stage"),
        _line("l2", "goals", "Raise the seed round"),
        _line("l3", "in_motion", "Banyan Seed Fund — first call held, data room asked",
              domain="banyanseed.test"),
        _line("l4", "in_motion", "Lakshya accelerator — application under review",
              address="programs@lakshya.test"),
        _line("l5", "in_motion", "Hiring a founding AI engineer"),
        _line("l6", "people", "Kiran — partner at Banyan Seed", address="kiran@banyanseed.test"),
        _line("l7", "connectors", "Introly — introduces the founder to investors",
              address="hello@introly.test"),
        _line("l8", "watchlist", "StartupSetu — the recognition portal",
              domain="startupsetu.gov.test"),
        _line("l9", "preferences", "Never on a Sunday"),
    ]
    return compose(org_id="org_pin", company="Nimbus Labs", founder="Arjun Rao",
                   us=("arjun@nimbuslabs.test", "nimbuslabs.test"),
                   lines=[replace(ln, kind=kinds[ln.line_id]) if ln.line_id in kinds else ln
                          for ln in lines])


def test_a_brief_that_names_no_kind_is_byte_for_byte_the_brief_it_was():
    brief = _every_section()
    assert brief.version == PINNED_VERSION
    assert hashlib.sha256(brief.prompt_block().encode("utf-8")).hexdigest() == PINNED_TEXT_SHA256


def test_a_kind_moves_the_version_and_never_the_words():
    plain = _every_section()
    named = _every_section(l3="investor", l4="program", l5="hiring")
    assert named.version != plain.version and named.version.startswith("cb-")
    assert len(named.version) == len(plain.version)
    assert (named.prompt_block().replace(named.version, "VERSION")
            == plain.prompt_block().replace(plain.version, "VERSION")), "a model was shown a kind"


def test_setting_or_correcting_a_kind_is_a_different_brief_and_the_same_kinds_the_same_one():
    one, other = _every_section(l3="investor"), _every_section(l3="partner")
    assert one.version != other.version != _every_section().version
    assert _every_section(l3="investor").version == one.version
    assert _every_section(l3="investor", l4="program").version != one.version
    # The same kinds on other lines say other files are that work — another brief.
    assert (_every_section(l3="investor", l4="program").version
            != _every_section(l3="program", l4="investor").version)


def test_the_kind_of_a_line_the_budget_left_out_does_not_move_the_version():
    """As its words do not (`test_the_version_names_what_the_model_sees_not_what_was_cut`): the
    version is over the lines the brief keeps — their words and, from STEP-11, their kinds."""
    lines = [_line(f"l{i:03d}", "in_motion", f"workstream {i:03d} — " + "y" * 150) for i in range(60)]
    plain = _brief(*lines)
    cut, kept = plain.truncated[-1], lines[0].line_id
    assert cut != kept and kept not in plain.truncated
    named_cut = _brief(*[replace(ln, kind="investor") if ln.line_id == cut else ln for ln in lines])
    named_kept = _brief(*[replace(ln, kind="investor") if ln.line_id == kept else ln for ln in lines])
    assert named_cut.version == plain.version
    assert named_kept.version != plain.version
