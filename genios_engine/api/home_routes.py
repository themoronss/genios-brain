"""Dashboard home aggregations — network health + first scan, computed from the v2 graph.

Not present in the legacy backend; built fresh from graph_nodes/graph_facts/graph_observations so
the dashboard's home cards render against the real graph. A "contact" is a current person/company
node; recency buckets come from the latest fact/observation timestamp per node; commitments are
`commitment.due_at` facts (same source the /context/commitments endpoint uses).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


def _days_since(value, now: datetime) -> float | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (now - value).total_seconds() / 86400.0


@router.get("/api/org/{org_id}/network-health")
def network_health(org_id: str, org: str = Depends(_org)) -> dict:
    now = datetime.now(timezone.utc)
    with _store().engine.connect() as conn:
        rows = conn.execute(text(
            "select n.node_id, n.display_name, n.node_type, "
            "  (select max(occurred_at) from graph_facts f "
            "   where f.org_id=n.org_id and f.subject_node_id=n.node_id) as fa, "
            "  (select max(occurred_at) from graph_observations o "
            "   where o.org_id=n.org_id and o.subject_node_id=n.node_id) as oa "
            "from graph_nodes n where n.org_id=:o and n.valid_to is null "
            "and n.node_type in ('person','company')"), {"o": org}).mappings().all()
        commits = conn.execute(text(
            "select f.subject_node_id, f.value, n.display_name from graph_facts f "
            "left join graph_nodes n on n.org_id=f.org_id and n.node_id=f.subject_node_id "
            "and n.valid_to is null "
            "where f.org_id=:o and f.field='commitment.due_at' and f.valid_to is null "
            "and f.status='active'"), {"o": org}).mappings().all()

    buckets = {"total_contacts": len(rows), "active_now": 0, "warm": 0,
               "needs_attention": 0, "cold": 0, "at_risk": 0}
    need_follow_up, at_risk_contacts = [], []
    for r in rows:
        last = max([d for d in (r["fa"], r["oa"]) if isinstance(d, datetime)], default=None)
        days = _days_since(last, now)
        card = {"id": r["node_id"], "name": r["display_name"] or r["node_id"],
                "type": r["node_type"], "days_since_contact": None if days is None else int(days)}
        if days is None or days > 90:
            buckets["at_risk"] += 1
            if len(at_risk_contacts) < 10:
                at_risk_contacts.append(card)
        elif days <= 7:
            buckets["active_now"] += 1
        elif days <= 30:
            buckets["warm"] += 1
        elif days <= 60:
            buckets["needs_attention"] += 1
            if len(need_follow_up) < 10:
                need_follow_up.append(card)
        else:
            buckets["cold"] += 1

    def _overdue(value) -> bool:
        try:
            due = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            return due < now
        except Exception:
            return False

    overdue = [{"id": c["subject_node_id"], "entity": c["display_name"], "due": c["value"]}
               for c in commits if _overdue(c["value"])]
    return {
        "network_health": buckets,
        "open_commitments": {"total": len(commits), "overdue": len(overdue)},
        "need_follow_up": need_follow_up,
        "at_risk_contacts": at_risk_contacts,
        "overdue_commitments": overdue[:10],
        "attention_required": (need_follow_up + at_risk_contacts)[:10],
    }


@router.get("/api/org/{org_id}/first-scan")
def first_scan(org_id: str, org: str = Depends(_org)) -> dict:
    now = datetime.now(timezone.utc)
    with _store().engine.connect() as conn:
        def count(sql: str) -> int:
            try:
                return int(conn.execute(text(sql), {"o": org}).scalar() or 0)
            except Exception:
                return 0
        items_read = count("select count(*) from source_events where org_id=:o")
        entities = count("select count(*) from graph_nodes where org_id=:o and valid_to is null "
                         "and node_type in ('person','company')")
        facts = count("select count(*) from graph_facts where org_id=:o and valid_to is null "
                      "and status='active'")
        situations = conn.execute(text(
            "select situation_type, anchor_node_id, confidence_overall from context_situations "
            "where org_id=:o and status='active' order by confidence_overall desc nulls last "
            "limit 5"), {"o": org}).mappings().all()

    findings = [{"type": s["situation_type"], "entity": s["anchor_node_id"],
                 "confidence": s["confidence_overall"]} for s in situations]
    headline = (f"Read {items_read} items, mapped {entities} contacts and {facts} facts."
                if items_read else "No data ingested yet — connect a source to begin.")
    return {
        "generated_at": now.isoformat(),
        "footprint": {"items_read": items_read, "entities": entities, "facts": facts},
        "headline": {"text": headline, "ready": items_read > 0},
        "findings": {"situations": findings, "count": len(findings)},
    }
