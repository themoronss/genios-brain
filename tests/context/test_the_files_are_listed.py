"""STEP-09 · the founder's files, listed — each with what the brief says it is, whose move it is, what
is asked, and which named counterparty has mail and no file.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_the_files_are_listed.py -q

`context/workstreams.files_for` (tree `yc2_w27_s09 · M27.C4.L-logic.V1.U01`). A file is one
counterparty's correlations — every domain, every generation — read from what memory holds: no table,
no model. The kind is the brief's word (`connector`, `watched`, `person`, `intro`, or none); whose move
it is comes from the turn the pipeline writes on the file's people; the open asks are their open
loops. An org-level reader: nothing a seat captured privately is listed.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.context.correlation import correlate_event
from genios_engine.context.workstreams import as_dict, files_for
from genios_engine.contracts.company_brief import CompanyBrief

from .workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, WATCHED, brief, later, ledger,
                               mention, node, process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_files"
RAHUL, FARAH = "rahul@kestrelcap.test", "farah@kitepath.test"
PRIYA, KAVITHA = "priya@northwind.test", "kavitha@inboxmail.test"
LATE_PORTAL, PROGRAM = "otherportal.gov.test", "lakshya.test"
NOW = later(10)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _world(store) -> CompanyBrief:
    """An introduction of two, one answered and answered back; a nudge; the connector's own ask; a
    portal's notice; an ordinary correspondent; a person the brief names."""
    b = brief(ORG, people=(KAVITHA,))
    for kw in (
            dict(event_id="evt_intro", sender=CONNECTOR, recipients=(FOUNDER, RAHUL, FARAH),
                 thread="t_intro", headers=UNSUBSCRIBE,
                 mentions=(mention("Rahul Menon"), mention("Farah Qureshi"),
                           mention("Kestrel Capital", "organization"),
                           mention("Kitepath", "organization"))),
            dict(event_id="evt_farah", sender=FARAH, recipients=(FOUNDER, CONNECTOR),
                 thread="t_intro", at=later(1)),
            dict(event_id="evt_mine", sender=FOUNDER, recipients=(FARAH,), thread="t_intro",
                 at=later(2)),
            dict(event_id="evt_nudge", sender=CONNECTOR, thread="t_nudges", headers=UNSUBSCRIBE,
                 mentions=(mention("Rahul"),), at=later(3)),
            dict(event_id="evt_ask", sender=CONNECTOR, thread="t_ask", headers=UNSUBSCRIBE,
                 at=later(4)),
            dict(event_id="evt_notice", sender=f"updates@{WATCHED}", at=later(5)),
            dict(event_id="evt_priya", sender=PRIYA, thread="t_priya", at=later(6)),
            dict(event_id="evt_kavitha", sender=KAVITHA, thread="t_kav", at=later(7))):
        process(store, ORG, company_brief=b, **kw)
    return b


def _files(store, b=None) -> dict:
    with store.engine.connect() as c:
        ws = files_for(c, ORG, now=NOW, company_brief=b)
    return {f.counterparty_key: f for f in ws.files}


def test_every_piece_of_work_is_a_file_of_the_kind_the_brief_gives_it(store):
    b = _world(store)
    files = _files(store, b)
    assert {k: f.kind for k, f in files.items()} == {
        "kestrelcap.test": "intro", "kitepath.test": "intro", "introly.test": "connector",
        WATCHED: "watched", "inboxmail.test": "person", "northwind.test": None}
    assert files["kestrelcap.test"].introduced_by == CONNECTOR
    assert files["kestrelcap.test"].line == "Introly — introduces the founder to people"
    assert files[WATCHED].line == "Startupsetu — a portal the founder watches"
    assert files["inboxmail.test"].line == "Kavitha — someone the founder works with"
    assert files["northwind.test"].line is None


def test_each_file_holds_its_own_mail_oldest_first(store):
    files = _files(store, _world(store))
    assert files["kestrelcap.test"].events == ("evt_intro", "evt_nudge")
    assert files["kitepath.test"].events == ("evt_intro", "evt_farah", "evt_mine")
    assert files["introly.test"].events == ("evt_ask",)
    assert files[WATCHED].events == ("evt_notice",)


def test_a_person_the_brief_names_and_a_connector_introduced_is_the_founders_person(store):
    """Both lines stand behind Rahul's file: the brief's own naming of him decides its kind, and
    who introduced him is still said."""
    _world(store)
    kestrel = _files(store, brief(ORG, people=(KAVITHA, RAHUL)))["kestrelcap.test"]
    assert (kestrel.kind, kestrel.line, kestrel.introduced_by) == (
        "person", "Rahul — someone the founder works with", CONNECTOR)


