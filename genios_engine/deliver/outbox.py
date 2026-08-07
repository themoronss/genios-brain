"""Layer 5.2's durable distribution worker.

The active path materialises one logical row from a persisted ``ExecutionObject`` and keeps
provider calls out of the reasoning sweep. A due row is claimed with a fenced lease; physical
attempts and engagement transitions are append-only evidence. One deterministic route ladder
lives on the row, so failover changes the route cursor rather than creating a second impression.

Admission sits between claim and send and produces three outcomes:

  SEND      → the existing path, unchanged.
  DEFER     → move `next_attempt_at`, bump `defer_count`, touch NOTHING else. A hold is
              not a failure, and if it spent an `attempts` slot a message queued at 22:00
              would be `failed_terminal` by breakfast — the exact one somebody wanted.
  SUPPRESS  → status `suppressed`, distinct from `cancelled`. Cancelled means the subject
              stopped being live; suppressed means this person, or this tenant, said no.
              Collapsing them makes "why did nothing arrive?" unanswerable from the row."""
from __future__ import annotations

import json
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import text

from genios_engine.contracts.delivery import DeliveryDecision, DeliveryVerdict
from genios_engine.contracts.execution import ChannelClass
from genios_engine.deliver.channels import get_channel
from genios_engine.deliver.channels.base import ChannelResult
from genios_engine.deliver.channels.slack import format_card_message, format_digest_message
from genios_engine.deliver.executive_bridge import (
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
from genios_engine.deliver.destination import destination_from_row
from genios_engine.deliver.rate_limit import (
    next_available,
    next_window,
    release as release_attention,
    reserve as reserve_attention,
)
from genios_engine.deliver.tracker import DeliveryState, append_event, expire_due
from genios_engine.executive.communication import may_interrupt
from genios_engine.executive.execution import execution_config
from genios_engine.platform.ids import new_id
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt
from genios_engine.reason.authority import (
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
)

# retry schedule (minutes after the Nth failure); after the last slot → failed_terminal.
BACKOFF_MINUTES: tuple[int, ...] = (5, 30, 120, 720)
MAX_RETRY_AFTER_MINUTES = BACKOFF_MINUTES[-1]
MAX_GENERATION_ATTEMPTS = len(BACKOFF_MINUTES) + 1
_NON_IDEMPOTENT_HUMAN_CHANNELS = frozenset({"slack", "teams"})
_log = logging.getLogger(__name__)
CLAIM_MINUTES = 5
_STALE_CLAIM = object()
_RATE_LIMITED = object()
_DESTINATION_CHANGED = object()


@dataclass(frozen=True, slots=True)
class _AttentionReservation:
    hourly: bool = False
    daily: bool = False
    hourly_start: datetime | None = None
    daily_start: datetime | None = None
    daily_seconds: int = 86_400


def _ambiguous_requires_manual(channel: str, result) -> bool:
    """Whether retrying uncertain transport could duplicate a human interruption."""
    return (channel in _NON_IDEMPOTENT_HUMAN_CHANNELS
            and bool(getattr(result, "unknown", False)))


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


def retry_delay(attempts: int, retry_after_seconds: int | None = None) -> int | None:
    """Combine bounded local backoff with a provider's bounded minimum wait.

    A provider may ask us to wait longer than the local rung, but it may neither shorten the
    rung nor park one retry slot forever. An exhausted local schedule always remains terminal.
    """
    delay = next_attempt_delay(attempts)
    if delay is None or retry_after_seconds is None:
        return delay
    provider = max(1, (max(0, int(retry_after_seconds)) + 59) // 60)
    return min(MAX_RETRY_AFTER_MINUTES, max(delay, provider))


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
    """Deliver due rows under fenced, expiring claims.

    A database claim prevents two live workers from sending concurrently. Provider transport is
    still at-least-once when an acknowledgement is ambiguous; webhook adapters carry the stable
    idempotency key so capable receivers can close that final external gap.
    """
    now = eval_time or datetime.now(timezone.utc)
    out = {"delivered": 0, "retried": 0, "terminal": 0, "cancelled": 0,
           "deferred": 0, "suppressed": 0}

    with engine.begin() as c:
        due = c.execute(text(
            "with ranked as (select id, row_number() over (partition by org_id order by "
            "least(5, priority_rank + greatest(0,floor(extract(epoch from "
            "(:now-created_at))/14400))) desc, "
            "next_attempt_at, created_at, id) as org_position "
            "from delivery_outbox where lifecycle_status in ('queued','deferred') "
            "and not exists (select 1 from feature_flags global_pause where "
            "global_pause.key='kill_switch_all' and not global_pause.enabled) "
            "and not exists (select 1 from feature_flags paused where "
            "paused.key='kill_switch:' || delivery_outbox.org_id and not paused.enabled) and ("
            "(status='queued' and next_attempt_at<=:now) or "
            "(status='in_flight' and claimed_until<=:now))) "
            "select d.id,d.org_id,d.card_id,d.channel,d.payload,d.attempts,d.signal_id,"
            "d.reasoning_run_id,d.reasoning_decision_hash,d.authority_pack_revision,"
            "d.authority_expires_at,d.recipient,d.band,d.channel_class,d.interrupt,"
            "d.defer_count,d.execution_id,d.execution_event_id,d.delivery_kind,d.audience,"
            "d.format_kind,d.route_reason,d.priority_class,d.priority_rank,"
            "d.source_payload,d.route_plan,d.route_index,d.retry_generation,d.execution_hash,"
            "d.generation_attempts,d.destination_fingerprint,d.control_failures,"
            "d.daily_budget,d.status,d.claim_token,d.legacy_reconciliation_required,"
            "d.manual_replay_approved_at "
            "from delivery_outbox d join ranked r on r.id=d.id "
            "order by r.org_position, "
            "least(5, d.priority_rank + greatest(0,floor(extract(epoch from "
            "(:now-d.created_at))/14400))) "
            "desc, d.next_attempt_at, d.created_at, d.id "
            "limit :l for update of d skip locked"),
            {"now": now, "l": max(1, min(int(limit), 200))}).fetchall()
        claimed: list[dict] = []
        # The token fences every completion write. Reclaiming an expired lease records the prior
        # provider call as ambiguous before a successor is allowed to start.
        for due_row in due:
            r = dict(due_row._mapping)
            if (r.get("delivery_kind") == "legacy_card"
                    and r.get("status") == "queued"
                    and bool(r.get("legacy_reconciliation_required"))):
                # Migration 0046 marks every pending pre-v2 row, including attempts=0: an old
                # process may have POSTed and crashed before persisting that counter. Nothing is
                # adopted until an owner explicitly acknowledges the duplicate-delivery risk.
                append_event(
                    c, org_id=r["org_id"], delivery_id=r["id"],
                    target=DeliveryState.FAILED,
                    reason_code="legacy_attempt_evidence_missing", actor_id="delivery",
                    idempotency_key="migration:legacy-delivery-manual-reconcile",
                    occurred_at=now,
                    metadata={"attempts": int(r.get("attempts") or 0),
                              "manual_reconciliation_required": True})
                c.execute(text(
                    "update delivery_outbox set status='failed_terminal',"
                    "last_error='pre-control-plane delivery may have reached its provider; "
                    "manual reconciliation and replay acknowledgement required',updated_at=:now "
                    "where id=:i and status='queued'"),
                    {"now": now, "i": r["id"]})
                out["terminal"] += 1
                continue
            if r.get("status") == "in_flight":
                started = c.execute(text(
                    "update delivery_attempts set outcome='unknown',retryable=true,"
                    "error_class='claim_expired',completed_at=:now "
                    "where delivery_id=:i and claim_token=:token and outcome='started' "
                    "returning attempt_id"),
                    {"now": now, "i": r["id"], "token": r.get("claim_token")}).first()
                if started is None:
                    # A lease can expire while this row is waiting behind earlier provider calls,
                    # or immediately after claim on worker crash. With no physical attempt for
                    # this token there is no ambiguity and no retry rung to spend. Requeue under
                    # the same row lock; a late original worker is fenced by its cleared token.
                    c.execute(text(
                        "update delivery_outbox set status='queued',next_attempt_at=:now,"
                        "claim_token=null,claimed_at=null,claimed_until=null,updated_at=:now "
                        "where id=:i and status='in_flight' and claim_token=:token"),
                        {"now": now, "i": r["id"], "token": r.get("claim_token")})
                    out["recovered_claims"] = out.get("recovered_claims", 0) + 1
                    continue
                attempt_identity = str(
                    started.attempt_id if hasattr(started, "attempt_id") else started[0])
                if r.get("channel") in _NON_IDEMPOTENT_HUMAN_CHANNELS:
                    # Incoming chat webhooks do not accept our idempotency key. After a worker
                    # loses the acknowledgement, retrying could wake the same human twice; stop
                    # for manual reconciliation instead of treating uncertainty as permission.
                    append_event(
                        c, org_id=r["org_id"], delivery_id=r["id"],
                        target=DeliveryState.FAILED,
                        reason_code="ambiguous_chat_transport", actor_id="delivery",
                        idempotency_key=f"attempt:{attempt_identity}:claim-expiry-ambiguous",
                        occurred_at=now,
                        metadata={"manual_reconciliation_required": True})
                    c.execute(text(
                        "update delivery_outbox set status='failed_terminal',"
                        "last_error='chat provider acknowledgement was lost; automatic retry "
                        "refused to prevent a duplicate human interruption',claim_token=null,"
                        "claimed_at=null,claimed_until=null,updated_at=:now "
                        "where id=:i and status='in_flight'"),
                        {"now": now, "i": r["id"]})
                    out["terminal"] += 1
                    continue
                if int(r.get("generation_attempts") or 0) >= MAX_GENERATION_ATTEMPTS:
                    append_event(
                        c, org_id=r["org_id"], delivery_id=r["id"],
                        target=DeliveryState.FAILED,
                        reason_code="claim_expiry_retry_exhausted", actor_id="delivery",
                        idempotency_key=f"attempt:{attempt_identity}:claim-expiry-exhausted",
                        occurred_at=now,
                        metadata={"manual_reconciliation_required": True})
                    c.execute(text(
                        "update delivery_outbox set status='failed_terminal',"
                        "last_error='claim expired after bounded ambiguous attempts; manual "
                        "reconciliation required',claim_token=null,claimed_at=null,"
                        "claimed_until=null,updated_at=:now where id=:i and status='in_flight'"),
                        {"now": now, "i": r["id"]})
                    out["terminal"] += 1
                    continue
                crash_delay = retry_delay(int(r.get("generation_attempts") or 0)) or 5
                c.execute(text(
                    "update delivery_outbox set status='queued',next_attempt_at=:next,"
                    "last_error='prior provider attempt lost its worker acknowledgement; "
                    "retry remains ambiguous',claim_token=null,claimed_at=null,"
                    "claimed_until=null,updated_at=:now where id=:i and status='in_flight'"),
                    {"next": now + timedelta(minutes=crash_delay),
                     "now": now, "i": r["id"]})
                out["retried"] += 1
                continue
            token = new_id("dclaim")
            c.execute(text(
                "update delivery_outbox set status='in_flight',claim_token=:token,"
                "claimed_at=:now,claimed_until=:until,"
                "updated_at=:now where id=:i"),
                {"token": token, "now": now,
                 "until": now + timedelta(minutes=CLAIM_MINUTES), "i": r["id"]})
            r["claim_token"] = token
            r["status"] = "in_flight"
            claimed.append(r)

    # One resolver for the whole pass: a tenant's quiet hours are read once, and — the part that
    # matters — the burst counter carries this pass's own sends forward. Ten intrusive messages
    # coming due together against a limit of three must send three and hold seven; a per-row
    # resolver would read "0 delivered this hour" ten times and let every one of them through.
    gate_conn = engine.connect()
    gate = PgDeliveryContext(gate_conn)
    try:
        _drain_claimed(
            engine, claimed, gate, now, out,
            clock=(None if eval_time is not None else lambda: datetime.now(timezone.utc)))
    finally:
        gate_conn.close()
    return out


def _channel_config(conn, row: dict, *, lock: bool = False) -> dict | None:
    """Load the exact tenant/agent credential set used by one provider call.

    The lock variant is read inside the authority transaction held through transport. That makes
    credential rotation/revocation linearizable with sending instead of using a stale batch cache.
    """
    from genios_engine.deliver.channels.surface import SURFACE_CHANNELS
    if row["channel"] in SURFACE_CHANNELS:
        return {}
    suffix = " for share" if lock else ""
    if row["channel"] == "agent":
        result = conn.execute(text(
            "select webhook_url,webhook_secret,webhook_config_encrypted,agent_id "
            "from agent_registry where org_id=:o and agent_id=:agent "
            "and coalesce(status,'active')='active'" + suffix),
            {"o": row["org_id"], "agent": row.get("recipient")}).mappings().first()
        cfg = dict(result) if result else None
        encrypted = cfg.pop("webhook_config_encrypted", None) if cfg else None
        if encrypted:
            raw = bytes(encrypted) if not isinstance(encrypted, bytes) else encrypted
            decoded = json.loads(decrypt(raw, get_settings().crypto_key))
            if not isinstance(decoded, dict):
                raise ValueError("decrypted agent channel config is not an object")
            cfg.update(decoded)
        return cfg

    result = conn.execute(text(
        "select config,config_encrypted from org_channels "
        "where org_id=:o and channel=:ch and active" + suffix),
        {"o": row["org_id"], "ch": row["channel"]}).first()
    if result is None:
        return None
    encrypted = getattr(result, "config_encrypted", None)
    routing_raw = getattr(result, "config", None)
    routing = (routing_raw if isinstance(routing_raw, dict)
               else json.loads(routing_raw or "{}"))
    if not isinstance(routing, dict):
        raise ValueError("channel routing config is not an object")
    if encrypted:
        raw = bytes(encrypted) if not isinstance(encrypted, bytes) else encrypted
        cfg = json.loads(decrypt(raw, get_settings().crypto_key))
        if not isinstance(cfg, dict):
            raise ValueError("decrypted channel config is not an object")
        return {**cfg, **routing}
    return routing


def _tenant_delivery_live(conn, org_id: str) -> bool:
    global_row = conn.execute(text(
        "select enabled from feature_flags where key='kill_switch_all' for share")).first()
    if global_row is None:
        return False
    global_enabled = global_row.enabled if hasattr(global_row, "enabled") else global_row[0]
    if not bool(global_enabled):
        return False
    row = conn.execute(text(
        "select enabled from feature_flags where key='kill_switch:' || :o for share"),
        {"o": org_id}).first()
    if row is None:
        return True
    enabled = row.enabled if hasattr(row, "enabled") else row[0]
    return bool(enabled)


def _destination_fingerprint(row: dict, config: dict) -> str:
    """Non-secret identity for the exact endpoint/config bound to one retry generation."""
    transport = {
        key: value for key, value in config.items()
        if key not in {"priority", "push_enabled", "digest_enabled"}}
    encoded = json.dumps(
        {"channel": row["channel"], "recipient": row.get("recipient"),
         "transport": transport},
        sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _bind_destination(engine, row: dict, config: dict) -> str:
    """Bind current credentials before an attempt: ready | stale | ambiguous.

    A retry after unknown acknowledgement may only revisit the same endpoint. Rotating a webhook
    underneath that retry could deliver once to the old receiver and once to the new one, so a
    changed fingerprint with ambiguous evidence is cancelled for manual reconciliation.
    """
    if not row.get("claim_token"):  # compatibility for pre-control-plane focused/legacy rows
        return "ready"
    fingerprint = _destination_fingerprint(row, config)
    with engine.begin() as conn:
        current = conn.execute(text(
            "select destination_fingerprint,generation_attempts,retry_generation "
            "from delivery_outbox where id=:i and status='in_flight' "
            "and claim_token=:token for update"),
            {"i": row["id"], "token": row["claim_token"]}).first()
        if current is None:
            return "stale"
        prior = (current.destination_fingerprint
                 if hasattr(current, "destination_fingerprint") else current[0])
        generation_attempts = int(
            current.generation_attempts if hasattr(current, "generation_attempts") else current[1])
        generation = int(
            current.retry_generation if hasattr(current, "retry_generation") else current[2])
        if prior == fingerprint:
            row["destination_fingerprint"] = fingerprint
            return "ready"
        if generation_attempts > 0:
            unsafe = conn.execute(text(
                "select 1 from delivery_attempts where org_id=:o and delivery_id=:d "
                "and outcome in ('started','unknown','delivered') limit 1"),
                {"o": row["org_id"], "d": row["id"]}).first()
            if unsafe is not None:
                return "ambiguous"
        bump = prior is not None or generation_attempts > 0
        bound = conn.execute(text(
            "update delivery_outbox set destination_fingerprint=:fingerprint,"
            "retry_generation=retry_generation+:bump,generation_attempts=0,updated_at=now() "
            "where id=:i and status='in_flight' and claim_token=:token returning retry_generation"),
            {"fingerprint": fingerprint, "bump": int(bump), "i": row["id"],
             "token": row["claim_token"]}).first()
        if bound is None:
            return "stale"
        generation = int(bound.retry_generation
                         if hasattr(bound, "retry_generation") else bound[0])
    row["destination_fingerprint"] = fingerprint
    row["retry_generation"] = generation
    row["generation_attempts"] = 0
    return "ready"


def _drain_claimed(engine, claimed: list[dict], gate: PgDeliveryContext, now: datetime,
                   out: dict, *, clock: Callable[[], datetime] | None = None) -> None:
    for r in claimed:
        # Production batches can spend minutes in provider calls. Authority, attention windows
        # and expiry are therefore evaluated at this row's send boundary, not at batch claim
        # time. Tests and explicit historical evaluations keep their supplied fixed clock.
        row_now = clock() if clock is not None else now
        try:
            payload = (r["payload"] if isinstance(r["payload"], dict)
                       else json.loads(r["payload"]))
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
        except (TypeError, ValueError) as exc:
            _finish(engine, r, row_now, ok=False, detail=f"invalid delivery payload: {exc}",
                    terminal=True, out=out)
            continue
        ch = get_channel(r["channel"])
        if ch is None:
            detail = "channel adapter is not registered"
            if _advance_route(engine, r, now=row_now, detail=detail, out=out):
                continue
            _finish(engine, r, row_now, ok=False, detail=detail, terminal=True, out=out)
            continue

        # ── Layer 5.2 admission ──────────────────────────────────────────────────────
        # Before the authority check, which is the expensive one: it takes `for share` locks on
        # the graph and holds them across an outbound POST. Discovering that the recipient is
        # asleep is a local question, and asking it first means a held message costs one cheap
        # read instead of a lock-held round trip.
        try:
            candidate = candidate_from_row(r)
            decision, context = admit(candidate, gate, now=row_now)
        except Exception as exc:      # noqa: BLE001 — see below; never send un-judged
            # A gate that cannot read must not decide by accident. Sending anyway would page
            # somebody at 03:00 on the strength of a failed query; dropping the row would lose
            # a message because a lookup blipped. So it takes the existing bounded retry ladder:
            # the message survives, nothing goes out un-judged, and a gate that stays broken
            # ends as `failed_terminal` with the reason in the row rather than silently.
            # Caught per row so one tenant's bad state cannot stop the whole pass draining.
            if r.get("claim_token"):
                _control_failure(engine, r, row_now,
                                 detail=f"delivery gate unavailable: {exc}"[:300], out=out)
            else:  # compatibility for pre-0046 in-flight rows and focused legacy tests
                delay = next_attempt_delay(r["attempts"] + 1)
                _finish(engine, r, row_now, ok=False,
                        detail=f"delivery gate unavailable: {exc}"[:300],
                        terminal=delay is None, out=out, delay_minutes=delay)
            continue
        if decision.verdict is DeliveryVerdict.SUPPRESS:
            _suppress(engine, r, decision, context, out)
            continue
        if decision.verdict is DeliveryVerdict.DEFER:
            _defer(engine, r, decision, context, row_now, out)
            continue

        reservation = _AttentionReservation()
        rate_not_before = next_window(row_now)
        rate_reason = "atomic_attention_limit"
        if is_executive_delivery(r["card_id"]):
            # A Layer 5 commitment message. Same law as a card — prove the subject is still live
            # *now*, not merely that it was when queued. A reminder can sit through a retry
            # backoff, and the customer can reply inside that window: sending it then is the
            # exact nudge the whole executive layer exists to never send.
            changed_but_live = False
            tenant_live = True
            config_problem: str | None = None
            policy_recheck: tuple[DeliveryDecision, object] | None = None
            try:
                with engine.begin() as authority_conn:
                    legacy_execution = r.get("delivery_kind") == "legacy_card"
                    live = executive_delivery_is_live(
                        authority_conn, r["org_id"], r["card_id"], now=row_now,
                        expected_hash=(None if legacy_execution else r.get("execution_hash")),
                        expected_route=(None if legacy_execution else r))
                    if live:
                        decision, context = admit(
                            candidate, PgDeliveryContext(authority_conn, release_between=False),
                            now=row_now)
                        if decision.verdict is not DeliveryVerdict.SEND:
                            policy_recheck = (decision, context)
                            res = None
                        else:
                            current_cfg = _channel_config(authority_conn, r, lock=True)
                            if current_cfg is None:
                                config_problem = "channel revoked before delivery"
                                res = None
                            else:
                                binding = _bind_destination(engine, r, current_cfg)
                                if binding == "ambiguous":
                                    res = _DESTINATION_CHANGED
                                elif binding == "stale":
                                    res = _STALE_CLAIM
                                else:
                                    allowed, reservation, rate_not_before, rate_reason = \
                                        _reserve_for_send(
                                            engine, r, candidate, context, row_now)
                                    res = (_STALE_CLAIM if rate_reason == "stale_claim" else
                                           _send_once(engine, r, row_now, ch, payload, current_cfg)
                                           if allowed else _RATE_LIMITED)
                    else:
                        # Distinguish closure from a semantic update while this transaction and
                        # its row lock are still live.
                        tenant_live = _tenant_delivery_live(authority_conn, r["org_id"])
                        changed_but_live = bool(
                            not legacy_execution and tenant_live and r.get("execution_hash")
                            and executive_delivery_is_live(
                                authority_conn, r["org_id"], r["card_id"], now=row_now))
                        res = None
            except Exception as exc:  # noqa: BLE001 - isolate one final authority/send phase
                _final_phase_exception(
                    engine, r, candidate, reservation, row_now, exc=exc, out=out)
                continue
            if policy_recheck is not None:
                final_decision, final_context = policy_recheck
                if final_decision.verdict is DeliveryVerdict.SUPPRESS:
                    _suppress(engine, r, final_decision, final_context, out)
                else:
                    _defer(engine, r, final_decision, final_context, row_now, out)
                continue
            if config_problem is not None:
                if _advance_route(engine, r, now=row_now, detail=config_problem, out=out):
                    continue
                _finish(engine, r, row_now, ok=False, detail=config_problem,
                        terminal=True, out=out)
                continue
            if res is None:
                if not tenant_live:
                    _processing_retry(
                        engine, r, row_now,
                        detail="workspace delivery paused; awaiting resume", out=out)
                elif changed_but_live:
                    if _route_refresh_is_safe(engine, r):
                        _processing_retry(
                            engine, r, row_now,
                            detail="execution changed before delivery; awaiting route refresh",
                            out=out)
                    else:
                        _cancel(
                            engine, r,
                            "delivery authority changed after ambiguous transport evidence; "
                            "automatic reroute refused",
                            out)
                else:
                    _cancel(engine, r, "commitment closed before delivery", out)
                continue
        elif not str(r["card_id"]).startswith("digest:"):
            # Hold the same graph/pack/card authority locks through the outbound POST. This is a
            # deliberately short human notification call; safety wins over sending a revoked card.
            config_problem = None
            policy_recheck = None
            tenant_live = True
            try:
                with engine.begin() as authority_conn:
                    authority_conn.execute(text("select id from orgs where id=:o for share"),
                                           {"o": r["org_id"]})
                    tenant_live = _tenant_delivery_live(authority_conn, r["org_id"])
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
                         "run": r["reasoning_run_id"],
                         "decision": r["reasoning_decision_hash"],
                         "revision": r["authority_pack_revision"],
                         "authority_time": row_now}).first()
                    if not tenant_live or live is None:
                        res = None
                    else:
                        decision, context = admit(
                            candidate, PgDeliveryContext(authority_conn, release_between=False),
                            now=row_now)
                        if decision.verdict is not DeliveryVerdict.SEND:
                            policy_recheck = (decision, context)
                            res = None
                        else:
                            current_cfg = _channel_config(authority_conn, r, lock=True)
                            if current_cfg is None:
                                config_problem = "channel revoked before delivery"
                                res = None
                            else:
                                binding = _bind_destination(engine, r, current_cfg)
                                if binding == "ambiguous":
                                    res = _DESTINATION_CHANGED
                                elif binding == "stale":
                                    res = _STALE_CLAIM
                                else:
                                    allowed, reservation, rate_not_before, rate_reason = \
                                        _reserve_for_send(
                                            engine, r, candidate, context, row_now)
                                    res = (_STALE_CLAIM if rate_reason == "stale_claim" else
                                           _send_once(engine, r, row_now, ch, payload, current_cfg)
                                           if allowed else _RATE_LIMITED)
            except Exception as exc:  # noqa: BLE001 - isolate one final authority/send phase
                _final_phase_exception(
                    engine, r, candidate, reservation, row_now, exc=exc, out=out)
                continue
            if policy_recheck is not None:
                final_decision, final_context = policy_recheck
                if final_decision.verdict is DeliveryVerdict.SUPPRESS:
                    _suppress(engine, r, final_decision, final_context, out)
                else:
                    _defer(engine, r, final_decision, final_context, row_now, out)
                continue
            if config_problem is not None:
                if _advance_route(engine, r, now=row_now, detail=config_problem, out=out):
                    continue
                _finish(engine, r, row_now, ok=False, detail=config_problem,
                        terminal=True, out=out)
                continue
            if res is None:
                if not tenant_live:
                    _processing_retry(
                        engine, r, row_now,
                        detail="workspace delivery paused; awaiting resume", out=out)
                else:
                    _cancel(engine, r, "decision authority revoked before delivery", out)
                continue
        else:
            policy_recheck = None
            tenant_live = True
            try:
                payload = _current_digest_payload(engine, r["org_id"], row_now, r["channel"])
                with engine.begin() as authority_conn:
                    authority_conn.execute(text("select id from orgs where id=:o for share"),
                                           {"o": r["org_id"]})
                    tenant_live = _tenant_delivery_live(authority_conn, r["org_id"])
                    if not tenant_live:
                        res = None
                        current_cfg = None
                    else:
                        decision, context = admit(
                            candidate, PgDeliveryContext(authority_conn, release_between=False),
                            now=row_now)
                        if decision.verdict is not DeliveryVerdict.SEND:
                            policy_recheck = (decision, context)
                            res = None
                            current_cfg = None
                        else:
                            current_cfg = _channel_config(authority_conn, r, lock=True)
                    if tenant_live and policy_recheck is None and current_cfg is None:
                        raise ValueError("channel revoked before delivery")
                    if tenant_live and policy_recheck is None:
                        binding = _bind_destination(engine, r, current_cfg)
                        if binding == "ambiguous":
                            res = _DESTINATION_CHANGED
                        elif binding == "stale":
                            res = _STALE_CLAIM
                        else:
                            allowed, reservation, rate_not_before, rate_reason = _reserve_for_send(
                                engine, r, candidate, context, row_now)
                            res = (_STALE_CLAIM if rate_reason == "stale_claim" else
                                   _send_once(engine, r, row_now, ch, payload, current_cfg)
                                   if allowed else _RATE_LIMITED)
            except Exception as exc:  # noqa: BLE001 - never send stale fallback bytes
                _final_phase_exception(
                    engine, r, candidate, reservation, row_now, exc=exc, out=out,
                    prefix="current digest projection unavailable")
                continue
            if not tenant_live:
                _processing_retry(
                    engine, r, row_now,
                    detail="workspace delivery paused; awaiting resume", out=out)
                continue
            if policy_recheck is not None:
                final_decision, final_context = policy_recheck
                if final_decision.verdict is DeliveryVerdict.SUPPRESS:
                    _suppress(engine, r, final_decision, final_context, out)
                else:
                    _defer(engine, r, final_decision, final_context, row_now, out)
                continue
        if res is _DESTINATION_CHANGED:
            _cancel(
                engine, r,
                "provider destination changed after ambiguous transport evidence; "
                "automatic retry refused",
                out)
            continue
        if res is _RATE_LIMITED:
            rate_decision = DeliveryDecision.defer(
                "rate_limiter", rate_reason, rate_not_before)
            _defer(engine, r, rate_decision, context, row_now, out)
            continue
        if res is _STALE_CLAIM:
            _release_reservation(engine, r, candidate, reservation, row_now)
            out["stale_claims"] = out.get("stale_claims", 0) + 1
            continue
        if res.ok:
            _finish(engine, r, row_now, ok=True, detail="", terminal=False, out=out,
                    decision=decision)
            # `_finish` commits before the next candidate resolves. The gate deliberately
            # re-reads the burst count in a fresh transaction, so this row is visible exactly
            # once to the next decision.
        else:
            cycle_attempt = int(r.get("generation_attempts") or r.get("attempt_number")
                                or r["attempts"] + 1)
            delay = retry_delay(cycle_attempt, getattr(res, "retry_after_seconds", None))
            terminal = _ambiguous_requires_manual(r["channel"], res) or (
                            not bool(getattr(res, "retryable", True)) or delay is None)
            if not bool(getattr(res, "unknown", False)):
                _release_reservation(engine, r, candidate, reservation, row_now)
            # A definite terminal response can safely use the next route. An ambiguous timeout
            # never cross-channel-fails-over because the primary may already have accepted it.
            if terminal and not bool(getattr(res, "unknown", False)) \
                    and _advance_route(engine, r, now=row_now, detail=res.detail, out=out,
                                       result=res):
                continue
            _finish(engine, r, row_now, ok=False, detail=res.detail,
                    terminal=terminal, out=out, delay_minutes=delay, result=res)


def _reserve_for_send(engine, row: dict, candidate, context, now: datetime) \
        -> tuple[bool, _AttentionReservation, datetime, str]:
    """Reserve attention and journal the physical attempt in one transaction.

    Once quota is committed a worker may call the provider. Recording the fenced attempt in the
    same transaction closes the crash gap where quota could be consumed with no claim-owned
    evidence available for recovery. A crash after this point is conservatively ambiguous.
    """
    if not row.get("claim_token") or not candidate.intrusive:
        return True, _AttentionReservation(), next_window(now), "not_intrusive"
    local = now.astimezone(context.profile.zone)
    local_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=1)
    daily_start = local_start.astimezone(timezone.utc)
    daily_end = local_end.astimezone(timezone.utc)
    daily_seconds = max(1, int((daily_end - daily_start).total_seconds()))
    hourly_recipient = (None if candidate.channel in {"slack", "teams"}
                        else candidate.recipient)
    # The Atlas daily budget is per person. Slack/Teams share one hourly interruption stream,
    # but two people in different timezones must not share overlapping local-day rows.
    daily_recipient = candidate.recipient
    with engine.begin() as conn:
        hourly = reserve_attention(
            conn, org_id=candidate.org_id, recipient=hourly_recipient,
            channel_class=candidate.channel_class.value,
            limit=context.profile.max_interrupts_per_hour, now=now, rolling=True)
        if not hourly:
            available_at = next_available(
                # Shared incoming webhooks spend one org-wide attention stream.
                conn, org_id=candidate.org_id, recipient=hourly_recipient,
                channel_class=candidate.channel_class.value, now=now)
            return (False, _AttentionReservation(), available_at,
                    "atomic_attention_limit")
        daily = reserve_attention(
            conn, org_id=candidate.org_id, recipient=daily_recipient,
            channel_class="daily", limit=int(row.get("daily_budget") or 7),
            now=now, seconds=daily_seconds, start=daily_start)
        if not daily:
            release_attention(
                conn, org_id=candidate.org_id, recipient=hourly_recipient,
                channel_class=candidate.channel_class.value, now=now,
                start=now, rolling=True)
            return (False, _AttentionReservation(), daily_end, "daily_attention_budget")
        if _start_attempt_in_conn(conn, row, now) is None:
            release_attention(
                conn, org_id=candidate.org_id, recipient=hourly_recipient,
                channel_class=candidate.channel_class.value, now=now,
                start=now, rolling=True)
            release_attention(
                conn, org_id=candidate.org_id, recipient=daily_recipient,
                channel_class="daily", now=now, seconds=daily_seconds,
                start=daily_start)
            return (False, _AttentionReservation(), now, "stale_claim")
    return (True, _AttentionReservation(
                hourly=True, daily=True, hourly_start=now,
                daily_start=daily_start, daily_seconds=daily_seconds),
            next_window(now), "reserved")


