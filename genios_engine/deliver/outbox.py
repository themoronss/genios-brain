"""The delivery outbox — every outbound human notification is a ROW, never a blocking
HTTP call inside the reasoning sweep.

Why this shape: the agent-webhook path does its POST synchronously inside the 6-hourly
cross-org thread, so one slow endpoint degrades every tenant's reasoning — the failure
that reads as "GeniOS is down". Human channels start correct instead: ENQUEUE (fast,
idempotent, deduped by (org, card, channel)) → DRAIN (claimed with FOR UPDATE SKIP
LOCKED, bounded backoff, terminal after the schedule ends) → every send lands a
card_events row, so delivered/failed is queryable state, not a log line.

Dispatch policy (mirrors the card pipeline's push law without touching it): HIGH and
CRITICAL band cards notify; STANDARD stays a dashboard rotation. The daily digest goes
once per org per UTC day under a synthetic card id — same dedup machinery, zero
special cases."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.deliver.channels import get_channel
from genios_engine.deliver.channels.slack import format_card_message, format_digest_message
from genios_engine.platform.ids import new_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
)

# retry schedule (minutes after the Nth failure); after the last slot → failed_terminal.
BACKOFF_MINUTES: tuple[int, ...] = (5, 30, 120, 720)
NOTIFY_BANDS = ("high", "critical")


def next_attempt_delay(attempts: int) -> int | None:
    """Pure: minutes until the next try after `attempts` failures; None = terminal."""
    if attempts < 1:
        return 0
    if attempts <= len(BACKOFF_MINUTES):
        return BACKOFF_MINUTES[attempts - 1]
    return None


def digest_card_id(day) -> str:
    """Synthetic card id for the daily digest → the (org, card, channel) unique index
    dedups it exactly like a real card."""
    return f"digest:{day.isoformat()}"


def _current_digest_payload(engine, org_id: str, evaluation_time: datetime) -> dict:
    """Build a non-actionable digest from current authority immediately before send."""
    from genios_engine.executive.summary import build_summary

    class _SummaryStore:
        pass

    store = _SummaryStore()
    store.engine = engine
    return format_digest_message(
        build_summary(store, org_id, "one_minute", eval_time=evaluation_time))


# ── enqueue ───────────────────────────────────────────────────────────────────────
def enqueue_pending(engine, org_id: str, channel: str = "slack",
                    base_url: str = "") -> int:
    """Queue un-notified HIGH/CRITICAL cards for this org's channel. Idempotent: the
    unique index makes a re-run a no-op. Payload is built from card columns that
    already passed the render validators — the channel adds no words."""
    queued = 0
    now = datetime.now(timezone.utc)
    with engine.begin() as c:
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        rows = c.execute(text(
            "select k.card_id,k.signal_id,k.headline,k.situation,k.urgency_band," +
            AUTHORITATIVE_SCORE_SQL + " as score,s.reasoning_run_id,"
            "s.reasoning_decision_hash,s.authority_pack_revision,s.authority_expires_at "
            "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id " +
            AUTHORITATIVE_SIGNAL_JOINS +
            "where k.org_id=:o and k.state in ('queued','surfaced') "
            "and s.status='open' and k.expires_at>:authority_time and " +
            AUTHORITATIVE_SIGNAL_PREDICATE + " "
            "and k.urgency_band in ('high','critical') "
            "and not exists (select 1 from delivery_outbox ob where ob.org_id=k.org_id "
            "and ob.card_id=k.card_id and ob.channel=:ch) "
            "for share of k,s,rr,ro,selected_rc,rcap,authority_ctx,authority_cfg,authority_pack"),
            {"o": org_id, "ch": channel, "authority_time": now}).fetchall()
        for r in rows:
            payload = format_card_message(dict(r._mapping), base_url=base_url)
            res = c.execute(text(
                "insert into delivery_outbox (id,org_id,card_id,channel,payload,signal_id,"
                "reasoning_run_id,reasoning_decision_hash,authority_pack_revision,"
                "authority_expires_at) values (:i,:o,:c,:ch,cast(:payload as jsonb),"
                ":signal,:run,:decision,:revision,:expires) "
                "on conflict (org_id, card_id, channel) do nothing"),
                {"i": new_id("ob"), "o": org_id, "c": r.card_id, "ch": channel,
                 "payload": json.dumps(payload), "signal": r.signal_id,
                 "run": r.reasoning_run_id, "decision": r.reasoning_decision_hash,
                 "revision": r.authority_pack_revision, "expires": r.authority_expires_at})
            queued += res.rowcount
    return queued


def enqueue_digest(engine, org_id: str, channel: str = "slack",
                   eval_time: datetime | None = None) -> int:
    """Claim one daily digest slot.

    The row is only a delivery intent.  Its authority-sensitive content is regenerated from the
    current executive projection in ``drain`` so a queued digest can never send yesterday's
    revoked recommendation after a graph/config/pack change.
    """
    now = eval_time or datetime.now(timezone.utc)
    today = now.date()
    payload = {"kind": "daily_digest_intent", "for_date": today.isoformat()}
    with engine.begin() as c:
        row = c.execute(text(
            "select last_digest_date from org_channels "
            "where org_id=:o and channel=:ch and active for update"),
            {"o": org_id, "ch": channel}).first()
        if row is None or (row.last_digest_date is not None
                           and row.last_digest_date >= today):
            return 0
        c.execute(text("update org_channels set last_digest_date=:d, updated_at=now() "
                       "where org_id=:o and channel=:ch"),
                  {"d": today, "o": org_id, "ch": channel})
        res = c.execute(text(
            "insert into delivery_outbox (id, org_id, card_id, channel, payload) "
            "values (:i, :o, :c, :ch, cast(:p as jsonb)) "
            "on conflict (org_id, card_id, channel) do nothing"),
            {"i": new_id("ob"), "o": org_id, "c": digest_card_id(today), "ch": channel,
             "p": json.dumps(payload)})
        return res.rowcount


# ── drain ─────────────────────────────────────────────────────────────────────────
def drain(engine, *, eval_time: datetime | None = None, limit: int = 50) -> dict:
    """Deliver due rows. Claim with FOR UPDATE SKIP LOCKED (two instances never send
    the same message), send OUTSIDE row-lock scope per row, record the outcome, and
    write a card_events audit row for real cards."""
    now = eval_time or datetime.now(timezone.utc)
    out = {"delivered": 0, "retried": 0, "terminal": 0, "cancelled": 0}

    with engine.begin() as c:
        due = c.execute(text(
            "select id,org_id,card_id,channel,payload,attempts,signal_id,reasoning_run_id,"
            "reasoning_decision_hash,authority_pack_revision,authority_expires_at "
            "from delivery_outbox "
            "where status='queued' and next_attempt_at <= :now "
            "order by next_attempt_at asc limit :l for update skip locked"),
            {"now": now, "l": max(1, min(int(limit), 200))}).fetchall()
        claimed = [dict(r._mapping) for r in due]
        # mark in-flight rows' next_attempt into the future so a crashed drain retries
        # them on schedule instead of double-sending on the very next tick
        for r in claimed:
            c.execute(text("update delivery_outbox set next_attempt_at=:na where id=:i"),
                      {"na": now + timedelta(minutes=5), "i": r["id"]})

    configs: dict[tuple[str, str], dict | None] = {}
    with engine.connect() as c:
        for r in claimed:
            key = (r["org_id"], r["channel"])
            if key not in configs:
                row = c.execute(text(
                    "select config from org_channels where org_id=:o and channel=:ch "
                    "and active"), {"o": key[0], "ch": key[1]}).first()
                cfg = row.config if row else None
                configs[key] = (cfg if isinstance(cfg, dict)
                                else json.loads(cfg) if cfg else None)

    for r in claimed:
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        cfg = configs.get((r["org_id"], r["channel"]))
        ch = get_channel(r["channel"])
        if ch is None or cfg is None:
            _finish(engine, r, now, ok=False, detail="channel unregistered or inactive",
                    terminal=True, out=out)
            continue
        if not str(r["card_id"]).startswith("digest:"):
            # Hold the same graph/pack/card authority locks through the outbound POST. This is a
            # deliberately short human notification call; safety wins over sending a revoked card.
            with engine.begin() as authority_conn:
                authority_conn.execute(text(
                    "select graph_version from graph_versions where org_id=:o for share"),
                    {"o": r["org_id"]})
                live = authority_conn.execute(text(
                    "select 1 from cards k join signals s "
                    "on s.signal_id=k.signal_id and s.org_id=k.org_id " +
                    AUTHORITATIVE_SIGNAL_JOINS +
                    "where k.org_id=:o and k.card_id=:card and k.signal_id=:signal "
                    "and s.reasoning_run_id=:run and s.reasoning_decision_hash=:decision "
                    "and s.authority_pack_revision=:revision and s.status='open' "
                    "and k.state in ('queued','surfaced') and k.expires_at>:authority_time "
                    "and " + AUTHORITATIVE_SIGNAL_PREDICATE +
                    " for share of k,s,rr,ro,selected_rc,rcap,authority_ctx,authority_cfg,"
                    "authority_pack"),
                    {"o": r["org_id"], "card": r["card_id"], "signal": r["signal_id"],
                     "run": r["reasoning_run_id"], "decision": r["reasoning_decision_hash"],
                     "revision": r["authority_pack_revision"], "authority_time": now}).first()
                if live is None:
                    res = None
                else:
                    res = ch.send(payload, cfg)
            if res is None:
                _cancel(engine, r, "decision authority revoked before delivery", out)
                continue
        else:
            try:
                payload = _current_digest_payload(engine, r["org_id"], now)
            except Exception as exc:  # noqa: BLE001 - never send stale fallback bytes
                delay = next_attempt_delay(r["attempts"] + 1)
                _finish(engine, r, now, ok=False,
                        detail=f"current digest projection unavailable: {exc}"[:300],
                        terminal=delay is None, out=out, delay_minutes=delay)
                continue
            res = ch.send(payload, cfg)
        if res.ok:
            _finish(engine, r, now, ok=True, detail="", terminal=False, out=out)
        else:
            delay = next_attempt_delay(r["attempts"] + 1)
            _finish(engine, r, now, ok=False, detail=res.detail,
                    terminal=delay is None, out=out, delay_minutes=delay)
    return out


def _cancel(engine, row: dict, detail: str, out: dict) -> None:
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set status='cancelled',attempts=attempts+1,last_error=:e "
            "where id=:i and status='queued'"),
            {"i": row["id"], "e": detail[:300]})
    out["cancelled"] += 1


def _finish(engine, row: dict, now: datetime, *, ok: bool, detail: str, terminal: bool,
            out: dict, delay_minutes: int | None = None) -> None:
    with engine.begin() as c:
        if ok:
            c.execute(text(
                "update delivery_outbox set status='delivered', delivered_at=:t, "
                "attempts=attempts+1, last_error=null where id=:i"),
                {"t": now, "i": row["id"]})
            out["delivered"] += 1
            if not str(row["card_id"]).startswith("digest:"):
                c.execute(text(
                    "insert into card_events (id, org_id, card_id, kind, cause, detail) "
                    "values (:i, :o, :c, 'notification.sent', :ch, cast(:d as jsonb))"),
                    {"i": new_id("ce"), "o": row["org_id"], "c": row["card_id"],
                     "ch": row["channel"], "d": json.dumps({"outbox_id": row["id"]})})
        elif terminal:
            c.execute(text(
                "update delivery_outbox set status='failed_terminal', attempts=attempts+1, "
                "last_error=:e where id=:i"), {"e": detail[:300], "i": row["id"]})
            out["terminal"] += 1
        else:
            c.execute(text(
                "update delivery_outbox set attempts=attempts+1, last_error=:e, "
                "next_attempt_at=:na where id=:i"),
                {"e": detail[:300], "na": now + timedelta(minutes=delay_minutes or 5),
                 "i": row["id"]})
            out["retried"] += 1


# ── the sweep entrypoint ──────────────────────────────────────────────────────────
def run_distribution(engine, *, base_url: str = "",
                     eval_time: datetime | None = None) -> dict:
    """One distribution pass: for every org with an active channel, enqueue new
    high/critical cards + the daily digest, then drain everything due. Called from the
    maintenance sweep; per-org failures isolate."""
    now = eval_time or datetime.now(timezone.utc)
    totals = {"orgs": 0, "queued": 0, "digests": 0}
    with engine.connect() as c:
        orgs = [r.org_id for r in c.execute(text(
            "select distinct org_id from org_channels where active"))]
    for org in orgs:
        totals["orgs"] += 1
        try:
            totals["queued"] += enqueue_pending(engine, org, base_url=base_url)
            totals["digests"] += enqueue_digest(engine, org, eval_time=now)
        except Exception:      # noqa: BLE001 — one org's enqueue never blocks the rest
            pass
    totals.update(drain(engine, eval_time=now))
    return totals