def test_a_file_anchored_on_a_person_reads_their_own_turn(store):
    """A personal mailbox has no company: the person is the file."""
    b = _world(store)
    process(store, ORG, event_id="evt_meera", sender="meera.iyer@gmail.com", thread="t_meera",
            company_brief=b, at=later(8))
    meera = _files(store, b)["meera.iyer@gmail.com"]
    assert meera.counterparty_type == "person" and meera.whose_move == "ours"


def test_anyone_in_the_file_waiting_on_us_makes_it_our_move(store):
    """We answered Rahul; his partner Ankit's mail is still unanswered — the move is ours."""
    b = _world(store)
    process(store, ORG, event_id="evt_ankit", sender="ankit@kestrelcap.test", thread="t_ankit",
            company_brief=b, at=later(8))
    process(store, ORG, event_id="evt_to_rahul", sender=FOUNDER, recipients=(RAHUL,),
            thread="t_intro", company_brief=b, at=later(9))
    assert _files(store, b)["kestrelcap.test"].whose_move == "ours"


def test_whose_move_is_read_from_the_files_people(store):
    """Rahul was introduced and nudged about: ours. Farah answered and we answered her: theirs —
    though her thread is Rahul's too. The connector's own ask: ours. A portal: nobody's."""
    files = _files(store, _world(store))
    assert {k: f.whose_move for k, f in files.items()} == {
        "kestrelcap.test": "ours", "kitepath.test": "theirs", "introly.test": "ours",
        WATCHED: None, "inboxmail.test": "ours", "northwind.test": "ours"}


def test_the_most_recently_touched_file_comes_first(store):
    with store.engine.connect() as c:
        ws = files_for(c, ORG, now=NOW, company_brief=_world(store))
    assert [f.counterparty_key for f in ws.files] == [
        "inboxmail.test", "northwind.test", WATCHED, "introly.test", "kestrelcap.test",
        "kitepath.test"]
    first = ws.files[0]
    assert first.last_touch == later(7) and first.first_touch == later(7)
    assert first.days_quiet == 3.0
    kitepath = ws.files[-1]
    assert (kitepath.first_touch, kitepath.last_touch) == (T0, later(2))


def test_the_open_asks_say_who_owes_the_answer(store):
    b = _world(store)
    us, priya, rahul = (node(store, ORG, k).node_id for k in (FOUNDER, PRIYA, RAHUL))
    with store.engine.begin() as c:
        for loop, subject, awaited, status, event in (
                ("loop_priya", priya, None, "open", "evt_priya"),       # she asked us
                ("loop_rahul", us, rahul, "open", "evt_intro"),         # we asked him
                ("loop_done", priya, None, "closed", "evt_priya")):
            c.execute(text(
                "insert into open_loops (org_id, loop_id, subject_node_id, kind, thread_id, status,"
                " opened_at, last_seen_at, opened_by_event, awaited_from_node_id) values "
                "(:o, :l, :s, 'question', 't_x', :st, :at, :at, :e, :a)"),
                {"o": ORG, "l": loop, "s": subject, "st": status, "at": T0, "e": event,
                 "a": awaited})
    files = _files(store, b)
    assert [(a.loop_id, a.owed_by) for a in files["northwind.test"].open_asks] == [
        ("loop_priya", "us")]
    assert [(a.loop_id, a.owed_by) for a in files["kestrelcap.test"].open_asks] == [
        ("loop_rahul", "them")]
    assert files["kitepath.test"].open_asks == ()


def test_one_counterparty_in_two_domains_is_one_file(store):
    b = _world(store)
    ledger(store, ORG, event_id="evt_sales", sender=PRIYA, thread=None, at=later(8))
    with store.engine.begin() as c:
        correlate_event(c, org_id=ORG, event_id="evt_sales", occurred_at=later(8), thread_id=None,
                        node_types={node(store, ORG, "northwind.test").node_id: "company"},
                        domain_hints=[{"domain": "sales", "source": "test"}])
    northwind = _files(store, b)["northwind.test"]
    assert len(northwind.correlations) == 2 and "sales" in northwind.domains
    assert northwind.events == ("evt_priya", "evt_sales")


