from __future__ import annotations

import math

# L3 scoring — score.v0.3 (spec §3.15). Integer basis points, round-half-up (Law 4).
# S = C · (0.45·U + 0.35·I + 0.20·R). U,I,R,C are integers 0..100; C is a percent.
# The curves use floats but every stored score is an integer → byte-identical replay.


def rhu(x: float) -> int:
    """Round half up (never banker's rounding, never float-truncation)."""
    return int(math.floor(x + 0.5))


def urgency(kind: str, elapsed_hours: float, h: float) -> int:
    """elapsed rules rise with time (stalled state); countdown rules decay toward a due
    moment. h = the rule's curve constant (in the rule's natural time unit)."""
    if kind == "countdown":
        return rhu(100 * math.exp(-max(0.0, elapsed_hours) / 24.0))
    return rhu(100 * (1 - math.exp(-max(0.0, elapsed_hours) / max(1.0, h))))


def impact(value: float | None, p90: float | None, *, linked_deal: bool = True,
           floor: float = 40.0, tier_mult: float = 1.0) -> int:
    """I = max(floor, 100·min(1, value/P90))·tier — floor (pack config) so real revenue
    never starves the gate at a pre-P90 (early) tenant. Floor applies to deal-linked only."""
    base = 100 * min(1.0, value / p90) if (value and p90) else 0.0
    i = base * tier_mult
    if linked_deal:
        i = max(float(floor), i)
    return rhu(min(100.0, i))


def recency(hours_since_flip: float, *, half_life: float = 72.0) -> int:
    """R = 100·e^(−hrs_since_flip/half_life). 100 at the episode flip, decays after."""
    return rhu(100 * math.exp(-max(0.0, hours_since_flip) / half_life))


def confidence(extraction_conf: float, *, freshness: float = 1.0,
               corroboration: float = 0.6, c_weights: dict | None = None) -> int:
    """C = w_conf·extraction + w_fresh·freshness + w_corr·corroboration, integer percent.
    Weights come from the pack (score.v0.3 defaults 50/30/20)."""
    w = c_weights or {"conf": 50, "fresh": 30, "corr": 20}
    return rhu(int(w["conf"]) * extraction_conf + int(w["fresh"]) * freshness
               + int(w["corr"]) * corroboration)


def score(U: int, I: int, R: int, C_pct: int, weights: dict | None = None) -> tuple[int, dict]:
    """S = rhu(C · (wu·U + wi·I + wr·R)). Weights from the pack; integer bp; every machine agrees."""
    w = weights or {"u": 45, "i": 35, "r": 20}
    terms_bp = int(w["u"]) * U + int(w["i"]) * I + int(w["r"]) * R
    S = rhu(C_pct * terms_bp / 10000.0)
    return S, {"U": U, "I": I, "R": R, "C": C_pct, "terms_bp": terms_bp}
