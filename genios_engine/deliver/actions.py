from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
)

# E8 · Action Ingester (§5.12) — the round trip both L1 and L6 depend on. Four buttons + requeue,
# each landing as an L1 human event AND a card lifecycle transition, all timestamped. A Wrong
# verdict requires one closed reason so a terminal action cannot silently disappear from learning.
# Requeue
# is NOT a fifth button: logged ui.requeued, excluded from precision math, expires normally.

BUTTONS = {"run_play", "do_it_myself", "snooze", "wrong", "requeue"}
WRONG_REASONS = {"not_relevant", "wrong_facts", "bad_timing"}


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


def ingest_action(*, card_store, graph, org_id: str, card_id: str, actor: str, action: str,
                  reason: str | None = None, snooze_option: str | None = None,
                  custom_until=None, eval_time: datetime | None = None,
                  allow_any_assignee: bool = False) -> dict:
    """Land a button press. Returns the resulting card state. Orphan actions (no card) are a
    counted no-op (V-09), never an exception loop."""
    eval_time = eval_time or datetime.now(timezone.utc)
    if action not in BUTTONS:
        return {"ok": False, "error": "unknown_action"}
    if action == "wrong" and reason not in WRONG_REASONS:
        return {"ok": False, "error": "invalid_wrong_reason",
                "allowed_reasons": sorted(WRONG_REASONS)}
    del card_store  # production actions commit through the graph/database transaction below
    allowed = {
        "run_play": ("queued", "surfaced", "snoozed", "delivered"),
        "do_it_myself": ("queued", "surfaced", "snoozed", "delivered"),
        "wrong": ("queued", "surfaced", "snoozed", "delivered"),
        "snooze": ("queued", "surfaced", "delivered"),
        "requeue": ("snoozed", "surfaced", "delivered"),
    }
    with graph.engine.begin() as c:
        # All graph writers lock this tenant row when bumping the graph version. Holding a shared
        # lock closes the check-to-action race for this irreversible authority transition.
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        card = c.execute(text(
            "select k.card_id, k.signal_id, k.org_id, k.assignee, k.state, k.expires_at "
            "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
            + AUTHORITATIVE_SIGNAL_JOINS +
            " where k.card_id=:card and k.org_id=:o and s.status='open' "
            "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE +
            " for update of k, s for share of rr, ro, selected_rc, rcap, authority_ctx, "
            "authority_cfg, authority_pack"),
            {"card": card_id, "o": org_id,
             "authority_time": eval_time}).mappings().first()
        if card is None:
            return {"ok": False, "error": "stale_or_unauthorized_card", "code": "V-09"}
        if (not allow_any_assignee and card["assignee"] is not None
                and card["assignee"] != actor):
            return {"ok": False, "error": "assigned_to_different_seat"}
        if card["state"] not in allowed[action]:
            return {"ok": False, "error": "card_not_actionable"}

        state = "acted" if action in {"run_play", "do_it_myself", "wrong"} \
            else ("snoozed" if action == "snooze" else "queued")
        detail = {"reason": reason} if reason else {}
        snooze_at = None
        if action == "snooze":
            snooze_at = min(snooze_until(snooze_option, eval_time, custom_until),
                            card["expires_at"])
            detail = {"until": snooze_at.isoformat()}

        c.execute(text(
            "update cards set state=:state, snooze_until=:snooze "
            "where card_id=:card and org_id=:o"),
            {"state": state, "snooze": snooze_at, "card": card_id, "o": org_id})
        if state == "acted":
            c.execute(text(
                "update signals set status='acted' where signal_id=:signal and org_id=:o"),
                {"signal": card["signal_id"], "o": org_id})

        c.execute(text(
            "insert into human_events (id, org_id, type, actor_id, target, detail, occurred_at) "
            "values (:id,:o,:type,:actor,cast(:target as jsonb),cast(:detail as jsonb),:at)"),
            {"id": new_id("hev"), "o": org_id, "type": f"card.{action}", "actor": actor,
             "target": json.dumps({"card_id": card_id, "signal_id": card["signal_id"]}),
             "detail": json.dumps(detail, default=str), "at": eval_time})
        c.execute(text(
            "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
            "values (:id,:card,:o,:kind,:cause,:actor,cast(:detail as jsonb))"),
            {"id": new_id("cev"), "card": card_id, "o": org_id,
             "kind": "ui.requeued" if action == "requeue" else "human.card_action",
             "cause": action, "actor": actor, "detail": json.dumps(detail, default=str)})

    if action == "snooze":
        return {"ok": True, "state": state, "snooze_until": snooze_at.isoformat()}
    return {"ok": True, "state": state, "action": action,
            **({"reason": reason} if action == "wrong" else {})}