def _release_reservation(engine, row: dict, candidate, reservation: _AttentionReservation,
                         now: datetime) -> None:
    if not (reservation.hourly or reservation.daily):
        return
    hourly_recipient = (None if candidate.channel in {"slack", "teams"}
                        else candidate.recipient)
    daily_recipient = candidate.recipient
    with engine.begin() as conn:
        if reservation.hourly:
            release_attention(
                conn, org_id=candidate.org_id, recipient=hourly_recipient,
                channel_class=candidate.channel_class.value, now=now,
                start=reservation.hourly_start, rolling=True)
        if reservation.daily:
            release_attention(
                conn, org_id=candidate.org_id, recipient=daily_recipient,
                channel_class="daily", now=now, seconds=reservation.daily_seconds,
                start=reservation.daily_start)


def _start_attempt_in_conn(conn, row: dict, now: datetime) -> str | None:
    """Start one physical provider call inside the caller's transaction."""
    token = row.get("claim_token")
    if not token:  # legacy claimed rows predating migration 0046
        row["attempt_number"] = int(row.get("attempts") or 0) + 1
        return None
    claimed = conn.execute(text(
        "update delivery_outbox set attempts=attempts+1,"
        "generation_attempts=generation_attempts+1,"
        "control_failures=0,"
        "claimed_until=now() + interval '5 minutes',updated_at=:now "
        "where id=:i and status='in_flight' and claim_token=:token "
        "and claimed_until>now() returning attempts"),
        {"now": now, "i": row["id"], "token": token}).first()
    if claimed is None:
        return None
    number = int(claimed.attempts if hasattr(claimed, "attempts") else claimed[0])
    attempt_id = new_id("dat")
    # All retries on one route generation carry the same provider idempotency key. A receiver
    # that honoured attempt-number keys would see an ACK-loss retry as a brand-new message.
    key = f"{row['id']}:{int(row.get('retry_generation') or 0)}:{row['channel']}"
    conn.execute(text(
        "insert into delivery_attempts (attempt_id,org_id,delivery_id,attempt_number,"
        "retry_generation,channel,destination_fingerprint,claim_token,idempotency_key,"
        "started_at) values "
        "(:a,:o,:d,:n,:generation,:ch,:fingerprint,:token,:key,:at)"),
        {"a": attempt_id, "o": row["org_id"], "d": row["id"], "n": number,
         "generation": int(row.get("retry_generation") or 0), "ch": row["channel"],
         "fingerprint": row.get("destination_fingerprint"),
         "token": token, "key": key, "at": now})
    row["attempt_number"] = number
    row["generation_attempts"] = int(row.get("generation_attempts") or 0) + 1
    row["attempt_id"] = attempt_id
    row["attempt_idempotency_key"] = key
    return key


