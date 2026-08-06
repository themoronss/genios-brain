"""L2 · Entity Resolution — many names, one node.

The danger in this module is not failing to merge. It is merging two real companies, or
two colleagues who share a name, silently and permanently. So most of these tests assert
that something does NOT happen.

The law under test (platform.identity, D8): exact key equality is the only auto-merge;
name similarity is a candidate finder, never a merge authority.
"""
from __future__ import annotations

from genios_engine.context.identity import (ALIAS_COMPANY_NAME, ALIAS_DOMAIN, ALIAS_EMAIL,
                                            ALIAS_PERSON_NAME, alias_keys_for_node)
from genios_engine.platform.identity import (company_slug, domain_root, norm_email,
                                             person_name_key)


def _keys(node_type: str, canonical_key: str | None, display_name: str | None = None):
    return {(t, k) for t, k, _ in alias_keys_for_node(
        node_type=node_type, canonical_key=canonical_key, display_name=display_name)}


# ── company names ────────────────────────────────────────────────────────────────

def test_the_five_ways_a_company_gets_written_collapse_to_one_key() -> None:
    """The actual reason this module exists. One company, five spellings, one key."""
    assert {company_slug(n) for n in
            ("Acme", "ACME", "Acme, Inc.", "Acme Inc", "  acme  ")} == {"acme"}


def test_legal_suffixes_are_stripped_but_never_everything() -> None:
    assert company_slug("Acme Technologies Pvt Ltd") == "acme technologies"
    assert company_slug("Northwind GmbH") == "northwind"
    # A company literally named "Co" must not shorten to nothing — every one-word
    # legal-form name would then collide into a single empty key.
    assert company_slug("Co") == "co"
    assert company_slug("Ltd.") == "ltd"


def test_different_companies_keep_different_keys() -> None:
    """Over-trimming is the failure mode that fuses real businesses."""
    assert company_slug("Apex Legal") != company_slug("Apex Logistics")
    assert company_slug("Acme Health") != company_slug("Acme Bank")


def test_company_slug_handles_junk() -> None:
    assert company_slug(None) is None
    assert company_slug("   ") is None
    assert company_slug("!!!") is None


# ── domains ──────────────────────────────────────────────────────────────────────

def test_domain_root_finds_the_company_label() -> None:
    assert domain_root("acme.io") == "acme"
    assert domain_root("mail.acme.io") == "acme"
    assert domain_root("acme.co.uk") == "acme"
    assert domain_root("careers.acme.com.au") == "acme"


def test_domain_root_handles_junk() -> None:
    assert domain_root("localhost") is None
    assert domain_root(None) is None
    assert domain_root("") is None


# ── what a node may be found by ──────────────────────────────────────────────────

def test_a_company_is_findable_by_its_domain_and_its_name() -> None:
    """The link that makes a bare 'Acme' in an email body reach the node built from
    acme.io — without that, the mention becomes a note on whoever sent the email."""
    keys = _keys("company", "acme.io", "Acme Technologies Pvt Ltd")
    assert (ALIAS_DOMAIN, "acme.io") in keys
    assert (ALIAS_COMPANY_NAME, "acme") in keys
    assert (ALIAS_COMPANY_NAME, "acme technologies") in keys


def test_a_person_is_findable_only_by_email() -> None:
    """A person's NAME is not an anchor key. Minting 'rohit s' as a lookup key would
    make every future Rohit collide with this one."""
    keys = _keys("person", "rohit@acme.io", "Rohit S.")
    assert keys == {(ALIAS_EMAIL, "rohit@acme.io")}
    assert not any(t == ALIAS_PERSON_NAME for t, _ in keys)


def test_the_person_key_matches_the_rest_of_the_system() -> None:
    """The alias must be byte-identical to the canonical_key every other layer mints,
    or the same human splits into strangers per tool."""
    keys = _keys("person", "Rohit+cal@Acme.io ", "Rohit")
    assert keys == {(ALIAS_EMAIL, norm_email("Rohit+cal@Acme.io "))}
    assert (ALIAS_EMAIL, "rohit@acme.io") in keys


def test_an_unanchored_node_claims_nothing() -> None:
    """No canonical key → no lookup keys. A node nothing anchors must not become
    findable by a name it merely happened to be displayed under."""
    assert _keys("company", None, "Acme") == set()
    assert _keys("person", None, "Rohit") == set()


def test_a_node_type_with_no_identity_scheme_claims_nothing() -> None:
    """deal / meeting / commitment are anchored by source ids, not names. Silence here
    is correct — inventing keys for them would collide unrelated records."""
    assert _keys("deal", "hubspot:1234", "Acme Q3 Renewal") == set()
    assert _keys("meeting", "gcal:evt_9", "Pricing Review") == set()


