from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    authority_time,
)

# CardStore — persistence + the queue state machine (§5.12). Every transition writes a timestamped
# card_event with an enumerated cause; nothing moves without one. One card per signal (enforced by
# a unique index — a re-run never double-delivers).


class CardStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    @property
    def engine(self):
        return self._engine

    def has_card(self, signal_id: str) -> bool:
        with self._engine.connect() as c:
            return c.execute(text("select 1 from cards where signal_id=:s"),
                             {"s": signal_id}).first() is not None

    def claim_build(self, org_id: str, signal_id: str, *, eval_time=None,
                    lease_minutes: int = 15) -> str | None:
        """Claim the expensive render step without holding a database lock across the LLM call."""
        if isinstance(lease_minutes, bool) or not isinstance(lease_minutes, int) \
                or not 1 <= lease_minutes <= 60:
            raise ValueError("lease_minutes must be between 1 and 60")
        now = authority_time(eval_time)
        token = new_id("cbuild")
        with self._engine.begin() as c:
            row = c.execute(text(
                "insert into card_build_claims "
                "(signal_id,org_id,claim_token,claimed_at,expires_at) "
                "select s.signal_id,s.org_id,:token,:now,:expires from signals s "
                "where s.signal_id=:signal and s.org_id=:o "
                "and not exists (select 1 from cards k where k.signal_id=s.signal_id) "
                "on conflict (signal_id) do update set "
                "claim_token=excluded.claim_token,claimed_at=excluded.claimed_at,"
                "expires_at=excluded.expires_at "
                "where card_build_claims.org_id=excluded.org_id "
                "and card_build_claims.expires_at<=:now "
                "and not exists (select 1 from cards k where k.signal_id=excluded.signal_id) "
                "returning claim_token"),
                {"token": token, "now": now, "expires": now + timedelta(minutes=lease_minutes),
                 "signal": signal_id, "o": org_id}).first()
        return token if row is not None and row.claim_token == token else None

    def release_build(self, org_id: str, signal_id: str, claim_token: str) -> bool:
        """Release only the caller's lease; an expired successor can never be deleted by it."""
        with self._engine.begin() as c:
            result = c.execute(text(
                "delete from card_build_claims where org_id=:o and signal_id=:signal "
                "and claim_token=:token"),
                {"o": org_id, "signal": signal_id, "token": claim_token})
        return bool(result.rowcount)

    def log_event(self, card_id, org_id, kind, *, cause=None, actor="system", detail=None, conn=None):
        row = {"id": new_id("cev"), "cid": card_id, "o": org_id, "k": kind, "cause": cause,
               "a": actor, "d": json.dumps(detail or {}, default=str)}
        sql = text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
                   "values (:id,:cid,:o,:k,:cause,:a,cast(:d as jsonb))")
        if conn is not None:
            conn.execute(sql, row)
        else:
            with self._engine.begin() as c:
                c.execute(sql, row)

    def insert_card(self, card: dict, copy: dict, *,
                    build_claim_token: str) -> tuple[str | None, bool]:
        """Persist a built+rendered card at state 'queued' (validators already green) + its
        card.created event, atomically. Returns ``(card_id, created)``. Idempotent and race-safe
        on signal_id; only the transaction that inserted the row may render/push it as new."""
        card_id = new_id("card")
        with self._engine.begin() as c:
            as_of = authority_time(card.get("_authority_time"))
            lease = c.execute(text(
                "select 1 from card_build_claims where org_id=:o and signal_id=:signal "
                "and claim_token=:token and expires_at>:authority_time for update"),
                {"o": card["org_id"], "signal": card["signal_id"],
                 "token": build_claim_token, "authority_time": as_of}).first()
            if lease is None:
                return None, False
            authority = card.get("_authority") or {}
            if authority:
                c.execute(text(
                    "select graph_version from graph_versions where org_id=:o for share"),
                    {"o": card["org_id"]})
                held = c.execute(text(
                    "select 1 from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
                    " where s.org_id=:o and s.signal_id=:signal and s.status='open' "
                    "and s.reasoning_run_id=:run and s.reasoning_candidate_id=:candidate "
                    "and s.reasoning_decision_hash=:decision and s.config_snapshot_id=:cfg "
                    "and " + AUTHORITATIVE_SIGNAL_PREDICATE +
                    " for share of s, rr, ro, selected_rc, rcap, authority_ctx, "
                    "authority_cfg, authority_pack"),
                    {"o": card["org_id"], "signal": card["signal_id"],
                     "run": authority.get("reasoning_run_id"),
                     "candidate": authority.get("reasoning_candidate_id"),
                     "decision": authority.get("reasoning_decision_hash"),
                     "cfg": authority.get("config_snapshot_id"),
                     "authority_time": as_of}).first()
                if held is None:
                    return None, False
            inserted = c.execute(text(
                "insert into cards (card_id, signal_id, org_id, execution_id, assignee, domain, level, "
                "urgency_band, headline, situation, score, score_block, actions, why, "
                "context_tags, artifact, render_mode, config_snapshot_id, template_version, "
                "state, expires_at) values (:id,:sig,:o,:execution,:asg,:dom,:lvl,:band,:head,:sit,:score,"
                "cast(:sb as jsonb),cast(:act as jsonb),cast(:why as jsonb),:tags,"
                "cast(:art as jsonb),:rm,:cs,:tv,'queued',:exp) "
                "on conflict (signal_id) do nothing returning card_id"),
                {"id": card_id, "sig": card["signal_id"], "o": card["org_id"],
                 "execution": card.get("_execution_id"),
                 "asg": card["assignee"], "dom": card["domain"], "lvl": card["level"],
                 "band": card["urgency_band"], "head": copy["headline"], "sit": copy["situation"],
                 "score": card["score"], "sb": json.dumps(card["score_block"], default=str),
                 "act": json.dumps(card["actions"], default=str),
                 "why": json.dumps(card["why"], default=str), "tags": card["context_tags"],
                 "art": json.dumps(copy["artifact"], default=str), "rm": copy["render_mode"],
                 "cs": card.get("config_snapshot_id"), "tv": card.get("template_version"),
                 "exp": card["expires_at"]}).first()
            if inserted is None:
                winner = c.execute(text(
                    "select card_id from cards where signal_id=:s and org_id=:o"),
                    {"s": card["signal_id"], "o": card["org_id"]}).first()
                return (winner.card_id if winner is not None else None), False
            self.log_event(card_id, card["org_id"], "card.created",
                           cause=card.get("resolved_rule"),
                           detail={"band": card["urgency_band"], "render_mode": copy["render_mode"],
                                   "reject_code": copy.get("reject_code")}, conn=c)
        return card_id, True

    def transition(self, card_id, org_id, to_state, kind, *, cause=None, actor="system",
                   detail=None, snooze_until=None, resolved=False, allowed_from=None) -> bool:
        """State move. If `allowed_from` is given, the UPDATE is guarded on the current state so a
        TERMINAL card (acted/expired/resolved) can't be resurrected (e.g. a stale context-match
        flipping a done card back to 'surfaced'). Returns True only if a row actually changed."""
        with self._engine.begin() as c:
            sets = ["state=:st"]
            params = {"st": to_state, "id": card_id, "o": org_id}
            if snooze_until is not None:
                sets.append("snooze_until=:su"); params["su"] = snooze_until
            if resolved:
                sets.append("resolved_at=now()")
            where = "card_id=:id and org_id=:o"
            if allowed_from is not None:
                where += " and state = any(:from_states)"
                params["from_states"] = list(allowed_from)
            res = c.execute(text(f"update cards set {', '.join(sets)} where {where}"), params)
            if res.rowcount == 0:
                return False                     # guarded no-op — nothing to log, no resurrection
            self.log_event(card_id, org_id, kind, cause=cause, actor=actor, detail=detail, conn=c)
            return True

    def sweep_lifecycle(self, *, eval_time=None) -> dict:
        """Cron tick (in-process, no Celery). Two transitions the queue otherwise never makes:
          • expire non-terminal cards past expires_at → 'expired' (feeds L6's ignore-rate)
          • wake snoozed cards past snooze_until → 'queued' (snooze was a black hole)."""
        now = eval_time or datetime.now(timezone.utc)
        with self._engine.begin() as c:
            expired = c.execute(text(
                "update cards set state='expired' where state in ('queued','surfaced','snoozed') "
                "and expires_at < :now returning card_id, org_id"), {"now": now}).fetchall()
            for r in expired:
                self.log_event(r.card_id, r.org_id, "window.lapsed", cause="expired", conn=c)
            woken = c.execute(text(
                "update cards set state='queued', snooze_until=null where state='snoozed' "
                "and snooze_until is not null and snooze_until <= :now "
                "returning card_id, signal_id, org_id"), {"now": now}).fetchall()
            if woken:
                c.execute(text(
                    "update signals set status='open' where signal_id=any(:ids) "
                    "and status='snoozed'"),
                    {"ids": [row.signal_id for row in woken]})
            for r in woken:
                self.log_event(r.card_id, r.org_id, "card.snooze_wake", cause="woke", conn=c)
            # an abandoned 15-min agent claim (§5.16): release the lock and RE-SURFACE the card to
            # the human — otherwise a claimed card is invisible (poll excludes it) until someone
            # happens to open it.
            released = c.execute(text(
                "update cards set state='surfaced' from agent_claims ac where cards.card_id=ac.card_id "
                "and cards.state='claimed' and ac.released_at is null and ac.result is null "
                "and ac.expires_at < :now returning cards.card_id, cards.org_id"),
                {"now": now}).fetchall()
            if released:
                c.execute(text("update agent_claims set released_at=:now where released_at is null "
                               "and result is null and expires_at < :now"), {"now": now})
            for r in released:
                self.log_event(r.card_id, r.org_id, "card.surfaced", cause="claim_expiry", conn=c)
        return {"expired": len(expired), "woken": len(woken), "claims_released": len(released)}

    def get_card(self, card_id: str) -> dict | None:
        with self._engine.connect() as c:
            r = c.execute(text("select * from cards where card_id=:id"), {"id": card_id}).mappings().first()
        return dict(r) if r else None

    def get_authoritative_card(self, card_id: str, org_id: str, *, eval_time=None) -> dict | None:
        """Return a card only while its exact Layer 4 winner remains authoritative."""
        now = authority_time(eval_time)
        with self._engine.connect() as c:
            r = c.execute(text(
                "select k.* from cards k join signals s on s.signal_id=k.signal_id "
                "and s.org_id=k.org_id " + AUTHORITATIVE_SIGNAL_JOINS +
                " where k.card_id=:id and k.org_id=:o and s.status='open' "
                "and k.state in ('queued','surfaced','snoozed','claimed','delivered') "
                "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE),
                {"id": card_id, "o": org_id, "authority_time": now}).mappings().first()
        return dict(r) if r else None

    def get_by_signal(self, signal_id: str) -> dict | None:
        with self._engine.connect() as c:
            r = c.execute(text("select * from cards where signal_id=:s"),
                          {"s": signal_id}).mappings().first()
        return dict(r) if r else None

    def surface_context_match(self, org_id: str, card_id: str, matched_tag: str,
                              *, actor_id: str, allow_any_assignee: bool = False,
                              eval_time=None) -> dict:
        """Atomically authorize a page match, move the card and record its impression."""
        now = authority_time(eval_time)
        with self._engine.begin() as c:
            c.execute(text(
                "select graph_version from graph_versions where org_id=:o for share"),
                {"o": org_id})
            card = c.execute(text(
                "select k.assignee,k.context_tags,k.state from cards k join signals s "
                "on s.signal_id=k.signal_id and s.org_id=k.org_id " +
                AUTHORITATIVE_SIGNAL_JOINS +
                "where k.org_id=:o and k.card_id=:card and s.status='open' "
                "and k.expires_at>:authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE +
                " for update of k,s for share of rr,ro,selected_rc,rcap,authority_ctx,"
                "authority_cfg,authority_pack"),
                {"o": org_id, "card": card_id, "authority_time": now}).mappings().first()
            if card is None:
                return {"ok": False, "error": "stale_or_unauthorized_card"}
            if (not allow_any_assignee and card["assignee"] is not None
                    and card["assignee"] != actor_id):
                return {"ok": False, "error": "assigned_to_different_seat"}
            if matched_tag not in (card["context_tags"] or []):
                return {"ok": False, "error": "invalid_context_tag"}
            if card["state"] not in ("queued", "snoozed", "surfaced"):
                return {"ok": True, "surfaced": False, "card_id": card_id}
            c.execute(text(
                "update cards set state='surfaced' where org_id=:o and card_id=:card"),
                {"o": org_id, "card": card_id})
            self.log_event(card_id, org_id, "card.surfaced", cause="context_match",
                           actor=actor_id, detail={"tag": matched_tag}, conn=c)
        return {"ok": True, "surfaced": True, "card_id": card_id}

    def queue(self, org_id: str, *, assignee: str | None = None, admin: bool = False,
              states=("queued", "surfaced", "snoozed", "claimed"),
              record_impressions: bool = True) -> list[dict]:
        """Dashboard read. admin sees all queues (incl. unrouted); a member sees only their own.
        Ranked by score desc — the morning's cards in priority order (§5.13 scenario 10)."""
        q = ("select k.card_id, k.signal_id, k.assignee, k.urgency_band, k.headline, "
             "k.situation, " + AUTHORITATIVE_SCORE_SQL +
             " as score, k.state, k.render_mode, k.created_at, k.expires_at "
             "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
             + AUTHORITATIVE_SIGNAL_JOINS +
             " where k.org_id=:o and k.state = any(:states) and s.status='open' "
             "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE)
        params = {"o": org_id, "states": list(states),
                  "authority_time": datetime.now(timezone.utc)}
        if not admin:
            q += " and k.assignee=:a"
            params["a"] = assignee
        q += (" order by selected_rc.final_utility_bp desc, k.created_at asc, k.card_id "
              "for share of k,s,rr,ro,selected_rc,rcap,authority_ctx,authority_cfg,authority_pack")
        with self._engine.begin() as c:
            # Impression and the exact authority projection it describes share one transaction.
            # Graph/config writers and card claims cannot interleave a revocation after SELECT but
            # before the learning event.
            c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                      {"o": org_id})
            rows = [dict(r) for r in c.execute(text(q), params).mappings()]
            if rows and record_impressions:
                c.execute(text(
                    "insert into card_events (id,card_id,org_id,kind,cause,actor_id) "
                    "select 'cevs_' || k.card_id,k.card_id,:o,'card.surfaced','dashboard','dashboard' "
                    "from cards k where k.org_id=:o and k.card_id=any(:ids) "
                    "and not exists (select 1 from card_events ce where ce.org_id=k.org_id "
                    "and ce.card_id=k.card_id and ce.kind='card.surfaced') "
                    "on conflict do nothing"),
                    {"o": org_id, "ids": [row["card_id"] for row in rows]})
            return rows