def _start_attempt(engine, row: dict, now: datetime) -> str | None:
    """Start one physical provider call, fenced by the current claim token."""
    if row.get("attempt_id"):
        return str(row.get("attempt_idempotency_key") or
                   f"{row['id']}:{int(row.get('retry_generation') or 0)}:{row['channel']}")
    with engine.begin() as conn:
        return _start_attempt_in_conn(conn, row, now)


def _send_once(engine, row: dict, now: datetime, channel, payload: dict, config: dict):
    key = _start_attempt(engine, row, now)
    if row.get("claim_token") and key is None:
        return _STALE_CLAIM
    send_config = dict(config)
    if key:
        send_config["_idempotency_key"] = key
    try:
        return channel.send(payload, send_config)
    except Exception as exc:  # noqa: BLE001 - an adapter throw is ambiguous transport evidence
        return ChannelResult(
            ok=False, retryable=True, unknown=True,
            detail=f"{type(exc).__name__}: {str(exc)[:160]}")


def _final_phase_exception(engine, row: dict, candidate,
                           reservation: _AttentionReservation, now: datetime, *,
                           exc: Exception, out: dict,
                           prefix: str = "final delivery authority unavailable") -> None:
    """Classify a final-phase throw by whether a physical attempt had already started."""
    detail = f"{prefix}: {type(exc).__name__}: {str(exc)[:180]}"[:300]
    if row.get("attempt_id") or row.get("attempt_number"):
        # The provider may already have accepted the bytes (for example the authority transaction
        # failed while exiting after the call). Preserve the quota and attempt evidence and apply
        # the bounded ambiguous-transport ladder; never relabel this as a harmless control retry.
        result = ChannelResult(ok=False, retryable=True, unknown=True, detail=detail)
        cycle_attempt = int(row.get("generation_attempts") or row.get("attempt_number")
                            or row.get("attempts") or 1)
        delay = retry_delay(cycle_attempt)
        terminal = _ambiguous_requires_manual(row.get("channel", ""), result) or delay is None
        _finish(engine, row, now, ok=False, detail=detail, terminal=terminal,
                out=out, delay_minutes=delay, result=result)
        return
    _release_reservation(engine, row, candidate, reservation, now)
    if row.get("claim_token"):
        _control_failure(engine, row, now, detail=detail, out=out)
        return
    delay = next_attempt_delay(int(row.get("attempts") or 0) + 1)
    _finish(engine, row, now, ok=False, detail=detail, terminal=delay is None,
            out=out, delay_minutes=delay)


