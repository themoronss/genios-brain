from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from genios_engine.contracts.domain_expertise import (
    BrainKind,
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.visibility import Visibility
from genios_engine.packs.compiler import (
    DomainCompiler,
    ExpertBrainCatalog,
    InMemoryExpertisePublisher,
    InMemoryRuntimeBrains,
    RuntimeBrainEntry,
)
from genios_engine.packs.compiler.authoring import default_authoring_root
from genios_engine.packs.compiler.context_adapter import ContextAdapter, PredicateState
from genios_engine.packs.compiler.errors import (
    BrainPolicyViolation,
    RequiredKnowledgeMissing,
    SituationContextConflict,
    SituationContextIncomplete,
)

NOW = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n")


def _authoring_root(tmp_path: Path, *, include_required: bool = True,
                    include_optional: bool = True) -> Path:
    root = tmp_path / "Domain Expertise"
    domain = root / "Sales Expertise"
    _write(domain / "domain.yaml", """
identity: {id: sales, name: Sales, version: 1.0.0, status: stable}
""")
    _write(domain / "registry/situation-capability-map.yaml", """
domain: Sales Expertise
map:
  buying_signal:
    situations: [sales.sit.inbound]
    capabilities: [sales.qualification.lead_qualification]
    objects:
      load: [sales.obj.core.account]
      optional: [sales.obj.core.champion]
""")
    cap = domain / "capabilities/01-qualification/lead-qualification"
    _write(cap / "capability.yaml", """
identity:
  id: sales.qualification.lead_qualification
  name: Lead Qualification
  domain: sales
  version: 1.0.0
  status: stable
  stub: false
description: Qualify the live opportunity.
""")
    _write(cap / "objects.yaml", """
capability: sales.qualification.lead_qualification
core:
  required: [sales.obj.core.account]
  optional: [sales.obj.core.champion]
scoped: {required: [], optional: []}
""")
    _write(cap / "knowledge.yaml", """
capability: sales.qualification.lead_qualification
playbooks: {core: [], scoped: []}
heuristics: {core: [], scoped: []}
mental_models: {core: [], scoped: []}
rules: {core: [sales.rule.core.account_gate], scoped: []}
decision_frameworks: {core: [], scoped: []}
""")
    _write(cap / "situations/inbound.yaml", """
identity:
  id: sales.sit.inbound
  name: Inbound
  domain: sales
  owner_capability: sales.qualification.lead_qualification
  version: 1.0.0
  status: stable
matches:
  l2_situation_types: [buying_signal]
  when: [{path: thread.ball_in_court, op: "=", value: us}]
objects:
  load: [sales.obj.core.account]
  optional: [sales.obj.core.champion]
""")
    if include_required:
        _write(domain / "objects/core/account.yaml", """
identity:
  id: sales.obj.core.account
  name: Account
  domain: sales
  scope: core
  version: 1.0.0
  status: stable
purpose: {statement: The buying organisation.}
inference_patterns: {deterministic: [], heuristic: []}
""")
    if include_optional:
        _write(domain / "objects/core/champion.yaml", """
identity:
  id: sales.obj.core.champion
  name: Champion
  domain: sales
  scope: core
  version: 1.0.0
  status: stable
purpose: {statement: The internal advocate.}
inference_patterns: {deterministic: [], heuristic: []}
""")
    _write(domain / "rules/core/account-gate.yaml", """
identity:
  id: sales.rule.core.account_gate
  name: Account Gate
  kind: rule
  domain: sales
  scope: core
  version: 1.0.0
  status: stable
rule:
  statement: An account must exist before qualification.
  spans: [sales.obj.core.account, sales.obj.core.champion]
""")
    _write(domain / "models/b2b/model.yaml", """
identity:
  id: sales.model.b2b
  name: B2B
  kind: model
  domain: sales
  version: 1.0.0
  status: stable
""")
    return root


def _situation(**metadata) -> BusinessSituationObject:
    base_metadata = {
        "domain_ids": ["sales"],
        "facts": {"thread.ball_in_court": {"value": "us"}},
        "model_ids": ["sales.model.b2b"],
    }
    base_metadata.update(metadata)
    return BusinessSituationObject(
        org_id="org_1",
        trace_id="trace_1",
        visibility=Visibility(scope="org", derived_from="test:org"),
        id="situation_1",
        signal_ids=("signal_1",),
        type="buying_signal",
        confidence_bp=8_200,
        importance_bp=7_600,
        evidence=({"signal_id": "signal_1", "source": "crm"},),
        entities=({"id": "account_1", "type": "account", "name": "Acme"},),
        metadata=base_metadata,
    )


def _context(*, org_id: str = "org_1", visibility: Visibility | None = None,
             facts=None, neighbor_facts=None, neighbor_observations=(),
             edge_count: int = 0, missing_fields=()) -> SituationContextSlice:
    return SituationContextSlice(
        org_id=org_id,
        trace_id="trace_context_1",
        visibility=visibility or Visibility(scope="org", derived_from="test:context"),
        id="context_1",
        graph_version=7,
        selector_version="selector.v1",
        evaluation_time=NOW,
        root_entity_ids=("account_1",),
        facts=(facts if facts is not None
               else {"thread.ball_in_court": {"value": "us"}}),
        neighbor_facts=neighbor_facts or {},
        neighbor_observations=neighbor_observations,
        edge_count=edge_count,
        missing_fields=missing_fields,
        evidence=({"source": "graph", "entity_id": "account_1"},),
    )


def _entry(*, brain: BrainKind, entry_id: str, subject_key: str,
           category: str, org_id: str = "org_1", visibility: Visibility | None = None,
           capability_id: str | None = None,
           conflict_key: str | None = None) -> RuntimeBrainEntry:
    value = {"category": category, "value": entry_id}
    if capability_id:
        value["capability_id"] = capability_id
    if conflict_key:
        value["conflict_key"] = conflict_key
    return RuntimeBrainEntry(
        org_id=org_id,
        brain=brain,
        entry_id=entry_id,
        subject_key=subject_key,
        version=1,
        value=value,
        confidence_bp=8_000,
        learning_id=f"learning:{entry_id}",
        effective_at=NOW,
        visibility=(visibility or Visibility(scope="org", derived_from="test:brain")).model_dump(),
        trace_id=f"trace:{entry_id}",
    )


def test_contract_envelope_and_compiler_are_deterministic(tmp_path: Path):
    catalog = ExpertBrainCatalog(_authoring_root(tmp_path))
    publisher = InMemoryExpertisePublisher()
    compiler = DomainCompiler(
        catalog=catalog,
        runtime_brains=InMemoryRuntimeBrains(),
        publisher=publisher,
    )

    first = compiler.compile(_situation())
    second = compiler.compile(_situation())

    assert first.id == second.id
    assert first.semantic_hash == second.semantic_hash
    assert first.brain_snapshot_id == second.brain_snapshot_id
    assert first.trace_id == "trace_1"
    assert first.visibility["scope"] == "org"
    assert first.schema_version == "expertise-package.v1"
    assert first.confidence_bp == 8_200
    assert [item["id"] for item in first.capabilities] == [
        "sales.qualification.lead_qualification"]
    assert {item["id"] for item in first.objects} == {
        "sales.obj.core.account", "sales.obj.core.champion"}
    account = next(item for item in first.objects
                   if item["id"] == "sales.obj.core.account")
    assert account["entity_bindings"] == ("account_1",)
    assert {item["id"] for item in first.expert_rules} == {
        "sales.rule.core.account_gate", "sales.model.b2b"}
    assert publisher.packages[("org_1", first.id)] is first


def test_runtime_brains_are_relevant_tenant_scoped_and_visibility_safe(tmp_path: Path):
    capability = "sales.qualification.lead_qualification"
    entries = (
        _entry(brain=BrainKind.ORGANIZATION, entry_id="org_policy",
               subject_key="policy:qualification", category="policy",
               capability_id=capability),
        _entry(brain=BrainKind.BEHAVIOR, entry_id="account_behavior",
               subject_key="behavior:account_1:reply_style", category="communication_style"),
        _entry(brain=BrainKind.ADAPTIVE, entry_id="private_preference",
               subject_key="adaptive:account_1:priority", category="current_priority",
               visibility=Visibility(scope="private", principals=["owner@example.com"],
                                     derived_from="test:private")),
        _entry(brain=BrainKind.ADAPTIVE, entry_id="unrelated",
               subject_key="adaptive:someone_else:priority", category="current_priority"),
        _entry(brain=BrainKind.ORGANIZATION, entry_id="other_tenant",
               subject_key="policy:qualification", category="policy", org_id="org_2",
               capability_id=capability),
    )
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path)),
        runtime_brains=InMemoryRuntimeBrains(entries),
    )

    package = compiler.compile(_situation())

    assert [item["entry_id"] for item in package.organization_rules] == ["org_policy"]
    assert [item["entry_id"] for item in package.behavior_patterns] == ["account_behavior"]
    assert package.adaptive_preferences == ()
    assert package.metadata["excluded_runtime_entry_ids"] == ("private_preference",)
    assert all(item.metadata.get("learning_id") != "learning:other_tenant"
               for item in package.evidence)


