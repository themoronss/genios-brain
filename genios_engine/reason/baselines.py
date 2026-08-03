from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore

# C9 — Baseline Builder. Closed-form per-contact statistics from graph/event history.
# reply_cadence = median gap (days) between a contact's messages. Cold-start fallback when
# there isn't enough history yet. Deterministic; stored versioned for replay.
#
# C1 extends it to two more per-contact metrics computed from the SAME event scan (no extra query):
#   momentum   = median(last-3 gaps) / median(all gaps)  — >1 the contact is cooling, <1 heating up.
#   engagement = events in the last 14d / events in the prior 14d — <1 interaction is thinning out.
# Both are stored as their own baseline keys and surfaced to rules as derived.* facts.

MIN_SAMPLES = 3
COLD_START_DAYS = 3.0


def _momentum(gaps: list[float]) -> float:
    """Recent cadence vs the contact's own norm. Needs ≥4 gaps to be meaningful, else neutral 1.0."""
    if len(gaps) < 4:
        return 1.0
    base = statistics.median(gaps)
    if base <= 0:
        return 1.0
    recent = statistics.median(gaps[-3:])
    return round(recent / base, 3)


def _engagement(times: list, eval_time: datetime) -> float:
    """Last-14d event volume vs the prior 14d. Neutral 1.0 until there's enough history in the window."""
    cut1 = eval_time - timedelta(days=14)
    cut2 = eval_time - timedelta(days=28)
    last = sum(1 for t in times if t and t >= cut1)
    prev = sum(1 for t in times if t and cut2 <= t < cut1)
    if prev == 0:
        return 1.0 if last <= 1 else 2.0        # ramping from cold, but don't divide by zero
    return round(last / float(prev), 3)


def build_baselines(store: GraphStore, org_id: str, eval_time: datetime | None = None) -> dict:
    eval_time = eval_time or datetime.now(timezone.utc)
    built = {"computed": 0, "cold_start": 0}
    with store.engine.connect() as c:
        people = c.execute(text(
            "select node_id, canonical_key from graph_nodes where org_id=:o "
            "and node_type='person' and canonical_key is not null and valid_to is null"),
            {"o": org_id}).fetchall()
        rows = []
        for p in people:
            times = [r.occurred_at for r in c.execute(text(
                "select occurred_at from source_events where org_id=:o and actor->>'email'=:e "
                "order by occurred_at"), {"o": org_id, "e": p.canonical_key})]
            times = [t if t is None or t.tzinfo else t.replace(tzinfo=timezone.utc) for t in times]
            if len(times) > MIN_SAMPLES:
                gaps = [max(0.0, (times[i + 1] - times[i]).total_seconds() / 86400.0)
                        for i in range(len(times) - 1)]
                val, cold, n = statistics.median(gaps) or COLD_START_DAYS, False, len(gaps)
                built["computed"] += 1
                mom = _momentum(gaps)
            else:
                gaps = []
                val, cold, n = COLD_START_DAYS, True, len(times)
                built["cold_start"] += 1
                mom = 1.0
            eng = _engagement(times, eval_time)
            rows.append([{"o": org_id, "k": f"reply_cadence:{p.node_id}", "v": float(val), "n": n, "c": cold},
                         {"o": org_id, "k": f"momentum:{p.node_id}", "v": float(mom), "n": len(gaps), "c": cold},
                         {"o": org_id, "k": f"engagement:{p.node_id}", "v": float(eng), "n": len(times), "c": cold}])
    with store.engine.begin() as c:
        for triple in rows:
            for r in triple:
                c.execute(text(
                    "insert into baselines (org_id, key, value, sample_size, cold_start, computed_at) "
                    "values (:o, :k, :v, :n, :c, now()) on conflict (org_id, key) do update set "
                    "value=excluded.value, sample_size=excluded.sample_size, "
                    "cold_start=excluded.cold_start, computed_at=now()"), r)
    return built


def load_baselines(store: GraphStore, org_id: str, node_id: str) -> dict[str, float]:
    """Back-compat: just the reply_cadence baseline used by `{baseline}` threshold resolution."""
    with store.engine.connect() as c:
        rows = c.execute(text("select key, value from baselines where org_id=:o and key=:k"),
                         {"o": org_id, "k": f"reply_cadence:{node_id}"}).fetchall()
    return {"reply_cadence": float(r.value) for r in rows} if rows else {}


def load_node_metrics(store: GraphStore, org_id: str, node_id: str):
    """One query for ALL of a node's baseline keys → (baselines, derived_facts). baselines feed
    `{baseline}` threshold resolution; derived_facts (momentum/engagement) are injected into
    ctx.facts as derived.* so pack rules can threshold them like any typed fact."""
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select key, value from baselines where org_id=:o and key like :pat"),
            {"o": org_id, "pat": f"%:{node_id}"}).fetchall()
    baselines: dict[str, float] = {}
    derived: dict[str, dict] = {}
    for r in rows:
        metric = str(r.key).split(":", 1)[0]
        v = float(r.value)
        if metric == "reply_cadence":
            baselines["reply_cadence"] = v
        elif metric in ("momentum", "engagement"):
            derived[f"derived.{metric}"] = {"value": v, "confidence": 0.85,
                                            "authority_rank": 2, "occurred_at": None, "src_count": 1}
    return baselines, derived
