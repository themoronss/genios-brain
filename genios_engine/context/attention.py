"""The Attention component — "look here first", precomputed per node.

CONSTITUTIONAL RULE (enforced by tests/test_attention.py::test_attention_never_gates_evaluation):
attention may
ORDER and BUDGET retrieval; it may NEVER gate evaluation. If evaluation scope were ever
narrowed by attention, the loop closes into self-reinforcing starvation — a low-attention
node is never evaluated, so it never produces signals, so its attention never rises.
Evaluation scope stays: every node, every sweep.

Deterministic integer arithmetic over graph-local features (no LLM, no floats stored):
  recency    0..40  how recently the thread moved (either direction)
  ball       0..15  ball in OUR court → someone is waiting on us
  commitment 0..25  an open commitment, more if overdue
  question   0..15  an open question asked in the last 14 days
  polarity  -10..10 windowed negative vs positive observation balance
  signal     0..20  max open L3 signal score / 5 (DATA read of the signals table)
Score clamps to 0..100. Bands: >=75 critical, >=50 high, >=25 medium, else low.

L2 is the SOLE WRITER of context_attention (refresh runs at the end of the L2 drain).
L4/L6 may read it; a reason/ or deliver/ module writing it is a layer violation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.vocabulary import OBS_NEGATIVE, OBS_POSITIVE

QUESTION_WINDOW_DAYS = 14
POLARITY_WINDOW_DAYS = 90


def _ts(v):
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


def _recency_points(last, now) -> int:
    if last is None:
        return 0
    age_d = (now - last).total_seconds() / 86400.0
    if age_d <= 3:
        return 40
    if age_d <= 7:
        return 30
    if age_d <= 14:
        return 20
    if age_d <= 45:
        return 10
    return 0


def score_node(*, now: datetime, last_inbound, last_outbound, ball_in_court: str | None,
               commitment_due, question_at, pos_recent: int, neg_recent: int,
               max_open_signal: int) -> tuple[int, str, dict]:
    """Pure scoring — every component integer, every input explicit, fully replayable."""
    last = max((t for t in (_ts(last_inbound), _ts(last_outbound)) if t is not None),
               default=None)
    recency = _recency_points(last, now)
    ball = 15 if ball_in_court == "us" else 0
    commitment = 0
    due = _ts(commitment_due)
    if due is not None:
        commitment = 25 if due < now else 15
    question = 0
    q_at = _ts(question_at)
    if q_at is not None and q_at >= now - timedelta(days=QUESTION_WINDOW_DAYS):
        question = 15
    if neg_recent > pos_recent:
        polarity = 10                      # trouble deserves attention
    elif pos_recent > neg_recent:
        polarity = 5                       # momentum deserves some too
    else:
        polarity = 0
    signal = min(20, int(max_open_signal) // 5) if max_open_signal else 0

    score = max(0, min(100, recency + ball + commitment + question + polarity + signal))
    band = ("critical" if score >= 75 else "high" if score >= 50
            else "medium" if score >= 25 else "low")
    inputs = {"recency": recency, "ball": ball, "commitment": commitment,
              "question": question, "polarity": polarity, "signal": signal,
              "last_activity": last.isoformat() if last else None}
    return score, band, inputs


def refresh_attention(store, org_id: str, *, node_ids: set[str] | None = None,
                      eval_time: datetime | None = None) -> int:
    """Recompute context_attention for the org's person/deal nodes (or just node_ids).
    A handful of org-wide bulk queries, then one upsert per node. Returns rows written."""
    now = eval_time or datetime.now(timezone.utc)
    import json
    with store.engine.connect() as c:
        nodes = [(r.node_id, r.node_type) for r in c.execute(text(
            "select node_id, node_type from graph_nodes where org_id=:o "
            "and valid_to is null and node_type in ('person','deal')"), {"o": org_id})
            if node_ids is None or r.node_id in node_ids]
        if not nodes:
            return 0
        want = {n for n, _ in nodes}

        facts: dict[str, dict] = {}
        for r in c.execute(text(
                "select subject_node_id nid, field, value, occurred_at from graph_facts "
                "where org_id=:o and valid_to is null and status='active' and field in "
                "('thread.last_inbound','thread.last_outbound','thread.ball_in_court',"
                "'commitment.due_at')"), {"o": org_id}):
            if r.nid in want:
                facts.setdefault(r.nid, {})[r.field] = (r.value, r.occurred_at)

        q_at: dict[str, datetime] = {}
        pol: dict[str, list[int]] = {}
        win = now - timedelta(days=POLARITY_WINDOW_DAYS)
        for r in c.execute(text(
                "select subject_node_id nid, kind, occurred_at from graph_observations "
                "where org_id=:o and status='active'"), {"o": org_id}):
            if r.nid not in want:
                continue
            ts = _ts(r.occurred_at)
            if r.kind == "question" and ts is not None:
                if r.nid not in q_at or ts > q_at[r.nid]:
                    q_at[r.nid] = ts
            if ts is not None and ts >= win:
                pn = pol.setdefault(r.nid, [0, 0])
                if r.kind in OBS_POSITIVE:
                    pn[0] += 1
                elif r.kind in OBS_NEGATIVE:
                    pn[1] += 1

        sig: dict[str, int] = {}
        for r in c.execute(text(
                "select subject_node_id nid, max(score) mx from signals "
                "where org_id=:o and status='open' group by subject_node_id"), {"o": org_id}):
            if r.nid in want:
                sig[r.nid] = int(r.mx or 0)

    written = 0
    with store.engine.begin() as c:
        for nid, _ntype in nodes:
            f = facts.get(nid, {})
            ball_v = f.get("thread.ball_in_court", (None, None))[0]
            ball = str(ball_v).strip('"') if ball_v is not None else None
            pn = pol.get(nid, [0, 0])
            score, band, inputs = score_node(
                now=now,
                last_inbound=str(f.get("thread.last_inbound", (None,))[0] or "") or None,
                last_outbound=str(f.get("thread.last_outbound", (None,))[0] or "") or None,
                ball_in_court=ball,
                commitment_due=str(f.get("commitment.due_at", (None,))[0] or "") or None,
                question_at=q_at.get(nid),
                pos_recent=pn[0], neg_recent=pn[1],
                max_open_signal=sig.get(nid, 0))
            c.execute(text(
                "insert into context_attention (org_id, node_id, score, band, inputs, computed_at) "
                "values (:o, :n, :s, :b, cast(:i as jsonb), :t) "
                "on conflict (org_id, node_id) do update set score=excluded.score, "
                "band=excluded.band, inputs=excluded.inputs, computed_at=excluded.computed_at"),
                {"o": org_id, "n": nid, "s": score, "b": band,
                 "i": json.dumps(inputs), "t": now})
            written += 1
    return written
