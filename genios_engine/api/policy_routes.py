"""Governance — Policies (dashboard → Settings → Policies). Rules-as-data CRUD + a symbolic
evaluator + dry-run. Ported from genios-brain (app/policy) to the engine's raw-SQL + `_org`
conventions. The evaluator is pure/self-contained so it can be reused when the engine gains a
server-side action path (open an approval on a require_approval decision).
"""
from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.ids import new_id
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

_DECISION_RANK = {"allow": 0, "warn": 1, "require_approval": 2, "block": 3}
_MODES = {"enforce", "warn_only", "shadow"}


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


# ── Rules-as-data evaluator (condition tree over an action context) ─────────────
def _get(ctx: dict, field: str | None) -> Any:
    cur: Any = ctx
    for part in (field or "").split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            break
    return cur


def _atom(ctx: dict, cond: dict) -> bool:
    lhs, op, rhs = _get(ctx, cond.get("field")), (cond.get("op") or "eq").lower(), cond.get("value")
    try:
        if op == "eq":         return lhs == rhs
        if op == "ne":         return lhs != rhs
        if op == "gt":         return lhs is not None and lhs > rhs
        if op == "gte":        return lhs is not None and lhs >= rhs
        if op == "lt":         return lhs is not None and lhs < rhs
        if op == "lte":        return lhs is not None and lhs <= rhs
        if op == "in":         return lhs in (rhs or [])
        if op == "nin":        return lhs not in (rhs or [])
        if op == "contains":   return isinstance(lhs, (str, list)) and rhs in lhs
        if op == "startswith": return isinstance(lhs, str) and lhs.startswith(rhs)
        if op == "endswith":   return isinstance(lhs, str) and lhs.endswith(rhs)
        if op == "regex":      return isinstance(lhs, str) and re.search(rhs, lhs) is not None
    except Exception:                                          # noqa: BLE001 - a bad atom never matches
        return False
    return False


def _matches(ctx: dict, cond: dict | None) -> bool:
    if not cond:
        return True
    if "all" in cond: return all(_matches(ctx, c) for c in cond["all"])
    if "any" in cond: return any(_matches(ctx, c) for c in cond["any"])
    if "not" in cond: return not _matches(ctx, cond["not"])
    return _atom(ctx, cond)


def evaluate(rules: list[dict], ctx: dict) -> dict:
    """Strongest decision across enabled rules (allow<warn<require_approval<block). `rules` are
    serialized policy rows. Kept importable for a future enforcement path."""
    strongest = {"decision": "allow", "rule_id": None, "rule_name": None, "mode": "enforce"}
    matches = []
    for r in sorted(rules, key=lambda x: (x.get("priority", 100))):
        if not r.get("enabled", True):
            continue
        rj = r.get("rule_json") or {}
        decision = (rj.get("decision") or "allow").lower()
        if decision not in _DECISION_RANK or not _matches(ctx, rj.get("condition")):
            continue
        matches.append({"rule_id": r["id"], "rule_name": r["name"], "decision": decision, "mode": r["mode"]})
        eff = decision if r["mode"] == "enforce" else "warn" if r["mode"] == "warn_only" else "allow"
        if _DECISION_RANK[eff] > _DECISION_RANK[strongest["decision"]]:
            strongest = {"decision": eff, "rule_id": r["id"], "rule_name": r["name"], "mode": r["mode"]}
    return {**strongest, "matches": matches}


# ── serialization ───────────────────────────────────────────────────────────────
_COLS = ("id, name, description, action_type, risk_tier, rule_json, priority, enabled, mode, "
         "version, created_at, updated_at, created_by")


def _ser(r) -> dict:
    rj = r.rule_json if isinstance(r.rule_json, dict) else (json.loads(r.rule_json) if r.rule_json else {})
    return {"id": r.id, "name": r.name, "description": r.description, "action_type": r.action_type,
            "risk_tier": r.risk_tier, "rule_json": rj, "priority": int(r.priority), "enabled": bool(r.enabled),
            "mode": r.mode, "version": int(r.version),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None, "created_by": r.created_by}


def _fetch(c, org: str, rule_id: str):
    return c.execute(text(f"select {_COLS} from policy_rules where org_id=:o and id=:i"),
                     {"o": org, "i": rule_id}).first()


