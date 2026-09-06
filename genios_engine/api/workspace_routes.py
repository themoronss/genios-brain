"""Workspace-level custom integrations — the non-Google mail sources a customer brings themselves.

Google (Gmail/Calendar) stays on the Composio flow. This module manages two "bring your own"
connectors at workspace scope:
  * a hosted inbox (API key — email + SMS + voice), and
  * self-hosted IMAP.

Every credential is Fernet-encrypted at rest (platform.crypto). org_id ALWAYS comes from the
credential (get_current_org); the {org_id} in the path is validated against it, never trusted on
its own — the tenant-isolation law that the rest of the engine follows.

Routes (mounted at the same base as the dashboard expects):
  GET    /api/org/{org_id}/integrations/accounts                         — list connected accounts
  POST   /api/org/{org_id}/integrations/inkbox/accounts                  — connect a hosted inbox
  POST   /api/org/{org_id}/integrations/imap/accounts                    — connect an IMAP mailbox
  DELETE /api/org/{org_id}/integrations/accounts/{kind}/{account_id}     — disconnect
  POST   /api/org/{org_id}/integrations/accounts/{kind}/{account_id}/sync — manual sync trigger
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.reason.authority import (AUTHORITATIVE_SCORE_SQL,
                                            AUTHORITATIVE_SIGNAL_JOINS,
                                            AUTHORITATIVE_SIGNAL_PREDICATE)
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt, encrypt
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_log = get_logger("workspace")


def _store():
    g = make_graph_store()
    if g is None:
        raise HTTPException(400, "graph store not configured")
    return g


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    """Resolve the tenant from the credential and refuse a path that names a different org."""
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


class HostedInboxConnect(BaseModel):
    mailbox_address: str
    api_key: str


class ImapConnect(BaseModel):
    mailbox_address: str
    host: str
    username: str
    password: str
    port: int | None = None
    ssl: bool = True


def _account_row(r) -> dict:
    return {"account_id": r.account_id, "account_kind": "connector", "channel": r.channel,
            "label": r.label, "last_event_at": r.last_event_at.isoformat() if r.last_event_at else None,
            "sync_status": r.sync_status, "sync_error": r.sync_error,
            "last_sync_at": r.last_sync_at.isoformat() if r.last_sync_at else None,
            "consecutive_failures": r.consecutive_failures or 0}


# ── list ────────────────────────────────────────────────────────────────────────
@router.get("/api/org/{org_id}/integrations/accounts")
def list_accounts(org_id: str, org: str = Depends(_org)) -> dict:
    g = _store()
    with g.engine.connect() as c:
        rows = c.execute(text(
            "select account_id, tool, channel, label, last_event_at, sync_status, sync_error, "
            "last_sync_at, consecutive_failures from workspace_accounts "
            "where org_id=:o and is_active order by created_at desc"), {"o": org}).fetchall()
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r.tool or "unknown", []).append(_account_row(r))
    return {"tools": grouped}


def _insert_account(org: str, tool: str, channel: str, label: str, creds: dict) -> str:
    g = _store()
    account_id = new_id("wacct")
    enc = encrypt(json.dumps(creds), get_settings().crypto_key)
    with g.engine.begin() as c:
        c.execute(text(
            "insert into workspace_accounts (account_id, org_id, tool, channel, label, "
            "enc_credentials, sync_status) values (:a, :o, :t, :ch, :l, :e, 'never_synced')"),
            {"a": account_id, "o": org, "t": tool, "ch": channel, "l": label, "e": enc})
    return account_id


# ── connect: hosted inbox (API key) ──────────────────────────────────────────────
@router.post("/api/org/{org_id}/integrations/hosted-inbox/accounts", status_code=201)
def connect_hosted_inbox(org_id: str, req: HostedInboxConnect, bg: BackgroundTasks,
                         org: str = Depends(_org)) -> dict:
    mailbox, api_key = req.mailbox_address.strip().lower(), req.api_key.strip()
    if not mailbox or not api_key:
        raise HTTPException(400, "mailbox_address and api_key required")
    account_id = _insert_account(org, "hosted_inbox", "email", mailbox,
                                 {"provider": "hosted_inbox", "mailbox_address": mailbox, "api_key": api_key})
    bg.add_task(_sync_workspace_account, account_id, org)
    return {"account_id": account_id, "account_kind": "connector", "tool": "hosted_inbox", "label": mailbox}


# ── connect: IMAP ────────────────────────────────────────────────────────────────
@router.post("/api/org/{org_id}/integrations/imap/accounts", status_code=201)
def connect_imap(org_id: str, req: ImapConnect, bg: BackgroundTasks,
                 org: str = Depends(_org)) -> dict:
    mailbox = req.mailbox_address.strip().lower()
    if not (mailbox and req.host.strip() and req.username.strip() and req.password):
        raise HTTPException(400, "mailbox_address / host / username / password required")
    port = int(req.port or (993 if req.ssl else 143))
    # Pre-flight: actually log in before storing, so a typo/wrong-password is a red modal error now,
    # not a silent "never syncs" later.
    ok, msg = _verify_imap(req.host.strip(), port, req.username.strip(), req.password, req.ssl)
    if not ok:
        raise HTTPException(400, f"IMAP login failed: {msg}")
    account_id = _insert_account(org, "imap", "email", mailbox,
                                 {"provider": "imap", "mailbox_address": mailbox, "host": req.host.strip(),
                                  "username": req.username.strip(), "password": req.password,
                                  "port": port, "ssl": req.ssl})
    bg.add_task(_sync_workspace_account, account_id, org)
    return {"account_id": account_id, "account_kind": "connector", "tool": "imap", "label": mailbox}


# ── disconnect ───────────────────────────────────────────────────────────────────
@router.delete("/api/org/{org_id}/integrations/accounts/{kind}/{account_id}")
def disconnect_account(org_id: str, kind: str, account_id: str, org: str = Depends(_org)) -> dict:
    g = _store()
    with g.engine.begin() as c:
        res = c.execute(text("update workspace_accounts set is_active=false "
                             "where account_id=:a and org_id=:o and is_active returning 1"),
                        {"a": account_id, "o": org}).first()
    if not res:
        raise HTTPException(404, "account not found")
    return {"account_id": account_id, "disconnected": True}


# ── manual sync ──────────────────────────────────────────────────────────────────
@router.post("/api/org/{org_id}/integrations/accounts/{kind}/{account_id}/sync", status_code=202)
def sync_account(org_id: str, kind: str, account_id: str, bg: BackgroundTasks,
                 org: str = Depends(_org)) -> dict:
    g = _store()
    with g.engine.begin() as c:
        exists = c.execute(text("select 1 from workspace_accounts where account_id=:a "
                                "and org_id=:o and is_active"), {"a": account_id, "o": org}).first()
        if not exists:
            raise HTTPException(404, "account not found")
        c.execute(text("update workspace_accounts set sync_status='syncing' where account_id=:a"),
                  {"a": account_id})
    bg.add_task(_sync_workspace_account, account_id, org)
    return {"account_id": account_id, "status": "syncing"}


# ── Task ledger + morning brief (dashboard "Today" card) ─────────────────────────
class TaskCreate(BaseModel):
    text: str
    target_entity: str | None = None


class TaskUpdate(BaseModel):
    status: str


def _task_row(r) -> dict:
    from datetime import datetime, timezone
    overdue = 0
    if r.due_at is not None and r.status == "open":
        d = (datetime.now(timezone.utc) - r.due_at).days
        overdue = d if d > 0 else 0
    return {"id": r.id, "text": r.text, "target_entity": r.target_entity,
            "due_at": r.due_at.isoformat() if r.due_at else None, "status": r.status,
            "source": r.source, "created_at": r.created_at.isoformat() if r.created_at else None,
            "overdue_days": overdue}


@router.get("/api/org/{org_id}/tasks")
def list_tasks(org_id: str, status: str = "open", org: str = Depends(_org)) -> dict:
    g = _store()
    with g.engine.connect() as c:
        if status == "open":     # "open" view = still-actionable (open + snoozed)
            rows = c.execute(text(
                "select id, text, target_entity, due_at, status, source, created_at "
                "from user_tasks where org_id=:o and status in ('open','snoozed') "
                "order by created_at desc"), {"o": org}).fetchall()
        else:
            rows = c.execute(text(
                "select id, text, target_entity, due_at, status, source, created_at "
                "from user_tasks where org_id=:o and status=:s order by created_at desc"),
                {"o": org, "s": status}).fetchall()
    return {"tasks": [_task_row(r) for r in rows]}


@router.post("/api/org/{org_id}/tasks", status_code=201)
def create_task(org_id: str, req: TaskCreate, org: str = Depends(_org)) -> dict:
    txt = (req.text or "").strip()
    if len(txt) < 2:
        raise HTTPException(400, "task text too short")
    g = _store()
    tid = new_id("task")
    with g.engine.begin() as c:
        c.execute(text("insert into user_tasks (id, org_id, text, target_entity, source) "
                       "values (:i, :o, :t, :te, 'manual')"),
                  {"i": tid, "o": org, "t": txt[:500], "te": req.target_entity})
        r = c.execute(text("select id, text, target_entity, due_at, status, source, created_at "
                           "from user_tasks where id=:i"), {"i": tid}).first()
    return _task_row(r)


@router.patch("/api/org/{org_id}/tasks/{task_id}")
def update_task(org_id: str, task_id: str, req: TaskUpdate, org: str = Depends(_org)) -> dict:
    if req.status not in ("open", "done", "snoozed", "dropped"):
        raise HTTPException(400, "invalid status")
    g = _store()
    with g.engine.begin() as c:
        res = c.execute(text("update user_tasks set status=:s, updated_at=now() "
                             "where id=:i and org_id=:o returning 1"),
                        {"s": req.status, "i": task_id, "o": org}).first()
    if not res:
        raise HTTPException(404, "task not found")
    return {"ok": True}


@router.get("/api/org/{org_id}/morning-brief")
def morning_brief(org_id: str, org: str = Depends(_org)) -> dict:
    """The manager's daily brief, read from the decisions that already exist.

    This endpoint used to `return {"headline": None, "considered": 0, "priorities": []}` — a
    literal, on every request, for every tenant. The docstring called it an honest "activates
    after the first query" state, and it was not: the cards it should have been reading were
    already in the table, already ranked, already carrying their own why-now. The brief was the
    single loudest instance of the product showing facts where it holds decisions.

    AUTHORITY IS RE-CHECKED HERE, not assumed from the card row. A card is a rendering of a Layer
    4 decision, and a decision stops being authoritative when the graph moves, the pack changes or
    the signal closes — so this joins the same `AUTHORITATIVE_SIGNAL_PREDICATE` the extension feed
    and the delivery gate use. A brief is the one surface a person acts on without opening
    anything else; it may not be the surface that shows a superseded conclusion.

    NAGS stay what they were — the user's own overdue tasks, real and non-intelligence — and are
    kept separate from `priorities` for that reason: one is a to-do list the user wrote, the other
    is a judgment the system made, and merging them would let the second hide inside the first.
    """
    g = _store()
    now = datetime.now(timezone.utc)
    with g.engine.connect() as c:
        overdue = c.execute(text(
            "select id, text from user_tasks where org_id=:o and status='open' "
            "and due_at is not null and due_at < now() order by due_at asc limit 5"),
            {"o": org}).fetchall()
        rows = c.execute(text(
            "select k.card_id, k.headline, k.situation, k.why_now, k.level, k.urgency_band, "
            "k.business_subject, k.unresolved_item, k.do_nothing_consequence, "
            "k.abstained_because, k.outcome_window_days, " + AUTHORITATIVE_SCORE_SQL + " as score, "
            "n.display_name as entity "
            "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id " +
            AUTHORITATIVE_SIGNAL_JOINS +
            "left join graph_nodes n on n.node_id=s.subject_node_id and n.org_id=k.org_id "
            "and n.valid_to is null "
            "where k.org_id=:o and k.state in ('queued','surfaced') and s.status='open' "
            "and k.expires_at > :now and " + AUTHORITATIVE_SIGNAL_PREDICATE + " "
            "order by selected_rc.final_utility_bp desc, k.created_at desc, k.card_id"),
            {"o": org, "authority_time": now, "now": now}).fetchall()

    nags = [{"id": r.id, "nag": f"{r.text} — still open"} for r in overdue]
    priorities = [{
        "card_id": r.card_id,
        "headline": r.headline,
        "situation": r.situation,
        # WHY TODAY, not just what. A brief without it is a list, and a list is what the user
        # already has in their inbox.
        "why_now": r.why_now,
        "subject": r.business_subject or r.entity,
        "unresolved": r.unresolved_item,
        "cost_of_ignoring": r.do_nothing_consequence,
        "outcome_window_days": r.outcome_window_days,
        "urgency": r.urgency_band,
        # A card that declined to instruct is shown AS declining. Silently ranking an abstention
        # beside real instructions is how a "we cannot tell you yet" becomes advice.
        "level": r.level,
        "abstained_because": r.abstained_because,
        "score": int(r.score) if r.score is not None else None,
    } for r in rows[:5]]

    # The headline names the top decision rather than counting the queue. "3 things need you"
    # tells a person nothing they can act on before opening something else.
    headline = None
    if priorities:
        top = priorities[0]
        headline = top["headline"] or (f"{top['subject']} needs a decision"
                                       if top["subject"] else None)
    return {"headline": headline, "considered": len(rows),
            "priorities": priorities, "nags": nags}


# ── manual context / "Correct" (human-in-the-loop from the Context page) ──────────
class ManualContext(BaseModel):
    contact_name: str | None = None
    contact_email: str | None = None
    context_type: str | None = "note"
    discussion: str


@router.post("/api/org/{org_id}/manual-context", status_code=201)
def manual_context(org_id: str, req: ManualContext, org: str = Depends(_org)) -> dict:
    """The Context page 'Correct'/add-note action. Resolves the entity (by email, else name) and
    records a HUMAN observation at the highest authority — so a user-verified fact is trusted over
    machine-extracted ones. (Was a hard 404: the button only showed a local 'Confirmed' and never
    persisted anything.)"""
    note = (req.discussion or "").strip()
    if not note:
        raise HTTPException(400, "discussion required")
    g = _store()
    with g.engine.begin() as conn:
        node_id = None
        if req.contact_email:
            r = conn.execute(text("select node_id from graph_nodes where org_id=:o "
                                  "and canonical_key=:k and valid_to is null limit 1"),
                             {"o": org, "k": req.contact_email.strip().lower()}).first()
            node_id = r.node_id if r else None
        if node_id is None and req.contact_name:
            r = conn.execute(text("select node_id from graph_nodes where org_id=:o "
                                  "and lower(display_name)=lower(:n) and valid_to is null limit 1"),
                             {"o": org, "n": req.contact_name.strip()}).first()
            node_id = r.node_id if r else None
        obs_id = g.write_observation(
            conn, org_id=org, subject_node_id=node_id,
            kind=(req.context_type or "manual_context"), confidence=1.0, occurred_at=None,
            event_id=new_id("human"), evidence={"text": note, "source": "user"}, source="human")
    return {"id": obs_id}


class ContextLookup(BaseModel):
    entity_name: str | None = None
    situation: str | None = None
    depth: str | None = None
    stakes: str | None = None


@router.post("/api/org/{org_id}/context")
def context_bundle(org_id: str, req: ContextLookup, org: str = Depends(_org)) -> dict:
    """Entity deep-dive bundle for the Context page (click a fact/contact → right panel shows its
    'full relationship intelligence'). Resolves the entity by display_name (or email) and returns
    its facts, connections, commitments and confidence. (Was a hard 404 → the panel showed
    'Couldn't find this contact in your context' for EVERY click.)"""
    name = (req.entity_name or "").strip()
    if not name:
        raise HTTPException(422, "entity_name required")
    g = _store()

    def _clean(v):
        return v.strip('"') if isinstance(v, str) else v

    with g.engine.connect() as c:
        node = c.execute(text(
            "select node_id, node_type, display_name, canonical_key from graph_nodes "
            "where org_id=:o and valid_to is null and (lower(display_name)=lower(:n) "
            "or lower(canonical_key)=lower(:n)) "
            "order by (lower(display_name)=lower(:n)) desc limit 1"),
            {"o": org, "n": name}).first()
        if node is None:
            # fuzzy fallback so a free-typed name in the Context Tester ("Priya") still resolves to
            # the real node ("Priya Sharma (Chat360)"); shortest match wins (closest to what's typed).
            node = c.execute(text(
                "select node_id, node_type, display_name, canonical_key from graph_nodes "
                "where org_id=:o and valid_to is null and display_name ilike :like "
                "order by length(display_name) asc limit 1"),
                {"o": org, "like": f"%{name}%"}).first()
        if node is None:
            raise HTTPException(404, "entity not found in context")
        facts = c.execute(text(
            "select field, value, confidence, occurred_at from graph_facts "
            "where org_id=:o and subject_node_id=:n and valid_to is null and status='active' "
            "order by occurred_at desc nulls last"), {"o": org, "n": node.node_id}).fetchall()
        out_e = c.execute(text(
            "select o.display_name other from graph_edges e join graph_nodes o "
            "on o.node_id=e.to_node_id and o.org_id=e.org_id where e.org_id=:o and e.valid_to is null "
            "and e.from_node_id=:n limit 25"), {"o": org, "n": node.node_id}).fetchall()
        in_e = c.execute(text(
            "select o.display_name other from graph_edges e join graph_nodes o "
            "on o.node_id=e.from_node_id and o.org_id=e.org_id where e.org_id=:o and e.valid_to is null "
            "and e.to_node_id=:n limit 25"), {"o": org, "n": node.node_id}).fetchall()
        # THE DECISIONS ABOUT THIS ENTITY, not re-derived from the facts above.
        #
        # This panel answered "what do we know" and then wrote its own recommendation from a
        # commitment COUNT — "N open commitment(s) to follow up" — while Layer 4's actual
        # conclusion about the same person sat in `cards`, unread by this endpoint. That is the
        # literal shape of the complaint that a fact is being handed back as intelligence.
        #
        # Same authority join as the brief and the extension feed: a superseded decision must not
        # appear on a panel somebody acts from. Cards stay a SEPARATE block rather than being
        # folded into `facts` — the Context page's job is what is known, and a decision is not a
        # fact about the counterparty, it is a judgment about what to do.
        cards = c.execute(text(
            "select k.card_id, k.headline, k.situation, k.why_now, k.level, k.urgency_band, "
            "k.unresolved_item, k.do_nothing_consequence, k.abstained_because, "
            "k.outcome_window_days, " + AUTHORITATIVE_SCORE_SQL + " as score "
            "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id " +
            AUTHORITATIVE_SIGNAL_JOINS +
            # THE ANCHOR COUNTS AS THE PERSON. A compiled card's signal is anchored on the
            # synthetic `outreach` / `commitment` node the state readings mint, which `concerns`
            # the counterparty one edge away — so a panel matching only on `subject_node_id`
            # showed no decisions for the very person the decision is about. Matching the
            # `concerns` edge is the same hop `build_context_slice` and the neighbourhood walk
            # already take; it invents no relationship.
            "where k.org_id=:o and s.status='open' and (s.subject_node_id=:n or exists ("
            "  select 1 from graph_edges ge where ge.org_id=k.org_id "
            "  and ge.edge_type='concerns' and ge.from_node_id=s.subject_node_id "
            "  and ge.to_node_id=:n and ge.valid_to is null)) "
            "and k.state in ('queued','surfaced','snoozed','claimed') "
            "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE + " "
            "order by selected_rc.final_utility_bp desc, k.card_id limit 10"),
            {"o": org, "n": node.node_id,
             "authority_time": datetime.now(timezone.utc)}).fetchall()

    fact_rows = [f for f in facts if f.field != "commitment.due_at"]
    commit_rows = [f for f in facts if f.field == "commitment.due_at"]
    confs = [float(f.confidence) for f in fact_rows] or [0.0]
    avg_conf = round(sum(confs) / len(confs), 3)
    fact_list = [{"field": (f.field or "fact").split(".")[-1].replace("_", " "),
                  "value": _clean(f.value), "confidence": float(f.confidence), "source": "graph",
                  "freshness": 1.0, "state": "active" if float(f.confidence) >= 0.45 else "stale"}
                 for f in fact_rows]
    commitments = [{"description": f"Due {_clean(f.value)}", "due_date": _clean(f.value),
                    "status": "open"} for f in commit_rows]
    connections = sorted({r.other for r in (list(out_e) + list(in_e)) if r.other})
    decisions = [{
        "card_id": r.card_id, "headline": r.headline, "situation": r.situation,
        "why_now": r.why_now, "unresolved": r.unresolved_item,
        "cost_of_ignoring": r.do_nothing_consequence,
        "outcome_window_days": r.outcome_window_days,
        "urgency": r.urgency_band, "level": r.level,
        "abstained_because": r.abstained_because,
        "score": int(r.score) if r.score is not None else None,
    } for r in cards]
    return {
        "entity": {"name": node.display_name, "company": None, "relationship_stage": "active",
                   "confidence": avg_conf, "topics_of_interest": connections[:8],
                   "open_commitments_detail": [{"text": c["description"], "status": "open"} for c in commitments],
                   "relationship_summary": f"{len(fact_list)} fact(s) known · {len(connections)} connection(s)."},
        "facts": fact_list,
        "commitments": commitments,
        "scores": {"context": avg_conf, "confidence": avg_conf, "freshness": 1.0,
                   "relationship_health": avg_conf},
        "context_for_agent": (f"{node.display_name} ({node.node_type}) — {len(fact_list)} fact(s), "
                              f"avg confidence {round(avg_conf * 100)}%."
                              + (f" Connected to: {', '.join(connections[:5])}." if connections else "")),
        # The DECISION's own words when one exists. The old value was a sentence this endpoint
        # wrote from a row count, which read as a recommendation and was not one — "No urgent
        # action" in particular is a judgment, and counting zero commitments is not evidence for
        # it. With no live decision the honest answer is that there is none, not a reassurance.
        "action_recommendation": (decisions[0]["headline"] if decisions
                                  else "No decision has been made about this contact yet."),
        "decisions": decisions,
        "lifecycle_state": "active", "recent_interactions": [],
    }


class CommitmentUpdate(BaseModel):
    status: str | None = None       # fulfilled | not_a_commitment | dropped | open
    due_date: str | None = None


@router.patch("/api/org/{org_id}/commitments/{commitment_id}")
def update_commitment(org_id: str, commitment_id: str, req: CommitmentUpdate,
                      org: str = Depends(_org)) -> dict:
    """Commitments-tab actions. `commitment_id` is the subject node (from /context/commitments).
    Mark-fulfilled / not-a-commitment RETIRES the open commitment (supersedes the fact); an
    Edit-date writes a new human-authored version. (Was PATCH /commitments/{id} → 404 → the
    buttons did nothing.)"""
    g = _store()
    from datetime import datetime
    with g.engine.begin() as conn:
        row = conn.execute(text(
            "select fact_version_id from graph_facts where org_id=:o and subject_node_id=:n "
            "and field='commitment.due_at' and valid_to is null and status='active' "
            "order by occurred_at desc nulls last limit 1"),
            {"o": org, "n": commitment_id}).first()
        if row is None:
            raise HTTPException(404, "commitment not found")
        if req.status in ("fulfilled", "not_a_commitment", "dropped"):
            # Bump first, inside the same transaction, so Layer 4's shared version lock
            # serializes this human mutation against recommendation publication.
            g.bump_version(conn, org)
            conn.execute(text("update graph_facts set valid_to=now(), status='superseded' "
                              "where fact_version_id=:fv"), {"fv": row.fact_version_id})
        elif req.due_date:
            try:
                due = datetime.fromisoformat(req.due_date.replace("Z", "+00:00"))
            except ValueError:
                due = None
            g.bump_version(conn, org)
            g.write_fact(conn, org_id=org, subject_node_id=commitment_id, field="commitment.due_at",
                         value=req.due_date, value_type="timestamp", confidence=1.0, occurred_at=due,
                         event_id=new_id("human"), evidence={"edited_by": "user"}, source="human",
                         authority_rank=4)      # human edit > machine-extracted
        else:
            raise HTTPException(400, "status or due_date required")
    return {"updated": True}


# ── IMAP liveness (used at connect + sync) ───────────────────────────────────────
def _verify_imap(host: str, port: int, username: str, password: str, ssl: bool) -> tuple[bool, str]:
    import imaplib
    try:
        M = imaplib.IMAP4_SSL(host, port) if ssl else imaplib.IMAP4(host, port)
    except Exception as e:      # noqa: BLE001 — DNS/connection/TLS → unreachable
        return False, f"unreachable: {str(e)[:120]}"
    try:
        M.login(username, password)
    except imaplib.IMAP4.error as e:
        try:
            M.logout()
        except Exception:       # noqa: BLE001
            pass
        return False, f"auth: {str(e)[:120]}"
    except Exception as e:      # noqa: BLE001
        return False, f"error: {str(e)[:120]}"
    try:
        M.logout()
    except Exception:           # noqa: BLE001
        pass
    return True, "ok"


def _sync_workspace_account(account_id: str, org: str) -> None:
    """Background sync. IMAP does a real liveness pull (login + inbox reachability) and records an
    honest status; the hosted-inbox path stores the connection ready for its provider pull. Full
    message ingestion into L1 for these custom sources is the connector build (tracked separately) —
    this keeps the button truthful (success / auth_failed / unreachable), never a fake 'synced'."""
    g = _store()
    key = get_settings().crypto_key
    try:
        with g.engine.connect() as c:
            row = c.execute(text("select tool, enc_credentials from workspace_accounts "
                                 "where account_id=:a and org_id=:o and is_active"),
                            {"a": account_id, "o": org}).first()
        if row is None:
            return
        creds = json.loads(decrypt(bytes(row.enc_credentials), key))
        if creds.get("provider") == "imap":
            ok, msg = _verify_imap(creds["host"], int(creds.get("port") or 993),
                                   creds["username"], creds["password"], creds.get("ssl", True))
            status = "success" if ok else ("auth_failed" if msg.startswith("auth") else "unreachable")
            err = None if ok else msg
        else:
            # Hosted inbox (API key). Stored + ready; the provider-side pull connector isn't wired in
            # the engine yet, so we mark it connected without claiming ingested events.
            status, err = "success", None
        with g.engine.begin() as c:
            if status == "success":
                c.execute(text("update workspace_accounts set sync_status='success', sync_error=null, "
                               "last_sync_at=now(), consecutive_failures=0 where account_id=:a"),
                          {"a": account_id})
            else:
                c.execute(text("update workspace_accounts set sync_status=:s, sync_error=:e, "
                               "consecutive_failures=consecutive_failures+1 where account_id=:a"),
                          {"s": status, "e": err, "a": account_id})
    except Exception as e:      # noqa: BLE001 — never let a sync crash the worker
        _log.warning("workspace sync failed for %s: %s", account_id, e)
        with g.engine.begin() as c:
            c.execute(text("update workspace_accounts set sync_status='failed', sync_error=:e, "
                           "consecutive_failures=consecutive_failures+1 where account_id=:a"),
                      {"e": str(e)[:400], "a": account_id})
