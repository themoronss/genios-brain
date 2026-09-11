from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import bindparam, text

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
              "and k.state in :refreshable and k.resolved_at is null")

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
                "returning claim_token").bindparams(bindparam("refreshable", expanding=True)),
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
                "and cards.state in :refreshable and cards.resolved_at is null "
                "returning card_id, (xmax = 0) as inserted").bindparams(
                    bindparam("refreshable", expanding=True)),
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
            self._stamp_recipients(c, card["org_id"], inserted.card_id,
                                   card.get("co_recipients") or (), owner=card.get("assignee"))
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
              record_impressions: bool = True, viewer: str | None = None) -> list[dict]:
        """Dashboard read. admin sees all queues (incl. unrouted); a member sees only their own.
        Ranked by score desc — the morning's cards in priority order (§5.13 scenario 10).

        `viewer` IS WHO IS LOOKING, and it is a different question from `assignee`.

        `assignee` and `admin` decide WHICH ROWS come back. `viewer` decides how they are
        ORDERED and what is stamped on them, and the two had been folded into one — with the
        consequence that every per-person feature was dead for the only person using the
        product. A founder signs in with an owner JWT, `sees_org_queue` is true, so the route
        passed `assignee=None`: correct for "show me everything", and it also meant their
        declared objective never reordered anything and no card could tell them why it was
        theirs. An org API key has no person behind it and resolves to no seat, so it keeps
        exactly the org-wide read it has.

        Defaults to `assignee` so every existing caller — the digest, the tests, the agent
        lane — behaves exactly as it did.
        """
        q = ("select k.card_id, k.signal_id, k.assignee, k.domain, k.urgency_band, k.headline, "
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
            # A SEAT SEES ITS OWN, THE UNCLAIMED, AND WHAT IT ANSWERS FOR. The third arm is a
            # LEFT-JOINLESS `exists` on purpose: on a tenant with no declarations the subquery
            # matches nothing and the queue is byte-identical to what it was.
            q += (" and (k.assignee=:a or k.assignee is null or exists ("
                  "select 1 from card_recipients cr where cr.org_id=k.org_id "
                  "and cr.card_id=k.card_id and cr.seat_id=:a))")
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
            # WHAT THIS PERSON IS WORKING ON, applied as ORDER and nothing else. A stable
            # partition — this viewer's objective domain first, then the rest — each half in the
            # utility order the SQL already produced. No score moves, nothing is removed, and two
            # viewers still see identical facts. See migration 0133 for why it must be a
            # partition and not a term.
            # WHO IS LOOKING, resolved once for both per-viewer passes. A seat id, an email or
            # nothing — an org-level key resolves to nothing and keeps the org-wide read.
            seat = self._viewer_seat(c, org_id, viewer if viewer is not None else assignee)
            rows = self._your_part(c, org_id, seat, rows)
            rows = self._objective_order(c, org_id, seat, rows)
            return rows

    #: What the History tab answers: every card somebody (or the world) already closed. `expired`
    #: also covers a card still sitting in an open state past its deadline — the sweep may simply
    #: not have run yet, and a card nobody can act on any more is history, not queue.
    HISTORY_STATES = ("acted", "resolved", "expired")
    OPEN_STATES = ("queued", "surfaced", "snoozed", "claimed", "delivered")

    #: Event kinds that describe what HAPPENED to a card, as opposed to it being shown. The newest
    #: one is the history row's "last action" line.
    _OUTCOME_KINDS = ("human.card_action", "ui.requeued", "agent.result", "human.override",
                      "success.detected", "window.lapsed", "card.dismissed")

    def history(self, org_id: str, *, assignee: str | None = None, admin: bool = False,
                states=HISTORY_STATES, since: datetime | None = None,
                limit: int = 50, offset: int = 0, eval_time=None) -> list[dict]:
        """Closed cards, newest first, each with the last thing that happened to it.

        Same visibility rule as `queue` (a member sees their own + unassigned). Unlike `queue` it
        does not require the Layer 4 authority to still be live: a decided card stays history even
        after the signal behind it is revoked, because what the user did about it still happened.
        """
        now = eval_time or datetime.now(timezone.utc)
        wanted = [s for s in states if s in self.HISTORY_STATES]
        if not wanted:
            return []
        clauses = []
        if "acted" in wanted:
            clauses.append("k.state = 'acted'")
        if "resolved" in wanted:
            clauses.append("k.state = 'resolved'")
        if "expired" in wanted:
            clauses.append("k.state = 'expired' "
                           "or (k.state = any(:open_states) and k.expires_at <= :now)")
        q = ("select * from (select k.card_id, k.signal_id, k.assignee, k.domain, k.urgency_band, "
             "k.headline, k.situation, k.score, "
             "case when k.state = any(:open_states) and k.expires_at <= :now then 'expired' "
             "else k.state end as state, "
             "k.created_at, k.expires_at, k.resolved_at, "
             "la.kind as last_event_kind, la.cause as last_action, la.actor_id as last_actor, "
             "la.detail as last_detail, la.occurred_at as last_event_at, "
             "coalesce(k.resolved_at, la.occurred_at, least(k.expires_at, :now)) as closed_at "
             "from cards k "
             "left join lateral (select ce.kind, ce.cause, ce.actor_id, ce.detail, ce.occurred_at "
             "  from card_events ce where ce.org_id = k.org_id and ce.card_id = k.card_id "
             "  and ce.kind = any(:outcome_kinds) "
             "  order by ce.occurred_at desc, ce.id desc limit 1) la on true "
             "where k.org_id = :o and 'app' = any(k.surfaces) "
             "and (" + " or ".join(f"({c})" for c in clauses) + ")")
        params = {"o": org_id, "now": now, "open_states": list(self.OPEN_STATES),
                  "outcome_kinds": list(self._OUTCOME_KINDS),
                  "limit": int(limit), "offset": int(offset)}
        if not admin and assignee is not None:
            q += " and (k.assignee = :a or k.assignee is null)"      # same rule as queue()
            params["a"] = assignee
        q += ") h"
        if since is not None:
            q += " where h.closed_at >= :since"
            params["since"] = since
        q += " order by h.closed_at desc, h.card_id limit :limit offset :offset"
        with self._engine.connect() as c:
            return [dict(r) for r in c.execute(text(q), params).mappings()]

    def timeline(self, org_id: str, card_id: str) -> list[dict]:
        """Every event on one card, oldest first. Tenant-scoped in SQL, not only by the caller."""
        with self._engine.connect() as c:
            return [dict(r) for r in c.execute(text(
                "select id, kind, cause, actor_id, detail, occurred_at from card_events "
                "where org_id = :o and card_id = :c order by occurred_at asc, id asc"),
                {"o": org_id, "c": card_id}).mappings()]

    @staticmethod
    def _viewer_seat(conn, org_id: str, viewer: str | None) -> str | None:
        """A credential's identity to an ACTIVE seat id, or None.

        A dashboard JWT carries the person's EMAIL as `actor_id`; a seat-scoped credential
        carries the seat id; an org key carries `org_primary_key`, which is nobody and must
        resolve to nobody. Fails to None: an unreadable seat table means the queue is ordered
        the way it always was, never that a card is hidden or mislabelled.
        """
        if not viewer:
            return None
        try:
            row = conn.execute(text(
                "select seat_id from org_seats where org_id=:o and active "
                "and (seat_id=:v or lower(email)=lower(:v)) limit 1"),
                {"o": org_id, "v": str(viewer)}).first()
        except Exception:      # noqa: BLE001 — see the docstring
            return None
        return row.seat_id if row is not None else None

    @staticmethod
    def _your_part(conn, org_id: str, seat: str | None, rows: list[dict]) -> list[dict]:
        """WHY THIS CARD IS ON THIS VIEWER'S QUEUE, when it is not theirs by ownership. A card a
        seat reaches through a declared responsibility carries `your_part` — the slice, the
        accountability, and who owns it — so "does this concern me" and "what stays with
        someone else" are answered on the row. Owned cards and unnamed viewers get nothing
        stamped. Fails to no stamps: an unreadable table hides no card and invents no reason."""
        if not seat or not rows:
            return rows
        try:
            from sqlalchemy import bindparam
            found = conn.execute(text(
                "select card_id, accountability, scope_kind, scope_key, owner_seat "
                "from card_recipients where org_id=:o and seat_id=:a and card_id in :ids"
            ).bindparams(bindparam("ids", expanding=True)),
                {"o": org_id, "a": seat, "ids": [r["card_id"] for r in rows]}).mappings().all()
        except Exception:      # noqa: BLE001 — see the docstring
            return rows
        parts = {f["card_id"]: {"accountability": f["accountability"],
                                "scope_kind": f["scope_kind"], "scope_key": f["scope_key"],
                                "owner_seat": f["owner_seat"]} for f in found}
        for r in rows:
            part = parts.get(r["card_id"])
            if part is not None and r.get("assignee") != seat:
                r["your_part"] = part
        return rows

    @staticmethod
    def _objective_order(conn, org_id: str, seat: str | None, rows: list[dict]) -> list[dict]:
        """Stable partition of a per-viewer queue by the viewer's declared objective domain.

        ONLY FOR A NAMED VIEWER. An admin reading the org queue and an org-level key have no
        person to hold an objective; their order is untouched. FAILS TO THE EXISTING ORDER on any
        read error — a preference table being unreadable must not reorder or lose a queue.
        """
        if not seat or not rows:
            return rows
        try:
            from datetime import datetime, timezone
            domain = conn.execute(text(
                "select o.domain from seat_objectives o "
                "join org_seats s on s.org_id = o.org_id and lower(s.email) = o.seat_key "
                "where o.org_id = :o and s.seat_id = :a and s.active "
                "and (o.valid_until is null or o.valid_until > :now) limit 1"),
                {"o": org_id, "a": seat, "now": datetime.now(timezone.utc)}).scalar()
        except Exception:      # noqa: BLE001 — a preference, never a reason to touch the queue
            return rows
        if not domain:
            return rows
        wanted = str(domain).strip().lower()
        first = [r for r in rows if str(r.get("domain") or "").strip().lower() == wanted]
        rest = [r for r in rows if str(r.get("domain") or "").strip().lower() != wanted]
        return first + rest

    @staticmethod
    def _stamp_recipients(conn, org_id: str, card_id: str, recipients, *, owner: str | None) -> int:
        """WHO ELSE ANSWERS FOR THIS CARD, rewritten with the card.

        A refresh recomputes them — a responsibility declared since the card was built reaches
        it on the next rebuild — so the previous set is replaced, not merged. The owner is never
        written as their own co-recipient. Empty in, empty table: a tenant that declared nothing
        gets exactly the rows it had, which is none.
        """
        if not recipients:
            # NOTHING TO SAY AND NOTHING TO CLEAR. The overwhelming majority of cards on every
            # tenant, and the reason this must not open a statement: a hermetic card test builds
            # its own three tables, and a DELETE against a table it never created would make
            # every such test depend on a feature it does not use.
            return 0
        conn.execute(text("delete from card_recipients where org_id=:o and card_id=:c"),
                     {"o": org_id, "c": card_id})
        written = 0
        for r in recipients:
            seat = str((r or {}).get("seat_id") or "").strip()
            if not seat or seat == owner:
                continue
            res = conn.execute(text(
                "insert into card_recipients (org_id, card_id, seat_id, accountability, "
                "scope_kind, scope_key, source, owner_seat) "
                "values (:o,:c,:s,:acc,:kind,:key,:src,:own) "
                "on conflict (org_id, card_id, seat_id) do nothing"),
                {"o": org_id, "c": card_id, "s": seat,
                 "acc": str(r.get("accountability") or "informed"),
                 "kind": str(r.get("scope_kind") or ""), "key": str(r.get("scope_key") or ""),
                 "src": str(r.get("source") or "admin_declared"), "own": owner})
            written += int(res.rowcount or 0)
        return written
