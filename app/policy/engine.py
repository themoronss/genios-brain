"""
Policy engine — rules-as-data evaluator.

A rule is a JSON document:

  {
    "condition": {
        "all": [
            {"field": "confidence", "op": "lt", "value": 0.6},
            {"field": "risk_tier",  "op": "eq", "value": "external_send"}
        ]
    },
    "decision": "block"      # allow | warn | block | require_approval
  }

Operators: eq, ne, gt, gte, lt, lte, in, nin, contains, startswith, endswith, regex.
Logical groupings: all (AND), any (OR), not.

Decision lattice (worst wins): allow < warn < require_approval < block.
"""

import logging
import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DECISION_RANK = {"allow": 0, "warn": 1, "require_approval": 2, "block": 3}


# ── Condition evaluation ─────────────────────────────────────────────────────

def _get(ctx: dict, field: str) -> Any:
    """Dotted-path lookup in the request context."""
    cur: Any = ctx
    for part in field.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _atom(ctx: dict, cond: dict) -> bool:
    field = cond.get("field")
    op = (cond.get("op") or "eq").lower()
    rhs = cond.get("value")
    lhs = _get(ctx, field)

    try:
        if op == "eq":          return lhs == rhs
        if op == "ne":          return lhs != rhs
        if op == "gt":          return lhs is not None and lhs > rhs
        if op == "gte":         return lhs is not None and lhs >= rhs
        if op == "lt":          return lhs is not None and lhs < rhs
        if op == "lte":         return lhs is not None and lhs <= rhs
        if op == "in":          return lhs in (rhs or [])
        if op == "nin":         return lhs not in (rhs or [])
        if op == "contains":    return isinstance(lhs, (str, list)) and (rhs in lhs)
        if op == "startswith":  return isinstance(lhs, str) and lhs.startswith(rhs)
        if op == "endswith":    return isinstance(lhs, str) and lhs.endswith(rhs)
        if op == "regex":       return isinstance(lhs, str) and re.search(rhs, lhs) is not None
    except Exception as e:
        logger.debug(f"policy atom {field} {op} {rhs} vs {lhs} errored: {e}")
    return False


def _matches(ctx: dict, cond: Optional[dict]) -> bool:
    if not cond:
        return True
    if "all" in cond:
        return all(_matches(ctx, c) for c in cond["all"])
    if "any" in cond:
        return any(_matches(ctx, c) for c in cond["any"])
    if "not" in cond:
        return not _matches(ctx, cond["not"])
    return _atom(ctx, cond)


# ── Public API ───────────────────────────────────────────────────────────────

def load_rules(
    db: Session,
    org_id: str,
    action_type: str,
    risk_tier: Optional[str] = None,
) -> list:
    """
    Fetch enabled rules applying to this action. Ordered by priority (asc).
    A rule matches when action_type is equal or '*', and risk_tier is NULL or equal.
    """
    rows = db.execute(
        text("""
            SELECT id, name, mode, rule_json, priority, action_type, risk_tier
            FROM policy_rules
            WHERE org_id = :org
              AND enabled = TRUE
              AND (action_type = :atype OR action_type = '*')
              AND (risk_tier IS NULL OR risk_tier = :rtier OR :rtier IS NULL)
            ORDER BY priority ASC, created_at ASC
        """),
        {"org": org_id, "atype": action_type, "rtier": risk_tier},
    ).fetchall()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "mode": r.mode,
            "rule_json": r.rule_json,
            "priority": r.priority,
            "action_type": r.action_type,
            "risk_tier": r.risk_tier,
        }
        for r in rows
    ]


def evaluate(
    db: Session,
    org_id: str,
    action_type: str,
    risk_tier: str,
    ctx: dict,
) -> dict:
    """
    Run all applicable rules against `ctx` and return the strongest decision.

    Returns:
        {
          "decision":   "allow|warn|block|require_approval",
          "rule_id":    "<uuid or None>",
          "rule_name":  "<str or None>",
          "mode":       "enforce|warn_only|shadow",
          "matches":    [ {rule_id, rule_name, decision, mode}, ... ]
        }
    """
    rules = load_rules(db, org_id, action_type, risk_tier)
    matches = []
    strongest = {"decision": "allow", "rule_id": None, "rule_name": None, "mode": "enforce"}

    for rule in rules:
        rj = rule["rule_json"] or {}
        decision = (rj.get("decision") or "allow").lower()
        if decision not in _DECISION_RANK:
            decision = "allow"
        if not _matches(ctx, rj.get("condition")):
            continue

        matches.append({
            "rule_id": rule["id"], "rule_name": rule["name"],
            "decision": decision, "mode": rule["mode"],
        })

        effective = decision if rule["mode"] == "enforce" else "warn" if rule["mode"] == "warn_only" else "allow"
        if _DECISION_RANK[effective] > _DECISION_RANK[strongest["decision"]]:
            strongest = {
                "decision": effective,
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "mode": rule["mode"],
            }

    return {**strongest, "matches": matches}


def dry_run(
    db: Session,
    org_id: str,
    rule_json: dict,
    samples: list,
    action_type: str = "*",
    risk_tier: Optional[str] = None,
) -> dict:
    """
    Evaluate a candidate rule against arbitrary sample contexts without
    persisting it. Used by dashboard "test rule" flow.
    """
    cond = (rule_json or {}).get("condition")
    decision = (rule_json or {}).get("decision", "allow")
    fired, passed = 0, 0
    for s in samples:
        if _matches(s, cond):
            fired += 1
        else:
            passed += 1
    return {
        "would_match": fired,
        "would_pass": passed,
        "total": len(samples),
        "decision_if_match": decision,
        "action_type": action_type,
        "risk_tier": risk_tier,
    }
