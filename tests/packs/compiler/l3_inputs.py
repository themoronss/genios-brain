"""Shared corpus and object fixtures for the L3.1 compiler-input tests (wave Y3).

The corpus fixture here is a REAL authored tree on disk, loaded by the REAL
`ExpertBrainCatalog`, routed by the REAL `CapabilityResolver` and compiled by the REAL
`DomainCompiler`. Nothing here stubs a compiler component: a predicate kind that only ever
appears in a hand-built `ContextAdapter` call is a grammar nobody can author, and Layer 1 shipped
six units that were reachable only from their own tests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from genios_engine.context.domain_spec import spec_for
from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.visibility import Visibility

NOW = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)

#: The L2 situation type the sales spec derives from a `company` anchor — the value production
#: actually emits. Sourced from the registry rather than written as a literal for the reason
#: `test_domain_expertise_compiler` gives: a fixture built on a pack reason_code tested a shape
#: the compiler will never receive, and a 100% live route miss stayed invisible behind it.
SALES_ANCHOR_TYPE = spec_for("sales").type_for("company")

CAPABILITY = "sales.qualification.lead_qualification"


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n")


def _yaml_conditions(conditions: str) -> str:
    return conditions or "[]"


def build_authoring_root(tmp_path: Path, *, when: str = "[]",
                         pattern_when: str | None = None,
                         pattern_id: str = "pattern.renewal_at_risk",
                         admitted: bool = False) -> Path:
    """A one-domain corpus whose route predicate is whatever the test wants to author.

    `when` is inlined as YAML, so a test authors the predicate exactly as a human would in
    THE SITUATIONS CARRY THEIR OWN `metadata.review_status`/`reviewed_by`. Without it every
    compile here returns `review_state='draft'` for a reason that has nothing to do with the
    variable under test: `capability_resolver.situation_admission_reason` asks a situation's WORDS
    the same question the capability ceremony asks its bytes, and a fixture silent on it isolates
    nothing. `tests/packs/compiler/test_situation_admission.py` is where that gate is exercised.

    `situations/*.yaml` — which is the only way to prove the grammar is expressible rather than
    merely callable.

    `pattern_when` (when given) adds a SECOND situation reached through the registry's optional
    `patterns:` section, under `pattern_id`. `admitted` stamps the capability through the full
    admission ceremony so a compile can be run with `require_admission=True`.
    """
    root = tmp_path / "Domain Expertise"
    domain = root / "Sales Expertise"
    _write(domain / "domain.yaml", """
identity: {id: sales, name: Sales, version: 1.0.0, status: stable}
""")
    registry = f"""
domain: Sales Expertise
map:
  {SALES_ANCHOR_TYPE}:
    situations: [sales.sit.anchor]
    capabilities: [{CAPABILITY}]
    objects:
      load: [sales.obj.core.account]
"""
    if pattern_when is not None:
        registry += f"""
patterns:
  {pattern_id}:
    situations: [sales.sit.pattern]
    capabilities: [{CAPABILITY}]
    objects:
      load: [sales.obj.core.account]
"""
    _write(domain / "registry/situation-capability-map.yaml", registry)

    cap = domain / "capabilities/01-qualification/lead-qualification"
    capability_body = f"""
identity:
  id: {CAPABILITY}
  name: Lead Qualification
  domain: sales
  version: 1.0.0
  status: stable
  stub: false
description: Qualify the live opportunity.
question: What does this opportunity need next?
outcomes: [a qualified opportunity]
"""
    _write(cap / "capability.yaml", capability_body)
    if admitted:
        _write(cap / "capability.yaml", capability_body + f"""
metadata:
  review_status: approved
  reviewed_by: a.named.human@example.com
admission:
  accepted_content_hash: {_accepted_hash(capability_body)}
""")
    _write(cap / "objects.yaml", f"""
capability: {CAPABILITY}
core:
  required: [sales.obj.core.account]
  optional: []
scoped: {{required: [], optional: []}}
""")
    _write(cap / "knowledge.yaml", f"""
capability: {CAPABILITY}
playbooks: {{core: [], scoped: []}}
heuristics: {{core: [], scoped: []}}
mental_models: {{core: [], scoped: []}}
rules: {{core: [], scoped: []}}
decision_frameworks: {{core: [], scoped: []}}
""")
    _write(cap / "situations/anchor.yaml", f"""
identity:
  id: sales.sit.anchor
  name: Anchor route
  domain: sales
  owner_capability: {CAPABILITY}
  version: 1.0.0
  status: stable
matches:
  l2_situation_types: [{SALES_ANCHOR_TYPE}]
  when: {_yaml_conditions(when)}
objects:
  load: [sales.obj.core.account]
metadata:
  owner: Sales
  review_status: approved
  reviewed_by: a.named.human@example.com
""")
    if pattern_when is not None:
        _write(cap / "situations/pattern.yaml", f"""
