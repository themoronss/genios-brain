"""Executive Summary ladder — one_line / one_minute / five_minute.

Deterministic composition over stored truth: the item SET, its ordering and its counts
are chosen by code; there is no LLM in v1 (when phrasing lands later, the model gets a
frozen, ranked item list and V-02 validation — it may re-word, never re-decide).
Numbers are counted, never estimated; an empty morning says "nothing needs you",
because a fabricated urgency costs the credibility of every real one."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from genios_engine.executive.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    EXECUTIVE_ATTENTION_AUTHORITY_JOIN,
    EXECUTIVE_ATTENTION_SCORE_SQL,
    authority_time,
)


def _counts(store, org_id: str, eval_time: datetime) -> dict:
    with store.engine.connect() as c:
        c.execute(text(
            "select graph_version from graph_versions where org_id=:o for share"),
            {"o": org_id})
        top = c.execute(text(
            "select " + AUTHORITATIVE_REASON_CODE_SQL + " as reason_code, "
            + AUTHORITATIVE_SCORE_SQL + " as score, n.display_name, "
            "count(*) over () as total, "
            "count(*) filter (where " + AUTHORITATIVE_SCORE_SQL + " >= 70) "
            "over () as high from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            "left join graph_nodes n on n.node_id=rr.root_node_id and n.org_id=s.org_id "
            "and n.valid_to is null where s.org_id=:o and s.status='open' and "
            + AUTHORITATIVE_SIGNAL_PREDICATE + " "
            "order by selected_rc.final_utility_bp desc, rr.completed_at desc, "
            "rr.capability_id asc, rr.root_node_id asc, s.signal_id asc limit 5"),
            {"o": org_id, "authority_time": eval_time}).fetchall()
        conflicts = c.execute(text(
            "select count(*) from discrepancies where org_id=:o and status='open'"),
            {"o": org_id}).scalar()
        overdue = c.execute(text(
            "select count(*) from graph_facts where org_id=:o and field='commitment.due_at' "
            "and valid_to is null and status='active' "
            "and (value #>> '{}')::timestamptz < :evaluation_time"),
            {"o": org_id, "evaluation_time": eval_time}).scalar()
        attention = c.execute(text(
            "select count(*) from (select " + EXECUTIVE_ATTENTION_SCORE_SQL + " as score "
            "from context_attention a " + EXECUTIVE_ATTENTION_AUTHORITY_JOIN +
            "where a.org_id=:o) executive_attention where executive_attention.score >= 50"),
            {"o": org_id, "authority_time": eval_time}).scalar()
    total = top[0].total if top else 0
    high = top[0].high if top else 0
    return {"open": int(total or 0), "high": int(high or 0),
            "top": [{"reason": t.reason_code, "score": int(t.score),
                     "entity": t.display_name} for t in top],
            "conflicts": int(conflicts or 0), "overdue_commitments": int(overdue or 0),
            "attention_hot": int(attention or 0)}


def build_summary(store, org_id: str, horizon: str = "one_line",
                  eval_time: datetime | None = None) -> dict:
    eval_time = authority_time(eval_time)
    k = _counts(store, org_id, eval_time)
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