def _complete_attempt(conn, row: dict, *, outcome: str, detail: str,
                      result=None, completed_at: datetime) -> None:
    if not row.get("attempt_id"):
        return
    conn.execute(text(
        "update delivery_attempts set outcome=:outcome,retryable=:retryable,"
        "provider_message_id=:provider,http_status=:http,retry_after_seconds=:retry_after,"
        "error_class=:error,detail=:detail,completed_at=:at "
        "where attempt_id=:a and claim_token=:token and outcome='started'"),
        {"outcome": outcome,
         "retryable": getattr(result, "retryable", None) if result is not None else None,
         "provider": getattr(result, "provider_message_id", None),
         "http": getattr(result, "http_status", None),
         "retry_after": getattr(result, "retry_after_seconds", None),
         "error": ("ambiguous_transport" if bool(getattr(result, "unknown", False)) else
                   type(result).__name__ if result is not None and not getattr(result, "ok", False)
                   else None),
         "detail": detail[:300], "at": completed_at, "a": row["attempt_id"],
         "token": row.get("claim_token")})


def _lock_claim(conn, row: dict) -> bool:
    """Take the canonical outbox-before-attempt lock order for a fenced completion."""
    return conn.execute(text(
        "select id from delivery_outbox where id=:i and status='in_flight' "
        "and claim_token=:token for update"),
        {"i": row["id"], "token": row.get("claim_token")}).first() is not None


