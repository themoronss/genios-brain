"""STEP-09's two numbers, measured · every piece of work the brief names in motion has ONE file.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_in_motion.py -q

`yc2_w27_align` M34.C2.L-interface.V1.U08. STEP-09 promised "investors in the brief with a live file:
all" and "one file per subject", and measured neither: `check_every_named_counterparty_has_a_file`
reads connectors, people and the watchlist, and a counterparty named only by an in-motion line is no
named sender (`03` F125) — so a programme the founder applied to, whose mail the gate archived, had no
file and no check said so. `check_every_piece_of_work_has_one_file` reads the in-motion lines (`06`
D31): each whose counterparty memory holds mail with — from them or to them, an archive included,
never a mailing, spam, an auto-reply or a private mail — has exactly one file, by the rule a file
takes its kind of work by (`context/workstreams._work_kind`). None is F125's gap; two or more is one
subject split. Read-only, like every check: the connection is rolled back here.
"""
from __future__ import annotations

import importlib
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.context.workstream_world import FOUNDER, T0, ledger, node, process, reset, tenant

pytestmark = pytest.mark.pg

FUND, PROGRAMME, PORTAL = "kestrelcap.test", "awadhec.test", "startupsetu.gov.test"


def _module():
    return importlib.import_module("scripts.pipeline_health")


@pytest.fixture
def org(pg_store):
    org = f"org_u08_{uuid.uuid4().hex[:8]}"
    tenant(pg_store, org)
    yield org
    reset(pg_store, org)


def _line(store, org, *, kind, words, domain=None, address=None, days=0) -> None:
    from genios_engine.platform import company_brief, company_brief_store
    with store.engine.begin() as c:
        company_brief_store.add(c, org_id=org, section="in_motion", words=words, domain=domain,
                                address=address, kind=kind, decided_by="the founder",
                                at=T0 - timedelta(days=30 - days))
    company_brief.invalidate(org)


def _check(store, org):
    with store.engine.connect() as c:
        try:
            return _module().check_every_piece_of_work_has_one_file(c, org)
        finally:
            c.rollback()


def test_a_fund_that_wrote_has_its_one_file(pg_store, org):
    _line(pg_store, org, kind="investor", words="Raise · Kestrel Capital — engaged", domain=FUND)
    process(pg_store, org, event_id=f"{org}_fund", sender=f"rahul@{FUND}", thread="t_fund")
    check = _check(pg_store, org)
    assert check.ok, (check.measured, check.detail)
    assert check.measured == "1 piece(s) of work in motion have mail — no file: 0, split across files: 0"


def test_a_named_programmes_archived_mail_with_no_file_fails_and_is_named(pg_store, org):
    """`03` F125's measure: the founder named the programme, the gate archived its mail, and an
    in-motion counterparty is no named sender — so nothing promoted it and it has no file."""
    _line(pg_store, org, kind="program", words="Program · Awadh Enterprise Centre — applied",
          domain=PROGRAMME)
    ledger(pg_store, org, event_id=f"{org}_eic", sender=f"eic@{PROGRAMME}", thread=None,
           recipients=(FOUNDER,))
    with pg_store.engine.begin() as c:
        c.execute(text("update source_events set outcome = 'archived' where org_id = :o"), {"o": org})
    check = _check(pg_store, org)
    assert not check.ok
    assert "no file: 1," in check.measured, check.measured
    assert any(PROGRAMME in line and "no file" in line and "program" in line
               for line in check.detail), check.detail


def test_one_subject_in_two_files_fails(pg_store, org):
    """The fund's company file, and a second file anchored on its partner: one subject, two files."""
    _line(pg_store, org, kind="investor", words="Raise · Kestrel Capital — engaged", domain=FUND)
    event_id = f"{org}_fund"
    process(pg_store, org, event_id=event_id, sender=f"rahul@{FUND}", thread="t_fund")
    partner = node(pg_store, org, f"rahul@{FUND}")
    assert partner is not None
    with pg_store.engine.begin() as c:
        c.execute(text(
            "insert into context_correlations (correlation_id, org_id, anchor_node_id, anchor_type, "
            " domain, first_event_at, last_event_at) values (:c, :o, :n, 'person', 'fundraising', "
            " :at, :at)"), {"c": f"corr_{org}_split", "o": org, "n": partner.node_id, "at": T0})
        c.execute(text("insert into context_correlation_members (org_id, correlation_id, event_id) "
                       "values (:o, :c, :e)"), {"o": org, "c": f"corr_{org}_split", "e": event_id})
    check = _check(pg_store, org)
    assert not check.ok
    assert "split across files: 1" in check.measured, check.measured
    assert any(FUND in line and "2 files" in line for line in check.detail), check.detail