def test_behavior_or_adaptive_brain_cannot_define_permission_axis(tmp_path: Path):
    hostile = _entry(
        brain=BrainKind.ADAPTIVE,
        entry_id="hostile_policy",
        subject_key="adaptive:account_1:approval",
        category="permission",
    )
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path)),
        runtime_brains=InMemoryRuntimeBrains((hostile,)),
    )
    with pytest.raises(BrainPolicyViolation, match="permission-axis"):
        compiler.compile(_situation())


def test_explicit_preference_conflicts_use_atlas_precedence(tmp_path: Path):
    conflict = "qualification:contact_preference"
    entries = (
        _entry(brain=BrainKind.BEHAVIOR, entry_id="observed_style",
               subject_key="account_1", category="communication_style",
               conflict_key=conflict),
        _entry(brain=BrainKind.ORGANIZATION, entry_id="company_style",
               subject_key="account_1", category="communication_style",
               conflict_key=conflict),
        _entry(brain=BrainKind.ADAPTIVE, entry_id="current_style",
               subject_key="account_1", category="communication_style",
               conflict_key=conflict),
    )
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path)),
        runtime_brains=InMemoryRuntimeBrains(entries),
    )
    package = compiler.compile(_situation())
    assert package.organization_rules == ()
    assert package.behavior_patterns == ()
    assert [item["entry_id"] for item in package.adaptive_preferences] == ["current_style"]
    assert package.metadata["shadowed_runtime_entry_ids"] == (
        "company_style", "observed_style")
    resolution = package.metadata["runtime_conflict_resolutions"][0]
    assert resolution["axis"] == "preference"
    assert resolution["winner_brain"] == "adaptive"


