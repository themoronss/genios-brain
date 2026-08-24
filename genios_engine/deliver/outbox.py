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
from genios_engine.platform.logging import get_logger
from genios_engine.deliver.channels import get_channel
from genios_engine.deliver.channels.slack import format_card_message, format_digest_message
from genios_engine.deliver.executive_bridge import (
    enqueue_executive_messages,
    executive_delivery_is_live,
    is_executive_delivery,
    link_commitment_cards,
)
from genios_engine.deliver.gate import (
    PgDeliveryContext,
    admit,
    candidate_from_row,
    channel_class_for,
    defer_until,
)
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

_log = get_logger("genios.deliver.outbox")


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
                    base_url: str = "") -> dict:
    """Queue un-notified HIGH/CRITICAL cards for this org's channel. Idempotent: the
    unique index makes a re-run a no-op. Payload is built from card columns that
    already passed the render validators — the channel adds no words.

    The delivery object is stamped here rather than at send time so a retry three hours later
    judges the *same* delivery it queued, and so the drain needs no extra joins to know whose
    attention a row is about to spend.

    Returns ``{"queued": n, "band_starved": n, "unrouted": n}``. The last two used to be silence.
    Every live card sits at ``urgency_band='standard'`` (scores 42-60 against thresholds of
    70/85), so the band filter below excludes ALL of them and this function returned 0 — which is
    indistinguishable from "there was nothing to send". A tenant where no card has ever cleared
    the push band is a broken scoring pipeline, not a quiet week, and the two have to be
    tellable apart from the sweep's own output."""
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
            payload = format_card_message(dict(r._mapping), base_url=base_url)
            # A card is pushed to chat *because* it cleared the push band, so this path never
            # builds a CommunicationPlan — but it still has to say whether the card may break
            # through quiet hours. Asking Layer 5's own predicate, with the tenant's own config
            # snapshot, is what makes `interrupt_band` and `interrupt_min_confidence_bp` one
            # dial rather than two: a tenant who says "too noisy" turns it down once, and both
            # their commitments and their cards go quiet together.
            interrupt = may_interrupt(r.urgency_band, card_confidence_bp(r.score_block),
                                      communication_config(r.effective_config))
            row_id = new_id("ob")
            res = c.execute(text(
                "insert into delivery_outbox (id,org_id,card_id,channel,payload,signal_id,"
                "reasoning_run_id,reasoning_decision_hash,authority_pack_revision,"
                "authority_expires_at,recipient,band,channel_class,interrupt,delivery_id) "
                "values (:i,:o,:c,:ch,cast(:payload as jsonb),"
                ":signal,:run,:decision,:revision,:expires,:seat,:band,:cclass,:interrupt,:i) "
                # matches delivery_outbox_once exactly — recipient joined the key so one card
            # can fan out to several agents without the second row silently deduping away
            "on conflict (org_id, card_id, channel, coalesce(recipient, '')) do nothing"),
                {"i": row_id, "o": org_id, "c": r.card_id, "ch": channel,
                 "payload": json.dumps(payload), "signal": r.signal_id,
                 "run": r.reasoning_run_id, "decision": r.reasoning_decision_hash,
                 "revision": r.authority_pack_revision, "expires": r.authority_expires_at,
                 # An unrouted card has no seat, so it is an org surface and the tenant's own
                 # quiet hours govern it — exactly what the '*' preference row is for.
                 "seat": r.assignee, "band": r.urgency_band, "cclass": channel_class,
                 "interrupt": interrupt})
            queued += res.rowcount

        # What the band filter above threw away. The owning defect is upstream (L4's ranking
        # formula never executes, so `I` is 5000 on every card and nothing reaches 70), but a
        # layer that silently discards its entire input is how an upstream defect stays invisible
        # for months — every L6 metric had an empty denominator and read as "no problem".
        starved = c.execute(text(
            "select count(*) from cards k "
            "where k.org_id=:o and k.state in ('queued','surfaced') and k.expires_at>:now "
            "and k.urgency_band not in ('high','critical')"),
            {"o": org_id, "now": now}).scalar() or 0
        # A card with no assignee has no authorized recipient, so audience and visibility rules
        # cannot even be evaluated for it. Counted rather than absorbed.
        unrouted = c.execute(text(
            "select count(*) from cards k "
            "where k.org_id=:o and k.state in ('queued','surfaced') and k.expires_at>:now "
            "and k.assignee is null"),
            {"o": org_id, "now": now}).scalar() or 0
    return {"queued": queued, "band_starved": int(starved), "unrouted": int(unrouted)}


