"""G012 H-20 · a need L2 files names something Layer 1 can fetch, and an answer found is one the need accepts.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_need_names_what_l1_can_fetch_pg.py -q

On the design partner's org (local copy, 24 Oct) 336 needs were open and a fetch could have answered — and the need
accepted — 7 of them: 184 named the graph's thread NODE where Gmail wants its thread id, 78 a meeting, a person, a
condition or nothing, and 329 said in prose what would settle them where the executor compares a source name. Arming
the fetchers would have closed the rest for good. After `scripts/reframe_open_needs.py`: 316 of 336.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.acquire.evidence_need import BACKFILL_WINDOW, FETCH_THREAD, plan_fetch
from genios_engine.capture.acquire.need_fetchers import party_of, window_query
from genios_engine.context.need_subjects import fetchable, resolve_subject
from genios_engine.contracts.evidence import EvidenceNeed
from genios_engine.reason.l2.evidence import source_names

ORG = "org_h20_need_subjects"
AT = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)
FILE, THREAD_NODE, MEETING, COMPANY = "node_h20_file", "node_h20_thread", "node_h20_meeting", "node_h20_company"


def _need(subject, **kw) -> EvidenceNeed:
    return EvidenceNeed(need_id=kw.pop("need_id", "l2need:h20"), org_id=ORG, trace_id="l2req:h20",
                        question="Has the fund replied since our update?", why_it_matters="it decides the follow-up",
                        subject_ref=subject, **kw)


@pytest.mark.unit
def test_a_party_need_is_a_window_fetch_scoped_to_that_partys_mail():
    need = _need("party:Kunal@MeridianVC.test", window_from=AT - timedelta(days=30))
    assert plan_fetch(need) == BACKFILL_WINDOW
    assert window_query(need) == f"{{from:kunal@meridianvc.test to:kunal@meridianvc.test}} after:{(AT - timedelta(days=30)):%Y/%m/%d}"
    assert window_query(_need("party:meridianvc.test")) == "{from:meridianvc.test to:meridianvc.test}"
    assert party_of(_need('party:x" OR in:anywhere')) is None, "a model's words never become query syntax"


@pytest.mark.unit
def test_only_source_names_are_kept_from_what_the_model_wrote():
    assert source_names(["A mailbox read of the relevant thread", "Gmail", " gcal ", "meeting notes"]) == ("gmail", "gcal")
    assert _need("thread:19ee5fa0cbd3ee9d", acceptable_sources=source_names(["the thread's mail"])).accepts("gmail")


@pytest.mark.unit
def test_the_pass_files_each_need_with_a_fetchable_subject():
    """The call site: every need the pass raises reaches the store through `fetchable`, beside its judged file."""
    from genios_engine.reason.l2 import evidence, sweep
    source = inspect.getsource(sweep.l2_pass)
    assert "store_needs(conn, [fetchable(conn, org_id, need, file_id=file_id)" in source
    assert "needs.extend((need, subject.file_id) for need in raised)" in source
    assert "source_names(raised.acceptable_sources)" in inspect.getsource(evidence.needs_from)


@pytest.fixture
def conn(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)

    def _clean(c):
        for t in ("evidence_needs", "qualified_signals", "source_events", "graph_nodes"):
            c.execute(text(f"delete from {t} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    with eng.begin() as c:
        _clean(c)
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
        for node_id, node_type, key in ((FILE, "person", "Kunal@MeridianVC.test"), (THREAD_NODE, "thread",
                                         "thread:1a16244fb626429f"), (MEETING, "meeting", "meeting:abc"),
                                        (COMPANY, "company", "meridianvc.test")):
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key) values (:n, :o, :t, :k)"),
                      {"n": node_id, "o": ORG, "t": node_type, "k": key})
        c.execute(text("insert into source_events (event_id, org_id, connection_id, source, object_type, "
                       "source_object_id, parent_object_id, dedup_key, actor, occurred_at) values ('evt_h20', :o, "
                       "'conn_h20', 'gmail', 'email_message', 'm1', '1a07a6e0ca77ad6f', 'd_h20', "
                       "cast('{\"email\": \"kunal@meridianvc.test\"}' as jsonb), :at)"), {"o": ORG, "at": AT})
        c.execute(text("insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, importance_bp, "
                       "importance_version, confidence_bp, visibility, extraction_ref, evidence_refs, occurred_at) "
                       "values ('sig_h20', :o, 'evt_h20', 't', 'decision_pending', 1, 'v', 1, "
                       "cast('{\"scope\": \"org\"}' as jsonb), 'x', cast('[\"evt_h20\"]' as jsonb), :at)"),
                  {"o": ORG, "at": AT})
    with eng.begin() as c:
        yield c
    with eng.begin() as c:
        _clean(c)


@pytest.mark.pg
@pytest.mark.parametrize("asked, filed", [
    (f"thread:{THREAD_NODE}", "thread:1a16244fb626429f"),          # the graph's node → the Gmail thread
    (f"node:{THREAD_NODE}", "thread:1a16244fb626429f"),
    ("evt_h20", "thread:1a07a6e0ca77ad6f"),                          # an event → the thread its message is in
    ("signal:sig_h20", "thread:1a07a6e0ca77ad6f"),                   # a signal with no window → its event's thread
    (f"node:{COMPANY}", "party:meridianvc.test"),                    # a company → its mail
    (f"node:{MEETING}", "party:kunal@meridianvc.test"),              # a meeting → the judged file's counterparty
    ("thread: Re: our seed update", "party:kunal@meridianvc.test"),  # a subject line → the same
    ("sit:sit_h20", "party:kunal@meridianvc.test"),
    (None, "party:kunal@meridianvc.test"),
    ("thread:19ee5fa0cbd3ee9d", "thread:19ee5fa0cbd3ee9d"),          # already fetchable: untouched
    ("document:doc_1", "document:doc_1"),
])
def test_a_raised_need_is_filed_with_what_l1_can_fetch(conn, asked, filed):
    assert resolve_subject(conn, ORG, asked, file_id=FILE) == filed
    need = fetchable(conn, ORG, _need(asked), file_id=FILE)
    assert need.subject_ref == filed and plan_fetch(need) in (FETCH_THREAD, BACKFILL_WINDOW, "reextract")


@pytest.mark.pg
def test_nothing_to_resolve_it_by_leaves_the_need_as_asked(conn):
    """No file, a meeting node: the need is filed as asked, and the executor says honestly why it cannot fetch."""
    assert fetchable(conn, ORG, _need(f"node:{MEETING}"), file_id=None).subject_ref == f"node:{MEETING}"
    assert fetchable(conn, ORG, _need("sit:sit_h20"), file_id=None).subject_ref == "sit:sit_h20"


@pytest.mark.pg
def test_the_open_queue_is_reframed_once_and_a_closed_need_keeps_its_answer(conn, live_db_url):
    """`scripts/reframe_open_needs.py`: a dry run writes nothing; `--apply` reframes the OPEN needs only."""
    from genios_engine.platform.db import get_engine
    from scripts import reframe_open_needs as script
    conn.commit()                       # the world, visible to the script's own connections
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        for need_id, state in (("l2need:open", "open"), ("l2need:closed", "unavailable")):
            c.execute(text("insert into evidence_needs (need_id, org_id, trace_id, question, why_it_matters, "
                           "subject_ref, acceptable_sources, state, unavailable_reason) values (:n, :o, 'l2req:none', "
                           "'q', 'w', :s, cast('[\"A mailbox read of the relevant thread\"]' as jsonb), :st, :why)"),
                      {"n": need_id, "o": ORG, "s": f"thread:{THREAD_NODE}", "st": state,
                       "why": "the fetch failed" if state != "open" else None})

    def rows():
        with eng.connect() as c:
            return {r.need_id: (r.subject_ref, r.acceptable_sources) for r in c.execute(text(
                "select need_id, subject_ref, acceptable_sources from evidence_needs where org_id = :o"), {"o": ORG})}

    args = ["--database-url", live_db_url, "--org", ORG]
    assert script.main(args) == 0
    assert rows()["l2need:open"][0] == f"thread:{THREAD_NODE}", "a dry run writes nothing"
    assert script.main([*args, "--apply"]) == 0
    after = rows()
    assert after["l2need:open"] == ("thread:1a16244fb626429f", []), \
        "the Gmail thread, and prose is no source name: any source the fetch kind returns may answer it"
    assert after["l2need:closed"][0] == f"thread:{THREAD_NODE}", "a closed need keeps the answer it had"
    from genios_engine.context.evidence_need_store import reframe_open
    with eng.begin() as c:
        assert not reframe_open(c, _need("thread:19ee5fa0cbd3ee9d", need_id="l2need:closed")), \
            "only an open need may be reframed"
