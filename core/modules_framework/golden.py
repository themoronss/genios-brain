"""Golden-test gate for module activation / hot-swap.

Per MD g-i-5 §5.1.1:
    activate(module, version):
        run module.goldenSet against core engine
        MUST pass threshold
        if pass: load atomically; keep previous version for instant rollback
        else:    block activation; report regressions

The evaluator script is module-supplied (e.g. modules/sales/evaluator.py).
It exposes a callable `evaluate(engine, dataset_dir) -> GoldenResult-like dict`.

This module runs the evaluator + applies the threshold from core.foundations.config.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.foundations.config import GOLDEN_THRESHOLD
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class GoldenResult:
    """Outcome of a golden-test run."""

    passed: bool
    score: float
    threshold: float
    metrics: dict[str, Any]
    reason: str


class GoldenTestError(Exception):
    """Evaluator script is invalid / unrunnable."""


def run_golden_test(
    evaluator_path: Path,
    *,
    module_id: str,
    threshold_key: str = "sales_initial",
    extra_args: dict[str, Any] | None = None,
) -> GoldenResult:
    """Import + run the module's evaluator. Apply threshold from config.

    The evaluator script must export `def evaluate(**kwargs) -> dict` returning
    at least `{"score": float, "metrics": {...}}`.

    `threshold_key` selects from config.GOLDEN_THRESHOLD (e.g. 'sales_initial' = 0.70).
    """
    if not evaluator_path.exists():
        raise GoldenTestError(f"Evaluator script not found: {evaluator_path}")

    threshold = GOLDEN_THRESHOLD.get(threshold_key)
    if threshold is None:
        raise GoldenTestError(f"Unknown threshold key: {threshold_key}")

    # Import the evaluator module by path (no package install required)
    spec = importlib.util.spec_from_file_location(f"_module_evaluator_{module_id}", evaluator_path)
    if spec is None or spec.loader is None:
        raise GoldenTestError(f"Cannot load evaluator from {evaluator_path}")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise GoldenTestError(f"Evaluator script error: {e}") from e

    evaluate = getattr(mod, "evaluate", None)
    if not callable(evaluate):
        raise GoldenTestError(f"Evaluator at {evaluator_path} must define a callable 'evaluate'")

    result = evaluate(**(extra_args or {}))
    if not isinstance(result, dict) or "score" not in result:
        raise GoldenTestError(
            f"Evaluator must return dict with 'score' key; got {type(result).__name__}"
        )

    score = float(result["score"])
    metrics = result.get("metrics", {})
    passed = score >= threshold

    log.info(
        "golden_test_run",
        module_id=module_id,
        score=score,
        threshold=threshold,
        passed=passed,
    )

    return GoldenResult(
        passed=passed,
        score=score,
        threshold=threshold,
        metrics=metrics,
        reason=(
            f"score {score:.3f} >= threshold {threshold:.3f}"
            if passed
            else f"score {score:.3f} < threshold {threshold:.3f} — activation BLOCKED"
        ),
    )
