"""A human confirming a duplicate may only merge the two nodes that proposal names.

⛔ `api/identity_routes.py` opens with why this matters: *"The resolver never merges. It records
that two nodes claim the same key and stops."* And merging *"is destructive (it rewrites who every
fact and edge is about), so it is a POST by a human, it is transactional, and it is undoable."*

⛔⛔ **Nothing asserted its gates.** This module was one of two in the engine that no test reached by
any means — the one real finding the audit's deleted naming column produced. Without the node-set
check, a human can confirm a proposal about `A` and `B` while the body names `A` and `C`, and the
engine will rewrite every fact and edge about a node **nobody proposed**.

⛔ THE TEST ASSERTS THE MERGE DID NOT HAPPEN, NOT ONLY THAT A 422 WAS RAISED. A gate that raises
after calling `apply_merge` would pass a test that checked the status code alone — so the double
below records every call, and the assertion is that the destructive one was never made.

⛔ No database: `_graph` is a module-level singleton, so the seam is the module namespace.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from genios_engine.api import identity_routes as IR


class _Row:
    def __init__(self, left: str, right: str, status: str):
        self.left_node_id, self.right_node_id, self.status = left, right, status


class _Conn:
    """Records what it was asked to run, and answers the proposal lookup."""

    def __init__(self, row: _Row | None):
        self.row, self.statements = row, []

    def execute(self, statement, params=None):          # noqa: ARG002 - mirrors SQLAlchemy
        self.statements.append(" ".join(str(statement).lower().split()))
        conn = self

        class _Result:
            def first(self_inner):
                return conn.row
        return _Result()


class _Engine:
    def __init__(self, conn: _Conn):
        self._conn = conn

    def begin(self):
        conn = self._conn

        class _Ctx:
            def __enter__(self_inner):
                return conn

            def __exit__(self_inner, *exc):
                return False
        return _Ctx()

    connect = begin


class _Graph:
    def __init__(self, conn: _Conn):
        self.engine = _Engine(conn)


@pytest.fixture
def merges(monkeypatch):
    """`apply_merge` replaced by a recorder, so a merge that should not happen is visible."""
    calls: list[dict] = []

    def _apply(conn, **kwargs):                         # noqa: ARG001 - signature mirrors the real one
        calls.append(kwargs)
        return {"repairs": {}, "survivor": kwargs.get("survivor_node_id")}

    monkeypatch.setattr(IR, "apply_merge", _apply, raising=True)
    monkeypatch.setattr(IR, "record", lambda *a, **k: None, raising=False)
    return calls


def _wire(monkeypatch, row: _Row | None) -> _Conn:
    conn = _Conn(row)
    monkeypatch.setattr(IR, "_graph", _Graph(conn), raising=True)
    return conn


def _body(survivor: str, merged: str):
    return IR.MergeIn(survivor_node_id=survivor, merged_node_id=merged)


# ── the gate this module exists for ────────────────────────────────────────────────────────────

def test_a_body_naming_a_node_the_proposal_does_not_is_refused(monkeypatch, merges):
    """⛔ THE ONE THAT MATTERS. The proposal is about A and B; the body names A and C."""
    _wire(monkeypatch, _Row("node_a", "node_b", "open"))
    with pytest.raises(HTTPException) as raised:
        IR.merge_proposal("org_1", "prop_1", _body("node_a", "node_c"), org="org_1")
    assert raised.value.status_code == 422
    assert raised.value.detail["error"] == "nodes_do_not_match_proposal"
    assert raised.value.detail["proposal_nodes"] == ["node_a", "node_b"], (
        "the refusal must name the two nodes the proposal holds, or a caller cannot correct it")
    assert merges == [], (
        "⛔ a merge was applied for nodes the proposal does not name. The 422 is not the "
        "protection — NOT CALLING `apply_merge` is")


def test_the_two_nodes_in_either_order_are_accepted(monkeypatch, merges):
    """A set comparison, not a tuple one: which side survives is the caller's choice."""
    _wire(monkeypatch, _Row("node_a", "node_b", "open"))
    IR.merge_proposal("org_1", "prop_1", _body("node_b", "node_a"), org="org_1")
    assert [(c["survivor_node_id"], c["merged_node_id"]) for c in merges] == [
        ("node_b", "node_a")]


def test_the_merge_carries_the_proposal_it_was_confirmed_from(monkeypatch, merges):
    """⛔ The reason is part of the record: a merge with no proposal behind it is indistinguishable
    from one a human never saw."""
    _wire(monkeypatch, _Row("node_a", "node_b", "open"))
    IR.merge_proposal("org_1", "prop_7", _body("node_a", "node_b"), org="org_1")
    assert merges[0]["proposal_id"] == "prop_7"
    assert merges[0]["reason"] == "human_confirmed:prop_7"


