"""Agent delegation's four verbs: propose, approve, dispatch, result — each once, in order.

`ExecutionState` deliberately does NOT grow agent states: its vocabulary describes the
COMMITMENT (pending, running, waiting, completed), and "an agent is attempting step 2" is a
fact about the machinery working it, not about where the commitment stands. Conflating the two
is how an agent crash would have read as a stalled human. A delegation is its own small ledger
row with its own lifecycle, joined to the execution — or, since P6, the MOMENT or CARD — it serves.

The law this encodes: **no approval, no dispatch — ever.** A proposal names the exact
instruction bytes; the approval pins a named human to those bytes with an expiry; dispatch
happens at most once inside the approval window; the result lands exactly once. Every verb is
guarded on the previous state, so a retry, a refresh or a concurrent click converges instead of
double-sending an external action.

P6 (SCREEN_INTEL_P6_BUILD §3) wires it end to end:

  propose_action       typed play + strict params (`executive/plays`), idempotent on proposal_key
  approve_and_enqueue  approve + claim_dispatch + freeze the §3.1 request bytes + ONE outbox row +
                       realtime `moment.updated` — one transaction, the delegation row locked, so
                       two concurrent approvals produce one outbox row
  reject / supersede   edit = reject + a new proposal naming `supersedes`
  record_agent_result  the named agent only (any other → not found), exactly once; a different
                       final status is a conflict

GeniOS never writes to a provider: the outbox hands the frozen bytes to the CLIENT'S agent
(`deliver/outbox.py` agent_action branch). Nothing here charges credits.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.executive import plays as P
from genios_engine.platform.ids import new_id

#: How long an approval authorises dispatch. Short on purpose: an approval is a human reading a
#: SPECIFIC draft at a specific moment, and the world the draft was written for moves.
APPROVAL_TTL_HOURS = 24
#: A proposal nobody decided within this window can no longer be approved (→ `expired`).
PROPOSAL_TTL_HOURS = 24
#: The outbox channel of an approved delegation; its synthetic card id prefix (0157).
ACT_CHANNEL = "agent_action"
CARD_PREFIX = "dlg:"
FINAL_STATES = ("succeeded", "failed")
STATES = ("proposed", "approved", "rejected", "dispatched", "succeeded", "failed", "expired",
          "cancelled")


class DelegationError(Exception):
    """A refusal with its HTTP shape — raised BEFORE anything is written (the caller's
    transaction rolls back either way)."""

    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra

    def body(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


class InvalidProposal(DelegationError, ValueError):
    """422 — invalid params, an unknown play, no subject named, or no agent runs the play."""


class SubjectNotFound(DelegationError, LookupError):
    """404 — the moment / card / delegation is not this org's."""


class NotPermitted(DelegationError, PermissionError):
    """403 — the seat is neither the subject's own nor an org admin."""


def _for_update(conn) -> str:
    return " for update" if conn.dialect.name == "postgresql" else ""


# ── the four verbs (execution-shaped callers keep working unchanged) ─────────────────────────
def propose(conn, *, org_id: str, execution_id: str | None, agent_id: str,
            instruction: dict, action_id: str | None = None) -> str:
    """The engine proposes handing one action to one agent. Nothing is sent."""
    delegation_id = new_id("dlg")
    conn.execute(text(
        "insert into agent_delegations (org_id, delegation_id, execution_id, action_id, "
        "agent_id, instruction) values (:o, :d, :x, :a, :ag, cast(:i as jsonb))"),
        {"o": org_id, "d": delegation_id, "x": execution_id, "a": action_id,
         "ag": agent_id, "i": json.dumps(instruction, default=str)})
    return delegation_id


def approve(conn, *, org_id: str, delegation_id: str, actor: str, at: datetime,
            reject: bool = False) -> bool:
    """A named human approves (or rejects) the proposal's exact bytes. Guarded on 'proposed'."""
    if reject:
        result = conn.execute(text(
            "update agent_delegations set state='rejected', approved_by=:by, approved_at=:at "
            "where org_id=:o and delegation_id=:d and state='proposed'"),
            {"by": actor, "at": at, "o": org_id, "d": delegation_id})
        return result.rowcount == 1
    result = conn.execute(text(
        "update agent_delegations set state='approved', approved_by=:by, approved_at=:at, "
        "approval_expires_at=:exp "
        "where org_id=:o and delegation_id=:d and state='proposed'"),
        {"by": actor, "at": at, "exp": at + timedelta(hours=APPROVAL_TTL_HOURS),
         "o": org_id, "d": delegation_id})
    return result.rowcount == 1


