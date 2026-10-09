"""STEP-11 · a brief line's kind of work is written, kept and read — by the brief's one writer.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_a_brief_line_keeps_its_kind.py -q

`platform/company_brief_store.py` (tree `yc2_w27_s11 · M30.C4.L-data.V1.U06`). The contract can say what
kind of work an in-motion line is (`contracts/company_brief.WORK_KINDS`, `06` D31) and migration 0196 can
hold it, but the store wrote, kept and read none of it: a kind the drafter proposed or the founder chose
would have been dropped on the way in. Now `propose`, `add` and `accept` write it, `accepted` and
`pending` read it, and accepting may set, correct or clear it — the founder's edit, like their words —
and may correct the counterparty. An in-motion line names its counterparty by address or domain,
checked as any line's is: a public mail host is never a domain.

NOTHING DROPS A KIND SILENTLY. Adding a line the brief already holds, with another kind, is refused —
never answered with the old line's id as if the kind were kept. And a stored kind the list no longer
holds is read as no kind, so one row can never make the whole brief unreadable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import company_brief_store as store

pytestmark = pytest.mark.pg

ORG = "org_s11_brief_kind"
AT = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)
FUND = "Banyan Seed — first call held, data room asked"


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, company) values (:o, 'Arjun Rao', 'Nimbus Labs')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _row(eng, line_id):
    with eng.connect() as c:
        return c.execute(text(
            "select status, text, proposed_text, address, domain, kind from company_brief_lines "
            " where org_id = :o and line_id = :l"), {"o": ORG, "l": line_id}).mappings().one()


def _propose(c, words=FUND, **kw):
    kw.setdefault("section", "in_motion")
    return store.propose(c, org_id=ORG, words=words, proposed_by="drafter", at=AT, **kw)


def _accepted(c):
    return {ln.line_id: (ln.kind, ln.address, ln.domain) for ln in store.accepted(c, ORG)}


def test_a_proposal_keeps_its_kind_and_counterparty_and_the_accepted_line_carries_them(engine):
    with engine.begin() as c:
        line = _propose(c, kind="investor", domain="banyanseed.test")
        assert [(p["kind"], p["domain"]) for p in store.pending(c, ORG)] == [
            ("investor", "banyanseed.test")]
        assert store.accepted(c, ORG) == []
    with engine.begin() as c:
        got = store.accept(c, org_id=ORG, line_id=line, decided_by="founder", at=AT)
        assert (got.kind, got.domain) == ("investor", "banyanseed.test")
        assert _accepted(c) == {line: ("investor", None, "banyanseed.test")}
    assert _row(engine, line)["kind"] == "investor"


def test_a_line_that_names_no_kind_is_written_and_read_as_before(engine):
    with engine.begin() as c:
        goal = store.add(c, org_id=ORG, section="goals", words="Raise the seed round",
                         decided_by="founder", at=AT)
        motion = _propose(c, words="Hiring a founding AI engineer")
        assert store.pending(c, ORG)[0]["kind"] is None
        store.accept(c, org_id=ORG, line_id=motion, decided_by="founder", at=AT)
        assert _accepted(c) == {goal: (None, None, None), motion: (None, None, None)}


def test_accepting_may_set_correct_or_clear_the_kind(engine):
    with engine.begin() as c:
        unnamed = _propose(c, words="Lakshya accelerator — application under review")
        wrong = _propose(c, words="Northfield — distribution partnership", kind="investor")
        unwanted = _propose(c, words="DigiVault — documents for the application", kind="compliance")
        kept = _propose(c, words="Tusker Capital — pitch on Friday", kind="investor")
    with engine.begin() as c:
        assert store.accept(c, org_id=ORG, line_id=unnamed, decided_by="founder", at=AT,
                            kind="program").kind == "program"
        assert store.accept(c, org_id=ORG, line_id=wrong, decided_by="founder", at=AT,
                            kind="partner").kind == "partner"
        assert store.accept(c, org_id=ORG, line_id=unwanted, decided_by="founder", at=AT,
                            kind=None).kind is None
        assert store.accept(c, org_id=ORG, line_id=kept, decided_by="founder", at=AT,
                            kind=store.AS_PROPOSED).kind == "investor"
    assert [_row(engine, ln)["kind"] for ln in (unnamed, wrong, unwanted, kept)] == [
        "program", "partner", None, "investor"]
    # A kind is not words: the proposal's words are kept only when the founder edits the WORDS.
    assert {_row(engine, ln)["proposed_text"] for ln in (unnamed, wrong, unwanted, kept)} == {None}


def test_accepting_may_correct_or_clear_the_counterparty(engine):
    with engine.begin() as c:
        by_domain = _propose(c, kind="investor", domain="banyanseed.test")
        by_address = _propose(c, words="Kiran — partner call booked", kind="investor",
                              address="kiran@banyanseed.test")
        loose = _propose(c, words="Fjord Ventures — intro asked", kind="investor",
                         domain="fjord.test")
    with engine.begin() as c:
        store.accept(c, org_id=ORG, line_id=by_domain, decided_by="founder", at=AT,
                     domain="BanyanSeed.vc")
        store.accept(c, org_id=ORG, line_id=by_address, decided_by="founder", at=AT,
                     address="kiran.r@banyanseed.vc", words="Kiran — partner call on Friday")
        store.accept(c, org_id=ORG, line_id=loose, decided_by="founder", at=AT, domain=None)
        assert _accepted(c) == {by_domain: ("investor", None, "banyanseed.vc"),
                                by_address: ("investor", "kiran.r@banyanseed.vc", None),
                                loose: ("investor", None, None)}
    assert _row(engine, by_address)["proposed_text"] == "Kiran — partner call booked"


def test_the_founders_own_line_keeps_its_kind_and_counterparty(engine):
    with engine.begin() as c:
        line = store.add(c, org_id=ORG, section="in_motion", words=FUND, decided_by="founder",
                         at=AT, kind="Investor", domain="banyanseed.test")
        assert _accepted(c) == {line: ("investor", None, "banyanseed.test")}
    assert _row(engine, line)["status"] == "accepted"


def test_adding_what_the_brief_holds_with_another_kind_is_refused_never_dropped(engine):
    """⛔ `add` answers a line the brief already holds with that line's id. Before this unit a kind on
    the second `add` was dropped on the floor and the caller told it was in force."""
    with engine.begin() as c:
        line = store.add(c, org_id=ORG, section="in_motion", words=FUND, decided_by="founder",
                         at=AT, domain="banyanseed.test")
    for kind in ("investor", "partner"):
        with pytest.raises(store.CompanyBriefError) as refused:
            with engine.begin() as c:
                store.add(c, org_id=ORG, section="in_motion", words=FUND, decided_by="founder",
                          at=AT, kind=kind, domain="banyanseed.test")
        assert refused.value.code == "kind_differs" and line in str(refused.value)
    with engine.begin() as c:
        assert store.add(c, org_id=ORG, section="in_motion", words=FUND.upper(),
                         decided_by="founder", at=AT) == line            # no kind asked for
    assert _row(engine, line)["kind"] is None
    with engine.begin() as c:
        named = store.add(c, org_id=ORG, section="in_motion", words="Tusker Capital — pitch on Friday",
                          decided_by="founder", at=AT, kind="investor")
        assert store.add(c, org_id=ORG, section="in_motion", words="Tusker Capital — pitch on Friday",
                         decided_by="founder", at=AT, kind="investor") == named
        # Asking for no kind is not asking to change it: the line the brief holds, as it holds it.
        assert store.add(c, org_id=ORG, section="in_motion", words="Tusker Capital — pitch on Friday",
                         decided_by="founder", at=AT) == named
    assert _row(engine, named)["kind"] == "investor"
    with pytest.raises(store.CompanyBriefError):
        with engine.begin() as c:
            store.add(c, org_id=ORG, section="in_motion", words="Tusker Capital — pitch on Friday",
                      decided_by="founder", at=AT, kind="partner")


def test_a_kind_where_none_may_be_is_refused_before_anything_is_written(engine):
    for act in (lambda c: _propose(c, section="goals", words="Raise the seed round", kind="investor"),
                lambda c: _propose(c, kind="fundraising"),
                lambda c: store.add(c, org_id=ORG, section="watchlist", words="StartupSetu",
                                    domain="startupsetu.gov.test", decided_by="founder", at=AT,
                                    kind="compliance")):
        with pytest.raises(ValueError):
            with engine.begin() as c:
                act(c)
    with engine.connect() as c:
        assert c.execute(text("select count(*) from company_brief_lines where org_id = :o"),
                         {"o": ORG}).scalar() == 0
    with engine.begin() as c:
        goal = _propose(c, section="goals", words="Raise the seed round")
    with pytest.raises(ValueError):
        with engine.begin() as c:
            store.accept(c, org_id=ORG, line_id=goal, decided_by="founder", at=AT, kind="investor")
    assert (_row(engine, goal)["status"], _row(engine, goal)["kind"]) == ("proposed", None)


def test_a_public_mail_host_is_never_a_counterparty_domain(engine):
    with pytest.raises(ValueError):
        with engine.begin() as c:
            _propose(c, kind="investor", domain="gmail.com")
    with engine.begin() as c:
        line = _propose(c, kind="investor", domain="banyanseed.test")
    with pytest.raises(ValueError):
        with engine.begin() as c:
            store.accept(c, org_id=ORG, line_id=line, decided_by="founder", at=AT, domain="GMAIL.com")
    assert _row(engine, line)["status"] == "proposed"


def test_the_brief_in_force_carries_each_lines_kind(engine):
    from genios_engine.platform.company_brief import brief_for

    with engine.begin() as c:
        store.add(c, org_id=ORG, section="in_motion", words=FUND, decided_by="founder", at=AT,
                  kind="investor", domain="banyanseed.test")
        store.add(c, org_id=ORG, section="in_motion", words="Hiring a founding AI engineer",
                  decided_by="founder", at=AT + timedelta(seconds=1), kind="hiring")
        brief = brief_for(c, ORG)
    assert [(ln.text, ln.kind) for ln in brief.lines] == [(FUND, "investor"),
                                                          ("Hiring a founding AI engineer", "hiring")]


def test_a_stored_kind_the_list_no_longer_holds_is_read_as_no_kind(engine, caplog):
    """The column is free text by design (0196), as `l3_activation.domain` is, and its reader
    filters what the list does not hold (`activated_domains`). A kind retired from `WORK_KINDS`, or a
    row written outside this store, is read as no kind — said in the log — and never makes the whole
    brief unreadable, which every prompt would then go without."""
    from genios_engine.platform.company_brief import brief_for

    with engine.begin() as c:
        for line_id, section, kind in (("cbl_retired", "in_motion", "a_retired_kind"),
                                       ("cbl_goal", "goals", "investor")):
            c.execute(text(
                "insert into company_brief_lines (org_id, line_id, section, text, status, proposed_by, "
                " proposed_at, decided_at, accepted_at, kind) values (:o, :l, :s, :t, 'accepted', "
                " 'sql', :at, :at, :at, :k)"),
                {"o": ORG, "l": line_id, "s": section, "t": f"a line written by hand ({section})",
                 "at": AT, "k": kind})
        with caplog.at_level("WARNING"):
            lines = _accepted(c)
            brief = brief_for(c, ORG)
    assert lines == {"cbl_retired": (None, None, None), "cbl_goal": (None, None, None)}
    assert brief and len(brief.lines) == 2
    assert "a_retired_kind" in caplog.text


def test_the_past_brief_keeps_the_kind_it_had(engine):
    """An accepted line's kind is changed the way its words are: removed and added again — so the
    brief in force at any instant still says what it said then."""
    with engine.begin() as c:
        first = store.add(c, org_id=ORG, section="in_motion", words=FUND, decided_by="founder",
                          at=AT, kind="investor", domain="banyanseed.test")
        store.remove(c, org_id=ORG, line_id=first, decided_by="founder", at=AT + timedelta(days=3))
        again = store.add(c, org_id=ORG, section="in_motion", words=FUND, decided_by="founder",
                          at=AT + timedelta(days=3), kind="partner", domain="banyanseed.test")
        then = {ln.line_id: ln.kind for ln in store.accepted(c, ORG, at=AT + timedelta(days=1))}
        now = {ln.line_id: ln.kind for ln in store.accepted(c, ORG)}
    assert then == {first: "investor"} and now == {again: "partner"}
