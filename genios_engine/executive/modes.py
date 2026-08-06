"""The four intelligence modes — and the machinery for the fourth.

    reactive    an answer to a question someone asked
    proactive   a rule fired on the CURRENT state (something already went wrong)
    predictive  a trajectory/forecast rule fired (something is trending wrong)
    preventive  NOTHING has fired yet — but a rule's time threshold is about to trip

Preventive is the vision's USP: "314 Capital follow-up miss hone se pehle bata dena."
It is pure arithmetic: for every elapsed-time rule condition (days_since ≥ N), compute
how far along the clock is. Inside the warning window (default: past 60% of the
threshold) → a preventive finding with the exact time remaining. Zero LLM, zero new
state — it reads the same facts and the same pack rules the reasoner already uses,
so a preventive warning can never disagree with the signal that later fires."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# rules whose derived.* trajectory conditions make a FIRED signal predictive
_PREDICTIVE_LEVELS = {"predictive"}
WARN_FRACTION = 0.6          # preventive window opens past this fraction of the threshold


def mode_of_signal(level: str, triggered_by: str = "rule") -> str:
    """Mode of an already-FIRED signal (preventive findings never come from here —
    by definition they exist only before a signal does)."""
    if triggered_by == "query":
        return "reactive"
    return "predictive" if level in _PREDICTIVE_LEVELS else "proactive"


@dataclass
class PreventiveFinding:
    rule_id: str
    subject_node_id: str
    path: str                     # the fact whose clock is running (e.g. thread.last_inbound)
    elapsed_days: float
    threshold_days: float
    days_remaining: float         # until the rule flips true
    fraction: float               # elapsed / threshold (0.6..1.0 inside the window)


def _ts(v):
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.strip('"').replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


def _elapsed_conditions(rule: dict):
    """Yield (path, threshold_days) for every days/hours_since ≥/> condition."""
    for c in rule.get("when", []):
        fn, op = c.get("fn"), c.get("op")
        if fn in ("days_since", "hours_since") and op in (">=", ">"):
            v = c.get("value")
            if isinstance(v, (int, float)):
                yield c.get("path"), (float(v) if fn == "days_since" else float(v) / 24.0)


def _static_conditions_hold(rule: dict, facts: dict) -> bool:
    """The NON-time conditions must already hold for a countdown to be meaningful
    (warning about a stalled deal that isn't open would be noise). Time conditions
    are skipped (they're what we're counting down); unknown condition kinds fail
    closed (no warning) — a preventive false alarm costs trust like any other."""
    for c in rule.get("when", []):
        if c.get("fn") in ("days_since", "hours_since"):
            continue
        if "path" in c and "op" in c:
            f = facts.get(c["path"])
            if f is None:
                return False
            val = f.get("value") if isinstance(f, dict) else f
            val = str(val).strip('"') if val is not None else None
            want = c.get("value")
            if c["op"] == "=" and val != str(want):
                return False
            if c["op"] == "!=" and val == str(want):
                return False
            if c["op"] not in ("=", "!="):
                return False              # numeric compares: fail closed in v1
        elif "has_obs" in c:
            if c["has_obs"] not in facts.get("_obs_kinds", set()):
                return False
        elif "no_obs" in c:
            if c["no_obs"] in facts.get("_obs_kinds", set()):
                return False
        else:
            return False                  # neighbor/exists/absent: fail closed in v1
    return True


def preventive_findings(rules: list[dict], facts_by_node: dict[str, dict],
                        eval_time: datetime, *,
                        warn_fraction: float = WARN_FRACTION) -> list[PreventiveFinding]:
    """All about-to-trip elapsed rules across the given nodes' facts. Pure function:
    (pack rules, node facts, clock) → findings. Same inputs, same warnings, replayable."""
    out: list[PreventiveFinding] = []
    for node_id, facts in facts_by_node.items():
        for rule in rules:
            if not _static_conditions_hold(rule, facts):
                continue
            for path, threshold_d in _elapsed_conditions(rule):
                f = facts.get(path)
                if f is None or threshold_d <= 0:
                    continue
                ts = _ts(f.get("value") if isinstance(f, dict) else f)
                if ts is None:
                    continue
                elapsed_d = (eval_time - ts).total_seconds() / 86400.0
                frac = elapsed_d / threshold_d
                if warn_fraction <= frac < 1.0:
                    out.append(PreventiveFinding(
                        rule_id=str(rule.get("id")), subject_node_id=node_id, path=path,
                        elapsed_days=round(elapsed_d, 2),
                        threshold_days=round(threshold_d, 2),
                        days_remaining=round(threshold_d - elapsed_d, 2),
                        fraction=round(frac, 3)))
    out.sort(key=lambda p: (p.days_remaining, p.rule_id, p.subject_node_id))
    return out


# ── store-reading loader (the pure function's data supplier) ──────────────────────
def load_preventive(store, org_id: str, *, registry=None,
                    eval_time: datetime | None = None, limit: int = 25) -> list[dict]:
    """Facts + pack rules → about-to-trip warnings, entity names attached. Skips any
    (rule, node) that ALREADY has an open signal — a warning about something that has
    fired is not preventive, it's an echo."""
    from sqlalchemy import text
    from genios_engine.executive.authority import (
        AUTHORITATIVE_SIGNAL_JOINS,
        AUTHORITATIVE_SIGNAL_PREDICATE,
        EXECUTIVE_RULE_ID_SQL,
        authority_time,
    )
    eval_time = authority_time(eval_time)
    rules: list[dict] = []
    if registry is not None:
        try:
            effective, _sid = registry.effective(org_id)
            if effective:
                rules = list(effective.get("rules") or [])
        except Exception:      # noqa: BLE001 — no pack, no warnings; never an error
            rules = []
    if not rules:
        return []

    with store.engine.connect() as c:
        c.execute(text(
            "select graph_version from graph_versions where org_id=:o for share"),
            {"o": org_id})
        facts_by_node: dict[str, dict] = {}
        for r in c.execute(text(
                "select subject_node_id nid, field, value from graph_facts "
                "where org_id=:o and valid_to is null and status='active'"), {"o": org_id}):
            facts_by_node.setdefault(r.nid, {})[r.field] = {"value": r.value}
        for r in c.execute(text(
                "select subject_node_id nid, kind from graph_observations "
                "where org_id=:o and status='active'"), {"o": org_id}):
            facts_by_node.setdefault(r.nid, {}).setdefault("_obs_kinds", set()).add(r.kind)
        already = {(r.rule_id, r.subject_node_id) for r in c.execute(text(
            "select " + EXECUTIVE_RULE_ID_SQL + " as rule_id, "
            "rr.root_node_id as subject_node_id from signals s "
            + AUTHORITATIVE_SIGNAL_JOINS +
            "where s.org_id=:o and s.status='open' and "
            + AUTHORITATIVE_SIGNAL_PREDICATE),
            {"o": org_id, "authority_time": eval_time})}
        names = {r.node_id: r.display_name for r in c.execute(text(
            "select node_id, display_name from graph_nodes where org_id=:o and valid_to is null"),
            {"o": org_id})}

    finds = [f for f in preventive_findings(rules, facts_by_node, eval_time)
             if (f.rule_id, f.subject_node_id) not in already]
    return [{"rule_id": f.rule_id, "entity": names.get(f.subject_node_id),
             "entity_id": f.subject_node_id, "path": f.path,
             "elapsed_days": f.elapsed_days, "threshold_days": f.threshold_days,
             "days_remaining": f.days_remaining, "fraction": f.fraction,
             "mode": "preventive"}
            for f in finds[:max(1, min(int(limit), 100))]]
