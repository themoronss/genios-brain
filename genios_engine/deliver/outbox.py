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
special cases.

Admission (Layer 5.2) sits between the claim and the send. Enqueue *materialises* the
delivery object onto the row — recipient, band, channel class, interrupt — and `drain`
asks `deliver/gate.py` whether that delivery may travel *now*. It runs before the
authority re-validation because it is local and lock-free while that check holds `for
share` locks across an outbound POST, and it produces three outcomes rather than two:

  SEND      → the existing path, unchanged.
  DEFER     → move `next_attempt_at`, bump `defer_count`, touch NOTHING else. A hold is
              not a failure, and if it spent an `attempts` slot a message queued at 22:00
              would be `failed_terminal` by breakfast — the exact one somebody wanted.
  SUPPRESS  → status `suppressed`, distinct from `cancelled`. Cancelled means the subject
              stopped being live; suppressed means this person, or this tenant, said no.
              Collapsing them makes "why did nothing arrive?" unanswerable from the row."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.contracts.delivery import DeliveryVerdict
from genios_engine.contracts.execution import ChannelClass
from genios_engine.deliver.channels import get_channel
from genios_engine.deliver.channels.slack import format_card_message, format_digest_message
from genios_engine.deliver.executive_bridge import (
    enqueue_executive_messages,
    executive_delivery_is_live,
    is_executive_delivery,
    link_commitment_cards,
    mark_executive_delivered,
)
from genios_engine.deliver.gate import (
    PgDeliveryContext,
    admit,
    candidate_from_row,
    channel_class_for,
    defer_until,
)
from genios_engine.deliver.destination import destination_from_row, route_destinations
from genios_engine.executive.communication import may_interrupt
from genios_engine.executive.execution import execution_config
from genios_engine.platform.ids import new_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
)

# retry schedule (minutes after the Nth failure); after the last slot → failed_terminal.
BACKOFF_MINUTES: tuple[int, ...] = (5, 30, 120, 720)
NOTIFY_BANDS = ("high", "critical")


def card_confidence_bp(score_block) -> int:
    """The reasoner's confidence in this card, in basis points.

    ``score_block.C`` is the 0..100 confidence percentage — the same number ``authority.py``
    projects out of ``confidence_bp`` and ``composer.py`` converts back with ``* 100``. Reusing
    that conversion rather than introducing a third shape is what keeps a card that Postgres
    calls authoritative from disagreeing with the interrupt rule about how sure the system is.

    A card with no recorded confidence returns 0, and 0 cannot clear any interrupt floor. That is
    the intended reading: an unmeasured conclusion is not a confident one, and the cost of being
    wrong here is somebody's sleep.
    """
    block = _as_dict(score_block)
    if not block:
        return 0
    try:
        return int(round(float(block.get("C", 0)))) * 100
    except (TypeError, ValueError):
        return 0


