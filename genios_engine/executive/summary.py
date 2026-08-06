"""Executive Summary ladder — one_line / one_minute / five_minute.

Deterministic composition over stored truth: the item SET, its ordering and its counts
are chosen by code; there is no LLM in v1 (when phrasing lands later, the model gets a
frozen, ranked item list and V-02 validation — it may re-word, never re-decide).
Numbers are counted, never estimated; an empty morning says "nothing needs you",
because a fabricated urgency costs the credibility of every real one."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text


def _counts(store, org_id: str) -> dict:
    with store.engine.connect() as c:
        sig = c.execute(text(
            "select count(*) total, count(*) filter (where score >= 70) high "
            "from signals where org_id=:o and status='open'"), {"o": org_id}).first()
        top = c.execute(text(
            "select s.reason_code, s.score, n.display_name from signals s "
            "left join graph_nodes n on n.node_id=s.subject_node_id and n.org_id=s.org_id "
            "and n.valid_to is null "
            "where s.org_id=:o and s.status='open' order by s.score desc limit 5"),
            {"o": org_id}).fetchall()
        conflicts = c.execute(text(
            "select count(*) from discrepancies where org_id=:o and status='open'"),
            {"o": org_id}).scalar()
        overdue = c.execute(text(
            "select count(*) from graph_facts where org_id=:o and field='commitment.due_at' "
            "and valid_to is null and status='active' "
            "and (value #>> '{}')::timestamptz < now()"), {"o": org_id}).scalar()
        attention = c.execute(text(
            "select count(*) from context_attention where org_id=:o "
            "and band in ('high','critical')"), {"o": org_id}).scalar()
    return {"open": int(sig.total or 0), "high": int(sig.high or 0),
            "top": [{"reason": t.reason_code, "score": int(t.score),
                     "entity": t.display_name} for t in top],
            "conflicts": int(conflicts or 0), "overdue_commitments": int(overdue or 0),
            "attention_hot": int(attention or 0)}


def build_summary(store, org_id: str, horizon: str = "one_line",
                  eval_time: datetime | None = None) -> dict:
    eval_time = eval_time or datetime.now(timezone.utc)
    k = _counts(store, org_id)
    top = k["top"][0] if k["top"] else None

    if top is None:
        one_line = "Nothing needs you right now."
    else:
        who = f" — top: {top['entity']}, {top['reason'].replace('_', ' ')}" if top["entity"] else ""
        one_line = f"{k['open']} open item(s), {k['high']} high-band{who}."

    out = {"horizon": horizon, "as_of": eval_time.isoformat(), "one_line": one_line,
           "counts": {kk: v for kk, v in k.items() if kk != "top"}}
    if horizon in ("one_minute", "five_minute"):
        out["top_items"] = k["top"][:3 if horizon == "one_minute" else 5]
        out["needs_decision"] = k["overdue_commitments"] + k["conflicts"]
    if horizon == "five_minute":
        out["conflicts_open"] = k["conflicts"]
        out["overdue_commitments"] = k["overdue_commitments"]
        out["attention_hot_entities"] = k["attention_hot"]
    return out
