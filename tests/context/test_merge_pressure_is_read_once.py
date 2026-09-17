"""One reader for `merge_proposals`, and it can tell a shared email from a shared first name.

Three modules read this table for one purpose and in three dialects. The outreach copy named
`from_node_id`/`to_node_id` — columns this table has never had — so `refresh_state_situations`
raised `UndefinedColumn` on every sweep and the per-pass boundary in `runner.py` logged it and
carried on. The pass never ran once while the sweep reported success. These tests pin the single
reader that replaces all three, and the strength distinction that is the point of having it.
"""
import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.identity import strong_proposal_reasons
from genios_engine.context.situations import merge_pressure

ORG = "org_test"


def _conn():
    engine = create_engine("sqlite://")
    c = engine.connect()
    c.execute(text(
        "create table merge_proposals (id text primary key, org_id text, left_node_id text, "
        "right_node_id text, evidence text, status text, created_at text, reason text, "
        "node_type text)"))
    return c


def _propose(c, pid, left, right, reason, *, org=ORG, status="open"):
    c.execute(text(
        "insert into merge_proposals (id, org_id, left_node_id, right_node_id, reason, status) "
        "values (:id, :o, :l, :r, :why, :st)"),
        {"id": pid, "o": org, "l": left, "r": right, "why": reason, "st": status})


def test_a_node_with_no_proposal_is_simply_absent() -> None:
    """Absent, not zero — the callers use `.get(node, (0, 0))` and a row per clean node would
    make this dict the size of the graph."""
    with _conn() as c:
        assert merge_pressure(c, ORG) == {}


def test_both_sides_of_a_pair_are_charged() -> None:
    """A duplicate splits the evidence in both directions; a situation anchored on either node
    is missing the half that lives on the other."""
    with _conn() as c:
        _propose(c, "m1", "node_a", "node_b", "shared_email")
        assert merge_pressure(c, ORG) == {"node_a": (1, 1), "node_b": (1, 1)}


def test_a_shared_email_is_strong_and_a_shared_name_is_not() -> None:
    """The whole reason this reader exists rather than a `count(*)`."""
    with _conn() as c:
        _propose(c, "m1", "node_a", "node_b", "shared_email")
        _propose(c, "m2", "node_a", "node_c", "shared_person_name")
        pressure = merge_pressure(c, ORG)
        assert pressure["node_a"] == (2, 1), "two proposals, one of them strong"
        assert pressure["node_b"] == (1, 1)
        assert pressure["node_c"] == (1, 0), "a name collision alone is weak"


@pytest.mark.parametrize("reason", sorted(strong_proposal_reasons()))
def test_every_strong_alias_kind_is_recognised(reason: str) -> None:
    """Parametrised over `identity.strong_proposal_reasons()` rather than a list written here,
    so adding a strong alias kind cannot leave this test asserting the old set."""
    with _conn() as c:
        _propose(c, "m1", "node_a", "node_b", reason)
        assert merge_pressure(c, ORG)["node_a"] == (1, 1)


def test_a_weak_alias_kind_is_not_counted_strong() -> None:
    with _conn() as c:
        _propose(c, "m1", "node_a", "node_b", "shared_company_name")
        _propose(c, "m2", "node_a", "node_c", "shared_canon")
        assert merge_pressure(c, ORG)["node_a"] == (2, 0)


def test_a_proposal_with_no_reason_counts_as_strong() -> None:
    """`reason` arrived in migration 0036, so an older row carries NULL. A doubt we cannot size
    is not a doubt we may discount — that would make the case we know least about the cheapest.
    """
    with _conn() as c:
        _propose(c, "m1", "node_a", "node_b", None)
        _propose(c, "m2", "node_c", "node_d", "")
        pressure = merge_pressure(c, ORG)
        assert pressure["node_a"] == (1, 1)
        assert pressure["node_c"] == (1, 1)


def test_a_decided_proposal_exerts_no_pressure() -> None:
    """`merged` and `rejected` are answered questions. Only `open` is a doubt."""
    with _conn() as c:
        _propose(c, "m1", "node_a", "node_b", "shared_email", status="merged")
        _propose(c, "m2", "node_a", "node_c", "shared_email", status="rejected")
        _propose(c, "m3", "node_a", "node_d", "shared_person_name", status="open")
        assert merge_pressure(c, ORG) == {"node_a": (1, 0), "node_d": (1, 0)}


def test_another_tenants_proposals_are_invisible() -> None:
    with _conn() as c:
        _propose(c, "m1", "node_a", "node_b", "shared_email", org="org_other")
        assert merge_pressure(c, ORG) == {}