@pytest.mark.parametrize("status", ["rejected", "merged", "reversed"])
def test_a_proposal_already_decided_cannot_be_decided_again(monkeypatch, merges, status):
    _wire(monkeypatch, _Row("node_a", "node_b", status))
    with pytest.raises(HTTPException) as raised:
        IR.merge_proposal("org_1", "prop_1", _body("node_a", "node_b"), org="org_1")
    assert raised.value.status_code == 409
    assert raised.value.detail == {"error": "already_decided", "status": status}
    assert merges == [], "a decided proposal was merged again"


def test_a_missing_proposal_is_a_404_and_merges_nothing(monkeypatch, merges):
    _wire(monkeypatch, None)
    with pytest.raises(HTTPException) as raised:
        IR.merge_proposal("org_1", "nope", _body("node_a", "node_b"), org="org_1")
    assert raised.value.status_code == 404
    assert merges == []


def test_a_merge_that_the_graph_refuses_becomes_a_422_not_a_500(monkeypatch, merges):
    """`apply_merge` raises `ValueError` for a merge the graph cannot do; the route must say so."""
    _wire(monkeypatch, _Row("node_a", "node_b", "open"))

    def _boom(conn, **kwargs):                          # noqa: ARG001
        raise ValueError("would orphan a fact")

    monkeypatch.setattr(IR, "apply_merge", _boom, raising=True)
    with pytest.raises(HTTPException) as raised:
        IR.merge_proposal("org_1", "prop_1", _body("node_a", "node_b"), org="org_1")
    assert raised.value.status_code == 422
    assert raised.value.detail["error"] == "merge_failed"
    assert "orphan" in raised.value.detail["message"], (
        "the reason the graph refused must survive into the response, or the caller is told only "
        "that something went wrong")


# ── the tenant boundary, which every route in the module depends on ────────────────────────────

def test_a_path_org_that_disagrees_with_the_credential_is_refused():
    """⛔ `_org` is the only thing between a credential for one tenant and another tenant's
    identity queue. Every route in this module depends on it."""
    with pytest.raises(HTTPException) as raised:
        IR._org("org_other", org="org_1")
    assert raised.value.status_code == 403
    assert IR._org("org_1", org="org_1") == "org_1"


def test_an_unconfigured_graph_store_is_a_400_not_an_attribute_error(monkeypatch):
    monkeypatch.setattr(IR, "_graph", None, raising=True)
    with pytest.raises(HTTPException) as raised:
        IR._store()
    assert raised.value.status_code == 400


# ── the reads and the undo ─────────────────────────────────────────────────────────────────────

def test_rejecting_a_proposal_that_is_not_open_is_a_404(monkeypatch):
    _wire(monkeypatch, None)
    monkeypatch.setattr(IR, "reject_merge", lambda conn, **k: False, raising=True)
    with pytest.raises(HTTPException) as raised:
        IR.reject_proposal("org_1", "prop_1", org="org_1")
    assert raised.value.status_code == 404


def test_rejecting_an_open_proposal_reports_it_rejected(monkeypatch):
    _wire(monkeypatch, None)
    monkeypatch.setattr(IR, "reject_merge", lambda conn, **k: True, raising=True)
    assert IR.reject_proposal("org_1", "prop_1", org="org_1") == {
        "proposal_id": "prop_1", "status": "rejected"}


def test_an_unreversible_merge_is_a_404_carrying_the_reason(monkeypatch):
    _wire(monkeypatch, None)

    def _boom(conn, **kwargs):                          # noqa: ARG001
        raise ValueError("no snapshot for that merge")

    monkeypatch.setattr(IR, "reverse_merge", _boom, raising=True)
    with pytest.raises(HTTPException) as raised:
        IR.undo_merge("org_1", "merge_1", org="org_1")
    assert raised.value.status_code == 404
    assert raised.value.detail["error"] == "cannot_reverse"
    assert "snapshot" in raised.value.detail["message"]


def test_listing_proposals_reports_its_own_count(monkeypatch):
    _wire(monkeypatch, None)
    monkeypatch.setattr(IR, "open_proposals",
                        lambda conn, org_id, limit: [{"id": "p1"}, {"id": "p2"}], raising=True)
    out = IR.list_proposals("org_1", limit=50, org="org_1")
    assert out["count"] == len(out["proposals"]) == 2, (
        "the count and the list must agree, or a caller paginating on the count skips rows")
