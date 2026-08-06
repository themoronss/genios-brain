"""Executive Memory — not storage, WORKING CONTEXT: what was recently decided, what is
still open, what is overdue, and where attention currently sits. Four org-scoped reads
over tables that already exist; nothing new is written. This is the panel an executive
(or an agent) loads before making the NEXT decision, so decisions stop being amnesiac."""
from __future__ import annotations

from sqlalchemy import text


def load_memory(store, org_id: str, *, limit: int = 10) -> dict:
    lim = max(1, min(int(limit), 50))
    with store.engine.connect() as c:
        recent = c.execute(text(
            "select decision_id, question, confidence, route, triggered_by, created_at "
            "from decisions where org_id=:o order by created_at desc limit :l"),
            {"o": org_id, "l": lim}).fetchall()
        open_signals = c.execute(text(
            "select s.signal_id, s.reason_code, s.score, s.created_at, n.display_name "
            "from signals s left join graph_nodes n on n.node_id=s.subject_node_id "
            "and n.org_id=s.org_id and n.valid_to is null "
            "where s.org_id=:o and s.status='open' order by s.score desc limit :l"),
            {"o": org_id, "l": lim}).fetchall()
        overdue = c.execute(text(
            "select f.subject_node_id, f.value, n.display_name from graph_facts f "
            "left join graph_nodes n on n.node_id=f.subject_node_id and n.org_id=f.org_id "
            "and n.valid_to is null "
            "where f.org_id=:o and f.field='commitment.due_at' and f.valid_to is null "
            "and f.status='active' and (f.value #>> '{}')::timestamptz < now() "
            "order by (f.value #>> '{}')::timestamptz asc limit :l"),
            {"o": org_id, "l": lim}).fetchall()
        hot = c.execute(text(
            "select a.node_id, a.score, a.band, n.display_name from context_attention a "
            "left join graph_nodes n on n.node_id=a.node_id and n.org_id=a.org_id "
            "and n.valid_to is null "
            "where a.org_id=:o order by a.score desc limit :l"),
            {"o": org_id, "l": lim}).fetchall()
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
