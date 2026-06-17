"""Tests that the REAL modules/sales/ package loads + validates + runs through SDK."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.modules_framework.golden import run_golden_test
from core.modules_framework.loader import load_module_package
from core.modules_framework.sdk import load_manifest, validate_module

SALES_ROOT = Path(__file__).resolve().parent.parent.parent / "modules" / "sales"


@pytest.mark.unit
def test_sales_manifest_loads() -> None:
    """Real manifest.json parses + validates against Pydantic."""
    m = load_manifest(SALES_ROOT)
    assert m.id == "sales"
    assert m.version == "1.0.0"
    assert "crm:read" in m.requiredScopes
    assert m.provides.rules == ["pricing", "churn", "velocity", "competition", "qualification"]


@pytest.mark.unit
def test_sales_module_passes_sdk_validation() -> None:
    """Real Sales module package passes ALL SDK rejection rules."""
    valid_scopes = ["crm:read", "email:read"]
    result = validate_module(SALES_ROOT, valid_scopes=valid_scopes)
    assert result.ok is True, f"SDK validation errors: {result.errors}"


@pytest.mark.unit
def test_sales_module_loads_into_package() -> None:
    """Loader pulls rules + graph + benchmarks + templates."""
    pkg = load_module_package(SALES_ROOT)
    assert pkg.manifest.id == "sales"
    # 5 rule files (churn, velocity, pricing, competition, qualification)
    assert len(pkg.ruleset.rules) >= 18  # deepened from 10 -> 20 (MEDDIC/deal-health signals)
    # Graph fragment has expected nodes
    assert "nodes" in pkg.graph_fragment
    assert len(pkg.graph_fragment["nodes"]) == 5
    # Benchmarks loaded
    assert "deal_cycle" in pkg.benchmarks
    # Artifact templates loaded
    assert "churn_brief" in pkg.artifact_templates
    assert "deal_risk_report" in pkg.artifact_templates


@pytest.mark.unit
def test_sales_rules_have_expected_hard_constraints() -> None:
    """Pricing rules MUST include hard constraints (block_or_escalate)."""
    pkg = load_module_package(SALES_ROOT)
    hard_rules = [r for r in pkg.ruleset.rules if r.hard]
    assert len(hard_rules) >= 2  # margin guard + extreme discount
    assert any(r.id == "pricing_discount_margin_guard" for r in hard_rules)
    assert any(r.then.conclusion == "block_or_escalate" for r in hard_rules)


@pytest.mark.unit
def test_sales_real_churn_rule_fires() -> None:
    """End-to-end: load module + run engine + churn rule fires on MD test case."""
    from core.reasoning.rule_engine import ForwardChainer

    pkg = load_module_package(SALES_ROOT)
    result = ForwardChainer(pkg.ruleset).run(
        {"usage_drop_pct_30d": 65, "days_since_last_contact": 18}
    )
    assert result.resolved
    assert "churn_risk_high" in [s.conclusion for s in result.proof.steps]


@pytest.mark.unit
def test_sales_real_stage_stall_rule_fires() -> None:
    """End-to-end: stage_stall rule from MD spec fires."""
    from core.reasoning.rule_engine import ForwardChainer

    pkg = load_module_package(SALES_ROOT)
    result = ForwardChainer(pkg.ruleset).run({"days_in_current_stage": 22, "stage": "negotiation"})
    assert result.resolved
    assert "deal_stalled" in [s.conclusion for s in result.proof.steps]


@pytest.mark.unit
def test_sales_real_hard_pricing_rule_fires() -> None:
    """Pricing hard constraint fires on MD test case (discount=30%, margin=35%)."""
    from core.reasoning.rule_engine import ForwardChainer

    pkg = load_module_package(SALES_ROOT)
    result = ForwardChainer(pkg.ruleset).run({"discount_pct": 30, "gross_margin_pct": 35})
    assert result.resolved
    assert result.has_hard
    assert any(s.conclusion == "block_or_escalate" for s in result.proof.steps)


@pytest.mark.unit
def test_sales_evaluator_runs_against_real_dataset() -> None:
    """Evaluator runs §7 against the labeled golden dataset (no smoke mode anymore)."""
    evaluator_path = SALES_ROOT / "evaluator.py"
    result = run_golden_test(
        evaluator_path,
        module_id="sales",
        threshold_key="sales_initial",
    )
    assert result.passed is True
    assert result.score >= 0.70
    assert "n_cases" in result.metrics
    assert "per_rule_firings" in result.metrics
    assert result.metrics["n_cases"] >= 25
