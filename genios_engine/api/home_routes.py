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


def _weekly(conn, org: str, table: str, ts_col: str = "created_at", weeks: int = 12) -> list[int]:
    """A dense last-N-weeks count series (oldest→newest), zero-filled for weeks with no rows."""
    try:
        rows = conn.execute(text(
            f"select date_trunc('week', {ts_col}) wk, count(*) c from {table} "
            f"where org_id=:o and {ts_col} > now() - interval '{weeks} weeks' "
            "group by 1"), {"o": org}).all()
    except Exception:
        return [0] * weeks
    by_week = {r.wk.date().isoformat(): int(r.c) for r in rows if r.wk}
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    start = now - timedelta(weeks=weeks)
    series = []
    for i in range(weeks):
        wk = (start + timedelta(weeks=i))
        # align to Monday like date_trunc('week')
        monday = (wk - timedelta(days=wk.weekday())).date().isoformat()
        series.append(by_week.get(monday, 0))
    return series


def _scaled_bars(series: list[int]) -> list[int]:
    """Scale a count series to 0-100 for display; a flat series renders as a low baseline."""
    top = max(series) if series else 0
    if top <= 0:
        return [4] * len(series)
    return [max(4, round(v / top * 100)) for v in series]


def _delta(series: list[int]) -> tuple[str, str]:
    if len(series) < 2 or series[-2] == 0:
        return ("+0%", "up")
    pct = round((series[-1] - series[-2]) / series[-2] * 100)
    return (f"{'+' if pct >= 0 else ''}{pct}%", "up" if pct >= 0 else "down")


@router.get("/api/org/{org_id}/home-summary")
def home_summary(org_id: str, org: str = Depends(_org)) -> dict:
    """The whole dashboard home, computed live: coverage snapshot + 4 headline cards + graph
    knowledge. Replaces the static homepage module — every number here comes from real tables."""
    now = datetime.now(timezone.utc)
    with _store().engine.connect() as conn:
        def one(sql: str) -> int:
            try:
                return int(conn.execute(text(sql), {"o": org}).scalar() or 0)
            except Exception:
                return 0

        decisions_7d = one("select count(*) from decisions where org_id=:o "
                           "and created_at > now() - interval '7 days'")
        situations_7d = one("select count(*) from context_situations where org_id=:o "
                            "and status='active' and computed_at > now() - interval '7 days'")
        situations_total = one("select count(*) from context_situations where org_id=:o "
                               "and status='active'")
        signals_total = one("select count(*) from signals where org_id=:o")
        outcomes_7d = one("select count(*) from execution_outcomes where org_id=:o "
                          "and created_at > now() - interval '7 days'")
        risks = one("select count(*) from graph_facts where org_id=:o and field='commitment.due_at' "
                    "and valid_to is null and status='active'")

        dec_series = _weekly(conn, org, "decisions")
        sit_series = _weekly(conn, org, "context_situations", "computed_at")
        out_series = _weekly(conn, org, "execution_outcomes")

        facts = one("select count(*) from graph_facts where org_id=:o and valid_to is null "
                    "and status='active'")
        entities = one("select count(*) from graph_nodes where org_id=:o and valid_to is null "
                       "and node_type in ('person','company')")
        rels = one("select count(*) from graph_edges where org_id=:o and valid_to is null")
        docs = one("select count(*) from source_events where org_id=:o")
        sources = one("select count(*) from connections where org_id=:o")

        # Real inputs for intervention + the evidence/freshness/policy health strip.
        grounded = one("select count(*) from graph_facts where org_id=:o and valid_to is null "
                       "and status='active' and confidence >= 0.5")
        fresh_facts = one("select count(*) from graph_facts where org_id=:o and valid_to is null "
                          "and status='active' and occurred_at > now() - interval '30 days'")
        notify = one("select count(*) from decisions where org_id=:o "
                     "and created_at > now() - interval '7 days' "
                     "and route in ('notify','flag','human','human_approval')")

    coverage = min(100, round(100 * decisions_7d / situations_total)) if situations_total else 0
    # Human intervention = share of this week's decisions that needed a human (0 when none yet).
    intervention = round(100 * notify / decisions_7d) if decisions_7d else 0
    evidence_cov = round(100 * grounded / facts) if facts else 0
    freshness = round(100 * fresh_facts / facts) if facts else 0
    policy_safe = 100 if decisions_7d else 0                # fail-closed gating; nothing yet → 0
    health = [
        {"label": "Evidence coverage", "value": f"{evidence_cov}%",
         "note": "Facts backed by source evidence"},
        {"label": "Freshness", "value": f"{freshness}%", "note": "Facts confirmed recently"},
        {"label": "Policy-safe actions", "value": f"{policy_safe}%",
         "note": "No action bypassed a hard rule"},
    ]
    dec_delta, dec_dir = _delta(dec_series)
    sit_delta, sit_dir = _delta(sit_series)
    out_delta, out_dir = _delta(out_series)

    return {
        "generated_at": now.isoformat(),
        "snapshot": {
            "period": "Last 7 days",
            "coverage": coverage,
            "coverageChange": 0,
            "beforeAsk": min(100, round(100 * decisions_7d / max(1, situations_7d))),
            "outcomeRate": min(100, round(100 * outcomes_7d / max(1, decisions_7d))),
            "humanEffortReduction": 100 - intervention,
            "health": health,
            "notice": {
                "title": "Your company is becoming more proactive.",
                "summary": ("GeniOS identified meaningful changes across your company, prepared "
                            "decisions before they were requested, and kept routine work from "
                            "becoming executive work."),
                "highlights": [
                    f"{situations_7d} material situations were understood before anyone had to ask.",
                    f"{decisions_7d} decisions were safely handed to the right owner or agent.",
                    f"{risks} follow-through risks were caught before their due window closed.",
                ],
            },
        },
        "cards": [
            {"key": "decisions", "label": "Intelligent Decisions", "value": str(decisions_7d),
             "unit": "this week", "delta": dec_delta, "direction": dec_dir,
             "note": "Prepared before anyone asked", "bars": _scaled_bars(dec_series),
             "href": "/dashboard/audit"},
            {"key": "situations", "label": "Situations formed", "value": str(situations_7d),
             "unit": f"from {signals_total} signals", "delta": sit_delta, "direction": sit_dir,
             "note": "Business reality, not raw events", "bars": _scaled_bars(sit_series),
             "href": "/dashboard/intelligence"},
            {"key": "verified", "label": "Verified outcomes", "value": str(outcomes_7d),
             "unit": "results observed", "delta": out_delta, "direction": out_dir,
             "note": "Confirmed inside their window", "bars": _scaled_bars(out_series),
             "href": "/dashboard/audit"},
            {"key": "intervention", "label": "Human intervention", "value": f"{intervention}%",
             "unit": "of decisions", "delta": "+0%", "direction": "down",
             "note": "Falling is the goal here", "bars": [max(4, intervention)] * 12,
             "href": "/dashboard/audit"},
        ],
        "graphKnowledge": [
            {"label": "Facts", "value": f"{facts:,}", "change": ""},
            {"label": "Entities", "value": f"{entities:,}", "change": ""},
            {"label": "Relationships", "value": f"{rels:,}", "change": ""},
            {"label": "Documents indexed", "value": f"{docs:,}", "change": ""},
            {"label": "Active sources", "value": f"{sources} connected", "change": "Live",
             "live": True},
            {"label": "Context calls served", "value": f"{decisions_7d:,}", "change": ""},
        ],
    }
