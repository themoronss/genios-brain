from __future__ import annotations

# E2 · Band Assigner (§5.11). Cut the urgency band from S using the pack's band cuts — data,
# not engine constants (Finding B). S<high → standard, [high,critical) → high, ≥critical →
# critical. Small-deal tenants can't reach critical by construction; that's documented, not a bug.


def band(S: int, bands_cfg: dict | None) -> str:
    cfg = bands_cfg or {"high": 70, "critical": 85}
    if S >= int(cfg.get("critical", 85)):
        return "critical"
    if S >= int(cfg.get("high", 70)):
        return "high"
    return "standard"