def _control_failure(engine, row: dict, now: datetime, *, detail: str, out: dict) -> None:
    """Bound a persistent internal fault without pretending it was a provider attempt."""
    failures = int(row.get("control_failures") or 0) + 1
    delay = next_attempt_delay(failures)
    with engine.begin() as conn:
        if delay is None:
            changed = conn.execute(text(
                "update delivery_outbox set status='failed_terminal',lifecycle_status='failed',"
                "control_failures=:failures,last_error=:e,claim_token=null,claimed_at=null,"
                "claimed_until=null,updated_at=:now where id=:i and status='in_flight' "
                "and claim_token=:token"),
                {"failures": failures, "e": detail[:300], "now": now,
                 "i": row["id"], "token": row.get("claim_token")})
            if getattr(changed, "rowcount", 0):
                append_event(
                    conn, org_id=row["org_id"], delivery_id=row["id"],
                    target=DeliveryState.FAILED, reason_code="control_plane_unavailable",
                    actor_id="delivery",
                    idempotency_key=(f"control-failure:"
                                     f"{int(row.get('retry_generation') or 0)}:{failures}:"
                                     f"{row.get('claim_token') or 'legacy'}:terminal"),
                    occurred_at=now, metadata={"detail": detail[:300]})
                out["terminal"] += 1
            return
        changed = conn.execute(text(
            "update delivery_outbox set status='queued',next_attempt_at=:next,"
            "control_failures=:failures,last_error=:e,claim_token=null,claimed_at=null,"
            "claimed_until=null,updated_at=:now where id=:i and status='in_flight' "
            "and claim_token=:token"),
            {"next": now + timedelta(minutes=delay), "failures": failures,
             "e": detail[:300], "now": now, "i": row["id"],
             "token": row.get("claim_token")})
    if getattr(changed, "rowcount", 0):
        row["control_failures"] = failures
        out["retried"] += 1


