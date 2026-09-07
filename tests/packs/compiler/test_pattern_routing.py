"""L3.1-U2 · routing on `pattern_id`, with the anchor-type route as the fallback.

Doc 01: *"the resolver tries `pattern_id` first, falls back to situation type. Migration is
non-breaking — anchor-based routing keeps working until L2's X6 lands per tenant."* Both paths are
tested here, and so is the state in between: a SHADOW fire (one the tenant has not activated) must
change nothing at all.
"""
from __future__ import annotations

import pytest
from l3_inputs import build_situation, build_slice

from genios_engine.packs.compiler import DomainCompiler, ExpertBrainCatalog, InMemoryRuntimeBrains
from genios_engine.packs.compiler.authoring import default_authoring_root
from genios_engine.packs.compiler.capability_resolver import (PATTERN_ROUTED, PATTERN_SHADOW,
                                                              PATTERN_UNREGISTERED,
                                                              CapabilityResolver)
from genios_engine.packs.compiler.errors import AuthoringIntegrityError

PATTERN = "pattern.renewal_at_risk"


def _fire(pattern_id=PATTERN, *, activated: bool, conditions=()):
    """`situation_bso._pattern_metadata`'s own shape, minus the keys it deliberately omits
    (`evaluated_at`, `fire_id` move on every sweep and are never hashed into a package)."""
    return {"pattern_id": pattern_id, "pattern_version": "1.0.0",
            "pattern_activated": activated, "pattern_match_strength_bp": 8_800,
            "matched_conditions": list(conditions)}


def _resolve(root, *, metadata=None):
    return CapabilityResolver(ExpertBrainCatalog(root), require_admission=False).resolve(
        build_situation(metadata=metadata), build_slice())


def test_an_activated_pattern_routes_and_the_route_says_so(authoring_root):
    root = authoring_root(when="[]", pattern_when="[]")
    plan = _resolve(root, metadata=_fire(activated=True))
    assert plan.situation_ids == ("sales.sit.pattern",)
    assert plan.pattern_route_id == PATTERN
    assert plan.pattern_route_state == PATTERN_ROUTED


def test_a_situation_with_no_fire_still_routes_on_its_anchor_type(authoring_root):
    """THE MIGRATION PROPERTY. No registry emits a `patterns:` section today and no tenant has X6
    activated, so this is what every live compile does — and it must be untouched."""
    root = authoring_root(when="[]", pattern_when="[]")
    plan = _resolve(root)
    assert plan.situation_ids == ("sales.sit.anchor",)
    assert plan.pattern_route_id is None
    assert plan.pattern_route_state is None


def test_a_shadow_fire_annotates_and_does_not_route(authoring_root):
    """`context/patterns/store.py`'s migration rule — *"compare fire sets on a pilot for 7 days
    before switching; do not delete the anchor path in this wave"* — and Law 5, activation is per
    tenant. Routing is a STRONGER effect than renaming, and `situation_bso._situation_type`
    already refuses to let an unactivated fire rename a situation."""
    root = authoring_root(when="[]", pattern_when="[]")
    plan = _resolve(root, metadata=_fire(activated=False))
    assert plan.situation_ids == ("sales.sit.anchor",)
    assert plan.pattern_route_id is None
    assert plan.pattern_route_state == PATTERN_SHADOW


def test_an_activated_fire_no_registry_names_falls_back_and_is_counted(authoring_root):
    """The state an operator has to act on: a tenant switched a pattern on and the corpus has
    nothing authored for it. The situation still routes — losing a real route to an authoring gap
    would be worse than the gap — and the gap is NAMED rather than silently absorbed."""
    root = authoring_root(when="[]", pattern_when="[]")
    plan = _resolve(root, metadata=_fire("pattern.nobody_authored", activated=True))
    assert plan.situation_ids == ("sales.sit.anchor",)
    assert plan.pattern_route_id is None
    assert plan.pattern_route_state == PATTERN_UNREGISTERED


