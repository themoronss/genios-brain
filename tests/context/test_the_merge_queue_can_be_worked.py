"""Eighty proposals accumulated because the queue could not be worked, not because nobody tried.

Three defects that compound, and each one alone would have been survivable:

    `defer` loaded the row, wrote nothing, and returned `{"status": "deferred"}`. Its own comment
    said so. A reviewer deferred the ambiguous pairs, reloaded, and got the identical list back.

    `open_proposals` ordered `created_at DESC` against a route whose default limit is 20. With
    eighty open proposals the sixty oldest were unreachable through the UI, and the twenty that
    were reachable were the twenty least likely to be stuck.

    Nothing ranked by how strong the collision was, though `identity._STRONG` has always known: a
    shared email IS a duplicate, a shared company name is a coincidence of spelling. One real
    duplicate sat behind sixty coincidences.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.merge import DEFAULT_DEFER_DAYS, defer_proposal, open_proposals

ORG = "o"
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table merge_proposals (id text primary key, org_id text, "
                       "left_node_id text, right_node_id text, node_type text, reason text, "
                       "evidence text, status text, created_at timestamp, "
                       "deferred_until timestamp)"))
        c.execute(text("create table graph_nodes (org_id text, node_id text, node_type text, "
                       "display_name text, canonical_key text, valid_to text)"))
    with engine.begin() as c:
        yield c


def _propose(c, pid, reason, *, age_days=1, status="open", deferred_until=None):
    c.execute(text(
        "insert into merge_proposals (id, org_id, left_node_id, right_node_id, reason, "
        "status, created_at, deferred_until) "
        "values (:id,:o,'a','b',:why,:st,:at,:d)"),
        {"id": pid, "o": ORG, "why": reason, "st": status,
         "at": NOW - timedelta(days=age_days), "d": deferred_until})


def _ids(c, **kw):
    return [p["id"] for p in open_proposals(c, org_id=ORG, now=NOW, **kw)]


# ── ordering: the queue is meant to be emptied ───────────────────────────────────────────────

def test_a_real_duplicate_outranks_a_coincidence_of_spelling(conn) -> None:
    """`identity._STRONG` — a shared email, domain or LinkedIn url identifies one party alone."""
    _propose(conn, "weak1", "shared_company_name", age_days=1)
    _propose(conn, "weak2", "shared_person_name", age_days=2)
    _propose(conn, "strong", "shared_email", age_days=3)
    assert _ids(conn)[0] == "strong"


def test_within_a_tier_the_oldest_comes_first(conn) -> None:
    """This read was newest-first, which is how a backlog stops being a backlog and becomes a
    permanent fixture."""
    _propose(conn, "newest", "shared_company_name", age_days=1)
    _propose(conn, "middle", "shared_company_name", age_days=20)
    _propose(conn, "oldest", "shared_company_name", age_days=200)
    assert _ids(conn) == ["oldest", "middle", "newest"]


def test_the_twenty_a_reviewer_sees_are_the_twenty_that_matter(conn) -> None:
    """The compounding failure, in one assertion. Sixty recent coincidences used to bury one
    real duplicate below a limit the UI never raises."""
    for i in range(60):
        _propose(conn, f"weak{i}", "shared_company_name", age_days=1)
    _propose(conn, "strong", "shared_email", age_days=300)
    assert "strong" in _ids(conn, limit=20)


# ── deferral: a control that reports success must change something ───────────────────────────

def test_deferring_takes_the_pair_out_of_the_queue(conn) -> None:
    _propose(conn, "p1", "shared_company_name")
    assert _ids(conn) == ["p1"]
    until = defer_proposal(conn, org_id=ORG, proposal_id="p1", now=NOW)
    assert until == NOW + timedelta(days=DEFAULT_DEFER_DAYS)
    assert _ids(conn) == [], "the reviewer does not see it again this sitting"


def test_a_lapsed_deferral_returns_by_itself(conn) -> None:
    """Read as `deferred_until <= now`, so there is no sweep and no second state to keep
    consistent with the first."""
    _propose(conn, "p1", "shared_company_name", deferred_until=NOW - timedelta(days=1))
    assert _ids(conn) == ["p1"]


def test_a_deferral_still_standing_keeps_it_out(conn) -> None:
    _propose(conn, "p1", "shared_company_name", deferred_until=NOW + timedelta(days=3))
    assert _ids(conn) == []


def test_deferring_is_not_deciding(conn) -> None:
    """The pair stays OPEN, so `situations.merge_pressure` still counts it and the situation goes
    on paying for the doubt. Choosing not to decide today is not a decision."""
    _propose(conn, "p1", "shared_email")
    defer_proposal(conn, org_id=ORG, proposal_id="p1", now=NOW)
    row = conn.execute(text("select status from merge_proposals where id='p1'")).first()
    assert row.status == "open"


def test_a_decided_pair_cannot_be_deferred(conn) -> None:
    """Deferring something a human already ruled on would reopen a settled question as a
    scheduling artefact."""
    _propose(conn, "p1", "shared_email", status="merged")
    assert defer_proposal(conn, org_id=ORG, proposal_id="p1", now=NOW) is None


def test_deferring_something_that_does_not_exist_changes_nothing(conn) -> None:
    assert defer_proposal(conn, org_id=ORG, proposal_id="nope", now=NOW) is None