identity:
  id: sales.sit.pattern
  name: Pattern route
  domain: sales
  owner_capability: {CAPABILITY}
  version: 1.0.0
  status: stable
matches:
  l2_situation_types: [{SALES_ANCHOR_TYPE}]
  when: {_yaml_conditions(pattern_when)}
objects:
  load: [sales.obj.core.account]
metadata:
  owner: Sales
  review_status: approved
  reviewed_by: a.named.human@example.com
""")
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
    return root


def _accepted_hash(body: str) -> str:
    """The admission hash the resolver will recompute: the content MINUS the admission block.

    Computed the way `capability_resolver._admission_reason` computes it, through the same
    `semantic_hash` and the same YAML loader, so a fixture cannot claim an acceptance the real
    gate would reject.
    """
    import yaml

    from genios_engine.packs.compiler.authoring import _DecimalSafeLoader
    from genios_engine.platform.canonical import semantic_hash

    reviewed = yaml.load(body + """
metadata:
  review_status: approved
  reviewed_by: a.named.human@example.com
""", Loader=_DecimalSafeLoader)
    return semantic_hash({k: v for k, v in reviewed.items() if k != "admission"})


def build_situation(*, metadata=None, org_id: str = "org_1",
                    trace_id: str = "trace_1") -> BusinessSituationObject:
    base = {"domain_ids": ["sales"]}
    base.update(metadata or {})
    return BusinessSituationObject(
        org_id=org_id,
        trace_id=trace_id,
        visibility=Visibility(scope="org", derived_from="test:org"),
        id="situation_1",
        signal_ids=("signal_1",),
        type=SALES_ANCHOR_TYPE,
        confidence_bp=8_200,
        importance_bp=7_600,
        evidence=({"signal_id": "signal_1", "source": "crm"},),
        entities=({"id": "account_1", "type": "account", "name": "Acme"},),
        metadata=base,
    )


def build_slice(*, facts=None, neighbor_facts=None, metadata=None, missing_fields=(),
                org_id: str = "org_1", trace_id: str = "trace_context_1",
                evaluation_time: datetime | None = None,
                graph_version: int = 7) -> SituationContextSlice:
    return SituationContextSlice(
        org_id=org_id,
        trace_id=trace_id,
        visibility=Visibility(scope="org", derived_from="test:context"),
        id="context_1",
        graph_version=graph_version,
        selector_version="selector.v1",
        evaluation_time=evaluation_time or NOW,
        root_entity_ids=("account_1",),
        facts=facts or {},
        neighbor_facts=neighbor_facts or {},
        edge_count=3,
        missing_fields=tuple(missing_fields),
        evidence=({"source": "graph", "entity_id": "account_1"},),
        metadata=metadata or {},
    )


def trend_fact(*, metric: str = "engagement", direction: str = "declining",
               confidence_bp: int = 7_000, points: int = 9) -> dict:
    """A `derived.trend.<metric>` body in `analytic.trend.trend_fact_value`'s own shape."""
    return {"metric": metric, "direction": direction, "relative_slope_bp": -1_800,
            "streak_periods": 3, "point_count": points, "coverage_ratio_bp": 9_000,
            "trend_confidence_bp": confidence_bp,
            "series": {"subject_node_id": "node_a", "metric": metric, "unit": "count",
                       "first_period": "2026-06-01T00:00:00+00:00",
                       "last_period": "2026-09-01T00:00:00+00:00", "periods": points}}


def cohort_fact(*, metric: str = "spend_growth", percentile_bp: int = 500,
                population: int = 47, band: str = "D1", refused: str | None = None) -> dict:
    """A `derived.cohort_position.<metric>` body, per `analytic.comparator.position_fact_value`."""
    if refused is not None:
        return {"metric": metric, "cohort_id": "cohort_growth", "refused": refused,
                "population_size": population, "detail": "fixture"}
    return {"metric": metric, "cohort_id": "cohort_growth", "value_bp": 2_200, "unit": "bp",
            "percentile_bp": percentile_bp, "band": band, "population_size": population,
            "p25_bp": None, "p50_bp": None, "p75_bp": None, "distribution_window": None,
            "distribution_withheld": "fixture", "phrase": "22%, the 5th percentile"}


def anomaly_fact(*, metric: str = "support_tickets", flagged: bool = True,
                 refusal: str | None = None, z_like_bp: int = 41_000,
                 direction: str = "above") -> dict:
    """A `derived.anomaly.<metric>` body, per `analytic.anomaly.anomaly_fact_value`."""
    return {"metric": metric, "flagged": flagged, "refusal": refusal,
            "current_bp": 4_100, "baseline_bp": 1_200, "mad_bp": 300,
            "deviation_bp": 2_900, "z_like_bp": z_like_bp,
            "direction": direction, "periods_used": 6}