def claim_dispatch(conn, *, org_id: str, delegation_id: str, at: datetime) -> dict | None:
    """Claim the single dispatch slot. None = not approved, expired, or already dispatched.

    The state transition IS the mutex: two concurrent dispatchers race this UPDATE and exactly
    one wins the row. An expired approval flips to 'expired' rather than silently refusing, so
    the operator sees WHY nothing went out.
    """
    row = conn.execute(text(
        "update agent_delegations set state='dispatched', dispatched_at=:at "
        "where org_id=:o and delegation_id=:d and state='approved' "
        "and approval_expires_at > :at "
        "returning execution_id, action_id, agent_id, instruction"),
        {"at": at, "o": org_id, "d": delegation_id}).mappings().first()
    if row is not None:
        return dict(row)
    conn.execute(text(
        "update agent_delegations set state='expired' "
        "where org_id=:o and delegation_id=:d and state='approved' "
        "and approval_expires_at <= :at"),
        {"o": org_id, "d": delegation_id, "at": at})
    return None


def record_result(conn, *, org_id: str, delegation_id: str, agent_id: str | None, ok: bool,
                  detail: dict, at: datetime) -> str:
    """The agent's outcome, exactly once, and only from the agent it was dispatched to.

    Returns 'recorded' | 'repeat' (same final status again — nothing written) | 'conflict' (a
    different final status) | 'not_dispatched' | 'not_found' (unknown id OR another agent: a
    stranger learns nothing about a delegation that is not theirs)."""
    row = conn.execute(text(
        "select state, agent_id from agent_delegations where org_id=:o and delegation_id=:d"
        + _for_update(conn)), {"o": org_id, "d": delegation_id}).first()
    if row is None or not agent_id or row.agent_id != agent_id:
        return "not_found"
    target = "succeeded" if ok else "failed"
    if row.state in FINAL_STATES:
        return "repeat" if row.state == target else "conflict"
    if row.state != "dispatched":
        return "not_dispatched"
    result = conn.execute(text(
        "update agent_delegations set state=:st, resulted_at=:at, result=cast(:r as jsonb) "
        "where org_id=:o and delegation_id=:d and state='dispatched' and agent_id=:ag"),
        {"st": target, "at": at, "r": json.dumps(detail, default=str), "o": org_id,
         "d": delegation_id, "ag": agent_id})
    return "recorded" if result.rowcount == 1 else "not_dispatched"


# ── subjects: the moment or card a delegation serves ──────────────────────────────────────────
@dataclass(frozen=True)
class Subject:
    seat_id: str | None
    moment_id: str | None
    card_id: str | None
    headline: str | None
    evidence: list = field(default_factory=list)


def _json(v, default):
    if v is None:
        return default
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return default
    return v


def load_subject(conn, org_id: str, *, moment_id: str | None = None,
                 card_id: str | None = None) -> Subject | None:
    """The moment (preferred) or card a proposal is about; None when it is not this org's."""
    if moment_id:
        r = conn.execute(text(
            "select seat_id, headline, evidence, card_id from moments "
            "where org_id = :o and moment_id = :m"), {"o": org_id, "m": moment_id}).first()
        if r is None:
            return None
        return Subject(seat_id=r.seat_id, moment_id=moment_id, card_id=r.card_id,
                       headline=r.headline, evidence=list(_json(r.evidence, [])))
    if card_id:
        r = conn.execute(text(
            "select assignee, headline, why from cards where org_id = :o and card_id = :c"),
            {"o": org_id, "c": card_id}).first()
        if r is None:
            return None
        why = _json(r.why, [])
        return Subject(seat_id=r.assignee, moment_id=None, card_id=card_id, headline=r.headline,
                       evidence=list(why) if isinstance(why, list) else [])
    return None


def subject_of(conn, org_id: str, delegation_id: str) -> Subject | None:
    """The subject a delegation serves (for the approve / reject permission check)."""
    r = conn.execute(text(
        "select seat_id, moment_id, card_id from agent_delegations "
        "where org_id = :o and delegation_id = :d"), {"o": org_id, "d": delegation_id}).first()
    if r is None:
        return None
    return Subject(seat_id=r.seat_id, moment_id=r.moment_id, card_id=r.card_id, headline=None)


