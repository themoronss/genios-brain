from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
)

# E9 · Agent API Gateway (§5.16) — the $15/agent metered read-and-claim surface. Same intelligence,
# its own identity, honest failures. Execution stays on the customer's side: GeniOS hands over the
# signal + rendered artifact and a 15-minute claim lock; the agent sends under its own credentials.
# First writer wins visibly (409 on double claim); a `failed` result re-surfaces to the human.

CLAIM_MINUTES = 15


def _agent_scope(c, org_id: str, agent_id: str) -> dict:
    """The agent's stored data-scope policy (segments/fact_types/min_confidence/max_age_days). This
    is what the dashboard sets; it MUST be enforced on every read/claim so a scoped key can't read
    outside its slice. Missing/blank → empty scope = no restriction (owner-equivalent)."""
    r = c.execute(text("select scope from agent_registry where org_id=:o and agent_id=:a"),
                  {"o": org_id, "a": agent_id}).first()
    s = (r.scope if r and r.scope is not None else {}) or {}
    if isinstance(s, str):
        try:
            s = json.loads(s or "{}")
        except Exception:      # noqa: BLE001
            s = {}
    return s if isinstance(s, dict) else {}


def _scope_filter(scope: dict, params: dict, now: datetime) -> str:
    """Extra SQL enforcing the agent scope (mutates params). Empty/None dimensions = unrestricted.
    Signals alias is `s`. connectors are not filterable on signals yet (no source column) — tracked."""
    frags = []
    segs = scope.get("segments")
    if segs:                                   # only these segments' subjects are visible
        frags.append("s.subject_node_id in (select node_id from segment_members "
                     "where org_id=:o and segment_id = any(:_segs))")
        params["_segs"] = list(segs)
    fts = scope.get("fact_types")
    if fts:                                     # only these reason_codes
        frags.append("s.reason_code = any(:_fts)")
        params["_fts"] = list(fts)
    try:
        minc = float(scope.get("min_confidence") or 0)
    except (TypeError, ValueError):
        minc = 0.0
    if minc > 0:
        frags.append("s.score >= :_minc")
        params["_minc"] = minc
    maxage = scope.get("max_age_days")
    if maxage:
        try:
            frags.append("s.created_at >= :_agecut")
            params["_agecut"] = now - timedelta(days=int(maxage))
        except (TypeError, ValueError):
            frags.pop()
    return (" and " + " and ".join(frags)) if frags else ""


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
    q = ("select k.signal_id, k.card_id, k.urgency_band, k.headline, k.situation, "
         + AUTHORITATIVE_SCORE_SQL + " as score, "
         "k.score_block, k.state, k.created_at from cards k "
         "join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
         + AUTHORITATIVE_SIGNAL_JOINS +
         " where k.org_id=:o and k.state in ('queued','surfaced','snoozed') "
         "and k.expires_at > :authority_time and s.status='open' and "
         + AUTHORITATIVE_SIGNAL_PREDICATE)
    params = {"o": org_id, "authority_time": eval_time}
    if since is not None:
        q += " and k.created_at > :since"; params["since"] = since
    with store.engine.begin() as c:
        q += _scope_filter(_agent_scope(c, org_id, agent_id), params, eval_time)   # enforce agent scope
        q += " order by selected_rc.final_utility_bp desc, k.card_id"
        rows = [dict(r) for r in c.execute(text(q), params).mappings()]
        _meter(c, org_id, agent_id, "reads", _period(eval_time))
    return rows


def get_artifact(store, org_id: str, signal_id: str, agent_id: str, *, eval_time=None) -> dict | None:
    """GET /v1/signals/{id}/artifact — the pre-rendered draft (a DB read; pure margin by design)."""
    eval_time = eval_time or datetime.now(timezone.utc)
    params = {"o": org_id, "s": signal_id, "authority_time": eval_time}
    with store.engine.begin() as c:
        scope_sql = _scope_filter(_agent_scope(c, org_id, agent_id), params, eval_time)
        r = c.execute(text(
            "select k.artifact, k.headline, k.situation, k.render_mode from cards k "
            "join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
            + AUTHORITATIVE_SIGNAL_JOINS +
            " where k.org_id=:o and k.signal_id=:s "
            "and k.state in ('queued','surfaced','snoozed','claimed','delivered') "
            "and k.expires_at > :authority_time and s.status='open' and "
            + AUTHORITATIVE_SIGNAL_PREDICATE + scope_sql),   # enforce agent scope
            params).mappings().first()
        _meter(c, org_id, agent_id, "reads", _period(eval_time))
    return dict(r) if r else None


