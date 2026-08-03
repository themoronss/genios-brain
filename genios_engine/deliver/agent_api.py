from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id

# E9 · Agent API Gateway (§5.16) — the $15/agent metered read-and-claim surface. Same intelligence,
# its own identity, honest failures. Execution stays on the customer's side: GeniOS hands over the
# signal + rendered artifact and a 15-minute claim lock; the agent sends under its own credentials.
# First writer wins visibly (409 on double claim); a `failed` result re-surfaces to the human.

CLAIM_MINUTES = 15


def _meter(c, org_id, agent_id, field, period):
    c.execute(text(
        f"insert into agent_metering (org_id, agent_id, period, {field}) values (:o,:a,:p,1) "
        f"on conflict (org_id, agent_id, period) do update set {field} = agent_metering.{field}+1"),
        {"o": org_id, "a": agent_id, "p": period})


def _period(eval_time: datetime) -> str:
    return eval_time.strftime("%Y-%m")


def poll_signals(store, org_id: str, agent_id: str, *, since=None, eval_time=None) -> list[dict]:
    """GET /v1/signals?status=delivered — un-resolved cards' signals + presentation, machine-readable."""
    eval_time = eval_time or datetime.now(timezone.utc)
    q = ("select k.signal_id, k.card_id, k.urgency_band, k.headline, k.situation, k.score, "
         "k.score_block, k.state, k.created_at from cards k "
         "where k.org_id=:o and k.state in ('queued','surfaced','snoozed')")
    params = {"o": org_id}
    if since is not None:
        q += " and k.created_at > :since"; params["since"] = since
    q += " order by k.score desc"
    with store.engine.begin() as c:
        rows = [dict(r) for r in c.execute(text(q), params).mappings()]
        _meter(c, org_id, agent_id, "reads", _period(eval_time))
    return rows


def get_artifact(store, org_id: str, signal_id: str, agent_id: str, *, eval_time=None) -> dict | None:
    """GET /v1/signals/{id}/artifact — the pre-rendered draft (a DB read; pure margin by design)."""
    eval_time = eval_time or datetime.now(timezone.utc)
    with store.engine.begin() as c:
        r = c.execute(text("select artifact, headline, situation, render_mode from cards "
                           "where org_id=:o and signal_id=:s"),
                      {"o": org_id, "s": signal_id}).mappings().first()
        _meter(c, org_id, agent_id, "reads", _period(eval_time))
    return dict(r) if r else None


def claim(store, org_id: str, signal_id: str, agent_id: str, *, eval_time=None) -> dict:
    """POST /v1/signals/{id}/claim — lock 15 min. Double claim → 409 with holder + expiry (V-07)."""
    eval_time = eval_time or datetime.now(timezone.utc)
    with store.engine.begin() as c:
        card = c.execute(text("select card_id, state from cards where org_id=:o and signal_id=:s"),
                         {"o": org_id, "s": signal_id}).mappings().first()
        if card is None:
            return {"ok": False, "status": 404, "error": "no_card"}
        expires = eval_time + timedelta(minutes=CLAIM_MINUTES)
        # Atomic claim: the conditional DO UPDATE runs under the row lock the INSERT..ON CONFLICT
        # takes, so it wins ONLY if the existing lock is released/resulted/expired — or it's our
        # own re-claim. Two concurrent claimants no longer both win (was a TOCTOU: check-then-upsert
        # let the later writer steal the lock and both agents executed the external action).
        won = c.execute(text(
            "insert into agent_claims (signal_id, card_id, org_id, agent_id, claimed_at, expires_at) "
            "values (:s,:c,:o,:a,:t,:e) on conflict (signal_id) do update set agent_id=:a, "
            "claimed_at=:t, expires_at=:e, released_at=null, result=null, result_detail=null "
            "where agent_claims.released_at is not null or agent_claims.result is not null "
            "   or agent_claims.expires_at <= :now or agent_claims.agent_id = :a "
            "returning agent_id"),
            {"s": signal_id, "c": card["card_id"], "o": org_id, "a": agent_id,
             "t": eval_time, "e": expires, "now": eval_time}).first()
        if won is None:                              # a live lock held by another agent
            held = c.execute(text("select agent_id, expires_at from agent_claims where signal_id=:s"),
                             {"s": signal_id}).mappings().first()
            return {"ok": False, "status": 409, "code": "V-07",
                    "holder": held["agent_id"], "expires_at": held["expires_at"].isoformat()}
        c.execute(text("update cards set state='claimed' where card_id=:c and state in "
                       "('queued','surfaced','snoozed')"), {"c": card["card_id"]})
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
                       "values (:id,:c,:o,'agent.claim',:a,:a,cast(:d as jsonb))"),
                  {"id": new_id("cev"), "c": card["card_id"], "o": org_id, "a": agent_id,
                   "d": json.dumps({"expires_at": expires.isoformat()})})
        _meter(c, org_id, agent_id, "claims", _period(eval_time))
    return {"ok": True, "status": 200, "expires_at": expires.isoformat(), "lock_minutes": CLAIM_MINUTES}


def result(store, org_id: str, signal_id: str, agent_id: str, status: str, *,
           detail=None, eval_time=None) -> dict:
    """POST /v1/signals/{id}/result — done | failed. done resolves; failed keeps it OPEN and
    re-surfaces to the human with the agent's failure detail (Law: honest failures). Late result
    on a resolved signal is a counted no-op (V-08), never an error loop."""
    eval_time = eval_time or datetime.now(timezone.utc)
    with store.engine.begin() as c:
        card = c.execute(text("select card_id, state from cards where org_id=:o and signal_id=:s"),
                         {"o": org_id, "s": signal_id}).mappings().first()
        if card is None:
            return {"ok": False, "status": 404, "error": "no_card"}
        _meter(c, org_id, agent_id, "results", _period(eval_time))
        sig = c.execute(text("select status from signals where signal_id=:s"),
                        {"s": signal_id}).mappings().first()
        if sig and sig["status"] not in ("open", "snoozed"):
            c.execute(text("update agent_claims set result=:r, result_detail=cast(:d as jsonb), "
                           "released_at=:t where signal_id=:s"),
                      {"r": status, "d": json.dumps(detail or {}, default=str),
                       "t": eval_time, "s": signal_id})
            return {"ok": True, "status": 200, "note": "late_result_noop", "code": "V-08"}
        c.execute(text("update agent_claims set result=:r, result_detail=cast(:d as jsonb), "
                       "released_at=:t where signal_id=:s"),
                  {"r": status, "d": json.dumps(detail or {}, default=str),
                   "t": eval_time, "s": signal_id})
        if status == "done":
            c.execute(text("update cards set state='acted' where card_id=:c"), {"c": card["card_id"]})
            c.execute(text("update signals set status='acted' where signal_id=:s"), {"s": signal_id})
            kind, cause = "agent.result", "done"
        else:                                        # failed → re-surface to the human, keep open
            c.execute(text("update cards set state='surfaced' where card_id=:c"), {"c": card["card_id"]})
            kind, cause = "agent.result", "failed"
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
                       "values (:id,:c,:o,:k,:cause,:a,cast(:d as jsonb))"),
                  {"id": new_id("cev"), "c": card["card_id"], "o": org_id, "k": kind, "cause": cause, "a": agent_id,
                   "d": json.dumps(detail or {}, default=str)})
    return {"ok": True, "status": 200, "result": status}
