from __future__ import annotations

import math
from collections.abc import Mapping

# L3 scoring — score.v0.3 (spec §3.15). Integer basis points, round-half-up (Law 4).
# S = C · (0.45·U + 0.35·I + 0.20·R). U,I,R,C are integers 0..100; C is a percent.
# The curves use floats but every stored score is an integer → byte-identical replay.


def _finite(name: str, value) -> float:
    """Return a finite numeric value or reject it explicitly.

    NaN and infinities are especially dangerous in ranking code: comparisons against NaN are
    always false, while infinities can silently dominate every candidate.  Keep this validation at
    the arithmetic boundary so callers cannot accidentally persist an unorderable score.
    """
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _bounded(name: str, value, low: float, high: float) -> float:
    return min(high, max(low, _finite(name, value)))


def _validated_weights(weights: Mapping | None, defaults: dict[str, int],
                       keys: tuple[str, ...]) -> dict[str, int]:
    raw = defaults if weights is None else weights
    if not isinstance(raw, Mapping) or any(k not in raw for k in keys):
        raise ValueError(f"weights must define {', '.join(keys)}")
    out: dict[str, int] = {}
    for key in keys:
        value = _finite(f"weights.{key}", raw[key])
        if value < 0 or not value.is_integer():
            raise ValueError(f"weights.{key} must be a non-negative integer")
        out[key] = int(value)
    if sum(out.values()) != 100:
        raise ValueError("weights must sum to 100")
    return out


def rhu(x: float) -> int:
    """Round half up (never banker's rounding, never float-truncation)."""
    return int(math.floor(_finite("x", x) + 0.5))


def urgency(kind: str, elapsed_hours: float, h: float, floor: float = 0.0) -> int:
    """elapsed rules rise with time (stalled state); countdown rules decay toward a due moment.
    h = the rule's curve constant (in the rule's natural time unit). `floor` (0..100) is the
    minimum urgency at the trigger moment — for HOT signals (budget approved, contract requested,
    objection raised) the signal ITSELF is the urgency, so they must fire immediately rather than
    wait for elapsed time to lift U off zero; U still grows with time above the floor."""
    if kind not in {"elapsed", "countdown"}:
        raise ValueError("kind must be 'elapsed' or 'countdown'")
    elapsed = max(0.0, _finite("elapsed_hours", elapsed_hours))
    curve_h = max(1.0, _finite("h", h))
    floor_pct = _bounded("floor", floor, 0.0, 100.0)
    if kind == "countdown":
        u = rhu(100 * math.exp(-elapsed / 24.0))
    else:
        u = rhu(100 * (1 - math.exp(-elapsed / curve_h)))
    return min(100, max(rhu(floor_pct), u))


def impact(value: float | None, p90: float | None, *, linked_deal: bool = True,
           floor: float = 40.0, tier_mult: float = 1.0) -> int:
    """I = max(floor, 100·min(1, value/P90))·tier — floor (pack config) so real revenue
    never starves the gate at a pre-P90 (early) tenant. Floor applies to deal-linked only."""
    amount = 0.0 if value is None else max(0.0, _finite("value", value))
    percentile = 0.0 if p90 is None else _finite("p90", p90)
    multiplier = max(0.0, _finite("tier_mult", tier_mult))
    floor_pct = _bounded("floor", floor, 0.0, 100.0)
    base = 100 * min(1.0, amount / percentile) if amount > 0 and percentile > 0 else 0.0
    i = base * multiplier
    if linked_deal:
        i = max(floor_pct, i)
    return rhu(min(100.0, max(0.0, i)))


def recency(hours_since_flip: float, *, half_life: float = 72.0) -> int:
    """R = 100·e^(−hrs_since_flip/half_life). 100 at the episode flip, decays after."""
    elapsed = max(0.0, _finite("hours_since_flip", hours_since_flip))
    half_life_value = _finite("half_life", half_life)
    if half_life_value <= 0:
        raise ValueError("half_life must be greater than zero")
    return rhu(100 * math.exp(-elapsed / half_life_value))


def confidence(extraction_conf: float, *, freshness: float = 1.0,
               corroboration: float = 0.6, c_weights: dict | None = None) -> int:
    """C = w_conf·extraction + w_fresh·freshness + w_corr·corroboration, integer percent.
    Weights come from the pack (score.v0.3 defaults 50/30/20)."""
    w = _validated_weights(c_weights, {"conf": 50, "fresh": 30, "corr": 20},
                           ("conf", "fresh", "corr"))
    extraction = _bounded("extraction_conf", extraction_conf, 0.0, 1.0)
    fresh = _bounded("freshness", freshness, 0.0, 1.0)
    corroborated = _bounded("corroboration", corroboration, 0.0, 1.0)
    result = rhu(w["conf"] * extraction + w["fresh"] * fresh + w["corr"] * corroborated)
    return min(100, max(0, result))


def score(U: int, I: int, R: int, C_pct: int, weights: dict | None = None) -> tuple[int, dict]:
    """S = rhu(C · (wu·U + wi·I + wr·R)). Weights from the pack; integer bp; every machine agrees."""
    w = _validated_weights(weights, {"u": 45, "i": 35, "r": 20}, ("u", "i", "r"))
    u = rhu(_bounded("U", U, 0.0, 100.0))
    impact_pct = rhu(_bounded("I", I, 0.0, 100.0))
    recency_pct = rhu(_bounded("R", R, 0.0, 100.0))
    confidence_pct = rhu(_bounded("C_pct", C_pct, 0.0, 100.0))
    terms_bp = w["u"] * u + w["i"] * impact_pct + w["r"] * recency_pct
    result = rhu(confidence_pct * terms_bp / 10000.0)
    S = min(100, max(0, result))
    return S, {"U": u, "I": impact_pct, "R": recency_pct, "C": confidence_pct,
               "terms_bp": terms_bp}