def claim(store, org_id: str, signal_id: str, agent_id: str, *, eval_time=None) -> dict:
    """POST /v1/signals/{id}/claim — lock 15 min. Double claim → 409 with holder + expiry (V-07)."""
    eval_time = eval_time or datetime.now(timezone.utc)
    with store.engine.begin() as c:
        # A successful claim is the authorization handed to an external executor. Keep both the
        # graph epoch and every row participating in the authority proof stable until that claim
        # and its card transition commit; otherwise a graph or pack revocation could land between
        # the SELECT and the grant.
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        claim_params = {"o": org_id, "s": signal_id, "authority_time": eval_time}
        scope_sql = _scope_filter(_agent_scope(c, org_id, agent_id), claim_params, eval_time)
        card = c.execute(text(
            "select k.card_id, k.state, k.expires_at, "
            "(rcap.manifest->'policies') ? 'human_approval_required' as approval_required "
            "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
            + AUTHORITATIVE_SIGNAL_JOINS +
            " where k.org_id=:o and k.signal_id=:s "
            "and k.state in ('queued','surfaced','snoozed','delivered','claimed') "
            "and k.expires_at > :authority_time and s.status='open' and "
            + AUTHORITATIVE_SIGNAL_PREDICATE + scope_sql +   # enforce agent scope before granting the lock
            " for update of k, s for share of rr, ro, selected_rc, rcap, authority_ctx, "
            "authority_cfg, authority_pack"),
            claim_params).mappings().first()
        if card is None:
            return {"ok": False, "status": 404, "error": "no_card"}
        if card["approval_required"]:
            return {"ok": False, "status": 403, "error": "human_approval_required"}
        expires = min(eval_time + timedelta(minutes=CLAIM_MINUTES), card["expires_at"])
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
        moved = c.execute(text(
            "update cards set state='claimed' where card_id=:c and org_id=:o and state in "
            "('queued','surfaced','snoozed','delivered','claimed')"),
            {"c": card["card_id"], "o": org_id})
        if moved.rowcount != 1:
            return {"ok": False, "status": 409, "error": "card_not_claimable"}
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
    if status not in {"done", "failed"}:
        return {"ok": False, "status": 422, "error": "invalid_result_status"}
    eval_time = eval_time or datetime.now(timezone.utc)
    encoded_detail = json.dumps(detail or {}, default=str)
    with store.engine.begin() as c:
        # A result is authority-bearing: only the agent holding this tenant's live claim may
        # submit one. Locking the claim first also makes duplicate/replayed result callbacks
        # deterministic instead of allowing one agent to release another agent's lock.
        claim_row = c.execute(text(
            "select card_id, expires_at, released_at, result from agent_claims "
            "where org_id=:o and signal_id=:s and agent_id=:a for update"),
            {"o": org_id, "s": signal_id, "a": agent_id}).mappings().first()
        if claim_row is None:
            return {"ok": False, "status": 403, "error": "claim_not_owned"}
        if claim_row["result"] is not None or claim_row["released_at"] is not None:
            return {"ok": True, "status": 200, "note": "result_already_recorded"}
        if claim_row["expires_at"] <= eval_time:
            return {"ok": False, "status": 409, "error": "claim_expired"}

        # Graph mutations take an exclusive lock on this tenant row while bumping the version.
        # Keep the shared lock until the result, card, signal and audit event commit together.
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        _meter(c, org_id, agent_id, "results", _period(eval_time))

        card = c.execute(text(
            "select k.card_id, k.state from cards k "
            "join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
            + AUTHORITATIVE_SIGNAL_JOINS +
            " where k.card_id=:card and k.org_id=:o and k.signal_id=:s "
            "and k.state='claimed' and k.expires_at > :authority_time "
            "and s.status='open' and " + AUTHORITATIVE_SIGNAL_PREDICATE +
            " for update of k, s for share of rr, ro, selected_rc, rcap, authority_ctx, "
            "authority_cfg, authority_pack"),
            {"card": claim_row["card_id"], "o": org_id, "s": signal_id,
             "authority_time": eval_time}).mappings().first()
        if card is None:
            # The agent may have performed the external action just before a human resolved the
            # card, a pack was revoked, the graph changed, or the decision expired. Preserve the
            # honest result on this agent's claim, but never let stale authority mutate L4/L5.
            c.execute(text(
                "update agent_claims set result=:r, result_detail=cast(:d as jsonb), "
                "released_at=:t where org_id=:o and signal_id=:s and agent_id=:a "),
                {"r": status, "d": encoded_detail, "t": eval_time, "o": org_id,
                 "s": signal_id, "a": agent_id})
            c.execute(text(
                "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
                "values (:id,:c,:o,'agent.result.late',:cause,:a,cast(:d as jsonb))"),
                {"id": new_id("cev"), "c": claim_row["card_id"], "o": org_id,
                 "cause": status, "a": agent_id, "d": encoded_detail})
            return {"ok": True, "status": 200, "note": "late_result_noop", "code": "V-08"}

        c.execute(text(
            "update agent_claims set result=:r, result_detail=cast(:d as jsonb), released_at=:t "
            "where org_id=:o and signal_id=:s and agent_id=:a and result is null "
            "and released_at is null"),
            {"r": status, "d": encoded_detail, "t": eval_time, "o": org_id,
             "s": signal_id, "a": agent_id})
        if status == "done":
            c.execute(text(
                "update cards set state='acted', resolved_at=:t where card_id=:c and org_id=:o "
                "and state='claimed'"),
                {"t": eval_time, "c": card["card_id"], "o": org_id})
            c.execute(text(
                "update signals set status='acted' where signal_id=:s and org_id=:o "
                "and status='open'"),
                {"s": signal_id, "o": org_id})
            kind, cause = "agent.result", "done"
        else:                                        # failed → re-surface to the human, keep open
            c.execute(text(
                "update cards set state='surfaced', snooze_until=null where card_id=:c "
                "and org_id=:o and state='claimed'"),
                {"c": card["card_id"], "o": org_id})
            kind, cause = "agent.result", "failed"
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
                       "values (:id,:c,:o,:k,:cause,:a,cast(:d as jsonb))"),
                  {"id": new_id("cev"), "c": card["card_id"], "o": org_id, "k": kind, "cause": cause, "a": agent_id,
                   "d": encoded_detail})
    return {"ok": True, "status": 200, "result": status}