# ── routes ──────────────────────────────────────────────────────────────────────
@router.get("/api/org/{org_id}/policies")
def list_policies(org_id: str, enabled_only: bool = False, org: str = Depends(_org)) -> dict:
    q = f"select {_COLS} from policy_rules where org_id=:o"
    if enabled_only:
        q += " and enabled = true"
    q += " order by priority asc, created_at asc"
    with _graph.engine.connect() as c:
        rows = c.execute(text(q), {"o": org}).fetchall()
    return {"rules": [_ser(r) for r in rows]}


class PolicyIn(BaseModel):
    name: str
    action_type: str = "*"
    rule_json: dict = {}
    description: str | None = None
    risk_tier: str | None = None
    priority: int = 100
    mode: str = "enforce"


@router.post("/api/org/{org_id}/policies")
def create_policy(org_id: str, body: PolicyIn, org: str = Depends(_org)) -> dict:
    if body.mode not in _MODES:
        raise HTTPException(422, {"error": "invalid_mode", "message": f"mode must be one of {sorted(_MODES)}"})
    rid = new_id("pol")
    with _graph.engine.begin() as c:
        c.execute(text(
            "insert into policy_rules (id, org_id, name, description, action_type, risk_tier, "
            "rule_json, priority, mode) values (:i,:o,:n,:d,:a,:r,cast(:rj as jsonb),:p,:m)"),
            {"i": rid, "o": org, "n": body.name, "d": body.description, "a": body.action_type,
             "r": body.risk_tier, "rj": json.dumps(body.rule_json or {}), "p": body.priority, "m": body.mode})
        row = _fetch(c, org, rid)
    from genios_engine.platform.audit import record
    record(org, "config_changed", actor_type="user", target_type="policy", target_id=rid,
           metadata={"event": "policy_created", "name": body.name})
    return _ser(row)


class PolicyPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    action_type: str | None = None
    risk_tier: str | None = None
    rule_json: dict | None = None
    priority: int | None = None
    enabled: bool | None = None
    mode: str | None = None


@router.patch("/api/org/{org_id}/policies/{rule_id}")
def update_policy(org_id: str, rule_id: str, body: PolicyPatch, org: str = Depends(_org)) -> dict:
    sets, params = [], {"o": org, "i": rule_id}
    for k in ("name", "description", "action_type", "risk_tier", "priority", "enabled", "mode"):
        v = getattr(body, k)
        if v is not None:
            sets.append(f"{k} = :{k}"); params[k] = v
    if body.rule_json is not None:
        sets.append("rule_json = cast(:rule_json as jsonb)"); params["rule_json"] = json.dumps(body.rule_json)
    with _graph.engine.begin() as c:
        if _fetch(c, org, rule_id) is None:
            raise HTTPException(404, {"error": "not_found", "message": "policy not found"})
        if sets:
            sets += ["version = version + 1", "updated_at = now()"]
            c.execute(text(f"update policy_rules set {', '.join(sets)} where org_id=:o and id=:i"), params)
        row = _fetch(c, org, rule_id)
    return _ser(row)


@router.delete("/api/org/{org_id}/policies/{rule_id}")
def delete_policy(org_id: str, rule_id: str, org: str = Depends(_org)) -> dict:
    with _graph.engine.begin() as c:
        res = c.execute(text("delete from policy_rules where org_id=:o and id=:i"), {"o": org, "i": rule_id})
    return {"deleted": (res.rowcount or 0) > 0}


class DryRunIn(BaseModel):
    rule_json: dict
    samples: list[dict] = []
    action_type: str = "*"
    risk_tier: str | None = None


@router.post("/api/org/{org_id}/policies/dry-run")
def dry_run(org_id: str, body: DryRunIn, org: str = Depends(_org)) -> dict:
    cond = (body.rule_json or {}).get("condition")
    fired = sum(1 for s in body.samples if _matches(s, cond))
    return {"would_match": fired, "would_pass": len(body.samples) - fired, "total": len(body.samples),
            "decision_if_match": (body.rule_json or {}).get("decision", "allow"),
            "action_type": body.action_type, "risk_tier": body.risk_tier}
