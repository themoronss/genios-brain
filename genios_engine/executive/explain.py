"""Explanation — and the half of it nobody ships: WHY NOT.

"Why did GeniOS not tell me about X?" has been answerable by a query since day one —
the reasoner writes a reason-coded row to signal_suppression_log for every silence
(below_gate | budget | cooldown | muted | shadow) — but nothing ever read it. Silence
without receipts is indistinguishable from a bug; this module turns the receipts into
an answer. Deterministic reads only; the explanation IS the stored arithmetic."""
from __future__ import annotations

from sqlalchemy import text

_REASON_HUMAN = {
    "below_gate": "the score didn't clear the gate — real, but not important enough yet",
    "budget": "the daily card budget was already spent on higher-scoring items",
    "cooldown": "the same finding fired recently — repeating it would be nagging",
    "muted": "this rule is auto-muted for you (its precision fell below the floor)",
    "shadow": "the pack is in shadow mode — evaluating silently, not allowed to surface",
    "situation": "a situational hold (e.g. a freeze window) suppressed it",
}


def why_not(store, org_id: str, *, entity_id: str | None = None,
            rule_id: str | None = None, days: int = 7, limit: int = 50) -> dict:
    """Every silence in the window, with its stored reason — newest first."""
    q = ("select rule_id, subject_node_id, reason_code, detail, eval_time "
         "from signal_suppression_log where org_id=:o "
         "and eval_time > now() - make_interval(days => :d)")
    params: dict = {"o": org_id, "d": max(1, min(int(days), 90)),
                    "l": max(1, min(int(limit), 200))}
    if entity_id:
        q += " and subject_node_id=:n"
        params["n"] = entity_id
    if rule_id:
        q += " and rule_id=:r"
        params["r"] = rule_id
    q += " order by eval_time desc limit :l"
    with store.engine.connect() as c:
        rows = c.execute(text(q), params).fetchall()
        names = {}
        ids = list({r.subject_node_id for r in rows})
        if ids:
            names = {n.node_id: n.display_name for n in c.execute(text(
                "select node_id, display_name from graph_nodes "
                "where org_id=:o and node_id = any(:n) and valid_to is null"),
                {"o": org_id, "n": ids})}
    return {"suppressions": [
        {"rule_id": r.rule_id, "entity": names.get(r.subject_node_id),
         "entity_id": r.subject_node_id, "reason_code": r.reason_code,
         "reason": _REASON_HUMAN.get(r.reason_code, r.reason_code),
         "detail": r.detail if isinstance(r.detail, dict) else {},
         "at": r.eval_time.isoformat() if r.eval_time else None}
        for r in rows]}