def enqueue_agent_push(engine, org_id: str, card_id: str) -> int:
    """Queue one agent-class delivery per active webhook agent — the outbox replaces the inline
    POST `deliver/push.py` used to fire from inside the card build.

    That inline call was the exact anti-pattern this module's own docstring names as its reason
    to exist: a slow client endpoint degraded the card build for the whole org, and the send
    appeared in no outbox, no retry schedule, no dead letter and no analytics. As a row it gets
    the same lifecycle a human delivery has, and the drain's authority recheck replaces push.py's
    hand-rolled pre-send projection comparison.

    One row PER AGENT (recipient = agent_id) — which is why migration 0068 put recipient into
    the outbox dedup key. AGENT channel class: never intrusive, so the timing unit passes it at
    any hour; policy still applies, so a tenant on hold pushes nothing to its agents either.
    Payload carries only the card reference — the projection is built at SEND time by the drain,
    so a card revoked between enqueue and send is never serialized to an external machine.
    """
    queued = 0
    with engine.begin() as c:
        agents = c.execute(text(
            "select agent_id from agent_registry "
            "where org_id=:o and status='active' and webhook_url is not null"),
            {"o": org_id}).fetchall()
        if not agents:
            return 0
        card = c.execute(text(
            "select signal_id from cards where card_id=:c and org_id=:o"),
            {"c": card_id, "o": org_id}).first()
        for a in agents:
            row_id = new_id("ob")
            res = c.execute(text(
                "insert into delivery_outbox (id, org_id, card_id, channel, payload, "
                "signal_id, recipient, channel_class, interrupt, delivery_id) "
                "values (:i, :o, :c, 'agent_push', cast(:p as jsonb), :sig, :agent, "
                ":cclass, false, :i) "
                "on conflict (org_id, card_id, channel, coalesce(recipient, '')) do nothing"),
                {"i": row_id, "o": org_id, "c": card_id,
                 "p": json.dumps({"kind": "agent_card_push", "card_id": card_id}),
                 "sig": card.signal_id if card else None, "agent": a.agent_id,
                 "cclass": ChannelClass.AGENT.value})
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
        # A digest is a batch somebody chose to read, not an interruption: it carries the DIGEST
        # class so the timing unit lets it through at any hour, and no recipient because the
        # whole team reads it. Policy still applies — a tenant on hold gets no digest either.
        row_id = new_id("ob")
        # `delivery_id` was written by exactly ONE function in the whole codebase —
        # `deliver/spine.py::materialize`, which has no production caller — so
        # `feedback/delivery_facts.py`'s `where delivery_id is not null` predicate excluded
        # every row either live enqueue path (this one and the one above) has ever written. A
        # fully working legacy delivery path still fed L7 zero DeliveryFacts, forever. The row's
        # own id already IS a unique logical-delivery identity for this path, so it doubles as
        # `delivery_id` rather than inventing a second one.
        res = c.execute(text(
            "insert into delivery_outbox "
            "(id, org_id, card_id, channel, payload, channel_class, delivery_id) "
            "values (:i, :o, :c, :ch, cast(:p as jsonb), :cclass, :i) "
            # matches delivery_outbox_once exactly — recipient joined the key so one card
            # can fan out to several agents without the second row silently deduping away
            "on conflict (org_id, card_id, channel, coalesce(recipient, '')) do nothing"),
            {"i": row_id, "o": org_id, "c": digest_card_id(today), "ch": channel,
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
            "recipient,band,channel_class,interrupt,defer_count,delivery_id "
            "from delivery_outbox "
            # `dedupe_key` is set by exactly one writer — `spine.materialize` — and this legacy
            # drain and `spine.claim_due` were not mechanically disjoint: neither excluded rows
            # the OTHER path could also claim. Risk was zero only because the v2 path has never
            # written a row yet; the moment it does, both workers could select the same one and
            # double-send. `dedupe_key is null` is true of every row this drain's own two writers
            # produce and false of everything `materialize` produces, so it costs no new column.
            "where status='queued' and next_attempt_at <= :now and dedupe_key is null "
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
        if r["channel_class"] == ChannelClass.AGENT.value:
            # An agent delivery's "config" is its agent_registry row, keyed by recipient —
            # org_channels describes human surfaces a tenant configures, and an agent is neither.
            with engine.connect() as agent_conn:
                agent_row = agent_conn.execute(text(
                    "select agent_id, webhook_url, webhook_secret from agent_registry "
                    "where org_id=:o and agent_id=:a and status='active'"),
                    {"o": r["org_id"], "a": r["recipient"]}).mappings().first()
            cfg = dict(agent_row) if agent_row else None
        else:
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
        elif r["channel_class"] == ChannelClass.AGENT.value:
            # The row carries only the card reference; the projection is built NOW, under the
            # same authority the human path proves, so a card revoked between enqueue and send
            # is cancelled instead of serialized to an external machine. Replaces push.py's
            # hand-rolled pre-send projection comparison with the drain's own recheck.
            from genios_engine.deliver.push import _card_projection
            with engine.begin() as authority_conn:
                proj = _card_projection(authority_conn, r["org_id"], r["card_id"])
                res = (ch.send({"type": "signal.created", "org_id": r["org_id"],
                                "signal": proj}, cfg)
                       if proj is not None else None)
            if res is None:
                _cancel(engine, r, "card no longer authoritative", out)
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
                payload = _current_digest_payload(engine, r["org_id"], now)
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


def _mark_lifecycle(c, row: dict, lifecycle: str, kind: str, now: datetime,
                    detail: dict | None = None) -> None:
    """The one canonical lifecycle writer for the legacy drain — column + event row together.

    Every terminal writer here used to update `status` alone: `lifecycle` stayed 'queued' on a
    row whose Slack message had already been delivered or terminally failed, so an operator
    asking "what failed?" through the delivery APIs (which read `lifecycle`, the public
    vocabulary) got an empty answer while transport calls were demonstrably happening, and
    analytics reported `by_status: {queued: N}` for delivered rows. Same job
    `spine.log_delivery_event` does for the v2 claimer — one vocabulary, whichever path sent.

    Called inside the writer's own transaction so the column and the event row cannot disagree.
    The event needs a `delivery_id`; rows enqueued before L6-05 stamped one get the column
    update only, which still fixes what the APIs read.
    """
    c.execute(text("update delivery_outbox set lifecycle=:l where id=:i"),
              {"l": lifecycle, "i": row["id"]})
    if row.get("delivery_id"):
        from genios_engine.deliver.spine import log_delivery_event
        log_delivery_event(c, org_id=row["org_id"], delivery_id=row["delivery_id"],
                           kind=kind, at=now, actor="legacy_drain", detail=detail)


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
        _mark_lifecycle(c, row, "deferred", "deferred", now,
                        {"reason": decision.reason_code})
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
        _mark_lifecycle(c, row, "suppressed", "suppressed",
                        datetime.now(timezone.utc), {"reason": decision.reason_code})
    out["suppressed"] += 1


def _cancel(engine, row: dict, detail: str, out: dict) -> None:
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set status='cancelled',attempts=attempts+1,last_error=:e "
            "where id=:i and status='queued'"),
            {"i": row["id"], "e": detail[:300]})
        _mark_lifecycle(c, row, "cancelled", "cancelled",
                        datetime.now(timezone.utc), {"detail": detail[:120]})
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
            _mark_lifecycle(c, row, "delivered", "delivered", now)
            out["delivered"] += 1
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
            # `failed`, not `failed_terminal`: lifecycle is the PUBLIC vocabulary (the enum the
            # APIs and analytics read), and it names one failure terminal. The transport-status
            # column keeps its own word; the two columns answer different questions.
            _mark_lifecycle(c, row, "failed", "failed", now, {"error": detail[:120]})
            out["terminal"] += 1
        else:
            c.execute(text(
                "update delivery_outbox set attempts=attempts+1, last_error=:e, "
                "next_attempt_at=:na where id=:i"),
                {"e": detail[:300], "na": now + timedelta(minutes=delay_minutes or 5),
                 "i": row["id"]})
            out["retried"] += 1


