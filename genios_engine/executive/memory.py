"""Executive Memory — not storage, WORKING CONTEXT: what was recently decided, what is
still open, what is overdue, and where attention currently sits. Four org-scoped reads
over tables that already exist; nothing new is written. This is the panel an executive
(or an agent) loads before making the NEXT decision, so decisions stop being amnesiac."""
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


def load_memory(store, org_id: str, *, limit: int = 10,
                eval_time: datetime | None = None) -> dict:
    eval_time = authority_time(eval_time)
    lim = max(1, min(int(limit), 50))
    with store.engine.connect() as c:
        c.execute(text(
            "select graph_version from graph_versions where org_id=:o for share"),
            {"o": org_id})
        recent = c.execute(text(
            "select decision_id, question, confidence, route, triggered_by, created_at "
            "from decisions where org_id=:o order by created_at desc limit :l"),
            {"o": org_id, "l": lim}).fetchall()
        open_signals = c.execute(text(
            "select s.signal_id, " + AUTHORITATIVE_REASON_CODE_SQL + " as reason_code, "
            + AUTHORITATIVE_SCORE_SQL + " as score, rr.completed_at as created_at, "
            "n.display_name from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            "left join graph_nodes n on n.node_id=rr.root_node_id "
            "and n.org_id=s.org_id and n.valid_to is null "
            "where s.org_id=:o and s.status='open' and "
            + AUTHORITATIVE_SIGNAL_PREDICATE + " "
            "order by selected_rc.final_utility_bp desc, rr.completed_at desc, "
            "rr.capability_id asc, rr.root_node_id asc, s.signal_id asc limit :l"),
            {"o": org_id, "l": lim, "authority_time": eval_time}).fetchall()
        overdue = c.execute(text(
            "select f.subject_node_id, f.value, n.display_name from graph_facts f "
            "left join graph_nodes n on n.node_id=f.subject_node_id and n.org_id=f.org_id "
            "and n.valid_to is null "
            "where f.org_id=:o and f.field='commitment.due_at' and f.valid_to is null "
            "and f.status='active' and (f.value #>> '{}')::timestamptz < :evaluation_time "
            "order by (f.value #>> '{}')::timestamptz asc limit :l"),
            {"o": org_id, "l": lim, "evaluation_time": eval_time}).fetchall()
        hot = c.execute(text(
            "select executive_attention.node_id, executive_attention.score, "
            "case when executive_attention.score >= 75 then 'critical' "
            "when executive_attention.score >= 50 then 'high' "
            "when executive_attention.score >= 25 then 'medium' else 'low' end as band, "
            "executive_attention.display_name from (select a.node_id, "
            + EXECUTIVE_ATTENTION_SCORE_SQL + " as score, n.display_name "
            "from context_attention a left join graph_nodes n on n.node_id=a.node_id "
            "and n.org_id=a.org_id and n.valid_to is null "
            + EXECUTIVE_ATTENTION_AUTHORITY_JOIN +
            "where a.org_id=:o) executive_attention "
            "order by executive_attention.score desc, executive_attention.node_id asc limit :l"),
            {"o": org_id, "l": lim, "authority_time": eval_time}).fetchall()
    return {
        "recent_decisions": [
            {"id": r.decision_id, "question": r.question,
             "confidence": float(r.confidence) if r.confidence is not None else None,
             "route": r.route, "triggered_by": r.triggered_by,
             "at": r.created_at.isoformat() if r.created_at else None} for r in recent],
        "open_decisions": [
            {"signal_id": r.signal_id, "reason": r.reason_code, "score": int(r.score),
             "entity": r.display_name,
             "since": r.created_at.isoformat() if r.created_at else None}
            for r in open_signals],
        "outstanding_items": [
            {"entity": r.display_name, "entity_id": r.subject_node_id,
             "due_at": str(r.value).strip('"')} for r in overdue],
        "strategic_priorities": [
            {"entity": r.display_name, "entity_id": r.node_id,
             "attention": int(r.score), "band": r.band} for r in hot],
    }
