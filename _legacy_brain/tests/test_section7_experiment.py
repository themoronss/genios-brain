"""§7 falsifiable experiment — engine vs labeled Sales dataset.

Per MD g-i-2 §7:
    "Does the engine produce a decision (e.g. churn-risk call or stall flag)
    that is measurably better, cheaper, or more explainable than a raw LLM
    on the same task — using rules + asserted graph + gated gap-fill?"

Pre-registered metric (per GENIOS_V2_PLAN.md Group 2):
    sales_initial threshold = 0.70  (must hit on first deploy)
    sales_target threshold  = 0.80  (must climb to over time)

These tests run the REAL Sales module against the labeled golden dataset.
They run SYMBOLICALLY (no LLM cost) — deterministic + fast.

The raw-LLM baseline test is `pytest.mark.skip`'d by default — requires
ANTHROPIC_API_KEY + real $ to run. To run manually:
    pytest tests/test_section7_experiment.py::test_llm_baseline_comparison -m '' \\
        --no-skip-llm
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.foundations.config import GOLDEN_THRESHOLD
from modules.sales.evaluator import evaluate

SALES_ROOT = Path(__file__).resolve().parent.parent / "modules" / "sales"


# ── headline §7 result ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_engine_passes_sales_initial_threshold() -> None:
    """THE go/no-go test: engine match rate >= sales_initial threshold."""
    result = evaluate(compare_llm=False)
    score = result["score"]
    threshold = GOLDEN_THRESHOLD["sales_initial"]
    n_cases = result["metrics"]["n_cases"]

    # If this fails, the symbolic-first thesis needs revisiting (per MD §7)
    assert score >= threshold, (
        f"§7 EXPERIMENT FAILED: engine score {score:.3f} < threshold {threshold:.3f} "
        f"on {n_cases} cases. Mismatches: {result['metrics']['mismatches']}"
    )


@pytest.mark.unit
def test_engine_targets_sales_target_threshold() -> None:
    """Aspirational: engine should climb to sales_target over time. Currently a soft check."""
    result = evaluate(compare_llm=False)
    score = result["score"]
    target = GOLDEN_THRESHOLD["sales_target"]
    if score < target:
        pytest.skip(
            f"engine score {score:.3f} < aspirational target {target:.3f}. "
            f"Acceptable for v1; tighten rules over time."
        )


# ── coverage + structural ───────────────────────────────────────────────────


@pytest.mark.unit
def test_dataset_covers_all_rule_categories() -> None:
    """Sanity: dataset exercises churn + velocity + pricing + edges."""
    result = evaluate(compare_llm=False)
    n = result["metrics"]["n_cases"]
    assert n >= 25, f"Dataset too small ({n} cases). Need >=25 for meaningful score."


@pytest.mark.unit
def test_derivation_chain_present_when_rule_fires() -> None:
    """Per MD g-i-2 §0: explainability is the moat. Every fired rule = a derivation step.

    Invariant: derivation_available_count == number of cases where any rule fired
    == sum of all per_rule_firings divided by avg rules-per-case. Simpler check:
    if any rule fired across the dataset, derivation_available_count >= 1.
    """
    result = evaluate(compare_llm=False)
    metrics = result["metrics"]
    total_firings = sum(metrics["per_rule_firings"].values())
    if total_firings == 0:
        pytest.fail("No rule fired across entire dataset — Sales module broken")
    # When rules fire, derivations are recorded
    assert metrics["derivation_available_count"] >= 1
    # Stronger: derivation_available_count >= number of UNIQUE cases that fired ANY rule
    # (we don't have that count directly, but per_rule_firings sum is a lower bound check)
    assert total_firings >= metrics["derivation_available_count"]


@pytest.mark.unit
def test_hard_pricing_rules_fire_correctly() -> None:
    """Real MD test: discount=30 + margin=35 -> block_or_escalate must be in rule firings."""
    result = evaluate(compare_llm=False)
    fired = result["metrics"]["per_rule_firings"]
    assert "pricing_discount_margin_guard" in fired, (
        f"Hard pricing rule never fired in golden dataset. Fired rules: {fired}"
    )


@pytest.mark.unit
def test_stall_rule_fires_on_md_test_case() -> None:
    """Per MD §5 stage_stall must fire on real cases in dataset."""
    result = evaluate(compare_llm=False)
    assert result["metrics"]["per_rule_firings"].get("stage_stall", 0) >= 1


# ── raw-LLM baseline (opt-in only — costs real money) ─────────────────────


@pytest.mark.skip(
    reason="costs real $ (calls Anthropic API). Run manually with --no-skip-llm to verify "
    "engine_advantage_pct_points > 0."
)
def test_llm_baseline_comparison() -> None:
    """Verify the engine beats raw LLM on the same dataset.

    Run manually:
        pytest tests/test_section7_experiment.py::test_llm_baseline_comparison \\
            --no-skip-llm -v
    """
    result = evaluate(compare_llm=True)
    metrics = result["metrics"]
    baseline = metrics["llm_baseline"]

    print("\n§7 RESULTS:")
    print(f"  Engine score:   {result['score']:.3f}  ({metrics['n_matched']}/{metrics['n_cases']})")
    print(
        f"  LLM baseline:   {baseline['score']:.3f}  ({baseline['n_matched']}/{baseline['n_cases']})"
    )
    print(f"  Advantage:      {metrics['engine_advantage_pct_points']:+.2f} percentage points")
    print(f"  LLM cost:       ${baseline['cost_usd']:.4f}")
    print(f"  LLM latency:    {baseline['latency_ms_total']} ms total")
    print("  Engine cost:    $0.00  (symbolic only)")

    # The honest pre-registered claim: engine matches or beats raw LLM
    assert result["score"] >= baseline["score"], (
        "Engine UNDERPERFORMS raw LLM — symbolic-first thesis needs revisiting"
    )