def test_nothing_a_seat_captured_privately_is_listed(store):
    b = _world(store)
    process(store, ORG, event_id="evt_private", sender=PRIYA, thread="t_priya", company_brief=b,
            at=later(9))
    priya = node(store, ORG, PRIYA).node_id
    with store.engine.begin() as c:
        c.execute(text("update source_events set visibility_scope = 'private' "
                       " where org_id = :o and event_id = 'evt_private'"), {"o": ORG})
        c.execute(text(
            "insert into open_loops (org_id, loop_id, subject_node_id, kind, thread_id, status,"
            " opened_at, last_seen_at, opened_by_event) values "
            "(:o, 'loop_private', :s, 'question', 't_priya', 'open', :at, :at, 'evt_private')"),
            {"o": ORG, "s": priya, "at": later(9)})
    northwind = _files(store, b)["northwind.test"]
    assert northwind.events == ("evt_priya",) and northwind.last_touch == later(6)
    assert northwind.open_asks == ()


def test_a_private_overlay_is_never_whose_move(store):
    b = _world(store)
    with store.engine.begin() as c:
        c.execute(text("update graph_facts set visibility_scope = 'private' "
                       " where org_id = :o and field = 'thread.ball_in_court' "
                       "   and subject_node_id = :n"),
                  {"o": ORG, "n": node(store, ORG, PRIYA).node_id})
    assert _files(store, b)["northwind.test"].whose_move is None


def test_a_named_counterparty_with_mail_and_no_file_is_named(store):
    """The portal the founder came to watch after its notice was read as a machine's noise has mail
    and no file; a program whose only mail is its mailing has none that could be a file."""
    _world(store)
    process(store, ORG, event_id="evt_late", sender=f"alerts@notify.{LATE_PORTAL}",
            company_brief=None, at=later(8))
    watching = brief(ORG, watchlist=(WATCHED, LATE_PORTAL, PROGRAM), people=(KAVITHA,))
    process(store, ORG, event_id="evt_social", sender=f"community@{PROGRAM}",
            headers={"List-Unsubscribe": "<mailto:leave@lakshya.test>"}, company_brief=watching,
            at=later(8))
    with store.engine.connect() as c:
        ws = files_for(c, ORG, now=NOW, company_brief=watching)
    assert {n.named: (n.mail, n.filed) for n in ws.named} == {
        f"connector:{CONNECTOR}": (3, 3), f"watchlist:{WATCHED}": (1, 1),
        f"watchlist:{LATE_PORTAL}": (1, 0), f"person:{KAVITHA}": (1, 1)}
    assert [n.named for n in ws.unfiled] == [f"watchlist:{LATE_PORTAL}"]


def test_without_a_brief_every_file_is_listed_with_no_kind(store):
    _world(store)
    files = _files(store, None)            # the accepted brief: this tenant accepted no line
    assert len(files) == 6 and {f.kind for f in files.values()} == {None}
    with store.engine.connect() as c:
        assert files_for(c, ORG, now=NOW).named == ()


def test_the_accepted_brief_is_read_when_none_is_given(store):
    from genios_engine.platform import company_brief_store
    _world(store)
    with store.engine.begin() as c:
        company_brief_store.add(c, org_id=ORG, section="connectors", address=CONNECTOR,
                                words="Introly — introduces the founder to people",
                                decided_by="founder", at=T0)
    with store.engine.connect() as c:
        ws = files_for(c, ORG, now=NOW)
    assert {f.counterparty_key: f.kind for f in ws.files}["kestrelcap.test"] == "intro"


def test_the_read_model_is_json(store):
    with store.engine.connect() as c:
        body = as_dict(files_for(c, ORG, now=NOW, company_brief=_world(store)), now=NOW)
    kestrel = next(f for f in body["files"] if f["counterparty"]["key"] == "kestrelcap.test")
    assert kestrel["kind"] == "intro" and kestrel["last_touch"] == later(3).isoformat()
    assert body["as_of"] == NOW.isoformat() and body["unfiled"] == []
    assert body["named"][0] == {"named": f"connector:{CONNECTOR}",
                                "line": "Introly — introduces the founder to people",
                                "mail": 3, "filed": 3}


def test_the_read_writes_nothing(store):
    b = _world(store)
    tables = ("graph_nodes", "graph_facts", "graph_edges", "graph_observations",
              "context_correlations", "context_correlation_members", "open_loops")
    def counts():
        with store.engine.connect() as c:
            return [c.execute(text(f"select count(*) from {t} where org_id = :o"),
                              {"o": ORG}).scalar() for t in tables]
    before = counts()
    _files(store, b)
    assert counts() == before
