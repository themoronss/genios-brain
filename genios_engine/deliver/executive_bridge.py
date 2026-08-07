"""Layer 6 · the bridge that carries Layer 5's commitments to a human.

Until this module existed, Layer 5 could decide that somebody needed nudging, record the
decision, fire the escalation rung — and then nothing left the building.  The reminder was a
row.  This is the wire.

**Why the wire runs this way round.**  Layer 5 may never import Layer 6, so it cannot enqueue
anything itself.  What it *can* do is write down its decision, and it does: an
``execution_events`` row of kind ``execution.reminded`` carries the routing plan on the parent
commitment and the grounded fact corpus in its own ``detail``.  Layer 6 reads that and turns it
into a message.  The dependency points downward, which is the rule, and the division of labour
comes out exactly right:

  * Layer 5 decides **whether to speak, to whom, through which channel, and what may be said.**
  * Layer 6 decides **how it looks and gets it there, with retries.**

**Nothing new is ever said.**  The message is assembled only from values Layer 5 put in the
event's fact corpus — days open, days remaining, the consequence sentence, the next action's
label. The bridge has no access to the graph and no way to look anything up, which makes the
invention guarantee structural rather than a matter of discipline.

**Exactly once, by construction.**  The synthetic ``card_id`` embeds the event id, so
``delivery_outbox``'s ``(org_id, card_id, channel)`` unique index absorbs a re-run. That is the
same trick the daily digest already uses; no new bookkeeping table, and a crashed sweep that
re-enqueues cannot double-send.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.deliver.gate import channel_class_for
from genios_engine.platform.ids import new_id

BRIDGE_VERSION = "exec_bridge.v1"

#: Marks an outbox row as a commitment message rather than a card. ``drain`` branches on this to
#: re-validate against ``executions`` instead of ``cards`` — the two have different proofs of
#: liveness, and using the card proof for a reminder would cancel every one of them.
EXECUTIVE_PREFIX = "exec:"

#: Only these events become messages. A state transition is audit, not news: telling somebody
#: their commitment moved from `pending` to `running` because they ticked a box is precisely the
#: kind of notification that trains people to ignore the channel.
_NOTIFIABLE = ("execution.reminded",)


def executive_card_id(execution_id: str, event_id: str) -> str:
    """Synthetic outbox key: one row per reminder, deduped by the unique index."""
    return f"{EXECUTIVE_PREFIX}{execution_id}:{event_id}"


def is_executive_delivery(card_id: Any) -> bool:
    return str(card_id or "").startswith(EXECUTIVE_PREFIX)


def parse_executive_card_id(card_id: str) -> tuple[str, str] | None:
    """``exec:<execution_id>:<event_id>`` → its two parts, or None if it is not one of ours."""
    if not is_executive_delivery(card_id):
        return None
    rest = str(card_id)[len(EXECUTIVE_PREFIX):]
    execution_id, _, event_id = rest.rpartition(":")
    return (execution_id, event_id) if execution_id and event_id else None


def format_reminder(row: dict) -> dict:
    """Grounded facts in, a channel-neutral message dict out.

    Channel-neutral on purpose: the adapter turns this into Slack blocks. Putting the words here
    rather than in the adapter means adding a second channel does not get a second chance to
    phrase the same reminder differently.
    """
    facts = row.get("facts") or {}
    urgency = str(row.get("urgency") or "gentle")
    goal = str(facts.get("goal") or row.get("goal") or "an open commitment")
    days_open = facts.get("days_open")
    days_left = facts.get("days_remaining")

    # Every clause is guarded on the fact existing. A reminder that says "0 days remaining"
    # because a value was missing reads as a crisis that is not happening.
    parts: list[str] = []
    if isinstance(days_open, int):
        parts.append(f"open {days_open}d")
    if isinstance(days_left, int):
        parts.append("due today" if days_left == 0 else f"{days_left}d left")
    if row.get("escalation_day") is not None:
        parts.append(f"day {row['escalation_day']} of the escalation ladder")

    return {
        "kind": "execution_reminder",
        "urgency": urgency,
        "headline": goal,
        "situation": " · ".join(parts),
        "next_action": str(facts.get("next_action") or ""),
        "consequence": str(facts.get("consequence") or ""),
        "execution_id": row.get("execution_id"),
        "card_id": row.get("card_id"),
        "reason_code": str(row.get("reason_code") or ""),
    }


def _render(channel: str, message: dict, *, base_url: str = "") -> dict:
    """Neutral message → the concrete channel's payload shape.

    One branch today because one human channel ships today. It exists as a seam rather than an
    inline call so adding a channel is a case here, not a second copy of the wording rules.
    """
    if channel == "slack":
        from genios_engine.deliver.channels.slack import format_reminder_message
        return format_reminder_message(message, base_url=base_url)
    return message


def _detail(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:                              # pragma: no cover - corrupt row
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def enqueue_executive_messages(engine, org_id: str, channel: str = "slack",
                               limit: int = 100, base_url: str = "") -> int:
    """Queue every un-sent reminder Layer 5 has decided on, for orgs on this channel.

    Filtered to commitments Layer 5 actually routed to this channel and marked as interrupting.
    A commitment planned for the digest is deliberately *not* pushed here — respecting that
    choice is the whole reason Layer 5 was given the channel decision in the first place.
    """
    queued = 0
    with engine.begin() as conn:
        rows = conn.execute(text(
            "select e.event_id, e.execution_id, e.reason_code, e.detail, e.occurred_at, "
            "x.goal, x.assignee, x.card_id, x.band, x.channel_class, x.interrupt "
            "from execution_events e join executions x "
            "on x.org_id=e.org_id and x.execution_id=e.execution_id "
            "where e.org_id=:o and e.kind = any(:kinds) "
            "and x.closed_at is null and x.channel_id=:ch and x.assignee is not null "
            "and not exists (select 1 from delivery_outbox ob where ob.org_id=e.org_id "
            "and ob.card_id=:prefix || e.execution_id || ':' || e.event_id "
            "and ob.channel=:ch) "
            "order by e.occurred_at asc limit :l"),
            {"o": org_id, "kinds": list(_NOTIFIABLE), "ch": channel,
             "prefix": EXECUTIVE_PREFIX, "l": max(1, min(int(limit), 500))}).mappings().all()

        for row in rows:
            detail = _detail(row["detail"])
            message = format_reminder({
                "execution_id": row["execution_id"], "goal": row["goal"],
                "card_id": row["card_id"], "reason_code": row["reason_code"],
                "urgency": detail.get("urgency"),
                "escalation_day": detail.get("escalation_day"),
                "facts": detail.get("facts") or {}})
            # The outbox posts payload bytes verbatim, so the channel shape is fixed here — the
            # same point in the flow where the card path calls format_card_message. The neutral
            # dict above stays the single place the *words* are decided, so a second channel
            # renders the same reminder rather than inventing its own phrasing.
            payload = _render(channel, message, base_url=base_url)
            # The delivery object, copied from the commitment rather than re-derived. Layer 5
            # already decided who owns this, how loud it is, and whether it earned the right to
            # interrupt — that last one behind a confidence floor this module cannot see. Layer
            # 5.2's gate then judges *when*, using exactly the decision Layer 5 recorded.
            result = conn.execute(text(
                "insert into delivery_outbox (id, org_id, card_id, channel, payload, "
                "recipient, band, channel_class, interrupt) "
                "values (:i, :o, :c, :ch, cast(:p as jsonb), :seat, :band, :cclass, :interrupt) "
                "on conflict (org_id, card_id, channel) do nothing"),
                {"i": new_id("ob"), "o": org_id,
                 "c": executive_card_id(row["execution_id"], row["event_id"]),
                 "ch": channel, "p": json.dumps(payload), "seat": row["assignee"],
                 "band": row["band"],
                 # The *surface* class, derived from the adapter this row is going out on. Layer
                 # 5's own channel_class is what it planned for; a commitment planned for the
                 # digest never reaches here because the enqueue filters on `channel_id`, so the
                 # two agree — and when a non-chat adapter ships, this follows it automatically.
                 "cclass": channel_class_for(channel).value,
                 "interrupt": bool(row["interrupt"])})
            queued += result.rowcount
    return queued


def executive_delivery_is_live(conn, org_id: str, card_id: str, *,
                               now: datetime | None = None) -> bool:
    """Re-validate a queued reminder immediately before it is sent.

    The same law the card path enforces, applied to commitments: a queued message must prove its
    subject is *still* live at send time, not merely that it was live when queued. A reminder
    can sit in the outbox through a retry backoff, and the customer can reply in that window —
    which is exactly the nudge this whole layer exists to never send.

    Deliberately cheap and local: the commitment being open is the proof. Layer 5's own guard
    already re-ran the full authority predicate before writing the event, and it closes the
    commitment the moment that predicate fails, so an open row *is* the authority check having
    passed. Re-running the whole join here would duplicate that logic in a second place, which
    is how two copies start disagreeing.
    """
    parsed = parse_executive_card_id(card_id)
    if parsed is None:
        return False
    execution_id, _event_id = parsed
    moment = now or datetime.now(timezone.utc)
    row = conn.execute(text(
        "select 1 from executions where org_id=:o and execution_id=:x "
        "and closed_at is null and expires_at > :now"),
        {"o": org_id, "x": execution_id, "now": moment}).first()
    return row is not None


def link_commitment_cards(engine, org_id: str, limit: int = 200) -> int:
    """Point each commitment at the card that surfaces it.

    Written as a self-healing sweep rather than a hook inside the card build, so a commitment
    created before its card, or a card built while the executive sweep was paused, still ends up
    linked. Guarded on ``card_id is null`` — the link is written once and never repointed.
    """
    linked = 0
    with engine.begin() as conn:
        rows = conn.execute(text(
            "select x.execution_id, k.card_id from executions x "
            "join cards k on k.org_id=x.org_id and k.signal_id=x.signal_id "
            "where x.org_id=:o and x.card_id is null and x.signal_id is not null "
            "and x.closed_at is null limit :l"),
            {"o": org_id, "l": max(1, min(int(limit), 500))}).mappings().all()
        for row in rows:
            result = conn.execute(text(
                "update executions set card_id=:c, updated_at=now() "
                "where org_id=:o and execution_id=:x and card_id is null"),
                {"c": row["card_id"], "o": org_id, "x": row["execution_id"]})
            linked += result.rowcount
    return linked


__all__ = ["BRIDGE_VERSION", "EXECUTIVE_PREFIX", "enqueue_executive_messages",
           "executive_card_id", "executive_delivery_is_live", "format_reminder",
           "is_executive_delivery", "link_commitment_cards", "parse_executive_card_id"]
