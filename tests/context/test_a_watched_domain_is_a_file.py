"""STEP-09 · a portal or program the company brief watches is a file, whatever address it writes from.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_watched_domain_is_a_file.py -q

`context/pipeline.process_event` (tree `yc2_w27_s09 · M27.C2.L-logic.V0.U01`). A government portal
writes from `updates@`, `no-reply@` and `support@`; `_is_automated_sender` makes each of those a
`service` node and the whole mail noise for the network and for correlation — so on the golden set the
StartupSetu application (F01, F02) and the State Startup Mission (F23) had no file at all, though
STEP-07 had made their mail kept and read (`03` F93). Now mail from a domain the founder's brief
watches — or a subdomain of it — is filed under that domain's organisation, one file for the portal,
whichever of its addresses wrote. A watched domain's MAILING (an unsubscribe header, a list id) is still
a newsletter, never a file — golden F32, which must stay without a card — and so is an auto-reply.
"""
from __future__ import annotations

import pytest

from .workstream_world import (FOUNDER, UNSUBSCRIBE, WATCHED, anchors, brief, later, mention, node,
                               noise, process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_watched"


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _notice(store, event_id, sender, **kw):
    kw.setdefault("company_brief", brief(ORG))
    process(store, ORG, event_id=event_id, sender=sender, thread=None, **kw)
    return anchors(store, ORG, event_id)


@pytest.mark.parametrize("address", [f"updates@{WATCHED}", f"no-reply@{WATCHED}",
                                     f"support@{WATCHED}"])
def test_a_portals_notice_is_filed_under_the_portal(store, address):
    assert _notice(store, "evt_notice", address) == {WATCHED}
    assert noise(store, ORG, "evt_notice") == ["email_relevance"]
    assert node(store, ORG, address).node_type == "service", "a portal's address is not a person"


def test_every_address_of_the_portal_shares_one_file(store):
    assert _notice(store, "evt_a", f"updates@{WATCHED}") == {WATCHED}
    assert _notice(store, "evt_b", f"no-reply@notify.{WATCHED}") == {WATCHED}
    assert node(store, ORG, f"notify.{WATCHED}") is None, "a subdomain became a second portal"


def test_a_notice_naming_a_known_company_is_still_the_portals(store):
    """The portal's address is a machine, and a machine's role carries to its company — which made
    the portal non-anchoring the moment its notice named anyone else the graph knows. The brief
    watches the portal: it is the counterparty of every notice it sends."""
    process(store, ORG, event_id="evt_vc", sender="rahul@kestrelcap.test", thread="t_vc",
            company_brief=brief(ORG))
    assert WATCHED in _notice(store, "evt_notice", f"updates@{WATCHED}", at=later(1),
                              mentions=(mention("Kestrelcap", "organization"),))


def test_a_watched_domains_newsletter_is_not_a_file(store):
    """Golden F32: the program's community mailing is read, and still never a file or a card."""
    assert _notice(store, "evt_news", f"community@{WATCHED}", headers=UNSUBSCRIBE) == set()


def test_a_notice_the_portal_marks_auto_generated_is_still_a_file(store):
    """RFC 3834's `auto-generated` is how a portal sends one founder a notice — not a mailing."""
    assert _notice(store, "evt_notice", f"updates@{WATCHED}",
                   headers={"Auto-Submitted": "auto-generated"}) == {WATCHED}


@pytest.mark.parametrize("headers", [{"List-Id": "<community.startupsetu.gov.test>"},
                                     {"Precedence": "bulk"}])
def test_every_mark_of_a_mailing_keeps_it_out(store, headers):
    assert _notice(store, "evt_news", f"community@{WATCHED}", headers=headers) == set()
    assert noise(store, ORG, "evt_news") == ["email_noise:newsletter"], "recorded as what it is"


def test_an_auto_reply_from_the_portal_is_not_a_file(store):
    assert _notice(store, "evt_ooo", f"support@{WATCHED}",
                   headers={"Auto-Submitted": "auto-replied"}) == set()
    assert noise(store, ORG, "evt_ooo") == ["email_noise:auto_reply"]


def test_an_out_of_office_layer_1_marked_is_not_a_file(store):
    from genios_engine.capture.gate.rules import AUTO_REPLY
    assert _notice(store, "evt_ooo", f"support@{WATCHED}", availability_marker=AUTO_REPLY) == set()


def test_a_machine_sender_the_brief_does_not_watch_is_still_noise(store):
    assert _notice(store, "evt_other", "no-reply@shop.test") == set()


def test_without_a_brief_the_portal_is_noise_as_before(store):
    assert _notice(store, "evt_notice", f"updates@{WATCHED}", company_brief=None) == set()
