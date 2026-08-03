from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id

# L6 · Feedback / Calibration (Agent F). labels → counters → nudges → LVL3. Arithmetic, not
# gradients. This module is the WEEKLY heartbeat: F2 aggregates a 28-day precision window per rule
# from card_events, then F5 auto-mutes rules that train the user to ignore cards (protection
# outranks optimization — armed from day one). Every action is an ordinary auditable row.

WINDOW_DAYS = 28
MIN_IMPRESSIONS = 8            # eligibility: below this, too little data to judge a rule
MUTE_PRECISION = 0.25         # a rule under this precision is actively harmful
MUTE_MIN_IMPRESSIONS = 12     # ...with enough evidence to be sure
# F3 nudge bands (Law 3: small bounded steps). A per-rule score offset moves the gate: a
# high-precision rule is loosened (fires at a lower S), a low one tightened. ±5/week, bounded.
LOOSEN_ABOVE = 0.70
TIGHTEN_BELOW = 0.40
OFFSET_STEP = 5
OFFSET_BOUND = 15             # cumulative offset clamp — no runaway drift

# F1 taxonomy — the routing table (Law 1: buckets never collapse). A button maps to a label whose
# destination is precision-numerator, precision-denominator-only, or ZERO precision impact (timing/
# data signals are routed elsewhere, never blamed on the rule).
TAXONOMY = {
    "run_play":      {"label": "positive_strong",   "precision": "numerator"},
    "do_it_myself":  {"label": "positive_moderate", "precision": "numerator"},
    "wrong:not_relevant": {"label": "negative_relevance", "precision": "denominator"},
    "wrong:wrong_facts":  {"label": "negative_relevance", "precision": "denominator"},
    "wrong:bad_timing":   {"label": "timing",       "precision": "none"},     # zero precision impact
    "snooze":        {"label": "timing",            "precision": "none"},
    "requeue":       {"label": "window_mgmt",       "precision": "none"},     # excluded (Law: not judgment)
}

_PRECISION_SQL = text("""
    select s.rule_id,
      count(*) filter (where ce.kind = 'card.surfaced')                          as impressions,
      count(*) filter (where ce.cause = 'run_play')                              as run_play,
      count(*) filter (where ce.cause = 'do_it_myself')                          as diy,
      count(*) filter (where ce.cause = 'wrong'
                        and (ce.detail->>'reason') in ('not_relevant','wrong_facts')) as rel_wrong
    from card_events ce
    join cards k   on k.card_id = ce.card_id
    join signals s on s.signal_id = k.signal_id
    where ce.org_id = :o and ce.occurred_at >= :since
    group by s.rule_id
""")


def precision_28d(store, org_id: str, *, eval_time: datetime | None = None) -> dict[str, dict]:
    """F2 — per-rule precision over the trailing 28 days. precision = (run_play + diy) /
    (run_play + diy + relevance_wrongs); timing/window buckets contribute ZERO (Law 1)."""
    now = eval_time or datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)
    out: dict[str, dict] = {}
    with store.engine.connect() as c:
        for r in c.execute(_PRECISION_SQL, {"o": org_id, "since": since}):
            pos = int(r.run_play) + int(r.diy)
            denom = pos + int(r.rel_wrong)
            out[r.rule_id] = {"impressions": int(r.impressions), "run_play": int(r.run_play),
                              "diy": int(r.diy), "rel_wrong": int(r.rel_wrong),
                              "precision": (pos / denom) if denom else None,
                              "eligible": int(r.impressions) >= MIN_IMPRESSIONS}
    return out


def muted_rules(store, org_id: str) -> set[str]:
    """Active mutes for L3 to skip (read before the gate)."""
    with store.engine.connect() as c:
        return {r.rule_id for r in c.execute(text(
            "select rule_id from rule_mutes where org_id=:o and active"), {"o": org_id})}


def run_calibration(store, org_id: str, *, registry=None, pack_id: str = "sales",
                    eval_time: datetime | None = None) -> dict:
    """The weekly job (F2 → F5 → F3/F4). Computes precision, auto-mutes harmful rules (armed day
    one) / un-mutes recovered ones, then — if a registry is given — applies bounded per-rule
    threshold NUDGES through the L4 merge (pins respected). Every change is an audit row."""
    now = eval_time or datetime.now(timezone.utc)
    stats = precision_28d(store, org_id, eval_time=now)
    muted, recovered = [], []
    with store.engine.begin() as c:
        already = {r.rule_id for r in c.execute(text(
            "select rule_id from rule_mutes where org_id=:o and active"), {"o": org_id})}
        for rule_id, s in stats.items():
            p, imp = s["precision"], s["impressions"]
            harmful = p is not None and p < MUTE_PRECISION and imp >= MUTE_MIN_IMPRESSIONS
            if harmful and rule_id not in already:
                c.execute(text("insert into rule_mutes (org_id, rule_id, active, reason, precision, "
                               "impressions) values (:o,:r,true,'low_precision',:p,:i) "
                               "on conflict (org_id, rule_id) do update set active=true, "
                               "reason='low_precision', precision=:p, impressions=:i, muted_at=now()"),
                          {"o": org_id, "r": rule_id, "p": p, "i": imp})
                c.execute(text("insert into calibration_nudges (id, org_id, rule_id, param, "
                               "direction, precision, impressions) values (:id,:o,:r,'rule','mute',:p,:i)"),
                          {"id": new_id("nudge"), "o": org_id, "r": rule_id, "p": p, "i": imp})
                muted.append(rule_id)
            elif rule_id in already and p is not None and p >= MUTE_PRECISION:
                c.execute(text("update rule_mutes set active=false where org_id=:o and rule_id=:r"),
                          {"o": org_id, "r": rule_id})
                recovered.append(rule_id)

    nudges = []
    if registry is not None:
        effective, _ = registry.effective(org_id, pack_id)
        cur_offsets = (effective or {}).get("scoring", {}).get("rule_offsets", {}) if effective else {}
        muted_now = set(muted) | already
        for rule_id, s in stats.items():
            p, imp = s["precision"], s["impressions"]
            if not s["eligible"] or p is None or rule_id in muted_now:
                continue                              # thin data / muted → no nudge
            if p >= LOOSEN_ABOVE:
                delta, direction = -OFFSET_STEP, "loosen"
            elif p < TIGHTEN_BELOW:
                delta, direction = OFFSET_STEP, "tighten"
            else:
                continue                              # dead zone → HOLD
            cur = int(cur_offsets.get(rule_id, 0))
            new = max(-OFFSET_BOUND, min(OFFSET_BOUND, cur + delta))
            if new == cur:                            # already at the bound → nothing to write
                continue
            if registry.write_lvl3_offset(org_id, pack_id, rule_id, new):   # F4, pin-respecting
                with store.engine.begin() as c:
                    c.execute(text(
                        "insert into calibration_nudges (id, org_id, rule_id, param, before_val, "
                        "after_val, offset_cumulative, direction, precision, impressions) "
                        "values (:id,:o,:r,'gate.s_min',:b,:a,:a,:d,:p,:i)"),
                        {"id": new_id("nudge"), "o": org_id, "r": rule_id, "b": cur, "a": new,
                         "d": direction, "p": p, "i": imp})
                nudges.append({"rule_id": rule_id, "before": cur, "after": new,
                               "direction": direction, "precision": round(p, 3)})
    return {"org_id": org_id, "rules_scored": len(stats), "muted": muted,
            "recovered": recovered, "nudges": nudges, "window_days": WINDOW_DAYS}
