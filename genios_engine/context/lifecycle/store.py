"""L2.7.7-U1 · the SQL seam — what the detector reads, and the ledger it writes.

Everything with a database in it lives here, so that `gate.py`, `judge.py` and `ledger.py` stay
pure functions over values: they are the parts whose behaviour a golden set has to be able to
replay, and a unit that opens its own connection cannot be replayed at all.

FOUR READS, EACH BOUNDED:

* `situations_to_examine` — the ACTIVE situations plus the ones THIS unit closed from a
  statement (a closed situation is the only place a contradiction can land, and doc 07's failure
  mode 5 requires the contradiction to reach it). Carries `deal.stage` on the anchor so
  `terminal_by_fact` is decided in the same read rather than by a second query per situation.
* `unexamined_messages` — member events with no claim row yet, newest first, inside a lookback
  window. The claim row IS the cache; "already examined" and "already paid for" are the same
  fact, which is why even a rejection is stored.
* `obligations_for` — the commitment NODES this situation's own events created, with the owner's
  address off the `owns` edge. This is what `scope` names and what the speaker-authority table
  needs to know whether the sender is the owner.
* `calls_today` — the two ceilings doc 11 sets, counted off this table.

THE LOOKBACK IS A DELIBERATE FLOOR ON WHAT WE WILL READ. Without it, the first drain after this
unit ships would treat eighteen months of every active situation's mail as "new" — the caps would
bound the spend, but they would spend it on the oldest messages in the org, which are the least
likely to contain a resolution and the most likely to be about something already settled. A
statement made more than `LOOKBACK_DAYS` ago and never noticed is out of this unit's reach by
design; the situation's own dormancy rules are what handle it.

THE PER-ORG CEILING IS COUNTED OFF THIS SITE'S OWN LEDGER, and that is a FLOOR on the truth
rather than the whole of it: doc 11's 200/day is a budget for all of L2's model calls, and no
shared per-org call ledger exists in this repo yet. Counting M-4's own rows is correct in the
only direction that matters (this site can never exceed the whole budget by itself) and it is
honest about what it is not. Flagged as **A-19** in `docs/plans/L2_MISSING_UNIT_SPECS.md` §3.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import text

from genios_engine.context.lifecycle.contract import Obligation, ResolutionClaim
from genios_engine.context.situations import (
    RESOLVED_BY_STATEMENT,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_PARTIALLY_RESOLVED,
    STATUS_RESOLVED,
)
from genios_engine.platform.ids import new_id

__all__ = ["LOOKBACK_DAYS", "MAX_MESSAGES_PER_SWEEP", "SituationRow", "apply_lifecycle",
           "claims_for", "calls_today", "decide_review", "extraction_outputs",
           "obligations_for", "pending_reviews", "situations_to_examine",
           "unexamined_messages", "write_claim"]

#: How far back a message may be and still be read for a stated resolution. Deliberately shorter
#: than `situations.DORMANT_AFTER_DAYS` (45): a situation that has been silent longer than this
#: is on its way to dormant anyway, and re-reading its history would spend the budget on the
#: least likely place for a resolution to be.
LOOKBACK_DAYS = 30

#: The per-sweep read ceiling, before the per-situation and per-org call ceilings apply. A bound
#: on the QUERY as well as on the spend: an org with 400 active situations must not pull every
#: unexamined message in one round trip to then discard most of them at the gate.
MAX_MESSAGES_PER_SWEEP = 500


class SituationRow:
    """One situation as the detector needs it — status, provenance, and its terminal fact."""

    __slots__ = ("situation_id", "correlation_id", "anchor_node_id", "status", "resolved_by",
                 "resolved_at", "last_seen_at", "deal_stage")

    def __init__(self, *, situation_id: str, correlation_id: str, anchor_node_id: str,
                 status: str | None, resolved_by: str | None, resolved_at, last_seen_at,
                 deal_stage) -> None:
        self.situation_id = situation_id
        self.correlation_id = correlation_id
        self.anchor_node_id = anchor_node_id
        self.status = status
        self.resolved_by = resolved_by
        self.resolved_at = resolved_at
        self.last_seen_at = last_seen_at
        self.deal_stage = deal_stage


def situations_to_examine(conn, org_id: str) -> list[SituationRow]:
    """Every situation a statement could still move, with the deal stage that would outrank one.

    The `left join` onto `graph_facts` is what makes `terminal_by_fact` a property of the row: a
    situation whose CRM already says closed-won is refused at the gate without a second query,
    and it is refused for every message on it, which on a noisy congratulations thread is the
    difference between zero calls and a dozen.
    """
    # The three state words are interpolated from `situations.py` rather than typed as SQL
    # literals: they are the same vocabulary `decide_lifecycle` writes, and two spellings of
    # "partial" would make this query quietly stop finding the rows this unit itself produced.
    rows = conn.execute(text(
        "select s.situation_id, s.correlation_id, s.anchor_node_id, s.status, s.resolved_by, "
        "       s.resolved_at, s.last_seen_at, f.value as deal_stage "
        "from context_situations s "
        "left join graph_facts f on f.org_id = s.org_id "
        "     and f.subject_node_id = s.anchor_node_id and f.field = 'deal.stage' "
        "     and f.valid_to is null and f.status = 'active' "
        # ARCHIVED IS IN THE SET, and leaving it out made dead code of a branch that names it.
        #
        # `decide_lifecycle`'s reopen arm lists STATUS_ARCHIVED explicitly (situations.py:549) —
        # "the claim that closed it no longer stands, contradicted or withdrawn". This query is
        # the only thing that feeds that arm, and it selected `resolved` and `partial` only. So a
        # statement-resolved situation that reached 180 days was archived and became permanently
        # unreachable to the contradiction path: the counterparty could say "actually that never
        # happened" and nothing could reopen it, ever.
        #
        # SCOPED TO STATEMENT RESOLUTIONS, exactly as the two statuses beside it are. An archived
        # row that a HUMAN closed, or one that aged out of `active`, is not pulled in — this adds
        # the third status to a filter that was already asking "did a CLAIM close this?", and
        # nothing else.
        "where s.org_id = :o and (s.status = :active "
        "      or (s.status in (:resolved, :partial, :archived) "
        "          and s.resolved_by = :by_statement))"),
        {"o": org_id, "active": STATUS_ACTIVE, "resolved": STATUS_RESOLVED,
         "partial": STATUS_PARTIALLY_RESOLVED, "archived": STATUS_ARCHIVED,
         "by_statement": RESOLVED_BY_STATEMENT}).mappings().all()
    return [SituationRow(situation_id=r["situation_id"], correlation_id=r["correlation_id"],
                         anchor_node_id=r["anchor_node_id"], status=r["status"],
                         resolved_by=r["resolved_by"], resolved_at=r["resolved_at"],
                         last_seen_at=r["last_seen_at"], deal_stage=r["deal_stage"])
            for r in rows]


def unexamined_messages(conn, org_id: str, correlation_ids: Sequence[str], *,
                        eval_time: datetime, lookback_days: int = LOOKBACK_DAYS,
                        limit: int = MAX_MESSAGES_PER_SWEEP) -> list[dict]:
    """Member events this unit has not judged yet, newest first.

    NEWEST FIRST is the budget's ordering and it is the right one twice over: a resolution is
    most likely to be in the latest message, and `ledger.derive_statement_state` sorts by
    `stated_at` anyway, so spending the cap on the newest messages cannot produce a stale answer.

    The join to `prepared_content` is an INNER one. A message with no prepared text is a message
    whose quote could not be verified against anything, and a resolution without a receipt is
    exactly what this unit refuses to produce.
    """
    if not correlation_ids:
        return []
    rows = conn.execute(text(
        "select s.situation_id, m.correlation_id, se.event_id, se.occurred_at, "
        "       lower(se.actor->>'email') as sender_email, pc.clean_text as text "
        "from context_situations s "
        "join context_correlation_members m on m.org_id = s.org_id "
        "     and m.correlation_id = s.correlation_id "
        "join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
        "join prepared_content pc on pc.event_id = se.event_id and pc.org_id = se.org_id "
        "left join situation_resolution_claims c on c.org_id = s.org_id "
        "     and c.situation_id = s.situation_id and c.event_id = se.event_id "
        "where s.org_id = :o and m.correlation_id = any(:cids) "
        "  and c.claim_id is null and se.occurred_at >= :since "
        "order by se.occurred_at desc, se.event_id limit :lim"),
        {"o": org_id, "cids": list(correlation_ids),
         "since": eval_time - timedelta(days=lookback_days), "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


def extraction_outputs(conn, org_id: str, event_ids: Sequence[str]) -> dict[str, dict]:
    """L1's stored extraction per event — the input to the deterministic CANDIDATE prior.

    One row per event is taken (`distinct on`) because the same event can carry several cached
    extractions — different profiles, different prompt versions — and the prior is a hint about
    where to look, not a fact worth reconciling two readings of.
    """
    if not event_ids:
        return {}
    rows = conn.execute(text(
        "select distinct on (event_id) event_id, output from l1_extraction_results "
        "where org_id = :o and event_id = any(:ids) "
        "order by event_id, created_at desc"),
        {"o": org_id, "ids": list(event_ids)}).mappings().all()
    out: dict[str, dict] = {}
    for row in rows:
        payload = row["output"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        out[row["event_id"]] = payload if isinstance(payload, dict) else {}
    return out


def obligations_for(conn, org_id: str,
                    correlation_ids: Sequence[str]) -> dict[str, tuple[Obligation, ...]]:
    """The OPEN commitment nodes each situation's own events created, with their owners.

    A commitment is a first-class node in this graph (`pipeline.py` promotes it because facts key
    on subject+field, so a second promise would otherwise silently supersede the first), and the
    `owns` edge from the actor is what makes "the obligation's owner" answerable at all. The
    owner's ADDRESS is the person node's canonical key — that is how `pipeline.py` mints a person
    node — and it is the only form the speaker-authority table can compare a sender to.

    A commitment whose `commitment.status` has moved off `open` is not listed: it is not
    outstanding, so a claim about it cannot be what makes a partial resolution partial.
    """
    if not correlation_ids:
        return {}
    rows = conn.execute(text(
        "select distinct m.correlation_id, n.node_id, n.display_name, "
        "       owner.canonical_key as owner_email "
        "from context_correlation_members m "
        "join graph_facts f on f.org_id = m.org_id and f.created_by_event_id = m.event_id "
        "     and f.field = 'commitment.text' and f.valid_to is null and f.status = 'active' "
        "join graph_nodes n on n.org_id = m.org_id and n.node_id = f.subject_node_id "
        "     and n.node_type = 'commitment' and n.valid_to is null "
        "left join graph_facts st on st.org_id = m.org_id and st.subject_node_id = n.node_id "
        "     and st.field = 'commitment.status' and st.valid_to is null "
        "     and st.status = 'active' "
        "left join graph_edges e on e.org_id = m.org_id and e.to_node_id = n.node_id "
        "     and e.edge_type = 'owns' and e.valid_to is null "
        "left join graph_nodes owner on owner.org_id = m.org_id "
        "     and owner.node_id = e.from_node_id and owner.node_type = 'person' "
        "     and owner.valid_to is null "
        "where m.org_id = :o and m.correlation_id = any(:cids) "
        "  and (st.value is null or st.value::text like '%open%') "
        "order by m.correlation_id, n.node_id"),
        {"o": org_id, "cids": list(correlation_ids)}).mappings().all()
    out: dict[str, list[Obligation]] = {}
    for row in rows:
        out.setdefault(row["correlation_id"], []).append(Obligation(
            obligation_id=row["node_id"],
            subject=str(row["display_name"] or "").strip() or row["node_id"],
            owner_email=row["owner_email"]))
    return {cid: tuple(obs) for cid, obs in out.items()}


def calls_today(conn, org_id: str, *, eval_time: datetime) -> tuple[int, dict[str, int]]:
    """(calls this org made today, calls per situation today) — doc 11's two ceilings.

    Counted against `eval_time`'s UTC day and not against `now()`: the sweep reads the clock once
    at the process boundary, and a budget that read its own would make a replay at a fixed instant
    spend a different amount than the run it is replaying.
    """
    day_start = eval_time.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = conn.execute(text(
        "select situation_id, count(*) as n from situation_resolution_claims "
        "where org_id = :o and created_at >= :since and created_at < :until "
        "group by situation_id"),
        {"o": org_id, "since": day_start, "until": day_start + timedelta(days=1)}).all()
    per_situation = {r.situation_id: int(r.n) for r in rows}
    return sum(per_situation.values()), per_situation


def claims_for(conn, org_id: str,
               situation_ids: Sequence[str]) -> dict[str, list[ResolutionClaim]]:
    """Every stored claim for these situations — the ledger `derive_statement_state` reduces.

    Rebuilt into the same dataclass the judge produces, so the reducer runs on one shape whether
    the claim was made this second or three weeks ago.
    """
    if not situation_ids:
        return {}
    rows = conn.execute(text(
        "select situation_id, event_id, stated_at, verdict, certainty, scope, speaker_email, "
        "       speaker_role, authority_bp, certainty_bp, effective_bp, decision, reason, "
        "       quote, source_ref, start_offset, end_offset, span_verdict, prompt_version, "
        "       schema_version, model, raw_confidence_bp "
        "from situation_resolution_claims "
        "where org_id = :o and situation_id = any(:sids) "
        "order by situation_id, stated_at, event_id"),
        {"o": org_id, "sids": list(situation_ids)}).mappings().all()
    out: dict[str, list[ResolutionClaim]] = {}
    for r in rows:
        scope = r["scope"]
        if isinstance(scope, str):
            try:
                scope = json.loads(scope)
            except ValueError:
                scope = []
        out.setdefault(r["situation_id"], []).append(ResolutionClaim(
            situation_id=r["situation_id"], event_id=r["event_id"], stated_at=r["stated_at"],
            verdict=r["verdict"], certainty=r["certainty"],
            scope=tuple(str(s) for s in (scope or [])), speaker_email=r["speaker_email"],
            speaker_role=r["speaker_role"], authority_bp=int(r["authority_bp"]),
            certainty_bp=int(r["certainty_bp"]), effective_bp=int(r["effective_bp"]),
            decision=r["decision"], reason=r["reason"], quote=r["quote"] or "",
            source_ref=r["source_ref"] or "", start_offset=int(r["start_offset"] or 0),
            end_offset=int(r["end_offset"] or 0), span_verdict=r["span_verdict"] or "",
            raw_confidence_bp=r["raw_confidence_bp"], prompt_version=r["prompt_version"],
            schema_version=r["schema_version"], model=r["model"] or ""))
    return out


def write_claim(conn, org_id: str, claim: ResolutionClaim, *, review_state: str | None) -> str:
    """Store one judgement. Idempotent on (org, situation, event) — the cache and the ledger are
    the same row, so a re-run of the same drain must not double it or pay for it twice."""
    claim_id = new_id("resclaim")
    conn.execute(text(
        "insert into situation_resolution_claims (claim_id, org_id, situation_id, event_id, "
        "  stated_at, verdict, certainty, scope, speaker_email, speaker_role, authority_bp, "
        "  certainty_bp, effective_bp, quote, source_ref, start_offset, end_offset, "
        "  span_verdict, decision, reason, review_state, prompt_version, schema_version, "
        "  model, raw_confidence_bp) "
        "values (:cid, :o, :sid, :eid, :stated, :verdict, :certainty, cast(:scope as jsonb), "
        "  :email, :role, :abp, :cbp, :ebp, :quote, :sref, :start, :end, :span, :decision, "
        "  :reason, :review, :pv, :sv, :model, :raw) "
        "on conflict (org_id, situation_id, event_id) do nothing"),
        {"cid": claim_id, "o": org_id, "sid": claim.situation_id, "eid": claim.event_id,
         "stated": claim.stated_at, "verdict": claim.verdict, "certainty": claim.certainty,
         "scope": json.dumps(list(claim.scope)), "email": claim.speaker_email,
         "role": claim.speaker_role, "abp": claim.authority_bp, "cbp": claim.certainty_bp,
         "ebp": claim.effective_bp, "quote": claim.quote or None,
         "sref": claim.source_ref or None, "start": claim.start_offset,
         "end": claim.end_offset, "span": claim.span_verdict or None,
         "decision": claim.decision, "reason": claim.reason, "review": review_state,
         "pv": claim.prompt_version, "sv": claim.schema_version, "model": claim.model or None,
         "raw": claim.raw_confidence_bp})
    return claim_id


def apply_lifecycle(conn, org_id: str, *, situation_id: str, status: str,
                    resolved_by: str | None, resolved_at: datetime | None,
                    note: str | None) -> bool:
    """Write the lifecycle decision back onto the situation.

    `resolved_at` is the moment the STATEMENT WAS MADE, not the moment we read it — a situation
    resolved by a sentence written on Tuesday was resolved on Tuesday, and the existing reopen
    rule compares `last_seen_at` against exactly this timestamp. Cleared for anything that is not
    a terminal state, and the note with it: a note explaining a close would read as the current
    state of something now open.
    """
    return conn.execute(text(
        "update context_situations set status = :status, resolved_by = :rby, "
        # CAST, not a bare parameter: on a reopen `:rat` is NULL, and PostgreSQL types an
        # untyped NULL parameter as `text` — so the whole CASE comes back text and the UPDATE
        # fails on a column that is `timestamptz`. Only the reopen path binds NULL, which is
        # exactly the path a happy-path test would never reach.
        "  resolved_at = case when :status in ('resolved', 'archived') "
        "                     then cast(:rat as timestamptz) end, "
        "  resolution_note = case when :status in ('resolved', 'archived', 'partial') "
        "                        then :note end "
        "where org_id = :o and situation_id = :sid "
        "  and (status is distinct from :status or resolved_by is distinct from :rby "
        "       or resolution_note is distinct from :note)"),
        {"o": org_id, "sid": situation_id, "status": status, "rby": resolved_by,
         "rat": resolved_at, "note": note}).rowcount > 0


def pending_reviews(conn, org_id: str, *, limit: int = 100) -> list[dict]:
    """The human review queue — every claim that described a resolution we would not act on.

    Ordered strongest first: the entries closest to the floor are the ones a human can settle
    fastest, and a queue that opened on its weakest item is a queue that reads as noise.
    """
    rows = conn.execute(text(
        "select c.claim_id, c.situation_id, c.event_id, c.stated_at, c.verdict, c.certainty, "
        "       c.scope, c.speaker_email, c.speaker_role, c.effective_bp, c.quote, c.reason, "
        "       s.situation_type, s.domain, n.display_name as about "
        "from situation_resolution_claims c "
        "join context_situations s on s.org_id = c.org_id and s.situation_id = c.situation_id "
        "left join graph_nodes n on n.org_id = c.org_id and n.node_id = s.anchor_node_id "
        "     and n.valid_to is null "
        "where c.org_id = :o and c.review_state = 'pending' "
        "order by c.effective_bp desc, c.stated_at desc limit :lim"),
        {"o": org_id, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


def decide_review(conn, org_id: str, *, claim_id: str, accepted: bool,
                  reviewed_by: str | None, eval_time: datetime) -> bool:
    """A human settles one queue entry.

    ACCEPTING DOES NOT PROMOTE THE CLAIM TO `apply`. The claim stays exactly what it was — a
    description that did not clear the floor — and the human's decision is recorded as the human
    resolution it is (`resolve_situation`, the path that already exists), so the row's provenance
    never becomes a mixture of "the model was sure" and "a person agreed".
    """
    return conn.execute(text(
        "update situation_resolution_claims set review_state = :state, reviewed_at = :at, "
        "  reviewed_by = :who where org_id = :o and claim_id = :cid "
        "  and review_state = 'pending'"),
        {"o": org_id, "cid": claim_id, "state": "accepted" if accepted else "dismissed",
         "at": eval_time, "who": reviewed_by}).rowcount > 0
