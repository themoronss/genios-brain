from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id

# E8 · Action Ingester (§5.12) — the round trip both L1 and L6 depend on. Four buttons + requeue,
# each landing as an L1 human event AND a card lifecycle transition, all timestamped. 'wrong'
# takes no reason by design (mandatory friction kills the most valuable negative signal). Requeue
# is NOT a fifth button: logged ui.requeued, excluded from precision math, expires normally.

BUTTONS = {"run_play", "do_it_myself", "snooze", "wrong", "requeue"}


def snooze_until(option: str | None, eval_time: datetime, custom=None) -> datetime:
    if option == "3d":
        return eval_time + timedelta(days=3)
    if option == "tomorrow_09":
        return (eval_time + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    if option == "custom" and custom:
        try:
            return datetime.fromisoformat(str(custom).replace("Z", "+00:00"))
        except ValueError:
            pass
    return eval_time + timedelta(hours=4)          # default '4h'


def _human_event(graph, org_id, actor, card, action, detail):
    with graph.engine.begin() as c:
        c.execute(text("insert into human_events (id, org_id, type, actor_id, target, detail, "
                       "occurred_at) values (:id,:o,:t,:a,cast(:tg as jsonb),cast(:d as jsonb),now())"),
                  {"id": new_id("hev"), "o": org_id, "t": f"card.{action}", "a": actor,
                   "tg": json.dumps({"card_id": card["card_id"], "signal_id": card["signal_id"]}),
                   "d": json.dumps(detail or {}, default=str)})


def _set_signal_status(graph, signal_id, status):
    with graph.engine.begin() as c:
        c.execute(text("update signals set status=:s where signal_id=:id"),
                  {"s": status, "id": signal_id})


def ingest_action(*, card_store, graph, org_id: str, card_id: str, actor: str, action: str,
                  reason: str | None = None, snooze_option: str | None = None,
                  custom_until=None, eval_time: datetime | None = None) -> dict:
    """Land a button press. Returns the resulting card state. Orphan actions (no card) are a
    counted no-op (V-09), never an exception loop."""
    eval_time = eval_time or datetime.now(timezone.utc)
    if action not in BUTTONS:
        return {"ok": False, "error": "unknown_action"}
    card = card_store.get_card(card_id)
    if card is None:
        return {"ok": False, "error": "orphan_action", "code": "V-09"}   # button with no card

    detail = {"reason": reason} if reason else {}
    _human_event(graph, org_id, actor, card, action, detail)

    if action in ("run_play", "do_it_myself"):
        card_store.transition(card_id, org_id, "acted", "human.card_action",
                              cause=action, actor=actor, detail=detail, resolved=False)
        _set_signal_status(graph, card["signal_id"], "acted")
        return {"ok": True, "state": "acted", "action": action}

    if action == "wrong":
        card_store.transition(card_id, org_id, "acted", "human.card_action",
                              cause="wrong", actor=actor, detail=detail, resolved=False)
        _set_signal_status(graph, card["signal_id"], "acted")   # closed; L6 reads the negative
        return {"ok": True, "state": "acted", "action": "wrong", "reason": reason}

    if action == "snooze":
        su = snooze_until(snooze_option, eval_time, custom_until)
        card_store.transition(card_id, org_id, "snoozed", "human.card_action",
                              cause="snooze", actor=actor, detail={"until": su.isoformat()},
                              snooze_until=su)
        _set_signal_status(graph, card["signal_id"], "snoozed")
        return {"ok": True, "state": "snoozed", "snooze_until": su.isoformat()}

    # requeue — window management, not judgment (excluded from precision)
    card_store.transition(card_id, org_id, "queued", "ui.requeued", cause="requeue", actor=actor)
    return {"ok": True, "state": "queued", "action": "requeue"}