def test_a_pattern_route_still_narrows_on_its_own_predicates(authoring_root):
    """A pattern selects the ROUTE; the authored `when:` still decides whether the situation
    applies. L3 never decides — and a pattern id is not a licence to skip the predicates."""
    root = authoring_root(when="[]",
                          pattern_when='[{path: thread.ball_in_court, op: "=", value: us}]')
    resolver = CapabilityResolver(ExpertBrainCatalog(root), require_admission=False)
    plan = resolver.resolve(build_situation(metadata=_fire(activated=True)),
                            build_slice(facts={"thread.ball_in_court": {"value": "us"}}))
    assert plan.situation_ids == ("sales.sit.pattern",)

    from genios_engine.packs.compiler.errors import NoExpertiseRoute
    with pytest.raises(NoExpertiseRoute):
        resolver.resolve(build_situation(metadata=_fire(activated=True)),
                         build_slice(facts={"thread.ball_in_court": {"value": "them"}}))


def test_the_receipt_reaches_the_package_only_when_there_is_one(authoring_root):
    """A key written `None` on every package is a key hashed into every package's content address
    — the churn `e1a0c47` stopped. Present when a fire reached the compile, absent otherwise."""
    root = authoring_root(when="[]", pattern_when="[]")
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(root),
                              runtime_brains=InMemoryRuntimeBrains(), require_admission=False)
    routed = compiler.compile(build_situation(metadata=_fire(activated=True)), build_slice())
    plain = compiler.compile(build_situation(), build_slice())

    assert routed.metadata["pattern_route_id"] == PATTERN
    assert routed.metadata["pattern_route_state"] == PATTERN_ROUTED
    assert "pattern_route_id" not in plain.metadata
    assert "pattern_route_state" not in plain.metadata


def test_the_pattern_section_is_validated_at_load_like_the_map(authoring_root):
    """A pattern route pointing at a situation nobody authored must be rejected when the catalog
    LOADS, not when a tenant compiles. The whole value of the integrity check is that a broken
    registry cannot reach production."""
    root = authoring_root(when="[]", pattern_when="[]")
    registry = root / "Sales Expertise" / "registry" / "situation-capability-map.yaml"
    registry.write_text(registry.read_text().replace("sales.sit.pattern", "sales.sit.ghost"))
    with pytest.raises(AuthoringIntegrityError, match="patterns"):
        ExpertBrainCatalog(root)


def test_the_shipped_corpus_carries_no_pattern_routes_yet():
    """The generated registry is never hand-edited (`_tools/index.py`'s header), and it emits no
    `patterns:` section. This asserts the migration state the fallback is designed for — and it is
    the test that will go red on the day Y2's index starts emitting one, which is exactly when
    somebody should look."""
    catalog = ExpertBrainCatalog(default_authoring_root())
    assert {domain_id: len(record.pattern_routes)
            for domain_id, record in catalog.domains.items()} == {
        "admin": 0, "customer_support": 0, "sales": 0}
    assert all(record.routes for record in catalog.domains.values())


def test_the_per_condition_evidence_travels_into_the_package_address(authoring_root):
    """Doc 00: *"the per-condition evidence flows into the package's evidence aggregation for
    free"*. FREE means exactly this — `matched_conditions` is on the BSO's metadata, the BSO's
    semantic hash is the package's `metadata['situation_hash']`, and the package is addressed by
    its content. So two fires that matched on DIFFERENT facts cannot compile to the same package,
    and no code in this wave had to copy the evidence anywhere to make that true.

    *"Without it, a pattern match is an assertion."*
    """
    root = authoring_root(when="[]", pattern_when="[]")
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(root),
                              runtime_brains=InMemoryRuntimeBrains(), require_admission=False)
    one = compiler.compile(
        build_situation(metadata=_fire(activated=True, conditions=[
            {"condition": "auto_renew", "fact": "contract.auto_renew"}])), build_slice())
    other = compiler.compile(
        build_situation(metadata=_fire(activated=True, conditions=[
            {"condition": "short_notice", "fact": "contract.cancellation_window_days"}])),
        build_slice())

    assert one.metadata["situation_hash"] != other.metadata["situation_hash"]
    assert one.id != other.id
