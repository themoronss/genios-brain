from __future__ import annotations

# D3 Merge Engine — the ONLY producer of effective config. effective = deep_merge(LVL1
# pack, LVL2 admin, LVL3 learned), with pin dominance (a pinned path freezes the LVL2/LVL1
# value; LVL3 nudges are rejected) and guardrail dominance (no level overrides a guardrail).


def deep_merge(*dicts: dict) -> dict:
    out: dict = {}
    for d in dicts:
        for k, v in (d or {}).items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = deep_merge(out[k], v)
            else:
                out[k] = v
    return out


def _get(cfg: dict, path: str):
    cur = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set(cfg: dict, path: str, val) -> None:
    parts = path.split(".")
    cur = cfg
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = val


def apply_guardrails(cfg: dict) -> dict:
    """Law 4 — absolute floors/ceilings no level can override (rejected, not silently kept)."""
    rejected = []
    gate = cfg.setdefault("gate", {})
    if int(gate.get("c_min", 60)) < 50:
        rejected.append(("gate.c_min", gate.get("c_min"), 50))
        gate["c_min"] = 50
    if int(cfg.get("budget_per_user_day", 7)) > 15:
        rejected.append(("budget_per_user_day", cfg.get("budget_per_user_day"), 15))
        cfg["budget_per_user_day"] = 15
    w = cfg.get("weights", {})
    if w and (int(w.get("u", 0)) + int(w.get("i", 0)) + int(w.get("r", 0))) != 100:
        rejected.append(("weights.sum", "≠100", "reset"))
        cfg["weights"] = {"u": 45, "i": 35, "r": 20}
    cfg["_guardrail_rejections"] = rejected
    return cfg


def merge_config(pack_defaults: dict, lvl2: dict, lvl3: dict, pins: list[str]) -> dict:
    """LVL1 (pack) → LVL2 (admin) → LVL3 (learned); pinned paths freeze at LVL2/LVL1;
    then guardrails clamp. Deterministic → same inputs, same effective config, same hash."""
    eff = deep_merge(pack_defaults or {}, lvl2 or {}, lvl3 or {})
    for path in (pins or []):                    # pin dominance: LVL3 cannot move a pin
        val = _get(lvl2 or {}, path)
        if val is None:
            val = _get(pack_defaults or {}, path)
        if val is not None:
            _set(eff, path, val)
    return apply_guardrails(eff)
