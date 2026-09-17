"""The 995 MB fix removed the clock and left a second one wearing a different face.

    pytest tests/packs/compiler/test_the_org_counter_is_not_the_package_address.py -q

`ExpertisePackage.to_semantic_dict` records what a churning content address cost this project:
a fresh `trace_id` per sweep meant a fresh package id per sweep, the publisher's
`on conflict (org_id, expertise_id) do nothing` never fired, and each sweep wrote a fresh ~238 kB
row per situation — 4,086 rows and 995 MB, 67% of the whole database for 127 distinct situations,
until the project crossed its disk quota into read-only.

That docstring says the id stayed stable "even when the situation, the knowledge, THE GRAPH
VERSION and every capability were byte-identical". The graph version is the one item on that list
that is not a property of the package: `context_graph_version` is the tenant's ORG-WIDE counter,
and it moves when any fact about any node anywhere in the tenant is written. It was hashed twice —
directly, in the package's own metadata, and again through `SituationContextSlice`, which listed
`graph_version` in its content.

MEASURED ON THE PILOT 2026-09-16, which is how this was found. J5 reported
`law2_one_address_per_situation: false` with `worst_addresses_per_situation: 4`, and 106 expertise
packages for 36 situations. Diffing the first and last package of `sit_00cae4087f72431d810a68db`
gave exactly three differing keys: `context_graph_version` (108 -> 110), the slice hash it churned,
and the package id derived from that hash. Every byte of knowledge was identical.

WHAT THIS FILE REFUSES TO LET HAPPEN AGAIN, in both directions. A package must not re-address
because an unrelated tenant fact moved — and it must still re-address when its own knowledge
changes, because a content address that ignores content is worse than one that churns.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts.domain_expertise import (
    OBSERVATION_METADATA_KEYS, addressable_metadata, expertise_id)

from l3_inputs import build_slice

pytestmark = pytest.mark.unit


def test_the_org_graph_counter_does_not_change_a_slice_address() -> None:
    """Two sweeps over an unchanged slice, with somebody else's email arriving between them."""
    before = build_slice(facts={"deal.stage": "negotiation"}, graph_version=108)
    after = build_slice(facts={"deal.stage": "negotiation"}, graph_version=110)
    assert before.semantic_hash == after.semantic_hash


def test_a_slice_whose_own_facts_change_still_re_addresses() -> None:
    """The other direction. A hash that ignored content would be worse than one that churned."""
    before = build_slice(facts={"deal.stage": "negotiation"}, graph_version=108)
    after = build_slice(facts={"deal.stage": "closed_won"}, graph_version=108)
    assert before.semantic_hash != after.semantic_hash


def test_the_clock_and_the_sweep_id_are_still_excluded() -> None:
    """The original fix must not be undone by this one."""
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    first = build_slice(facts={"a": "1"}, trace_id="trace_a", evaluation_time=base)
    second = build_slice(facts={"a": "1"}, trace_id="trace_b",
                         evaluation_time=base + timedelta(hours=5))
    assert first.semantic_hash == second.semantic_hash


def test_the_counter_is_dropped_from_a_packages_hashed_metadata() -> None:
    """It is hashed a second time, directly, and fixing only the slice would leave that."""
    assert "context_graph_version" in OBSERVATION_METADATA_KEYS
    kept = addressable_metadata(
        {"situation_type": "deal", "context_graph_version": 110, "context_slice_hash": "abc"})
    assert kept == {"situation_type": "deal", "context_slice_hash": "abc"}, (
        "the slice hash addresses real content and must stay in the address")


def test_the_id_and_the_hash_agree_about_what_a_package_is() -> None:
    """`expertise_id` builds from the builder's hand-written dict and `to_semantic_dict` from the
    dataclass. If the two disagree, the publisher's immutability check rejects a package identical
    to the one it already holds — so both must drop the same keys."""
    body = {"org_id": "org_1", "trace_id": "trace_a", "capabilities": (),
            "metadata": {"situation_type": "deal", "context_graph_version": 108}}
    later = {**body, "trace_id": "trace_b",
             "metadata": {"situation_type": "deal", "context_graph_version": 110}}
    assert expertise_id(body) == expertise_id(later)


def test_a_package_whose_knowledge_changes_gets_a_new_id() -> None:
    body = {"org_id": "org_1", "trace_id": "t", "capabilities": (),
            "metadata": {"situation_type": "deal", "context_graph_version": 108}}
    changed = {**body, "metadata": {"situation_type": "renewal", "context_graph_version": 108}}
    assert expertise_id(body) != expertise_id(changed)