def _processing_retry(engine, row: dict, now: datetime, *, detail: str, out: dict) -> None:
    """Wait on mutable authority/pause state indefinitely without spending a failure rung."""
    with engine.begin() as conn:
        changed = conn.execute(text(
            "update delivery_outbox set status='queued',next_attempt_at=:next,last_error=:e,"
            "control_failures=0,claim_token=null,claimed_at=null,claimed_until=null,updated_at=:now "
            "where id=:i and status='in_flight' and claim_token=:token"),
            {"next": now + timedelta(minutes=5), "e": detail[:300], "now": now,
             "i": row["id"], "token": row.get("claim_token")})
    out["retried"] += int(bool(getattr(changed, "rowcount", 0)))


def _route_refresh_is_safe(engine, row: dict) -> bool:
    """Whether recipient/route bytes may change without duplicating an uncertain send."""
    if int(row.get("attempts") or 0) == 0:
        return True
    with engine.connect() as conn:
        result = conn.execute(text(
            "select exists (select 1 from delivery_attempts safe where safe.org_id=:o "
            "and safe.delivery_id=:d) and not exists (select 1 from delivery_attempts unsafe "
            "where unsafe.org_id=:o and unsafe.delivery_id=:d "
            "and unsafe.outcome in ('started','unknown','delivered')) as refresh_safe"),
            {"o": row["org_id"], "d": row["id"]}).first()
    if result is None:
        return False
    value = result.refresh_safe if hasattr(result, "refresh_safe") else result[0]
    return bool(value)


