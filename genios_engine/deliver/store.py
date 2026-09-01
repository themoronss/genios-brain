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

    #: A card is REFRESHABLE only from a state the user has not touched.
    #:
    #: `snoozed`, `claimed`, `acted` and `resolved` all record a human decision about this exact
    #: card, and rewriting the words underneath one of those is not an improvement — it is
    #: changing what somebody already answered. A card still sitting in the queue has been
    #: decided about by nobody, so replacing weak copy with better copy costs nothing.
    REFRESHABLE_STATES = ("built", "queued", "surfaced")

    #: The staleness test, shared by the claim and the upsert so the two can never disagree about
    #: which cards may be rewritten. `is distinct from` rather than `<>` because the column is
    #: NULL on every card built before it existed, and those are exactly the stale ones.
    _STALE = ("k.builder_version is distinct from :builder "
              "and k.state = any(:refreshable) and k.resolved_at is null")

    def claim_build(self, org_id: str, signal_id: str, *, eval_time=None,
                    lease_minutes: int = 15, builder_version: str | None = None) -> str | None:
        """Claim the expensive render step without holding a database lock across the LLM call.

        Claims a signal with NO card, or one whose card was composed by an older builder and is
        still untouched. Without the second case every upstream improvement — a wider slot
        vocabulary, better authored copy, a fixed prompt — was invisible on every card that
        already existed, which is every card a real tenant has.
        """
        if isinstance(lease_minutes, bool) or not isinstance(lease_minutes, int) \
                or not 1 <= lease_minutes <= 60:
            raise ValueError("lease_minutes must be between 1 and 60")
        now = authority_time(eval_time)
        token = new_id("cbuild")
        # `not exists (no card)` OR `exists (a stale, untouched card)` — spelled as one NOT EXISTS
        # over the cards that BLOCK a claim, so the two branches cannot drift apart.
        blocked = ("not exists (select 1 from cards k where k.signal_id=%s "
                   "and not (" + self._STALE + "))")
        with self._engine.begin() as c:
            row = c.execute(text(
                "insert into card_build_claims "
                "(signal_id,org_id,claim_token,claimed_at,expires_at) "
                "select s.signal_id,s.org_id,:token,:now,:expires from signals s "
                "where s.signal_id=:signal and s.org_id=:o "
                "and " + (blocked % "s.signal_id") + " "
                "on conflict (signal_id) do update set "
                "claim_token=excluded.claim_token,claimed_at=excluded.claimed_at,"
                "expires_at=excluded.expires_at "
                "where card_build_claims.org_id=excluded.org_id "
                "and card_build_claims.expires_at<=:now "
                "and " + (blocked % "excluded.signal_id") + " "
                "returning claim_token"),
                {"token": token, "now": now, "expires": now + timedelta(minutes=lease_minutes),
                 "signal": signal_id, "o": org_id,
                 "builder": builder_version,
                 "refreshable": list(self.REFRESHABLE_STATES)}).first()
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
                    build_claim_token: str) -> tuple[str | None, bool, bool]:
        """Persist a built+rendered card at state 'queued' (validators already green) + its
        card.created event, atomically. Returns ``(card_id, created, refreshed)``.

        Idempotent and race-safe on signal_id; only the transaction that INSERTED the row may
        render/push it as new. A card that already exists and is stale (older builder, untouched
        by the user) is rewritten IN PLACE — same `card_id`, same queue state, same snooze and
        feedback history — and reported as ``refreshed`` rather than ``created``, because
        improving the words on a card the user has already been shown is not a new notification
        and must never be pushed as one."""
        card_id = new_id("card")
        with self._engine.begin() as c:
            as_of = authority_time(card.get("_authority_time"))
            lease = c.execute(text(
                "select 1 from card_build_claims where org_id=:o and signal_id=:signal "
                "and claim_token=:token and expires_at>:authority_time for update"),
                {"o": card["org_id"], "signal": card["signal_id"],
                 "token": build_claim_token, "authority_time": as_of}).first()
            if lease is None:
                return None, False, False
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
                    return None, False, False
            inserted = c.execute(text(
                "insert into cards (card_id, signal_id, org_id, assignee, domain, level, "
                "urgency_band, headline, situation, score, score_block, actions, why, "
                "context_tags, artifact, render_mode, config_snapshot_id, template_version, "
                "reject_code, reject_detail, abstained_because, "
                # the Customer Intelligence Contract — six answers that had nowhere to land
                "business_subject, relationship_role, unresolved_item, why_now, "
                "capability_key, capability_version, capability_review_state, "
                "outcome_window_days, success_signal, do_nothing_consequence, "
                "confidence_vector, surfaces, builder_version, "
                "state, expires_at) values (:id,:sig,:o,:asg,:dom,:lvl,:band,:head,:sit,:score,"
                "cast(:sb as jsonb),cast(:act as jsonb),cast(:why as jsonb),:tags,"
                "cast(:art as jsonb),:rm,:cs,:tv,:rjc,:rjd,:abst,"
                ":bsub,:brole,:bitem,:bwhy,:ckey,:cver,:crev,:owin,:osig,:odnc,"
                "cast(:cvec as jsonb),:surf,:bver,'queued',:exp) "
                # PRESENTATION ONLY. `state`, `created_at`, `snooze_until`, `resolved_at` and
                # `expires_at` are the user's side of the row and are never touched here: a
                # refresh improves what the card SAYS, never where it sits or what was decided
                # about it. The guard repeats `_STALE` against the held row so a concurrent
                # writer that already refreshed it cannot be overwritten by a slower one.
                "on conflict (signal_id) do update set "
                "assignee=excluded.assignee, domain=excluded.domain, level=excluded.level, "
                "urgency_band=excluded.urgency_band, headline=excluded.headline, "
                "situation=excluded.situation, score=excluded.score, "
                "score_block=excluded.score_block, actions=excluded.actions, "
                "why=excluded.why, context_tags=excluded.context_tags, "
                "artifact=excluded.artifact, render_mode=excluded.render_mode, "
                "config_snapshot_id=excluded.config_snapshot_id, "
                "template_version=excluded.template_version, reject_code=excluded.reject_code, "
                "reject_detail=excluded.reject_detail, "
                "abstained_because=excluded.abstained_because, "
                "business_subject=excluded.business_subject, "
                "relationship_role=excluded.relationship_role, "
                "unresolved_item=excluded.unresolved_item, why_now=excluded.why_now, "
                "capability_key=excluded.capability_key, "
                "capability_version=excluded.capability_version, "
                "capability_review_state=excluded.capability_review_state, "
                "outcome_window_days=excluded.outcome_window_days, "
                "success_signal=excluded.success_signal, "
                "do_nothing_consequence=excluded.do_nothing_consequence, "
                "confidence_vector=excluded.confidence_vector, surfaces=excluded.surfaces, "
                "builder_version=excluded.builder_version "
                "where cards.builder_version is distinct from excluded.builder_version "
                "and cards.state = any(:refreshable) and cards.resolved_at is null "
                "returning card_id, (xmax = 0) as inserted"),
                {"id": card_id, "sig": card["signal_id"], "o": card["org_id"],
                 "asg": card["assignee"], "dom": card["domain"], "lvl": card["level"],
                 "band": card["urgency_band"], "head": copy["headline"], "sit": copy["situation"],
                 "score": card["score"], "sb": json.dumps(card["score_block"], default=str),
                 "act": json.dumps(card["actions"], default=str),
                 "why": json.dumps(card["why"], default=str), "tags": card["context_tags"],
                 "art": json.dumps(copy["artifact"], default=str), "rm": copy["render_mode"],
                 "cs": card.get("config_snapshot_id"), "tv": card.get("template_version"),
                 # Provenance for the fallback: which validator refused the draft, and on what.
                 "rjc": copy.get("reject_code"), "rjd": copy.get("reject_detail"),
                 "bsub": card.get("business_subject"),
                 "brole": card.get("relationship_role"),
                 "bitem": card.get("unresolved_item"),
                 "bwhy": card.get("why_now"),
                 "ckey": card.get("capability_key"),
                 "cver": card.get("capability_version"),
                 "crev": card.get("capability_review_state"),
                 "owin": card.get("outcome_window_days"),
                 "osig": card.get("success_signal"),
                 "odnc": card.get("do_nothing_consequence"),
                 "cvec": json.dumps(card.get("confidence_vector") or {}, default=str),
                 # Default to all four when the builder did not decide, so a caller that predates
                 # surface-awareness keeps today's behaviour instead of silently vanishing.
                 "surf": card.get("surfaces") or ["app", "agent", "ask", "api"],
                 # why this card declines to instruct, or NULL when it does
                 "abst": card.get("abstained_because"),
                 "bver": card.get("builder_version"),
                 "refreshable": list(self.REFRESHABLE_STATES),
                 "exp": card["expires_at"]}).first()
            if inserted is None:
                # The DO UPDATE's WHERE refused: a card exists and is NOT stale — either the
                # user has acted on it, or another writer already refreshed it to this builder.
                winner = c.execute(text(
                    "select card_id from cards where signal_id=:s and org_id=:o"),
                    {"s": card["signal_id"], "o": card["org_id"]}).first()
                return (winner.card_id if winner is not None else None), False, False
            detail = {"band": card["urgency_band"], "render_mode": copy["render_mode"],
                      "reject_code": copy.get("reject_code"),
                      # the offending token was computed and discarded; a 90% fallback rate is
                      # not diagnosable without it
                      "reject_detail": copy.get("reject_detail")}
            if not inserted.inserted:
                # The row already existed and carried an older builder. Its identity is the HELD
                # card_id, not the one minted above — returning the fresh id would name a row
                # that was never written.
                self.log_event(inserted.card_id, card["org_id"], "card.rebuilt",
                               cause=card.get("resolved_rule"),
                               detail={**detail, "builder_version": card.get("builder_version")},
                               conn=c)
                return inserted.card_id, False, True
            self.log_event(card_id, card["org_id"], "card.created",
                           cause=card.get("resolved_rule"), detail=detail, conn=c)
        return card_id, True, False

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
                # The signal's decision columns (0070) ride along: the projection layer reads
                # THEM for its recommendation instead of re-deriving one from the reason_code
                # string, and the signals row is already in this join.
                "select k.*, s.candidate_steps, s.rejected_candidates, "
                "s.uncertainty as decision_uncertainty "
                "from cards k join signals s on s.signal_id=k.signal_id "
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
             # The APP surface, not every card the org holds. A rejected deal past its deadline
             # still answers "what happened with Antler?" — it just does not belong in a queue
             # whose only honest measure is whether the reader acts on every line.
             " where k.org_id=:o and k.state = any(:states) and s.status='open' "
             "and 'app' = any(k.surfaces) "
             "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE)
        params = {"o": org_id, "states": list(states),
                  "authority_time": datetime.now(timezone.utc)}
        if not admin and assignee is not None:
            # A seat- or agent-bound credential sees loops routed to IT plus the org's UNCLAIMED
            # loops (assignee null) — an unassigned open loop belongs to whoever picks it up.
            #
            # `assignee is not None` is load-bearing. The comment here used to promise that "a
            # single-seat app connecting with a scoped key still sees the org's queue, not
            # nothing", and the code delivered the opposite: an org-level API key has no personal
            # identity, so :a bound to NULL, `k.assignee = NULL` is never true, and the fallback
            # `k.assignee is null` matched nothing because L5 routes every card to a seat. The
            # desktop app read an empty queue for as long as it has existed. A caller with no
            # person to filter by must not be filtered to a person.
            q += " and (k.assignee=:a or k.assignee is null)"
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
