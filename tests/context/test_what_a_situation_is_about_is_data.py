"""CORR-03 · CORR-04 — two Python tuples decided what a situation could be about, and who
counted as one party.

    pytest tests/context/test_what_a_situation_is_about_is_data.py -q

`_anchor_priority()`'s own comment records what a literal costs: *"Without them here,
`choose_anchors` returns [] for every Stripe/client-DB structured event → it reaches NO
situation, and admin/account situations report their fields missing forever — the 'built,
green, does nothing' dead-end."* A business object the tuple has not heard of does not rank
low; it anchors NOTHING, silently.

`find_organizations` hardcoded `works_at` / `person` / `company`. That is one business's
version of a true statement: a hospital groups clinicians by DEPARTMENT, a school groups
guardians by HOUSEHOLD, a broker by DESK, a consultancy by the ENGAGEMENT people are staffed
on. Every one is the same reading over a different edge.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.internal_knowledge import ANCHORING_KINDS
from genios_engine.context.correlation import ANCHOR_PRIORITY, _anchor_priority
from genios_engine.context.correlation_organization import (
    MIN_MEMBERS,
    Grouping,
    GroupingError,
    group_by_organization,
    load_groupings,
)

pytestmark = pytest.mark.unit


# =============================================================================================
# CORR-03 — the anchor tiers.
# =============================================================================================
def test_the_order_is_byte_identical_to_the_literal_it_replaced():
    """Day one changes nothing. This is the assertion that says so."""
    assert ANCHOR_PRIORITY == ("deal", *sorted(ANCHORING_KINDS), "subscription",
                               "product_account", "company", "person")


def test_two_tiers_at_one_rank_do_not_silently_swap():
    """A BUG THIS CAUGHT. `subscription` and `product_account` are one tier conceptually; giving
    them the same rank and breaking the tie on name reversed them, and an event carrying both
    would have anchored differently from the day it shipped. A tie-break rule is not a place to
    hide a behaviour change."""
    order = list(ANCHOR_PRIORITY)

    assert order.index("subscription") < order.index("product_account")


def test_an_authored_tier_takes_its_place_by_rank(tmp_path, monkeypatch):
    (tmp_path / "matter.yaml").write_text("node_type: matter\nrank: 15\nwhy: a legal matter\n")
    monkeypatch.setattr("genios_engine.context.correlation.ANCHORS_DIR", tmp_path)

    order = _anchor_priority()

    assert "matter" in order
    assert order.index("deal") < order.index("matter") < order.index("company")


def test_a_tier_file_may_not_delete_a_shipped_one(tmp_path, monkeypatch):
    """A tenant that removed `person` by omission would silently lose every situation about a
    human being, which is not a thing a YAML file should be able to do."""
    (tmp_path / "matter.yaml").write_text("node_type: matter\nrank: 15\n")
    monkeypatch.setattr("genios_engine.context.correlation.ANCHORS_DIR", tmp_path)

    assert set(ANCHOR_PRIORITY) <= set(_anchor_priority())


def test_an_authored_tier_may_restate_a_shipped_rank(tmp_path, monkeypatch):
    """A tenant whose company really does outrank its deals has a reason and may say so."""
    (tmp_path / "company.yaml").write_text("node_type: company\nrank: 5\n")
    monkeypatch.setattr("genios_engine.context.correlation.ANCHORS_DIR", tmp_path)

    order = _anchor_priority()

    assert order.index("company") < order.index("deal")


def test_one_bad_tier_does_not_lose_the_others(tmp_path, monkeypatch):
    (tmp_path / "broken.yaml").write_text("node_type: [not a string\n")
    (tmp_path / "matter.yaml").write_text("node_type: matter\nrank: 15\n")
    monkeypatch.setattr("genios_engine.context.correlation.ANCHORS_DIR", tmp_path)

    order = _anchor_priority()

    assert "matter" in order and "person" in order


def test_a_missing_directory_leaves_the_shipped_tiers(tmp_path, monkeypatch):
    monkeypatch.setattr("genios_engine.context.correlation.ANCHORS_DIR",
                        tmp_path / "does-not-exist")

    assert _anchor_priority() == ANCHOR_PRIORITY


# =============================================================================================
# CORR-04 — who counts as one party.
# =============================================================================================
def test_the_shipped_grouping_is_the_one_that_was_hardcoded():
    got = {g.grouping_id: g for g in load_groupings()}

    assert got["works_at"].edge_type == "works_at"
    assert got["works_at"].member_node_type == "person"
    assert got["works_at"].group_node_type == "company"
    assert got["works_at"].min_members == MIN_MEMBERS


def test_a_hospital_can_group_by_department(tmp_path):
    (tmp_path / "department.yaml").write_text(
        "grouping_id: department\nedge_type: works_in\nmember_node_type: person\n"
        "group_node_type: department\nmin_members: 3\nwhy: a clinical department\n")

    got = load_groupings(tmp_path)

    assert got[0].edge_type == "works_in"
    assert got[0].min_members == 3


def test_a_grouping_of_one_is_refused(tmp_path):
    """A "group" of one is a duplicate of the per-member card with a firm's name on it."""
    (tmp_path / "solo.yaml").write_text(
        "grouping_id: solo\nedge_type: e\nmember_node_type: person\n"
        "group_node_type: company\nmin_members: 1\n")

    with pytest.raises(GroupingError, match="refuses below"):
        load_groupings(tmp_path)


@pytest.mark.parametrize("missing", ["grouping_id", "edge_type",
                                     "member_node_type", "group_node_type"])
def test_an_incomplete_grouping_names_its_file(tmp_path, missing):
    fields = {"grouping_id": "g", "edge_type": "e",
              "member_node_type": "person", "group_node_type": "company"}
    del fields[missing]
    (tmp_path / "partial.yaml").write_text(
        "\n".join(f"{k}: {v}" for k, v in fields.items()) + "\n")

    with pytest.raises(GroupingError, match=f"partial.yaml is missing.*{missing}"):
        load_groupings(tmp_path)


def test_a_malformed_grouping_is_loud_rather_than_ignored(tmp_path):
    """STRICT, unlike the corpus reads elsewhere on this branch. An unreadable corpus is a
    deployment problem where the shipped default is still correct; a grouping file that will
    not parse is a statement somebody wrote about who counts as one party, and ignoring it
    would group people the author said not to group."""
    (tmp_path / "broken.yaml").write_text("grouping_id: [unclosed\n")

    with pytest.raises(GroupingError, match="broken.yaml"):
        load_groupings(tmp_path)


def test_the_member_floor_travels_with_the_grouping():
    rows = [{"company_node": "c1", "company": "Peak XV", "person_node": f"p{n}",
             "person": f"Partner {n}"} for n in range(2)]

    assert len(group_by_organization(rows, (), min_members=2)) == 1
    assert group_by_organization(rows, (), min_members=3) == ()


def test_the_node_types_are_bound_not_interpolated():
    """They arrive from a YAML file a tenant can edit, and a node type spliced into SQL is a
    node type that can end a statement."""
    from genios_engine.context.correlation_organization import _ORG_MEMBERS

    assert ":group_type" in _ORG_MEMBERS
    assert ":member_type" in _ORG_MEMBERS
    assert ":edge_type" in _ORG_MEMBERS
    assert "'company'" not in _ORG_MEMBERS
    assert "'works_at'" not in _ORG_MEMBERS


def test_a_grouping_is_a_frozen_record():
    g = Grouping(grouping_id="g", edge_type="e", member_node_type="person",
                 group_node_type="company")

    with pytest.raises(Exception):
        g.edge_type = "other"      # type: ignore[misc]