# ── the safety rules ─────────────────────────────────────────────────────────────

def test_person_name_key_normalises_but_never_identifies() -> None:
    """It exists to make a proposal readable, not to prove anything. Two colleagues
    genuinely share a name, so this key never appears in alias_keys_for_node."""
    assert person_name_key("Rohit  S.") == "rohit s"
    assert person_name_key("ROHIT S") == "rohit s"
    assert person_name_key(None) is None
    for name in ("Rohit S.", "ROHIT S"):
        assert not any(t == ALIAS_PERSON_NAME
                       for t, _, _ in alias_keys_for_node(
                           node_type="person", canonical_key="rohit@acme.io",
                           display_name=name))


def test_matching_is_string_equality_and_nothing_else() -> None:
    """No edit distance, no embeddings, no 'similar enough'. Near-misses must NOT
    collapse — each one would be a permanent, invisible join between real entities."""
    assert company_slug("Acme") != company_slug("Acmee")
    assert company_slug("Acme") != company_slug("Acme Global")
    assert domain_root("acme.io") == domain_root("acme.com")   # same label, different org
    # ...which is exactly why a shared label is a PROPOSAL, never a merge. The two
    # company nodes stay separate; a human is asked.


def test_no_resolver_function_can_create_a_node() -> None:
    """The P1 anchor rule. This module widens what counts as anchored; it must never
    lower the bar by minting a node from a bare name."""
    import inspect

    from genios_engine.context import identity
    source = inspect.getsource(identity)
    assert "insert into graph_nodes" not in source
    assert "find_or_create_node" not in source


def test_nothing_in_this_module_merges_anything() -> None:
    """A merge is a human decision. The module may only PROPOSE."""
    import inspect

    from genios_engine.context import identity
    source = inspect.getsource(identity)
    assert "insert into merge_history" not in source
    assert "update graph_nodes" not in source
    assert "propose_merge" in source


# ── merge execution ──────────────────────────────────────────────────────────────
#
# Merging rewrites who every fact and edge is about. These pin the parts that go wrong
# quietly — Postgres enforces none of them.

def test_merging_repoints_every_table_that_names_a_node() -> None:
    """A table left out leaves rows pointing at a closed node: invisible in the UI,
    still returned by anything that joins on node_id."""
    from genios_engine.context.merge import _NODE_REFERENCES
    referenced = {table for table, _ in _NODE_REFERENCES}
    assert {"graph_facts", "graph_observations", "graph_aliases",
            "source_identity_map", "context_attention"} <= referenced


def test_merge_repairs_both_invariants_it_can_break() -> None:
    """Two duplicates each holding `deal.stage` leaves the survivor with two active
    values for one field, and readers take `limit 1` — so 'the' value becomes whichever
    row the planner returns first. Duplicates are also usually linked to each other,
    which repointing turns into 'Acme corresponded_with Acme'."""
    import inspect

    from genios_engine.context import merge
    source = inspect.getsource(merge)
    assert "_resolve_duplicate_facts" in source
    assert "_close_self_edges" in source
    # The loser is kept with its provenance, never deleted — an unmerge needs it back.
    assert "status='superseded'" in source
    assert "delete from graph_facts" not in source


def test_a_merge_can_always_be_undone() -> None:
    """'Merge them back' is not a repair — the original ownership is gone. So every
    merge snapshots what it moved before moving it."""
    import inspect

    from genios_engine.context.merge import apply_merge
    source = inspect.getsource(apply_merge)
    assert "_snapshot(conn, org_id, survivor_node_id)" in source
    assert "_snapshot(conn, org_id, merged_node_id)" in source
    assert "insert into merge_history" in source


def test_the_merged_node_is_closed_not_deleted() -> None:
    """Its id may already sit in a delivery card, a reasoning trace or an audit row.
    Those must still resolve after the merge."""
    import inspect

    from genios_engine.context.merge import apply_merge
    source = inspect.getsource(apply_merge)
    assert "update graph_nodes set valid_to=now()" in source
    assert "delete from graph_nodes" not in source


def test_merging_a_node_into_itself_is_refused() -> None:
    from genios_engine.context.merge import apply_merge
    import pytest
    with pytest.raises(ValueError, match="into itself"):
        apply_merge(conn=None, org_id="o1", survivor_node_id="n1", merged_node_id="n1",
                    reason="x")


def test_a_rejected_pair_is_never_proposed_again() -> None:
    """Without this the next email about either entity re-raises the same question,
    and the queue becomes something people stop reading."""
    import inspect

    from genios_engine.context.identity import propose_merge
    source = inspect.getsource(propose_merge)
    assert "'merged','rejected'" in source
    # The pair is ordered first, so (A,B) and (B,A) are one proposal, not two.
    assert "sorted((left_node_id, right_node_id))" in source
