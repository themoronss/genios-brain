"""STEP-12 · a counterparty a work line of the brief names is a named sender, like a watched portal (`03` F125).

    pytest tests/contracts/test_an_in_motion_counterparty_is_a_named_sender.py -q

`contracts/company_brief.py` (tree `yc2_w27_s12` M32.C1.L-contract.V0.U05, added by `yc2_w27_align`
M34.C4). Promotion and the gate's W-07 kept the mail of the senders the brief names — a connector, a key
person, a watched domain — and nothing else. A work line ("Program · Awadh Enterprise Centre — applied",
kind `program`, domain `awadhec.test`) names its counterparty too, and its mail stayed archived: on the
golden set F21's and F22's programmes had no file (M34's health check measured it). Now `named_sender`
answers `in_motion:<kind>:<address or domain>` for a WORK line — an in-motion line that names its kind
and its counterparty, the lines `context/workstreams` files work by — after the three it answered
before, which keep their precedence. `names_a_sender` says, for every door that accepts a line, whether
accepting it promotes that sender's archive.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts.company_brief import CompanyBriefLine, compose, names_a_sender

pytestmark = pytest.mark.unit


def _line(line_id, section, text, **kw):
    return CompanyBriefLine(line_id=line_id, section=section, text=text, **kw)


def _brief(*lines):
    return compose(org_id="org_a", company="Nimbus Labs", founder="Arjun Rao",
                   us=("arjun@nimbuslabs.test", "nimbuslabs.test"), lines=lines)


PROGRAMME = _line("l_awadh", "in_motion", "Program · Awadh Enterprise Centre — applied",
                  kind="program", domain="awadhec.test")
CANDIDATE = _line("l_kavitha", "in_motion", "Hiring · Kavitha Nair — the offer",
                  kind="hiring", address="kavitha.nair@inboxmail.test")


def test_a_work_line_names_its_counterparty_by_domain():
    brief = _brief(PROGRAMME)
    assert brief.named_sender("eic@awadhec.test") == "in_motion:program:awadhec.test"
    assert brief.named_sender("EIC@Mail.AwadhEC.test") == "in_motion:program:awadhec.test"
    assert brief.named_sender("eic@notawadhec.test") is None
    assert brief.named_sender("eic@awadhec.test.example") is None


def test_a_work_line_names_its_counterparty_by_address_alone():
    brief = _brief(CANDIDATE)
    assert brief.named_sender("kavitha.nair@inboxmail.test") == \
        "in_motion:hiring:kavitha.nair@inboxmail.test"
    assert brief.named_sender("someone.else@inboxmail.test") is None


def test_an_in_motion_line_without_its_kind_or_counterparty_names_no_one():
    """Not a work line — `context/workstreams` files no work by it either."""
    no_kind = _line("l_a", "in_motion", "Talking to Awadh Enterprise Centre", domain="awadhec.test")
    no_party = _line("l_b", "in_motion", "Program · some accelerator", kind="program")
    brief = _brief(no_kind, no_party)
    assert brief.named_sender("eic@awadhec.test") is None


def test_the_names_the_brief_gave_before_keep_their_precedence():
    connector = _line("l_c", "connectors", "Awadh's partner desk", address="desk@awadhec.test")
    watched = _line("l_w", "watchlist", "The centre's portal", domain="portal.awadhec.test")
    person = _line("l_p", "people", "Kavitha Nair", address="kavitha.nair@inboxmail.test")
    brief = _brief(PROGRAMME, CANDIDATE, connector, watched, person)
    assert brief.named_sender("desk@awadhec.test") == "connector:desk@awadhec.test"
    assert brief.named_sender("kavitha.nair@inboxmail.test") == "person:kavitha.nair@inboxmail.test"
    assert brief.named_sender("noreply@portal.awadhec.test") == "watchlist:portal.awadhec.test"
    assert brief.named_sender("eic@awadhec.test") == "in_motion:program:awadhec.test"


def test_the_first_work_line_the_founder_accepted_names_a_shared_counterparty():
    first = _line("l_1", "in_motion", "Program · Awadh — applied", kind="program",
                  domain="awadhec.test")
    second = _line("l_2", "in_motion", "Partner · Awadh — a pilot", kind="partner",
                   domain="awadhec.test")
    assert _brief(first, second).named_sender("eic@awadhec.test") == "in_motion:program:awadhec.test"
    assert _brief(second, first).named_sender("eic@awadhec.test") == "in_motion:partner:awadhec.test"


def test_an_empty_brief_or_no_address_names_no_one():
    assert _brief().named_sender("eic@awadhec.test") is None
    assert _brief(PROGRAMME).named_sender(None) is None
    assert _brief(PROGRAMME).named_sender("not an address") is None


@pytest.mark.parametrize("section, kw, names", [
    ("connectors", {"address": "hello@introly.test"}, True),
    ("people", {"address": "kavitha@x.test"}, True),
    ("watchlist", {"domain": "portal.gov.test"}, True),
    ("in_motion", {"kind": "program", "domain": "awadhec.test"}, True),
    ("in_motion", {"kind": "hiring", "address": "kavitha@x.test"}, True),
    ("in_motion", {"domain": "awadhec.test"}, False),               # no kind: not a work line
    ("in_motion", {"kind": "program"}, False),                      # no counterparty
    ("goals", {}, False),
    ("company", {}, False),
])
def test_names_a_sender_is_the_one_answer_every_door_asks(section, kw, names):
    assert names_a_sender(section, address=kw.get("address"), domain=kw.get("domain"),
                          kind=kw.get("kind")) is names
    if section in ("connectors", "watchlist") or kw:
        line = _line("l_x", section, "a line", **kw)
        assert line.names_a_sender is names