def seat_is_org_admin(conn, org_id: str, seat_id: str | None) -> bool:
    """Owner (by address) or an active admin seat — the same rule `platform/auth.seat_role` uses."""
    if not seat_id:
        return False
    from genios_engine.platform.auth import ROLE_ADMIN, ROLE_OWNER, seat_role
    r = conn.execute(text(
        "select s.email, s.role, o.email as org_email from org_seats s "
        "join orgs o on o.id = s.org_id where s.org_id = :o and s.seat_id = :s and s.active"),
        {"o": org_id, "s": seat_id}).first()
    return r is not None and seat_role(r.email, r.role, r.org_email) in (ROLE_OWNER, ROLE_ADMIN)


def may_act(conn, org_id: str, subject: Subject, seat_id: str | None) -> bool:
    """Only the subject's own seat (a card: its assignee or a routed recipient) or an org admin
    may propose, approve or reject — never `orgs.email` by default."""
    if not seat_id:
        return False
    if subject.seat_id and subject.seat_id == seat_id:
        return True
    # A card also reaches a seat through `card_recipients` (0135). Same predicate as
    # `deliver/seat_access.SEAT_REACH_SQL`, restated here because Layer 5 may never import Layer 6.
    if subject.card_id and conn.execute(text(
            "select 1 from cards k where k.org_id = :o and k.card_id = :c and "
            "(k.assignee = :seat or exists (select 1 from card_recipients cr "
            "where cr.org_id = k.org_id and cr.card_id = k.card_id and cr.seat_id = :seat))"),
            {"o": org_id, "c": subject.card_id, "seat": seat_id}).first() is not None:
        return True
    return seat_is_org_admin(conn, org_id, seat_id)


def _agent_audience(conn, org_id: str, agent_id: str, subject: Subject) -> list[str]:
    """Who the agent reads FOR. An agent bound to the subject's own seat (0158, group B) reads that
    seat's private evidence; an unbound agent serves the org and reads none."""
    if conn.dialect.name != "postgresql" or not subject.seat_id:
        return []
    bound = conn.execute(text(
        "select 1 from information_schema.columns where table_name = 'agent_registry' "
        "and column_name = 'seat_id'")).first()
    if bound is None:
        return []
    email = conn.execute(text(
        "select s.email from agent_registry a join org_seats s on s.org_id = a.org_id "
        "and s.seat_id = a.seat_id where a.org_id = :o and a.agent_id = :a and a.seat_id = :s"),
        {"o": org_id, "a": agent_id, "s": subject.seat_id}).scalar()
    return [email] if email else []