def _as_dict(value) -> dict:
    """A jsonb column as a dict, whatever the driver handed back. Never raises."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def communication_config(effective_config) -> dict:
    """The tenant's own interrupt settings, from the config snapshot the card scored under.

    Not the *current* pack config — the snapshot this specific card was authorised by, which the
    authority join already carries. That matters: a tenant who tightens `interrupt_band` while a
    card is queued should not have the old card re-judged by the new rule, because the card's
    band was cut by the old one. Reading both from the same snapshot is what keeps the two ends
    of the comparison talking about the same configuration.

    Empty when a pack has not opted into tuning, which every unit reads as "use the defaults".
    """
    return dict(execution_config(_as_dict(effective_config)).get("communication") or {})


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


def _neutral_card_payload(card: dict, *, base_url: str = "") -> dict:
    """Grounded adapter-neutral card bytes for Teams, webhook and pull surfaces."""
    link = f"{base_url.rstrip('/')}/cards/{card.get('card_id')}" if base_url else None
    return {"kind": "intelligence_card", "card_id": card.get("card_id"),
            "headline": str(card.get("headline") or "")[:150],
            "situation": str(card.get("situation") or "")[:300],
            "band": str(card.get("urgency_band") or "standard"),
            "score": card.get("score"), "url": link}


def format_card_for_channel(channel: str, card: dict, *, base_url: str = "") -> dict:
    return (format_card_message(card, base_url=base_url) if channel == "slack"
            else _neutral_card_payload(card, base_url=base_url))


def format_digest_for_channel(channel: str, digest: dict) -> dict:
    if channel == "slack":
        return format_digest_message(digest)
    return {"kind": "daily_digest", "one_line": str(digest.get("one_line") or ""),
            "items": list(digest.get("top_items") or digest.get("items") or [])[:5]}


def _current_digest_payload(engine, org_id: str, evaluation_time: datetime,
                            channel: str = "slack") -> dict:
    """Build a non-actionable digest from current authority immediately before send."""
    from genios_engine.executive.summary import build_summary

    class _SummaryStore:
        pass

    store = _SummaryStore()
    store.engine = engine
    return format_digest_for_channel(
        channel, build_summary(store, org_id, "one_minute", eval_time=evaluation_time))


# ── enqueue ───────────────────────────────────────────────────────────────────────
def enqueue_pending(engine, org_id: str, channel: str = "slack",
                    base_url: str = "") -> int:
    """Queue un-notified HIGH/CRITICAL cards for this org's channel. Idempotent: the
    unique index makes a re-run a no-op. Payload is built from card columns that
    already passed the render validators — the channel adds no words.

    The delivery object is stamped here rather than at send time so a retry three hours later
    judges the *same* delivery it queued, and so the drain needs no extra joins to know whose
    attention a row is about to spend."""
    queued = 0
    now = datetime.now(timezone.utc)
    channel_class = channel_class_for(channel).value
    with engine.begin() as c:
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        rows = c.execute(text(
            "select k.card_id,k.signal_id,k.headline,k.situation,k.urgency_band,"
            "k.assignee,k.score_block,authority_cfg.effective as effective_config," +
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
            payload = format_card_for_channel(channel, dict(r._mapping), base_url=base_url)
            # A card is pushed to chat *because* it cleared the push band, so this path never
            # builds a CommunicationPlan — but it still has to say whether the card may break
            # through quiet hours. Asking Layer 5's own predicate, with the tenant's own config
            # snapshot, is what makes `interrupt_band` and `interrupt_min_confidence_bp` one
            # dial rather than two: a tenant who says "too noisy" turns it down once, and both
            # their commitments and their cards go quiet together.
            interrupt = may_interrupt(r.urgency_band, card_confidence_bp(r.score_block),
                                      communication_config(r.effective_config))
            res = c.execute(text(
                "insert into delivery_outbox (id,org_id,card_id,channel,payload,signal_id,"
                "reasoning_run_id,reasoning_decision_hash,authority_pack_revision,"
                "authority_expires_at,recipient,band,channel_class,interrupt) "
                "values (:i,:o,:c,:ch,cast(:payload as jsonb),"
                ":signal,:run,:decision,:revision,:expires,:seat,:band,:cclass,:interrupt) "
                "on conflict (org_id, card_id, channel) do nothing"),
                {"i": new_id("ob"), "o": org_id, "c": r.card_id, "ch": channel,
                 "payload": json.dumps(payload), "signal": r.signal_id,
                 "run": r.reasoning_run_id, "decision": r.reasoning_decision_hash,
                 "revision": r.authority_pack_revision, "expires": r.authority_expires_at,
                 # An unrouted card has no seat, so it is an org surface and the tenant's own
                 # quiet hours govern it — exactly what the '*' preference row is for.
                 "seat": r.assignee, "band": r.urgency_band, "cclass": channel_class,
                 "interrupt": interrupt})
            queued += res.rowcount
    return queued


def enqueue_failover(engine, org_id: str, *, failed_channel: str, channel: str,
                     base_url: str = "") -> int:
    """Move an authoritative card to the next configured destination after terminal failure.

    A separate row preserves the failed attempt and its cause. Only ``failed_terminal`` opens
    this path; a policy suppression, quiet-hours deferral or authority cancellation must never
    be routed around on another channel.
    """
    if failed_channel == channel:
        return 0
    queued = 0
    now = datetime.now(timezone.utc)
    channel_class = channel_class_for(channel).value
    with engine.begin() as c:
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        rows = c.execute(text(
            "select k.card_id,k.signal_id,k.headline,k.situation,k.urgency_band,"
            "k.assignee,k.score_block,authority_cfg.effective as effective_config," +
            AUTHORITATIVE_SCORE_SQL + " as score,s.reasoning_run_id,"
            "s.reasoning_decision_hash,s.authority_pack_revision,s.authority_expires_at "
            "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id " +
            AUTHORITATIVE_SIGNAL_JOINS +
            "where k.org_id=:o and k.state in ('queued','surfaced') "
            "and s.status='open' and k.expires_at>:authority_time and " +
            AUTHORITATIVE_SIGNAL_PREDICATE + " "
            "and k.urgency_band in ('high','critical') "
            "and exists (select 1 from delivery_outbox failed where failed.org_id=k.org_id "
            "and failed.card_id=k.card_id and failed.channel=:failed "
            "and failed.status='failed_terminal') "
            "and not exists (select 1 from delivery_outbox next where next.org_id=k.org_id "
            "and next.card_id=k.card_id and next.channel=:ch) "
            "for share of k,s,rr,ro,selected_rc,rcap,authority_ctx,authority_cfg,authority_pack"),
            {"o": org_id, "failed": failed_channel, "ch": channel,
             "authority_time": now}).fetchall()
        for row in rows:
            payload = format_card_for_channel(channel, dict(row._mapping), base_url=base_url)
            interrupt = may_interrupt(row.urgency_band, card_confidence_bp(row.score_block),
                                      communication_config(row.effective_config))
            result = c.execute(text(
                "insert into delivery_outbox (id,org_id,card_id,channel,payload,signal_id,"
                "reasoning_run_id,reasoning_decision_hash,authority_pack_revision,"
                "authority_expires_at,recipient,band,channel_class,interrupt) "
                "values (:i,:o,:card,:ch,cast(:payload as jsonb),:signal,:run,:decision,"
                ":revision,:expires,:seat,:band,:cclass,:interrupt) "
                "on conflict (org_id, card_id, channel) do nothing"),
                {"i": new_id("ob"), "o": org_id, "card": row.card_id, "ch": channel,
                 "payload": json.dumps(payload), "signal": row.signal_id,
                 "run": row.reasoning_run_id, "decision": row.reasoning_decision_hash,
                 "revision": row.authority_pack_revision, "expires": row.authority_expires_at,
                 "seat": row.assignee, "band": row.urgency_band,
                 "cclass": channel_class, "interrupt": interrupt})
            queued += result.rowcount
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
        # A digest is a batch somebody chose to read, not an interruption: it carries the DIGEST
        # class so the timing unit lets it through at any hour, and no recipient because the
        # whole team reads it. Policy still applies — a tenant on hold gets no digest either.
        res = c.execute(text(
            "insert into delivery_outbox (id, org_id, card_id, channel, payload, channel_class) "
            "values (:i, :o, :c, :ch, cast(:p as jsonb), :cclass) "
            "on conflict (org_id, card_id, channel) do nothing"),
            {"i": new_id("ob"), "o": org_id, "c": digest_card_id(today), "ch": channel,
             "p": json.dumps(payload), "cclass": ChannelClass.DIGEST.value})
        return res.rowcount


# ── drain ─────────────────────────────────────────────────────────────────────────
def drain(engine, *, eval_time: datetime | None = None, limit: int = 50) -> dict:
    """Deliver due rows. Claim with FOR UPDATE SKIP LOCKED (two instances never send
    the same message), send OUTSIDE row-lock scope per row, record the outcome, and
    write a card_events audit row for real cards."""
    now = eval_time or datetime.now(timezone.utc)
    out = {"delivered": 0, "retried": 0, "terminal": 0, "cancelled": 0,
           "deferred": 0, "suppressed": 0}

    with engine.begin() as c:
        due = c.execute(text(
            "select id,org_id,card_id,channel,payload,attempts,signal_id,reasoning_run_id,"
            "reasoning_decision_hash,authority_pack_revision,authority_expires_at,"
            "recipient,band,channel_class,interrupt,defer_count "
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

    # One resolver for the whole pass: a tenant's quiet hours are read once, and — the part that
    # matters — the burst counter carries this pass's own sends forward. Ten intrusive messages
    # coming due together against a limit of three must send three and hold seven; a per-row
    # resolver would read "0 delivered this hour" ten times and let every one of them through.
    gate_conn = engine.connect()
    gate = PgDeliveryContext(gate_conn)
    try:
        _drain_claimed(engine, claimed, gate, now, out)
    finally:
        gate_conn.close()
    return out


def _drain_claimed(engine, claimed: list[dict], gate: PgDeliveryContext, now: datetime,
                   out: dict) -> None:
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

        # ── Layer 5.2 admission ──────────────────────────────────────────────────────
        # Before the authority check, which is the expensive one: it takes `for share` locks on
        # the graph and holds them across an outbound POST. Discovering that the recipient is
        # asleep is a local question, and asking it first means a held message costs one cheap
        # read instead of a lock-held round trip.
        candidate = candidate_from_row(r)
        try:
            decision, context = admit(candidate, gate, now=now)
        except Exception as exc:      # noqa: BLE001 — see below; never send un-judged
            # A gate that cannot read must not decide by accident. Sending anyway would page
            # somebody at 03:00 on the strength of a failed query; dropping the row would lose
            # a message because a lookup blipped. So it takes the existing bounded retry ladder:
            # the message survives, nothing goes out un-judged, and a gate that stays broken
            # ends as `failed_terminal` with the reason in the row rather than silently.
            # Caught per row so one tenant's bad state cannot stop the whole pass draining.
            delay = next_attempt_delay(r["attempts"] + 1)
            _finish(engine, r, now, ok=False, detail=f"delivery gate unavailable: {exc}"[:300],
                    terminal=delay is None, out=out, delay_minutes=delay)
            continue
        if decision.verdict is DeliveryVerdict.SUPPRESS:
            _suppress(engine, r, decision, context, out)
            continue
        if decision.verdict is DeliveryVerdict.DEFER:
            _defer(engine, r, decision, context, now, out)
            continue

        if is_executive_delivery(r["card_id"]):
            # A Layer 5 commitment message. Same law as a card — prove the subject is still live
            # *now*, not merely that it was when queued. A reminder can sit through a retry
            # backoff, and the customer can reply inside that window: sending it then is the
            # exact nudge the whole executive layer exists to never send.
            with engine.begin() as authority_conn:
                live = executive_delivery_is_live(authority_conn, r["org_id"], r["card_id"],
                                                  now=now)
                res = ch.send(payload, cfg) if live else None
            if res is None:
                _cancel(engine, r, "commitment closed before delivery", out)
                continue
        elif not str(r["card_id"]).startswith("digest:"):
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
                payload = _current_digest_payload(engine, r["org_id"], now, r["channel"])
            except Exception as exc:  # noqa: BLE001 - never send stale fallback bytes
                delay = next_attempt_delay(r["attempts"] + 1)
                _finish(engine, r, now, ok=False,
                        detail=f"current digest projection unavailable: {exc}"[:300],
                        terminal=delay is None, out=out, delay_minutes=delay)
                continue
            res = ch.send(payload, cfg)
        if res.ok:
            _finish(engine, r, now, ok=True, detail="", terminal=False, out=out,
                    decision=decision)
            # `_finish` commits before the next candidate resolves. The gate deliberately
            # re-reads the burst count in a fresh transaction, so this row is visible exactly
            # once to the next decision.
        else:
            delay = next_attempt_delay(r["attempts"] + 1)
            _finish(engine, r, now, ok=False, detail=res.detail,
                    terminal=delay is None, out=out, delay_minutes=delay)


def _defer(engine, row: dict, decision, context, now: datetime, out: dict) -> None:
    """Hold a message until its window opens — and spend nothing to do it.

    The single most important update statement in this layer. It moves the clock, counts the
    hold, and records why. It does **not** touch ``attempts``, and it does not write
    ``last_error``, because nothing failed. A quiet-hours hold that consumed a retry would spend
    the whole backoff ladder overnight and mark the message ``failed_terminal`` at 05:00 —
    turning the politeness feature into a delivery-loss bug.

    Staleness is deliberately not handled here either. A card that expires while held is caught
    by the authority re-validation the moment the window opens, which is the predicate that
    already owns expiry; a second age check here would be a second, weaker copy of it.
    """
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set next_attempt_at=:na, defer_count=defer_count+1, "
            "gate_unit=:u, gate_reason=:r where id=:i and status='queued'"),
            {"na": defer_until(decision, now), "u": decision.unit,
             "r": decision.reason_code, "i": row["id"]})
    out["deferred"] += 1


def _suppress(engine, row: dict, decision, context, out: dict) -> None:
    """Stop a message for good, and say who stopped it.

    Terminal, and distinct from both ``cancelled`` (the subject stopped being live) and
    ``failed_terminal`` (the transport gave up). Three different fixes, so three different
    statuses: an operator seeing ``suppressed`` should look at preferences, not at Slack's
    status page. The reason travels into ``last_error`` as well as ``gate_reason`` so the
    existing operator queries — which all read ``last_error`` — surface it without changing.
    """
    note = f"{decision.unit}:{decision.reason_code}"
    if context.config_error:
        note = f"{note} ({context.config_error})"
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set status='suppressed', gate_unit=:u, gate_reason=:r, "
            "last_error=:e where id=:i and status='queued'"),
            {"u": decision.unit, "r": decision.reason_code, "e": note[:300], "i": row["id"]})
    out["suppressed"] += 1


def _cancel(engine, row: dict, detail: str, out: dict) -> None:
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set status='cancelled',attempts=attempts+1,last_error=:e "
            "where id=:i and status='queued'"),
            {"i": row["id"], "e": detail[:300]})
    out["cancelled"] += 1


def _finish(engine, row: dict, now: datetime, *, ok: bool, detail: str, terminal: bool,
            out: dict, delay_minutes: int | None = None, decision=None) -> None:
    with engine.begin() as c:
        if ok:
            # The verdict that let this through is written on success too, not only on a hold.
            # Without it a row that was deferred overnight keeps the *stale* `quiet_hours`
            # reason after it finally sends, and — worse — a message that woke somebody at 02:00
            # cannot say why. `override_band_critical` in the row is the whole answer to "who
            # authorised this at 2am?", which is a question that does get asked.
            c.execute(text(
                "update delivery_outbox set status='delivered', delivered_at=:t, "
                "attempts=attempts+1, last_error=null, gate_unit=:u, gate_reason=:r "
                "where id=:i"),
                {"t": now, "i": row["id"],
                 "u": decision.unit if decision else None,
                 "r": decision.reason_code if decision else None})
            out["delivered"] += 1
            if is_executive_delivery(row["card_id"]):
                mark_executive_delivered(c, row["org_id"], row["card_id"], at=now,
                                         channel=row["channel"])
            if not str(row["card_id"]).startswith("digest:") \
                    and not is_executive_delivery(row["card_id"]):
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
    totals = {"orgs": 0, "queued": 0, "failovers": 0, "digests": 0,
              "reminders": 0, "linked": 0}
    with engine.connect() as c:
        channel_rows = c.execute(text(
            "select org_id, channel, config from org_channels where active "
            "order by org_id, channel")).mappings().all()
    grouped: dict[str, list] = {}
    for row in channel_rows:
        grouped.setdefault(str(row["org_id"]), []).append(destination_from_row(row))
    for org, destinations in grouped.items():
        totals["orgs"] += 1
        try:
            push_routes = route_destinations(destinations, purpose="push")
            if push_routes:
                totals["queued"] += enqueue_pending(
                    engine, org, channel=push_routes[0].channel, base_url=base_url)
                for previous, fallback in zip(push_routes, push_routes[1:]):
                    totals["failovers"] += enqueue_failover(
                        engine, org, failed_channel=previous.channel,
                        channel=fallback.channel, base_url=base_url)
            digest_routes = route_destinations(destinations, purpose="digest")
            if digest_routes:
                totals["digests"] += enqueue_digest(
                    engine, org, channel=digest_routes[0].channel, eval_time=now)
            # Layer 5 decided somebody needed nudging and wrote it down; this is where it
            # actually leaves the building. Linking runs first so a reminder can name the card
            # it belongs to.
            totals["linked"] += link_commitment_cards(engine, org)
            for destination in destinations:
                totals["reminders"] += enqueue_executive_messages(
                    engine, org, channel=destination.channel, base_url=base_url)
        except Exception:      # noqa: BLE001 — one org's enqueue never blocks the rest
            pass
    totals.update(drain(engine, eval_time=now))
    return totals