def _route_names(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    return []


def _advance_route(engine, row: dict, *, now: datetime, detail: str, out: dict,
                   result=None) -> bool:
    """Advance the same logical delivery to one definite fallback; never create a duplicate."""
    token = row.get("claim_token")
    routes = _route_names(row.get("route_plan"))
    current = int(row.get("route_index") or 0)
    if not token or current + 1 >= len(routes) or not row.get("source_payload"):
        return False
    try:
        source = (row["source_payload"] if isinstance(row["source_payload"], dict)
                  else json.loads(row["source_payload"]))
        if not isinstance(source, dict):
            return False
    except (TypeError, ValueError):
        return False
    next_channel = routes[current + 1]
    from genios_engine.deliver.orchestrator import format_kind_for, render_for_channel
    payload = render_for_channel(next_channel, source)
    next_class = channel_class_for(next_channel)
    interrupt = bool(row.get("interrupt")) and next_class is ChannelClass.CHAT
    prior_reason = str(row.get("route_reason") or "planned_route")
    with engine.begin() as conn:
        if not _lock_claim(conn, row):
            return False
        _complete_attempt(conn, row, outcome="terminal_failure", detail=detail,
                          result=result, completed_at=now)
        changed = conn.execute(text(
            "update delivery_outbox set channel=:channel,destination=:channel,"
            "channel_class=:class,format_kind=:format,interrupt=:interrupt,"
            "route_reason=:route_reason,payload=cast(:payload as jsonb),route_index=:route_index,"
            "retry_generation=retry_generation+1,generation_attempts=0,"
            "destination_fingerprint=null,"
            "status='queued',next_attempt_at=:now,last_error=:error,claim_token=null,"
            "claimed_at=null,claimed_until=null,updated_at=:now "
            "where id=:i and status='in_flight' and claim_token=:token"),
            {"channel": next_channel, "class": next_class.value,
             "format": format_kind_for(next_channel), "interrupt": interrupt,
             "route_reason": f"{prior_reason}:fallback:{next_channel}"[:192],
             "payload": json.dumps(payload, default=str), "route_index": current + 1,
             "now": now, "error": f"fallback from {row['channel']}: {detail}"[:300],
             "i": row["id"], "token": token})
    if not getattr(changed, "rowcount", 0):
        return False
    out["recovered"] = out.get("recovered", 0) + 1
    return True


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
        changed_count = 0
        if not row.get("claim_token"):
            changed = c.execute(text(
                "update delivery_outbox set next_attempt_at=:na,defer_count=defer_count+1,"
                "control_failures=0,"
                "gate_unit=:u, gate_reason=:r where id=:i and status='queued'"),
                {"na": defer_until(decision, now), "u": decision.unit,
                 "r": decision.reason_code, "i": row["id"]})
            changed_count = 1  # legacy compatibility path has no fencing token
        else:
            changed = c.execute(text(
                "update delivery_outbox set status='queued',next_attempt_at=:na,"
                "defer_count=defer_count+1,control_failures=0,"
                "gate_unit=:u,gate_reason=:r,claim_token=null,"
                "claimed_at=null,claimed_until=null,updated_at=:now "
                "where id=:i and status='in_flight' and claim_token=:token"),
                {"na": defer_until(decision, now), "u": decision.unit,
                 "r": decision.reason_code, "i": row["id"],
                 "token": row.get("claim_token"), "now": now})
            if getattr(changed, "rowcount", 0):
                changed_count = 1
                append_event(c, org_id=row["org_id"], delivery_id=row["id"],
                             target=DeliveryState.DEFERRED,
                             reason_code=decision.reason_code, actor_id="delivery",
                             idempotency_key=f"defer:{row.get('defer_count', 0) + 1}",
                             occurred_at=now, metadata={"unit": decision.unit})
    out["deferred"] += changed_count


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
        changed_count = 0
        if not row.get("claim_token"):
            changed = c.execute(text(
                "update delivery_outbox set status='suppressed', gate_unit=:u, gate_reason=:r, "
                "last_error=:e where id=:i and status='queued'"),
                {"u": decision.unit, "r": decision.reason_code,
                 "e": note[:300], "i": row["id"]})
            changed_count = 1  # legacy compatibility path has no fencing token
        else:
            changed = c.execute(text(
                "update delivery_outbox set status='suppressed',gate_unit=:u,gate_reason=:r,"
                "last_error=:e,claim_token=null,claimed_at=null,claimed_until=null,updated_at=now() "
                "where id=:i and status='in_flight' and claim_token=:token"),
                {"u": decision.unit, "r": decision.reason_code, "e": note[:300],
                 "i": row["id"], "token": row.get("claim_token")})
            if getattr(changed, "rowcount", 0):
                changed_count = 1
                append_event(c, org_id=row["org_id"], delivery_id=row["id"],
                             target=DeliveryState.SUPPRESSED,
                             reason_code=decision.reason_code, actor_id="delivery",
                             idempotency_key="system:suppressed", metadata={"unit": decision.unit})
    out["suppressed"] += changed_count


def _cancel(engine, row: dict, detail: str, out: dict) -> None:
    with engine.begin() as c:
        changed_count = 0
        if not row.get("claim_token"):
            changed = c.execute(text(
                "update delivery_outbox set status='cancelled',attempts=attempts+1,last_error=:e "
                "where id=:i and status='queued'"),
                {"i": row["id"], "e": detail[:300]})
            changed_count = 1  # legacy compatibility path has no fencing token
        else:
            changed = c.execute(text(
                "update delivery_outbox set status='cancelled',last_error=:e,claim_token=null,"
                "claimed_at=null,claimed_until=null,updated_at=now() where id=:i "
                "and status='in_flight' and claim_token=:token"),
                {"i": row["id"], "e": detail[:300], "token": row.get("claim_token")})
            if getattr(changed, "rowcount", 0):
                changed_count = 1
                append_event(c, org_id=row["org_id"], delivery_id=row["id"],
                             target=DeliveryState.CANCELLED, reason_code="authority_revoked",
                             actor_id="delivery", idempotency_key="system:cancelled")
    out["cancelled"] += changed_count


def _attempt_event_identity(row: dict) -> str:
    """Unique lifecycle identity for both provider and pre-provider terminal attempts."""
    if row.get("attempt_id"):
        return str(row["attempt_id"])
    if row.get("attempt_number") is not None:
        return f"number-{row['attempt_number']}"
    return (f"preflight-{int(row.get('retry_generation') or 0)}-"
            f"{row.get('claim_token') or 'legacy'}")


def _finish(engine, row: dict, now: datetime, *, ok: bool, detail: str, terminal: bool,
            out: dict, delay_minutes: int | None = None, decision=None, result=None) -> None:
    with engine.begin() as c:
        if row.get("claim_token"):
            if not _lock_claim(c, row):
                return
            outcome = ("delivered" if ok else
                       "unknown" if bool(getattr(result, "unknown", False)) else
                       "terminal_failure" if terminal else "retryable_failure")
            _complete_attempt(c, row, outcome=outcome, detail=detail,
                              result=result, completed_at=now)
            if ok:
                changed = c.execute(text(
                    "update delivery_outbox set status='delivered',delivered_at=:t,"
                    "last_error=null,gate_unit=:u,gate_reason=:r,claim_token=null,"
                    "claimed_at=null,claimed_until=null,updated_at=:t where id=:i "
                    "and status='in_flight' and claim_token=:token"),
                    {"t": now, "i": row["id"],
                     "u": decision.unit if decision else None,
                     "r": decision.reason_code if decision else None,
                     "token": row.get("claim_token")})
                if not getattr(changed, "rowcount", 0):
                    return
                append_event(c, org_id=row["org_id"], delivery_id=row["id"],
                             target=DeliveryState.DELIVERED,
                             reason_code=(decision.reason_code if decision else "transport_delivered"),
                             actor_id="delivery",
                             idempotency_key=(f"attempt:{_attempt_event_identity(row)}:"
                                              "delivered"),
                             occurred_at=now, metadata={"channel": row["channel"]})
                out["delivered"] += 1
                if is_executive_delivery(row["card_id"]):
                    mark_executive_delivered(c, row["org_id"], row["card_id"], at=now,
                                             channel=row["channel"])
            elif terminal:
                changed = c.execute(text(
                    "update delivery_outbox set status='failed_terminal',last_error=:e,"
                    "claim_token=null,claimed_at=null,claimed_until=null,updated_at=:now "
                    "where id=:i and status='in_flight' and claim_token=:token"),
                    {"e": detail[:300], "i": row["id"], "token": row.get("claim_token"),
                     "now": now})
                if getattr(changed, "rowcount", 0):
                    append_event(c, org_id=row["org_id"], delivery_id=row["id"],
                                 target=DeliveryState.FAILED,
                                 reason_code=("ambiguous_transport" if bool(
                                     getattr(result, "unknown", False)) else "transport_failed"),
                                 actor_id="delivery",
                                 idempotency_key=(f"attempt:{_attempt_event_identity(row)}:"
                                                  "failed"),
                                 occurred_at=now)
                    out["terminal"] += 1
            else:
                changed = c.execute(text(
                    "update delivery_outbox set status='queued',last_error=:e,next_attempt_at=:na,"
                    "claim_token=null,claimed_at=null,claimed_until=null,updated_at=:now "
                    "where id=:i and status='in_flight' and claim_token=:token"),
                    {"e": detail[:300], "na": now + timedelta(minutes=delay_minutes or 5),
                     "i": row["id"], "token": row.get("claim_token"), "now": now})
                out["retried"] += int(bool(getattr(changed, "rowcount", 0)))
            return

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
    """Materialise ExecutionObjects, expire stale results and drain due deliveries.

    Raw cards and the old synchronous agent fan-out are intentionally absent. Existing legacy
    rows continue to drain, but every newly queued outward delivery is execution-bound.
    """
    now = eval_time or datetime.now(timezone.utc)
    totals = {"orgs": 0, "initial": 0, "events": 0, "refreshed": 0, "invalid": 0,
              "linked": 0, "expired": 0, "errors": 0}
    with engine.connect() as c:
        global_flag = c.execute(text(
            "select enabled from feature_flags where key='kill_switch_all'")).first()
        global_enabled = (global_flag.enabled if hasattr(global_flag, "enabled")
                          else global_flag[0] if global_flag is not None else False)
        if not bool(global_enabled):
            return {**totals, "paused": True, "delivered": 0, "retried": 0,
                    "terminal": 0, "cancelled": 0, "deferred": 0, "suppressed": 0}
        channel_rows = c.execute(text(
            "select org_id, channel, config, config_encrypted from org_channels where active "
            "and not exists (select 1 from feature_flags paused where "
            "paused.key='kill_switch:' || org_channels.org_id and not paused.enabled) "
            "order by org_id, channel")).mappings().all()
        org_rows = c.execute(text(
            "select distinct org_id from executions where closed_at is null and not exists "
            "(select 1 from feature_flags paused where paused.key='kill_switch:' || "
            "executions.org_id and not paused.enabled) "
            "union select distinct org_id from org_channels where active and not exists "
            "(select 1 from feature_flags paused where paused.key='kill_switch:' || "
            "org_channels.org_id and not paused.enabled) "
            "order by org_id")).fetchall()
    grouped: dict[str, list] = {}
    from genios_engine.deliver.units import configured_channel
    for row in channel_rows:
        if configured_channel(dict(row)):
            grouped.setdefault(str(row["org_id"]), []).append(destination_from_row(row))
    org_ids = {str(row.org_id if hasattr(row, "org_id") else row[0]) for row in org_rows}
    org_ids.update(grouped)
    from genios_engine.deliver.orchestrator import enqueue_execution_deliveries
    for org in sorted(org_ids):
        destinations = grouped.get(org, [])
        totals["orgs"] += 1
        try:
            totals["linked"] += link_commitment_cards(engine, org)
            materialized = enqueue_execution_deliveries(
                engine, org, destinations=destinations, base_url=base_url, eval_time=now)
            for key in ("initial", "events", "refreshed", "invalid"):
                totals[key] += materialized[key]
        except Exception:      # noqa: BLE001 — one org's enqueue never blocks the rest
            totals["errors"] += 1
            _log.exception("delivery materialisation failed org=%s", org)
    with engine.begin() as conn:
        totals["expired"] = expire_due(conn, now=now)
    # Keep an explicit caller-supplied evaluation time deterministic, but production drains use
    # a fresh per-row clock so a long provider batch cannot cross expiry under stale authority.
    totals.update(drain(engine, eval_time=eval_time))
    return totals