def test_mail_we_sent_them_is_their_mail_too(pg_store, org):
    """"Written to in the seed wave": the fund never answered, and the founder's mail to it is work."""
    _line(pg_store, org, kind="investor", words="Raise · Kestrel Capital — written to", domain=FUND)
    ledger(pg_store, org, event_id=f"{org}_out", sender=FOUNDER, thread=None,
           recipients=(f"rahul@{FUND}",))
    check = _check(pg_store, org)
    assert "1 piece(s) of work in motion have mail" in check.measured, check.measured


def test_a_mailing_or_a_private_mail_is_no_pieces_mail(pg_store, org):
    _line(pg_store, org, kind="program", words="Program · Awadh Enterprise Centre — applied",
          domain=PROGRAMME)
    process(pg_store, org, event_id=f"{org}_news", sender=f"news@{PROGRAMME}", thread=None,
            noise_type="newsletter")
    ledger(pg_store, org, event_id=f"{org}_mine", sender=f"eic@{PROGRAMME}", thread=None,
           recipients=(FOUNDER,))
    with pg_store.engine.begin() as c:
        c.execute(text("update source_events set visibility_scope = 'private' "
                       " where org_id = :o and event_id = :e"), {"o": org, "e": f"{org}_mine"})
    check = _check(pg_store, org)
    assert check.ok and check.measured.startswith("0 piece(s) of work in motion have mail"), (
        check.measured, check.detail)


def test_a_person_named_by_address_is_matched_by_address_only(pg_store, org):
    """A hire named by her address: her mail is hers; a colleague at the same mail provider's is not."""
    _line(pg_store, org, kind="hiring", words="Hiring · Kavitha Nair — offered the role",
          address="kavitha.nair@inboxmail.test")
    ledger(pg_store, org, event_id=f"{org}_other", sender="someone.else@inboxmail.test",
           thread=None, recipients=(FOUNDER,))
    check = _check(pg_store, org)
    assert check.measured.startswith("0 piece(s) of work in motion have mail"), check.measured


def test_a_hire_named_by_address_has_the_file_her_mail_is_in(pg_store, org):
    """F25's shape: the candidate on a personal mailbox, named by her address — one file, hers."""
    _line(pg_store, org, kind="hiring", words="Hiring · Kavitha Nair — offered the role",
          address="kavitha.nair@inboxmail.test")
    process(pg_store, org, event_id=f"{org}_offer", sender="kavitha.nair@inboxmail.test",
            thread="t_offer")
    check = _check(pg_store, org)
    assert check.ok and check.measured.startswith("1 piece(s) of work in motion have mail — no file: 0,"), (
        check.measured, check.detail)


@pytest.mark.parametrize("address, named", [
    ("eic@awadhec.test", True), ("news@mail.awadhec.test", True), ("eic@notawadhec.test", False),
    ("eic@awadhec.test.example", False), ("", False), (None, False)])
def test_a_domain_line_names_its_domain_and_the_domains_under_it(address, named):
    from genios_engine.contracts.company_brief import CompanyBriefLine
    line = CompanyBriefLine(line_id="cbl_x", section="in_motion", text="Program · Awadh",
                            domain=PROGRAMME, kind="program")
    assert _module()._names(line, address) is named


def test_a_brief_with_no_work_in_motion_measures_nothing_and_says_so(pg_store, org):
    process(pg_store, org, event_id=f"{org}_fund", sender=f"rahul@{FUND}", thread="t_fund")
    check = _check(pg_store, org)
    assert check.ok and check.measured.startswith("not exercised"), check.measured


def test_the_check_runs_with_the_others():
    module = _module()
    assert module.check_every_piece_of_work_has_one_file in module.CHECKS
