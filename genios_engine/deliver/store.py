from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id

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

    def insert_card(self, card: dict, copy: dict) -> str:
        """Persist a built+rendered card at state 'queued' (validators already green) + its
        card.created event, atomically. Returns card_id. Idempotent on signal_id."""
        card_id = new_id("card")
        with self._engine.begin() as c:
            exists = c.execute(text("select card_id from cards where signal_id=:s"),
                               {"s": card["signal_id"]}).first()
            if exists:
                return exists.card_id
            c.execute(text(
                "insert into cards (card_id, signal_id, org_id, assignee, domain, level, "
                "urgency_band, headline, situation, score, score_block, actions, why, "
                "context_tags, artifact, render_mode, config_snapshot_id, template_version, "
                "state, expires_at) values (:id,:sig,:o,:asg,:dom,:lvl,:band,:head,:sit,:score,"
                "cast(:sb as jsonb),cast(:act as jsonb),cast(:why as jsonb),:tags,"
                "cast(:art as jsonb),:rm,:cs,:tv,'queued',:exp)"),
                {"id": card_id, "sig": card["signal_id"], "o": card["org_id"],
                 "asg": card["assignee"], "dom": card["domain"], "lvl": card["level"],
                 "band": card["urgency_band"], "head": copy["headline"], "sit": copy["situation"],
                 "score": card["score"], "sb": json.dumps(card["score_block"], default=str),
                 "act": json.dumps(card["actions"], default=str),
                 "why": json.dumps(card["why"], default=str), "tags": card["context_tags"],
                 "art": json.dumps(copy["artifact"], default=str), "rm": copy["render_mode"],
                 "cs": card.get("config_snapshot_id"), "tv": card.get("template_version"),
                 "exp": card["expires_at"]})
            self.log_event(card_id, card["org_id"], "card.created",
                           cause=card.get("resolved_rule"),
                           detail={"band": card["urgency_band"], "render_mode": copy["render_mode"],
                                   "reject_code": copy.get("reject_code")}, conn=c)
        return card_id

    def transition(self, card_id, org_id, to_state, kind, *, cause=None, actor="system",
                   detail=None, snooze_until=None, resolved=False, allowed_from=None) -> bool:
        """State move. If `allowed_from` is given, the UPDATE is guarded on the current state so a
        TERMINAL card (acted/expired/resolved) can't be resurrected (e.g. a stale context-match
        flipping a done card back to 'surfaced'). Returns True only if a row actually changed."""
        with self._engine.begin() as c:
            sets = ["state=:st"]
            params = {"st": to_state, "id": card_id}
            if snooze_until is not None:
                sets.append("snooze_until=:su"); params["su"] = snooze_until
            if resolved:
                sets.append("resolved_at=now()")
            where = "card_id=:id"
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
                "returning card_id, org_id"), {"now": now}).fetchall()
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

    def get_by_signal(self, signal_id: str) -> dict | None:
        with self._engine.connect() as c:
            r = c.execute(text("select * from cards where signal_id=:s"),
                          {"s": signal_id}).mappings().first()
        return dict(r) if r else None

    def queue(self, org_id: str, *, assignee: str | None = None, admin: bool = False,
              states=("queued", "surfaced", "snoozed", "claimed")) -> list[dict]:
        """Dashboard read. admin sees all queues (incl. unrouted); a member sees only their own.
        Ranked by score desc — the morning's cards in priority order (§5.13 scenario 10)."""
        q = ("select card_id, signal_id, assignee, urgency_band, headline, situation, score, "
             "state, render_mode, created_at, expires_at from cards "
             "where org_id=:o and state = any(:states)")
        params = {"o": org_id, "states": list(states)}
        if not admin:
            q += " and assignee=:a"
            params["a"] = assignee
        q += " order by score desc, created_at asc"
        with self._engine.connect() as c:
            return [dict(r) for r in c.execute(text(q), params).mappings()]