def shadow_resolve_v2(engine, org_id: str, *, now: datetime) -> dict:
    """Run the v2 control plane's RESOLUTION over this org's live cards — measure, send nothing.

    Ten of the layer's 28 modules (orchestrator, audience, presence, routing, scheduler, spine…)
    had zero production reach: ~700 lines of Atlas-shaped machinery proven by tests and exercised
    by nothing. A cutover decided from that state is a leap; this pass is the measurement that
    makes it a step. `orchestrator.resolve` is PURE — no row is written, no channel touched — so
    the ten modules execute against real cards, real seats and real channel config, and the sweep
    reports how the v2 path WOULD have routed: per-channel counts and per-reason unroutables,
    directly comparable with what the legacy enqueue actually did in the same tick.

    Per-org failures isolate into a count: a shadow must never be able to break the live sweep
    it is shadowing.
    """
    from genios_engine.contracts.execution import AudienceClass
    from genios_engine.deliver.orchestrator import Unroutable, resolve
    from genios_engine.executive.assignment import PgSeatDirectory

    counts: dict = {"resolved": 0, "by_channel": {}, "unroutable": {}, "errors": 0}
    with engine.connect() as c:
        channels = [r[0] for r in c.execute(text(
            "select channel from org_channels where org_id=:o and active"), {"o": org_id})]
        cards = c.execute(text(
            "select card_id, signal_id, assignee, urgency_band from cards "
            "where org_id=:o and state in ('queued','surfaced') and expires_at > :now"),
            {"o": org_id, "now": now}).fetchall()
        directory = PgSeatDirectory(conn=c, org_id=org_id)
        for card in cards:
            try:
                obj = resolve(
                    org_id=org_id, delivery_id=f"shadow:{card.card_id}",
                    execution_id=f"shadow:{card.signal_id}", execution_hash="shadow",
                    band=card.urgency_band or "standard", interrupt=False,
                    audience=(AudienceClass.OWNER if card.assignee
                              else AudienceClass.ADMIN_QUEUE),
                    recipient=card.assignee, dedupe_key=f"shadow:{card.card_id}",
                    directory=directory, available_channels=channels,
                    # Org-scope default until card rows carry the evidence ACL — matches what
                    # the legacy path enforces today, so the comparison stays apples-to-apples.
                    can_view=lambda _seat: True,
                    now=now)
                counts["resolved"] += 1
                counts["by_channel"][obj.channel] = counts["by_channel"].get(obj.channel, 0) + 1
            except Unroutable as u:
                counts["unroutable"][u.reason_code] = counts["unroutable"].get(u.reason_code, 0) + 1
            except Exception:      # noqa: BLE001 — a shadow never breaks the sweep it shadows
                counts["errors"] += 1
    return counts