# ── P6 verbs ──────────────────────────────────────────────────────────────────────────────────
def proposal_key(org_id: str, *, moment_id: str | None, card_id: str | None, play: str,
                 params: dict) -> str:
    raw = json.dumps([org_id, moment_id or "", card_id or "", play, params], sort_keys=True,
                     separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


_COLS = ("delegation_id, org_id, seat_id, moment_id, card_id, agent_id, play, params, "
         "instruction, state, proposed_at, approved_by, approved_at, approval_expires_at, "
         "dispatched_at, resulted_at, result, superseded_by, request_sha256, decision_reason")


def _row(conn, org_id: str, delegation_id: str, *, lock: bool = False):
    return conn.execute(text(
        f"select {_COLS} from agent_delegations where org_id = :o and delegation_id = :d"
        + (_for_update(conn) if lock else "")),
        {"o": org_id, "d": delegation_id}).mappings().first()


def _iso(v) -> str | None:
    if v is None:
        return None
    v = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _result_out(raw) -> dict | None:
    """The stored result → the pinned `{status, summary, provider_ref, completed_at}`."""
    res = _json(raw, None)
    if not isinstance(res, dict):
        return None
    detail = res.get("detail") if isinstance(res.get("detail"), dict) else {}
    return {"status": res.get("status"), "summary": detail.get("summary") or detail.get("error"),
            "provider_ref": detail.get("provider_ref"), "completed_at": res.get("completed_at")}


def delegation_out(r) -> dict:
    """The pinned §3.3 list item (SCREEN_INTEL_P6_BUILD, website + desktop built to it)."""
    instr = _json(r["instruction"], {}) or {}
    return {
        "delegation_id": r["delegation_id"], "state": r["state"], "play": r["play"],
        "params": _json(r["params"], {}) or {}, "instruction": instr.get("text"),
        "headline": (instr.get("context") or {}).get("headline"), "agent_id": r["agent_id"],
        "agent_name": r.get("agent_name"), "moment_id": r["moment_id"], "card_id": r["card_id"],
        "supersedes": r.get("supersedes"), "proposed_at": _iso(r["proposed_at"]),
        "approved_by": r["approved_by"], "approved_at": _iso(r["approved_at"]),
        "result": _result_out(r["result"])}


def _announce(conn, r, state: str, *, summary: str | None = None) -> None:
    """`moment.updated {moment_id, delegation:{id,state,play,summary}}` in the caller's
    transaction (no-op off PostgreSQL or without a moment). The caller wakes after commit."""
    if not r["moment_id"]:
        return
    from genios_engine.platform import realtime
    realtime.publish(conn, org_id=r["org_id"], seat_id=r["seat_id"], kind="moment.updated",
                     payload={"moment_id": r["moment_id"],
                              "delegation": {"id": r["delegation_id"], "state": state,
                                             "play": r["play"],
                                             "summary": summary or P.summary(
                                                 r["play"], _json(r["params"], {}))}})


def _proposal_out(r) -> dict:
    instr = _json(r["instruction"], {}) or {}
    return {"delegation_id": r["delegation_id"], "state": r["state"],
            "instruction": instr.get("text"), "agent_id": r["agent_id"]}


def supersede(conn, *, org_id: str, delegation_id: str, by: str, subject: Subject) -> str:
    """Retire `delegation_id` in favour of `by` (an edit), in the proposing transaction: the old
    proposal → `cancelled`, `superseded_by` = the new one (clients never reject first — pinned
    §3.3). Only a `proposed` delegation can be superseded; anything else is 409 and, because the
    caller's transaction rolls back, the new proposal is not written either."""
    r = _row(conn, org_id, delegation_id, lock=True)
    if r is None:
        raise SubjectNotFound(404, "NOT_FOUND", "The delegation to supersede does not exist.")
    if (r["moment_id"], r["card_id"]) != (subject.moment_id, subject.card_id) and not (
            subject.moment_id is None and r["card_id"] == subject.card_id):
        raise InvalidProposal(422, "SUBJECT_MISMATCH",
                              "An edit must be about the same moment or card.")
    if r["state"] != "proposed":
        raise DelegationError(409, "NOT_EDITABLE",
                              f"The delegation is already {r['state']}; only a proposed one can "
                              "be edited.", state=r["state"])
    conn.execute(text(
        "update agent_delegations set state = 'cancelled', superseded_by = :by "
        "where org_id = :o and delegation_id = :d and state = 'proposed'"),
        {"by": by, "o": org_id, "d": delegation_id})
    _announce(conn, r, "cancelled")
    return "cancelled"


def propose_action(conn, *, org_id: str, subject: Subject, play: str, params, now: datetime,
                   agent_id: str | None = None, supersedes: str | None = None,
                   via: str = "api", proposed_by: str | None = None) -> dict:
    """The proposal verb in the CALLER's transaction (`create_proposal` wraps it; the handoff
    route calls it directly). Validates first — invalid params, an unknown play or no qualifying
    agent raise BEFORE any write. Idempotent: the same (org, moment|card, play, params) returns
    the existing proposal."""
    errors = P.validate(play, params)
    if errors:
        raise InvalidProposal(422, "INVALID_PARAMS", "The action parameters are invalid.",
                              errors=errors)
    chosen = P.select_agent(conn, org_id, play, agent_id)
    if chosen is None:
        raise InvalidProposal(422, "NO_AGENT",
                              "No active agent with a webhook is allowed to run this play.")
    key = proposal_key(org_id, moment_id=subject.moment_id, card_id=subject.card_id, play=play,
                       params=params)
    held = conn.execute(text(
        f"select {_COLS} from agent_delegations where org_id = :o and proposal_key = :k"),
        {"o": org_id, "k": key}).mappings().first()
    if held is not None:
        return _proposal_out(held)
    evidence = P.request_evidence(conn, org_id, subject.evidence,
                                  _agent_audience(conn, org_id, chosen, subject))
    instr = {"text": P.instruction(play, params),
             "context": {"moment_id": subject.moment_id, "card_id": subject.card_id,
                         "headline": subject.headline, "evidence": evidence},
             "via": via, "proposed_by": proposed_by}
    delegation_id = new_id("dlg")
    made = conn.execute(text(
        "insert into agent_delegations (org_id, delegation_id, execution_id, agent_id, "
        "instruction, seat_id, moment_id, card_id, play, params, proposal_key, proposed_at) "
        "values (:o, :d, null, :ag, cast(:i as jsonb), :s, :m, :c, :p, cast(:pa as jsonb), :k, "
        ":now) on conflict (org_id, proposal_key) where proposal_key is not null do nothing "
        "returning delegation_id"),
        {"o": org_id, "d": delegation_id, "ag": chosen, "i": json.dumps(instr, default=str),
         "s": subject.seat_id, "m": subject.moment_id, "c": subject.card_id, "p": play,
         "pa": json.dumps(params, default=str), "k": key, "now": now}).first()
    if made is None:           # a concurrent identical proposal won the key
        held = conn.execute(text(
            f"select {_COLS} from agent_delegations where org_id = :o and proposal_key = :k"),
            {"o": org_id, "k": key}).mappings().first()
        return _proposal_out(held)
    if supersedes:
        supersede(conn, org_id=org_id, delegation_id=supersedes, by=delegation_id,
                  subject=subject)
    r = _row(conn, org_id, delegation_id)
    _announce(conn, r, "proposed")
    return _proposal_out(r)


def create_proposal(engine, *, org_id: str, seat_id: str | None, seat_email: str | None,
                    moment_id: str | None, card_id: str | None, play: str, params,
                    agent_id: str | None = None, via: str = "api",
                    supersedes: str | None = None, now: datetime | None = None) -> dict:
    """THE proposal entry point — POST /v1/delegations and MCP `propose_action` (group B) both
    call it. One transaction; returns {delegation_id, state, instruction, agent_id}. Raises
    `InvalidProposal` (a ValueError: bad params / play / subject / no agent), `SubjectNotFound`
    (a LookupError) or `NotPermitted` (a PermissionError: not the subject's seat nor an org
    admin) — each before anything is written."""
    if bool(moment_id) == bool(card_id):
        raise InvalidProposal(422, "SUBJECT_REQUIRED", "Name exactly one of moment_id or card_id.")
    from genios_engine.platform import realtime
    with engine.begin() as c:
        subject = load_subject(c, org_id, moment_id=moment_id, card_id=card_id)
        if subject is None:
            raise SubjectNotFound(404, "NOT_FOUND", "No such moment or card.")
        if not may_act(c, org_id, subject, seat_id):
            raise NotPermitted(403, "FORBIDDEN",
                               "Only its own seat or an org admin can ask an agent to act on this.")
        out = propose_action(c, org_id=org_id, subject=subject, play=play, params=params,
                             agent_id=agent_id, supersedes=supersedes,
                             now=now or datetime.now(timezone.utc), via=via,
                             proposed_by=seat_email)
    realtime.wake()
    return out


def approve_and_enqueue(conn, *, org_id: str, delegation_id: str, approver_seat_id: str,
                        approver_email: str, at: datetime, result_base_url: str) -> dict | None:
    """Approve + claim the dispatch slot + freeze the request bytes + one outbox row + realtime,
    in the CALLER's single transaction. The delegation row is locked first, so a concurrent
    approval waits, then sees `dispatched` and returns it: one outbox row, ever. A repeat returns
    the current state; a proposal older than PROPOSAL_TTL_HOURS becomes `expired` (nothing sent).
    None = no such delegation."""
    r = _row(conn, org_id, delegation_id, lock=True)
    if r is None:
        return None
    if r["state"] != "proposed":
        return {"delegation_id": delegation_id, "state": r["state"]}
    proposed_at = r["proposed_at"] if r["proposed_at"].tzinfo else \
        r["proposed_at"].replace(tzinfo=timezone.utc)
    if proposed_at + timedelta(hours=PROPOSAL_TTL_HOURS) <= at:
        conn.execute(text(
            "update agent_delegations set state = 'expired' where org_id = :o "
            "and delegation_id = :d and state = 'proposed'"), {"o": org_id, "d": delegation_id})
        _announce(conn, r, "expired")
        return {"delegation_id": delegation_id, "state": "expired"}
    if not approve(conn, org_id=org_id, delegation_id=delegation_id, actor=approver_email, at=at):
        return {"delegation_id": delegation_id, "state": _row(conn, org_id, delegation_id)["state"]}
    if claim_dispatch(conn, org_id=org_id, delegation_id=delegation_id, at=at) is None:
        return {"delegation_id": delegation_id, "state": _row(conn, org_id, delegation_id)["state"]}
    instr = _json(r["instruction"], {}) or {}
    params = _json(r["params"], {}) or {}
    body = P.request_body(P.request_document(
        delegation_id=delegation_id, org_id=org_id, agent_id=r["agent_id"], play=r["play"],
        params=params, context=instr.get("context") or {}, approved_by=approver_email,
        approved_at=at, expires_at=at + timedelta(hours=APPROVAL_TTL_HOURS),
        result_url=f"{result_base_url.rstrip('/')}/v1/delegations/{delegation_id}/result"))
    conn.execute(text(
        "update agent_delegations set approver_seat_id = :s, request_sha256 = :h "
        "where org_id = :o and delegation_id = :d"),
        {"s": approver_seat_id, "h": P.body_sha256(body), "o": org_id, "d": delegation_id})
    conn.execute(text(
        "insert into delivery_outbox (id, org_id, card_id, channel, payload, status, "
        "next_attempt_at, recipient, channel_class, priority, delegation_id) values "
        "(:i, :o, :card, :ch, cast(:p as jsonb), 'queued', :at, :agent, 'agent', 'high', :d) "
        "on conflict do nothing"),
        {"i": new_id("obx"), "o": org_id, "card": CARD_PREFIX + delegation_id,
         "ch": ACT_CHANNEL, "at": at, "agent": r["agent_id"], "d": delegation_id,
         "p": json.dumps({"kind": ACT_CHANNEL, "delegation_id": delegation_id,
                          "body": body.decode("ascii"), "sha256": P.body_sha256(body)})})
    _announce(conn, r, "dispatched")
    return {"delegation_id": delegation_id, "state": "dispatched"}


def reject(conn, *, org_id: str, delegation_id: str, actor_email: str, actor_seat_id: str,
           reason: str | None, at: datetime) -> dict | None:
    """A named human says no. Guarded on 'proposed'; a repeat returns the current state."""
    r = _row(conn, org_id, delegation_id, lock=True)
    if r is None:
        return None
    if r["state"] != "proposed":
        return {"delegation_id": delegation_id, "state": r["state"]}
    approve(conn, org_id=org_id, delegation_id=delegation_id, actor=actor_email, at=at,
            reject=True)
    conn.execute(text(
        "update agent_delegations set approver_seat_id = :s, decision_reason = :r "
        "where org_id = :o and delegation_id = :d"),
        {"s": actor_seat_id, "r": (reason or "")[:500] or None, "o": org_id, "d": delegation_id})
    _announce(conn, r, "rejected")
    return {"delegation_id": delegation_id, "state": "rejected"}


def record_agent_result(conn, *, org_id: str, delegation_id: str, agent_id: str | None,
                        status: str, detail: dict, completed_at: datetime | None,
                        at: datetime) -> tuple[str, str | None]:
    """§3.4 in one transaction: the result (exactly once, named agent only) and — only when it
    was recorded — `moment_feedback 'acted'` on success, `moment.updated`, and `card_events
    'agent.result'` when a card exists. Returns (outcome, current state)."""
    outcome = record_result(
        conn, org_id=org_id, delegation_id=delegation_id, agent_id=agent_id,
        ok=status == "succeeded", at=at,
        detail={"status": status, "detail": detail or {}, "completed_at": _iso(completed_at)})
    if outcome == "not_found":
        return outcome, None
    r = _row(conn, org_id, delegation_id)
    if outcome != "recorded":
        return outcome, r["state"]
    summary = str((detail or {}).get("summary") or "")[:300] or None
    if status == "succeeded" and r["moment_id"]:
        conn.execute(text(
            "insert into moment_feedback (org_id, moment_id, seat_id, capability_id, action, "
            "reason, at) select m.org_id, m.moment_id, m.seat_id, m.capability_id, 'acted', "
            ":why, :at from moments m where m.org_id = :o and m.moment_id = :m "
            "on conflict do nothing"),
            {"why": f"agent:{r['play']}", "at": at, "o": org_id, "m": r["moment_id"]})
    card_id = r["card_id"]
    if not card_id and r["moment_id"]:
        card_id = conn.execute(text(
            "select card_id from moments where org_id = :o and moment_id = :m"),
            {"o": org_id, "m": r["moment_id"]}).scalar()
    if card_id:
        conn.execute(text(
            "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
            "select :i, k.card_id, k.org_id, 'agent.result', :cause, :actor, cast(:d as jsonb) "
            "from cards k where k.org_id = :o and k.card_id = :c"),
            {"i": new_id("cev"), "c": card_id, "o": org_id, "cause": r["play"],
             "actor": agent_id,
             "d": json.dumps({"delegation_id": delegation_id, "status": status,
                              "summary": summary}, default=str)})
    _announce(conn, r, r["state"], summary=summary)
    return outcome, r["state"]


def list_delegations(conn, org_id: str, *, seat_id: str | None, state: str | None = None,
                     moment_id: str | None = None, limit: int = 50) -> list[dict]:
    """Newest first. `seat_id` narrows to one seat's delegations (None = the whole org)."""
    cols = ", ".join(f"d.{c.strip()}" for c in _COLS.split(","))
    rows = conn.execute(text(
        f"select {cols}, a.name as agent_name, (select p.delegation_id from agent_delegations p "
        " where p.org_id = d.org_id and p.superseded_by = d.delegation_id "
        " order by p.proposed_at desc limit 1) as supersedes "
        "from agent_delegations d left join agent_registry a on a.org_id = d.org_id "
        " and a.agent_id = d.agent_id "
        "where d.org_id = :o and d.play is not null "
        "and (cast(:s as text) is null or d.seat_id = cast(:s as text)) "
        "and (cast(:st as text) is null or d.state = cast(:st as text)) "
        "and (cast(:m as text) is null or d.moment_id = cast(:m as text)) "
        "order by d.proposed_at desc, d.delegation_id desc limit :n"),
        {"o": org_id, "s": seat_id, "st": state, "m": moment_id,
         "n": max(1, min(int(limit or 50), 200))}).mappings().all()
    return [delegation_out(r) for r in rows]


# ── the drain's side (deliver/outbox.py agent_action branch) ──────────────────────────────────
def send_state(conn, org_id: str, delegation_id: str):
    """(state, agent_id, approval_expires_at) of the delegation an outbox row carries, or None."""
    return conn.execute(text(
        "select state, agent_id, approval_expires_at from agent_delegations "
        "where org_id = :o and delegation_id = :d"), {"o": org_id, "d": delegation_id}).first()


def close_undelivered(conn, *, org_id: str, delegation_id: str, state: str, detail: str,
                      at: datetime) -> bool:
    """A dispatched request that never reached the agent ends `expired` (approval window passed
    before any attempt) or `failed` (transport gave up) — so the person sees that nothing ran.
    Guarded on 'dispatched': a result that already landed wins."""
    if state not in ("expired", "failed"):
        raise ValueError(state)
    done = conn.execute(text(
        "update agent_delegations set state = :st, resulted_at = :at, "
        "result = cast(:r as jsonb) where org_id = :o and delegation_id = :d "
        "and state = 'dispatched'"),
        {"st": state, "at": at, "o": org_id, "d": delegation_id,
         "r": json.dumps({"status": state, "detail": {"error": detail[:300]},
                          "source": "genios"})}).rowcount == 1
    if done:
        _announce(conn, _row(conn, org_id, delegation_id), state)
    return done


__all__ = ["ACT_CHANNEL", "APPROVAL_TTL_HOURS", "CARD_PREFIX", "DelegationError",
           "InvalidProposal", "NotPermitted", "PROPOSAL_TTL_HOURS", "Subject", "SubjectNotFound",
           "approve", "approve_and_enqueue", "claim_dispatch", "close_undelivered",
           "create_proposal", "delegation_out", "list_delegations", "load_subject", "may_act",
           "propose", "propose_action", "proposal_key", "record_agent_result", "record_result",
           "reject", "send_state", "seat_is_org_admin", "supersede"]