def test_same_rank_conflict_fails_instead_of_using_an_arbitrary_tiebreak(tmp_path: Path):
    entries = (
        _entry(brain=BrainKind.ORGANIZATION, entry_id="org_style_a",
               subject_key="account_1", category="communication_style",
               conflict_key="contact_preference"),
        _entry(brain=BrainKind.ORGANIZATION, entry_id="org_style_b",
               subject_key="sales.obj.core.account", category="communication_style",
               conflict_key="contact_preference"),
    )
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path)),
        runtime_brains=InMemoryRuntimeBrains(entries),
    )
    with pytest.raises(BrainPolicyViolation, match="ambiguous preference conflict"):
        compiler.compile(_situation())


def test_missing_situation_context_does_not_guess_a_route(tmp_path: Path):
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path)),
        runtime_brains=InMemoryRuntimeBrains(),
    )
    with pytest.raises(SituationContextIncomplete, match="thread.ball_in_court"):
        compiler.compile(_situation(facts={}))


def test_typed_context_slice_is_pinned_and_cannot_cross_tenant_or_visibility(tmp_path: Path):
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path)),
        runtime_brains=InMemoryRuntimeBrains(),
    )
    situation = _situation(facts={})
    package = compiler.compile(situation, _context())
    assert package.metadata["context_slice_id"] == "context_1"
    assert len(package.metadata["context_slice_hash"]) == 64
    assert package.metadata["context_graph_version"] == 7

    with pytest.raises(SituationContextConflict, match="does not match"):
        compiler.compile(situation, _context(org_id="org_2"))
    with pytest.raises(SituationContextConflict, match="visibility is narrower"):
        compiler.compile(situation, _context(visibility=Visibility(
            scope="private", principals=["owner@example.com"],
            derived_from="test:private")))


def test_context_slice_supports_bounded_neighbor_and_edge_predicates():
    adapter = ContextAdapter(_situation(facts={}), _context(
        neighbor_facts={"contact.role": {"value": "buyer"}},
        neighbor_observations=("pricing_discussed",),
        edge_count=3,
    ))
    verdict = adapter.matches((
        {"neighbor_fact": "contact.role", "op": "=", "value": "buyer"},
        {"neighbor_has_obs": "pricing_discussed"},
        {"fn": "edge_count", "op": ">=", "value": 2},
    ))
    assert verdict.state is PredicateState.TRUE

    missing = ContextAdapter(_situation(facts={}), _context(
        facts={}, missing_fields=("commitment.action",)))
    assert missing.evaluate({"exists": "commitment.action"}).state \
        is PredicateState.UNKNOWN


def test_missing_required_object_fails_closed(tmp_path: Path):
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path, include_required=False)),
        runtime_brains=InMemoryRuntimeBrains(),
    )
    with pytest.raises(RequiredKnowledgeMissing, match="sales.obj.core.account"):
        compiler.compile(_situation())


def test_missing_optional_object_is_visible_and_lowers_confidence(tmp_path: Path):
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path, include_optional=False)),
        runtime_brains=InMemoryRuntimeBrains(),
    )
    package = compiler.compile(_situation())
    assert package.metadata["missing_optional_object_ids"] == ("sales.obj.core.champion",)
    assert package.confidence_bp == 5_000


def test_current_three_domain_corpus_compiles_a_real_sales_slice():
    catalog = ExpertBrainCatalog(default_authoring_root())
    assert set(catalog.domains) == {"admin", "customer_support", "sales"}
    compiler = DomainCompiler(
        catalog=catalog,
        runtime_brains=InMemoryRuntimeBrains(),
    )
    package = compiler.compile(_situation(model_ids=()))
    assert package.metadata["domain_ids"] == ("sales",)
    assert package.metadata["matched_situation_ids"] == (
        "sales.sit.inbound_fit_check", "sales.sit.inbound_lead")
    assert len(package.capabilities) == 2
    assert len(package.objects) == 10
    assert package.metadata["missing_artifact_ids"] == ()


def test_layer3_migration_is_immutable_tenant_scoped_and_enveloped():
    migration = (Path(__file__).resolve().parents[1]
                 / "migrations/0048_l3_domain_compiler.sql").read_text().lower()
    assert "create table if not exists expertise_packages" in migration
    assert "references orgs(id) on delete cascade" in migration
    assert "payload->>'trace_id' = trace_id" in migration
    assert "payload->'visibility' = visibility" in migration
    assert "before update on expertise_packages" in migration