# ── the sweep entrypoint ──────────────────────────────────────────────────────────
def run_distribution(engine, *, base_url: str = "",
                     eval_time: datetime | None = None) -> dict:
    """One distribution pass: for every org with an active channel, enqueue new
    high/critical cards + the daily digest, then drain everything due. Called from the
    maintenance sweep; per-org failures isolate."""
    now = eval_time or datetime.now(timezone.utc)
    totals = {"orgs": 0, "queued": 0, "digests": 0, "reminders": 0, "linked": 0,
              # Named conditions, not silence. `band_starved` on every org means the scoring
              # pipeline is broken upstream; `unrouted` means cards exist with nobody to send
              # them to. Both previously presented as a clean zero.
              "band_starved": 0, "unrouted": 0, "org_failures": 0,
              # The v2 control plane's shadow resolution: how the unwired path WOULD have routed
              # the same cards this tick. The measurement a cutover decision needs.
              "v2_shadow_resolved": 0, "v2_shadow_unroutable": 0}
    with engine.connect() as c:
        # NOT `org_channels` alone. That equated "this tenant has delivery" with "this tenant has
        # configured a channel row", and with the table empty the sweep enumerated nothing and
        # returned success — zero deliveries, no error, for every tenant, forever. An org with
        # live cards has delivery work by definition; the pull surface is a floor it always has,
        # not an integration it opts into.
        orgs = [r[0] for r in c.execute(text(
            "select org_id from org_channels where active "
            "union "
            "select distinct org_id from cards "
            "where state in ('queued','surfaced') and expires_at > :now"),
            {"now": now})]
    for org in orgs:
        totals["orgs"] += 1
        try:
            pending = enqueue_pending(engine, org, base_url=base_url)
            totals["queued"] += pending["queued"]
            totals["band_starved"] += pending["band_starved"]
            totals["unrouted"] += pending["unrouted"]
            totals["digests"] += enqueue_digest(engine, org, eval_time=now)
            # Layer 5 decided somebody needed nudging and wrote it down; this is where it
            # actually leaves the building. Linking runs first so a reminder can name the card
            # it belongs to.
            totals["linked"] += link_commitment_cards(engine, org)
            totals["reminders"] += enqueue_executive_messages(engine, org, base_url=base_url)
            shadow = shadow_resolve_v2(engine, org, now=now)
            totals["v2_shadow_resolved"] += shadow["resolved"]
            totals["v2_shadow_unroutable"] += sum(shadow["unroutable"].values())
            totals.setdefault("v2_shadow_detail", {})[org] = shadow
        except Exception:      # noqa: BLE001 — one org's enqueue never blocks the rest
            # Isolate, but never silently: a bare `pass` here makes the most likely activation
            # failure (one tenant's malformed channel config) indistinguishable from "nothing
            # to send". Compare api/routes.py, which isolates the same way and does log.
            totals["org_failures"] += 1
            _log.exception("distribution enqueue failed org=%s", org)
    totals.update(drain(engine, eval_time=now))
    return totals
