"""STEP-11 · a file knows what kind of work it is — from the in-motion line of the brief that names it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_file_knows_its_kind_of_work.py -q

`context/workstreams.files_for` (tree `yc2_w27_s11 · M30.C4.L-logic.V1.U04`, `06` D31). A file's `kind`
is a ROLE — connector, watched, person, intro — so no file could say what kind of WORK it is, and the next
step's expert could not pick the playbook for it (`speedrun008/YC-II W27/` STEP-11 §8.3 N1). Now a file
takes the `work_kind` of the accepted in-motion line whose counterparty names it: the line's address is
one of the file's people's, or its domain is the file's anchor's domain or a parent of it. The roles
stay beside it. Two lines naming one file: the first the founder accepted wins. A line with a kind and no
counterparty names no file; a line naming a counterparty with no kind gives none.
"""
from __future__ import annotations

import pytest

from genios_engine.context.workstreams import as_dict, file_as_dict, files_for
from genios_engine.contracts.company_brief import CompanyBriefLine, compose

from .workstream_world import (CONNECTOR, FOUNDER, UNSUBSCRIBE, WATCHED, brief, later, mention,
                               process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s11_work_kind"
RAHUL, FARAH = "rahul@kestrelcap.test", "farah@kitepath.test"
KIRAN, MEERA = "kiran@banyanseed.test", "meera.iyer@gmail.com"
NEHA, ANITA, PRIYA = "neha@apply.lakshya.test", "anita@notbanyanseed.test", "priya@northwind.test"
NOW = later(10)


def _motion(line_id, text, *, kind=None, address=None, domain=None):
    return CompanyBriefLine(line_id=line_id, section="in_motion", text=text, kind=kind,
                            address=address, domain=domain)


#: The founder's in-motion lines, in the order they were accepted.
MOTION = (
    _motion("cbl_m0", "Banyan Seed — first call held, data room asked", kind="investor",
            domain="banyanseed.test"),
    _motion("cbl_m1", "Meera Iyer — an angel cheque", kind="investor", address=MEERA),
    _motion("cbl_m2", "Kestrel Capital — Rahul, introduced by Introly", kind="investor",
            address=RAHUL),
    _motion("cbl_m3", "StartupSetu — the recognition application", kind="compliance",
            domain=WATCHED),
    _motion("cbl_m4", "Lakshya — the accelerator application", kind="program",
            domain="lakshya.test"),
    _motion("cbl_m5", "Hiring a founding AI engineer", kind="hiring"),
    _motion("cbl_m6", "Northwind — design partner talks", domain="northwind.test"),
)


def _brief(*motion):
    base = brief(ORG)
    return compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                   lines=[*base.lines, *motion])


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _world(store):
    """An introduction of two; a portal's notice; a fund's partner; an angel on a personal mailbox;
    a program writing from a subdomain; a lookalike of the fund; a correspondent the brief names
    with no kind."""
    b = _brief(*MOTION)
    for kw in (
            dict(event_id="evt_intro", sender=CONNECTOR, recipients=(FOUNDER, RAHUL, FARAH),
                 thread="t_intro", headers=UNSUBSCRIBE,
                 mentions=(mention("Rahul Menon"), mention("Farah Qureshi"),
                           mention("Kestrel Capital", "organization"),
                           mention("Kitepath", "organization"))),
            dict(event_id="evt_notice", sender=f"updates@{WATCHED}", at=later(1)),
            dict(event_id="evt_fund", sender=KIRAN, thread="t_fund", at=later(2)),
            dict(event_id="evt_angel", sender=MEERA, thread="t_angel", at=later(3)),
            dict(event_id="evt_program", sender=NEHA, thread="t_program", at=later(4)),
            dict(event_id="evt_lookalike", sender=ANITA, thread="t_lookalike", at=later(5)),
            dict(event_id="evt_priya", sender=PRIYA, thread="t_priya", at=later(6))):
        process(store, ORG, company_brief=b, **kw)


def _files(store, b):
    with store.engine.connect() as c:
        return {f.counterparty_key: f for f in files_for(c, ORG, now=NOW, company_brief=b).files}


def test_each_file_takes_the_kind_of_work_of_the_line_that_names_it(store):
    _world(store)
    files = _files(store, _brief(*MOTION))
    assert {k: f.work_kind for k, f in files.items()} == {
        "banyanseed.test": "investor",        # the fund's domain
        MEERA: "investor",                    # the angel, by her address: her file is her
        "kestrelcap.test": "investor",        # a company's file, by one of its people's address
        WATCHED: "compliance",                # the portal's domain
        "apply.lakshya.test": "program",      # a parent domain names the program's subdomain
        "kitepath.test": None,                # introduced too, and no line names it
        "notbanyanseed.test": None,           # a lookalike is not a subdomain
        "northwind.test": None}               # named by a line that names no kind


def test_the_role_stays_beside_the_kind_of_work(store):
    _world(store)
    files = _files(store, _brief(*MOTION))
    assert (files["kestrelcap.test"].kind, files["kestrelcap.test"].work_kind) == ("intro",
                                                                                   "investor")
    assert (files[WATCHED].kind, files[WATCHED].work_kind) == ("watched", "compliance")
    assert (files["banyanseed.test"].kind, files["banyanseed.test"].work_kind) == (None,
                                                                                   "investor")


def test_when_two_lines_name_one_file_the_first_accepted_wins(store):
    _world(store)
    by_domain = _motion("cbl_d", "Kestrel Capital — a distribution partnership", kind="partner",
                        domain="kestrelcap.test")
    by_address = _motion("cbl_a", "Rahul at Kestrel — raising", kind="investor", address=RAHUL)
    assert _files(store, _brief(by_domain, by_address))["kestrelcap.test"].work_kind == "partner"
    assert _files(store, _brief(by_address, by_domain))["kestrelcap.test"].work_kind == "investor"


def test_a_line_that_names_no_kind_does_not_stand_in_the_way_of_one_that_does(store):
    """"The first accepted wins" is among lines that give a kind: a line naming the file with no kind
    of work says nothing about its work, so a later line that names one still gives it."""
    _world(store)
    silent = _motion("cbl_s", "Kestrel Capital — we met at the demo day", domain="kestrelcap.test")
    named = _motion("cbl_n", "Rahul at Kestrel — raising", kind="investor", address=RAHUL)
    assert _files(store, _brief(silent, named))["kestrelcap.test"].work_kind == "investor"


def test_the_anchors_domain_is_a_companys_key_or_a_persons_host():
    """Pure. A company file is at its key; a person's file at their address's host — the rule the
    watchlist already follows (`_named`). Only a personal mailbox anchors a person today, and the
    store never takes one as a counterparty domain, so a person's file is named by their address."""
    from genios_engine.context.workstreams import _anchor_domain

    assert _anchor_domain("apply.lakshya.test") == "apply.lakshya.test"
    assert _anchor_domain(" Meera.Iyer@Gmail.com ") == "gmail.com"
    assert _anchor_domain(None) is None and _anchor_domain("") is None


def test_a_kind_with_no_counterparty_names_no_file(store):
    _world(store)
    files = _files(store, _brief(_motion("cbl_h", "Hiring a founding AI engineer", kind="hiring")))
    assert {f.work_kind for f in files.values()} == {None}


def test_without_a_brief_no_file_has_a_kind_of_work(store):
    _world(store)
    with store.engine.connect() as c:
        ws = files_for(c, ORG, now=NOW)                  # the store holds no accepted line
    assert ws.files and {f.work_kind for f in ws.files} == {None}


def test_the_brief_the_founder_accepted_types_the_files(store):
    """No brief handed in: the accepted lines are read where every reader reads them
    (`platform/company_brief.brief_for`), each with the kind its row keeps."""
    from datetime import timedelta

    from genios_engine.platform import company_brief_store as briefs

    _world(store)
    with store.engine.begin() as c:
        for n, line in enumerate(MOTION):
            briefs.add(c, org_id=ORG, section=line.section, words=line.text, address=line.address,
                       domain=line.domain, kind=line.kind, decided_by="founder",
                       at=NOW + timedelta(seconds=n))
    with store.engine.connect() as c:
        files = {f.counterparty_key: f.work_kind for f in files_for(c, ORG, now=NOW).files}
    assert (files["banyanseed.test"], files[MEERA], files["apply.lakshya.test"],
            files["kitepath.test"]) == ("investor", "investor", "program", None)


def test_the_file_as_json_says_its_kind_of_work(store):
    _world(store)
    with store.engine.connect() as c:
        ws = files_for(c, ORG, now=NOW, company_brief=_brief(*MOTION))
    fund = next(f for f in ws.files if f.counterparty_key == "banyanseed.test")
    assert file_as_dict(fund)["work_kind"] == "investor" and file_as_dict(fund)["kind"] is None
    listed = {f["counterparty"]["key"]: f["work_kind"] for f in as_dict(ws, now=NOW)["files"]}
    assert listed["kestrelcap.test"] == "investor" and listed["kitepath.test"] is None
