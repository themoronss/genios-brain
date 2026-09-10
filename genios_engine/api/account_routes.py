"""Account & org management — the Settings page. Dashboard-auth, path-scoped /api/org/{org}/*
(the {org} in the path is validated against the credential, never trusted). Profile, password,
API-key rotation, usage, notification prefs, team members/invites, and the two destructive actions
(wipe graph / delete account). Ported onto the engine's orgs/api_keys model so Settings is real,
not dead calls.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform import billing as B
from genios_engine.platform.auth import get_current_org, hash_key, hash_password, verify_password
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_log = get_logger("genios.account")
_graph = make_graph_store()

# seat allowance by plan (Settings shows "used / limit"). Trial is deliberately small.
# Seats and the credit allowance both come from `platform/billing.PLANS`. Two rival tables used
# to live here: they had no row for `early` — a real, sellable plan — so a paying Early customer
# got the 3-seat fallback and a 100-credit allowance, and they priced `startup` at 2,000 credits
# against billing.py's 100,000.


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _org_row(c, org_id: str):
    r = c.execute(text("select id, name, email, pass_hash, subscription_tier, plan_status, "
                       "first_name, last_name, company, role, notif_prefs, created_at, "
                       # the billing period columns: /usage reports the ORG's period and
                       # its real expiry, not the calendar month and a hardcoded null
                       "plan_expires_at, grace_until, credit_period_start "
                       "from orgs where id=:o"), {"o": org_id}).first()
    if r is None:
        raise HTTPException(404, "org not found")
    return r


# ── profile ────────────────────────────────────────────────────────────────
@router.get("/api/org/{org_id}/profile")
def get_profile(org_id: str, org: str = Depends(_org)) -> dict:
    with _graph.engine.connect() as c:
        r = _org_row(c, org)
    # Single full-name model: orgs.name is the person's full name; orgs.company is the workspace.
    # Company no longer falls back to the person's name (that was showing the user's name as the
    # "Company"). first_name/last_name kept in the response (derived) only for older callers.
    full_name = r.name or " ".join(x for x in (r.first_name, r.last_name) if x) or ""
    parts = full_name.split(" ", 1)
    return {"full_name": full_name,
            "first_name": parts[0] if parts else "", "last_name": parts[1] if len(parts) > 1 else "",
            "email": r.email or "", "company": r.company or "", "role": r.role or ""}


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    company: str | None = None
    role: str | None = None


@router.patch("/api/org/{org_id}/profile")
def update_profile(org_id: str, body: ProfileUpdate, org: str = Depends(_org)) -> dict:
    fields, params = [], {"o": org}
    # full_name is the person's name → orgs.name (what the sidebar/greeting reads).
    col_map = {"full_name": "name", "company": "company", "role": "role"}
    for attr, col in col_map.items():
        v = getattr(body, attr)
        if v is not None:
            fields.append(f"{col}=:{col}")
            params[col] = v.strip()[:120]
    if not fields:
        return {"updated": False}
    with _graph.engine.begin() as c:
        c.execute(text(f"update orgs set {', '.join(fields)} where id=:o"), params)
    return {"updated": True}


# ── password ─────────────────────────────────────────────────────────────────
class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/api/org/{org_id}/password/change")
def change_password(org_id: str, body: PasswordChange, org: str = Depends(_org)) -> dict:
    if len(body.new_password or "") < 8:
        raise HTTPException(400, "new password must be at least 8 characters")
    with _graph.engine.begin() as c:
        r = _org_row(c, org)
        if not r.pass_hash or not verify_password(body.current_password, r.pass_hash):
            raise HTTPException(403, "current password is incorrect")
        c.execute(text("update orgs set pass_hash=:h where id=:o"),
                  {"h": hash_password(body.new_password), "o": org})
    return {"updated": True}


# ── API key rotation ─────────────────────────────────────────────────────────
@router.post("/api/org/{org_id}/apikey/regenerate")
def regenerate_api_key(org_id: str, org: str = Depends(_org)) -> dict:
    raw = "gn_live_" + secrets.token_urlsafe(24)
    kh, prefix = hash_key(raw), raw[:12]
    with _graph.engine.begin() as c:
        _org_row(c, org)
        c.execute(text("update orgs set api_key_hash=:h where id=:o"), {"h": kh, "o": org})
        # keep a display row in api_keys (deactivate old primary rows first)
        c.execute(text("update api_keys set is_active=false where org_id=:o and name='primary'"),
                  {"o": org})
        c.execute(text("insert into api_keys (id, org_id, key_hash, key_prefix, name, scopes) "
                       "values (:i,:o,:h,:p,'primary','{read_context}')"),
                  {"i": new_id("key"), "o": org, "h": kh, "p": prefix})
    # frontend reads `api_key` (matches fetchApiKey + auth_routes convention); keep `key` too.
    return {"api_key": raw, "key": raw}


@router.get("/api/org/{org_id}/apikey")
def get_api_key(org_id: str, org: str = Depends(_org)) -> dict:
    """The primary key can't be shown in full (only its hash is stored) — return the safe prefix so
    the Settings 'Primary Key' card can display gn_live_ab12… without a fabricated secret."""
    with _graph.engine.connect() as c:
        r = c.execute(text("select key_prefix from api_keys where org_id=:o and name='primary' "
                           "and is_active order by created_at desc limit 1"), {"o": org}).first()
    prefix = (r.key_prefix if r else None) or "gn_live_"
    return {"api_key": f"{prefix}…", "key_prefix": prefix, "masked": True}


# ── usage ────────────────────────────────────────────────────────────────────
@router.get("/api/org/{org_id}/usage")
def usage(org_id: str, org: str = Depends(_org)) -> dict:
    """What this workspace has actually spent, read from `credit_ledger`.

    This used to count rows in `decisions` since the 1st of the calendar month and divide a
    hardcoded plan limit by 30. It therefore disagreed with the balance in both directions — a
    cached answer writes no decision but also costs nothing, a draft costs credits and writes no
    decision at all, and the period it measured was the calendar month rather than the org's own
    billing period. `expires_at` and `days_remaining` were hardcoded `null` while the columns
    that answer them sat in `orgs`.
    """
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with _graph.engine.connect() as c:
        r = _org_row(c, org)
        bal = B.balance(c, org)
        period_start = getattr(r, "credit_period_start", None) or day_start
        used = c.execute(text(
            "select coalesce(sum(-amount),0) from credit_ledger "
            "where org_id=:o and kind='deduct' and occurred_at>=:s"),
            {"o": org, "s": period_start}).scalar() or 0
        today = c.execute(text(
            "select coalesce(sum(-amount),0) from credit_ledger "
            "where org_id=:o and kind='deduct' and occurred_at>=:s"),
            {"o": org, "s": day_start}).scalar() or 0
        by_bucket = {row.bucket or "other": int(row.n) for row in c.execute(text(
            "select bucket, coalesce(sum(-amount),0) n from credit_ledger "
            "where org_id=:o and kind='deduct' and occurred_at>=:s group by bucket"),
            {"o": org, "s": period_start})}
    tier = B.normalize_plan(r.subscription_tier or "trial")
    plan = B.plan_of(tier)
    expires = getattr(r, "plan_expires_at", None)
    state = B.expiry_state(r.plan_status, expires,
                           getattr(r, "grace_until", None), now=now)
    from genios_engine.platform.quota import sync_status
    sync = sync_status(_graph.engine, org)
    return {"plan": tier, "plan_status": r.plan_status or "active", "state": state,
            # The SECOND meter. Ingestion is included in the plan and never charged in credits —
            # one email costs ~1.3 credits to process, so charging it would empty a free plan
            # before the product had answered anything, and would bill the customer for how much
            # mail other people send them.
            "sync": {"used": sync["used"], "limit": sync["limit"],
                     "remaining": sync["remaining"], "exhausted": sync["exhausted"]},
            "seats_limit": plan.seats, "domains_limit": plan.domains,
            # CREDITS everywhere on this route — the store is points, the customer is not.
            "today": B.to_credits(today), "today_limit": B.to_credits(B.daily_credit_ceiling(tier)),
            "period_used": B.to_credits(used), "period_limit": plan.credits,
            "balance": B.to_credits(bal["balance"]),
            "plan_credits": B.to_credits(bal["plan"]),
            "topup_credits": B.to_credits(bal["topup"]),
            "by_bucket": {k: B.to_credits(v) for k, v in by_bucket.items()},
            "prices": {a: B.to_credits(pts) for a, pts in B.COSTS.items()},
            "free_units": list(B.FREE_UNITS),
            "used": B.to_credits(today), "limit": B.to_credits(B.daily_credit_ceiling(tier)),
            "days_remaining": (max(0, (expires - now).days) if expires else None),
            "expires_at": expires.isoformat() if expires else None,
            "overage_allowed": False}


# ── notification preferences ─────────────────────────────────────────────────
@router.get("/api/org/{org_id}/notifications/preferences")
def get_notif_prefs(org_id: str, org: str = Depends(_org)) -> dict:
    with _graph.engine.connect() as c:
        r = _org_row(c, org)
    prefs = r.notif_prefs if isinstance(r.notif_prefs, dict) else json.loads(r.notif_prefs or "{}")
    # keys MUST match the Settings NotificationsTab toggles, else saved values never bind to a toggle.
    defaults = {"syncComplete": True, "conflictDetected": True, "commitmentOverdue": True,
                "stageChange": True, "lowConfidence": True, "weeklyDigest": False}
    return {**defaults, **prefs}


@router.put("/api/org/{org_id}/notifications/preferences")
def set_notif_prefs(org_id: str, prefs: dict, org: str = Depends(_org)) -> dict:
    clean = {k: bool(v) for k, v in (prefs or {}).items()}
    with _graph.engine.begin() as c:
        c.execute(text("update orgs set notif_prefs=cast(:p as jsonb) where id=:o"),
                  {"p": json.dumps(clean), "o": org})
    return {"saved": True}


# ── source / integration preferences (Sources modal: Gmail, Calendar, …) ──────
# The Sources "preferences" modal PUTs the per-tool connector settings + toggles here. Persisted
# per (org, canonical tool) so a reconnect/restart keeps them; the same normalization as
# connect/sync/disconnect keeps every path agreeing on the tool key.
def _canonical_tool(tool: str) -> str:
    from genios_engine.api.routes import _norm_source   # lazy — avoid an import cycle at module load
    try:
        return _norm_source(tool)
    except Exception:      # noqa: BLE001 — a bad label must never 500 the config save
        return (tool or "").strip().lower()


@router.get("/api/org/{org_id}/integrations/{tool}/config")
def get_integration_config(org_id: str, tool: str, org: str = Depends(_org)) -> dict:
    t = _canonical_tool(tool)
    with _graph.engine.connect() as c:
        r = c.execute(text("select sync_settings, preferences, domains, updated_at "
                           "from integration_preferences where org_id=:o and tool=:t"),
                      {"o": org, "t": t}).first()
    if r is None:
        return {"tool": t, "sync_settings": {}, "preferences": {}, "domains": [],
                "configured": False}
    return {"tool": t, "sync_settings": r.sync_settings or {},
            "preferences": r.preferences or {}, "domains": r.domains or [],
            "updated_at": r.updated_at.isoformat() if r.updated_at else None, "configured": True}


@router.put("/api/org/{org_id}/integrations/{tool}/config")
def set_integration_config(org_id: str, tool: str, body: dict, org: str = Depends(_org)) -> dict:
    t = _canonical_tool(tool)
    if not t:
        raise HTTPException(422, "tool is required")
    sync_settings = body.get("syncSettings") or body.get("sync_settings") or {}
    preferences = body.get("preferences") or {}
    domains = body.get("domains") or []
    if not isinstance(sync_settings, dict) or not isinstance(preferences, dict):
        raise HTTPException(422, "syncSettings and preferences must be JSON objects")
    if not isinstance(domains, list):
        raise HTTPException(422, "domains must be a JSON array")
    try:
        s, p, d = (json.dumps(x, default=str, allow_nan=False)
                   for x in (sync_settings, preferences, domains))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "config must be finite JSON") from exc
    if sum(len(x.encode("utf-8")) for x in (s, p, d)) > 64_000:   # durable config, not a data dump
        raise HTTPException(413, "integration config is too large")
    with _graph.engine.begin() as c:
        c.execute(text(
            "insert into integration_preferences (org_id, tool, sync_settings, preferences, domains) "
            "values (:o, :t, cast(:s as jsonb), cast(:p as jsonb), cast(:d as jsonb)) "
            "on conflict (org_id, tool) do update set sync_settings=excluded.sync_settings, "
            "preferences=excluded.preferences, domains=excluded.domains, "
            "updated_at=clock_timestamp()"),
            {"o": org, "t": t, "s": s, "p": p, "d": d})
    return {"saved": True, "tool": t}


# ── team members / invites ───────────────────────────────────────────────────
@router.get("/api/org/{org_id}/members")
def list_members(org_id: str, org: str = Depends(_org)) -> dict:
    with _graph.engine.connect() as c:
        r = _org_row(c, org)
        owner_name = " ".join(x for x in (r.first_name, r.last_name) if x) or r.name or "Owner"
        members = [{"id": "owner", "email": r.email or "", "name": owner_name, "role": "owner",
                    "invited_at": r.created_at.isoformat() if r.created_at else None,
                    "accepted_at": r.created_at.isoformat() if r.created_at else None,
                    "status": "active"}]
        for m in c.execute(text("select id, email, name, role, invited_at, accepted_at, status "
                                "from org_members where org_id=:o order by invited_at"), {"o": org}):
            members.append({"id": m.id, "email": m.email, "name": m.name or m.email,
                            "role": m.role, "status": m.status,
                            "invited_at": m.invited_at.isoformat() if m.invited_at else None,
                            "accepted_at": m.accepted_at.isoformat() if m.accepted_at else None})
        invites = [{"id": i.id, "email": i.email, "role": i.role,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                    "expires_at": i.expires_at.isoformat() if i.expires_at else None}
                   for i in c.execute(text("select id, email, role, created_at, expires_at "
                                           "from org_invites where org_id=:o order by created_at"),
                                      {"o": org})]
        tier = (r.subscription_tier or "trial").lower()
    return {"members": members, "pending_invites": invites, "count": len(members),
            "seat_limit": B.plan_seat_limit(tier), "plan": tier}


class InviteBody(BaseModel):
    email: str
    role: str = "member"


@router.post("/api/org/{org_id}/members/invite")
def invite_member(org_id: str, body: InviteBody, org: str = Depends(_org)) -> dict:
    email = (body.email or "").strip().lower()
    if "@" not in email:
        raise HTTPException(400, "a valid email is required")
    with _graph.engine.begin() as c:
        r = _org_row(c, org)
        tier = (r.subscription_tier or "trial").lower()
        seats = B.plan_seat_limit(tier)
        taken = 1 + (c.execute(text("select count(*) from org_members where org_id=:o"),
                               {"o": org}).scalar() or 0) \
                  + (c.execute(text("select count(*) from org_invites where org_id=:o"),
                               {"o": org}).scalar() or 0)
        if taken >= seats:
            raise HTTPException(409, f"seat limit reached for the {tier} plan ({seats} seats)")
        c.execute(text("insert into org_invites (id, org_id, email, role) values (:i,:o,:e,:r) "
                       "on conflict (org_id, email) do update set role=:r, created_at=now()"),
                  {"i": new_id("inv"), "o": org, "e": email, "r": body.role})
    return {"invited": True, "email": email, "role": body.role}


@router.delete("/api/org/{org_id}/members/{member_id}")
def remove_member(org_id: str, member_id: str, org: str = Depends(_org)) -> dict:
    if member_id == "owner":
        raise HTTPException(400, "the owner cannot be removed")
    with _graph.engine.begin() as c:
        c.execute(text("delete from org_members where id=:i and org_id=:o"),
                  {"i": member_id, "o": org})
    return {"removed": True}


@router.delete("/api/org/{org_id}/invites/{invite_id}")
def cancel_invite(org_id: str, invite_id: str, org: str = Depends(_org)) -> dict:
    with _graph.engine.begin() as c:
        c.execute(text("delete from org_invites where id=:i and org_id=:o"),
                  {"i": invite_id, "o": org})
    return {"cancelled": True}


# ── destructive: wipe graph / delete account ─────────────────────────────────
# Reset removes the tenant's learned/runtime state while preserving account configuration,
# connected sources, seats, billing ledgers, policies, and channels. Uploaded files are removed
# too: retaining an ``indexed`` file after deleting every derived event/fact would be a false and
# unrecoverable UI state (the upload API has no re-index-existing-file operation).
# Full account deletion is guaranteed separately by org FKs in migration 0033.
_ORG_SCOPED_TABLES = [
    "delivery_outbox", "agent_claims", "card_build_claims", "card_feedback_revisions",
    # migration 0132: who else a card reached by declared responsibility — named staff
    "card_feedback_verdicts", "card_events", "card_recipients", "cards", "signals",
    # Layer 4 deletion order is load-bearing: signals reference runs; runs reference context +
    # config; context references capability. Payloads are explicit as defense in depth even though
    # the context FK also cascades them.
    # Layer 4.5's narratives and consult ledger (migration 0120). The narrative is prose ABOUT a
    # tenant's own counterparties, quoting their own material, so a deletion that skipped it would
    # leave a deleted account's sentences behind; the ledger says what we spent narrating them.
    # Both org FKs cascade on account deletion; these entries are what make /reset erase them too,
    # and the loop below runs with no try/except by design, so a name missing here leaks silently.
    # BEFORE reasoning_runs: the bundle points at a run, and the deletion order in this list is
    # load-bearing.
    "l4_reasoning_bundles", "l4_r_site_calls",
    "reasoning_runs", "reasoning_evidence_digests", "reasoning_evidence_id_map",
    "reasoning_context_payloads", "reasoning_context_snapshots",
    "reasoning_capability_snapshots", "config_snapshots",
    "signal_suppression_log", "decisions", "approvals_queue",
    "rule_mutes", "calibration_nudges", "calibration_runs", "macv_ledger",
    "context_attention", "context_read_models", "graph_change_outbox",
    "discrepancies", "merge_history", "merge_proposals",
    "graph_source_refs", "graph_facts", "graph_edges", "graph_observations",
    # L2.4.1's metric history (migration 0094). `graph_facts` holds what is true now and this
    # holds what was true THEN — one row per subject per metric per period, keyed on a graph node
    # of the tenant's own. It is a behavioural record of their counterparties (how often they were
    # touched, how long a deal sat in a stage), so a deletion that skipped it would leave a
    # deleted customer's engagement history in the one table built to be read across time. The
    # org FK cascades on account deletion; this entry is what makes /reset erase it too — and the
    # loop below runs with no try/except by design, so a name missing here leaks silently.
    "metric_history",
    # L-4's convergence ledger (migration 0105). One row per org holding the semantic fingerprint
    # of that tenant's situations, memberships and lifecycle states, plus — when a tenant breaches
    # `MAX_PASSES` — the ids of the situations still moving. Both are statements about the
    # tenant's own graph, so the hash of a deleted account's situation set has no business
    # outliving it. The org FK cascades on account deletion; this entry is what makes /reset erase
    # it too — and the loop below runs with no try/except by design, so a name missing here leaks
    # silently.
    "l2_convergence",
    # L4 Z6's daily book-level brief (migration 0119). One row per tenant per day holding the
    # ranking of that tenant's own open decisions, the components that produced it, and the
    # headline of every card it ranked. Every byte of it is a statement about this tenant's
    # situations, so it has no business outliving the account; the org FK cascades on account
    # deletion and this entry is what makes /reset erase it too.
    "l4_brief_rankings",
    # L2.4.4's cohorts (migration 0096). `cohort_membership` says which of the tenant's accounts,
    # deals and people sit in which peer group — a statement ABOUT their counterparties (who is in
    # the bottom ARR quartile, who dropped out of the healthy-engagement cohort), keyed on their
    # graph nodes. `cohort_definitions` carries the predicate a human wrote and the human who
    # wrote it. Membership is deleted BEFORE its definition because it also cascades from
    # `cohort_definitions`, and a list that relied on the cascade would be one refactor away from
    # leaving rows behind. Both org FKs cascade on account deletion; these entries are what make
    # /reset erase them too — and the loop below runs with no try/except by design, so a name
    # missing here leaks silently.
    # L2.4.6's peer baselines (migration 0098). Five order statistics per (cohort, metric)
    # per week — an aggregate over the tenant's own counterparties, never over anyone
    # else's (the cross-org baseline is deferred by decision, and the module refuses it).
    # It is still a statement about THIS tenant's population and it outlives the points it
    # was cut from by nothing, so it is erased with them. Deleted BEFORE the cohorts it
    # names, so a ladder never outlives the population it describes. The org FK cascades on
    # account deletion; this entry is what makes /reset erase it too — and the loop below
    # runs with no try/except by design, so a name missing here leaks silently.
    "peer_baselines", "contract_spend_attributions", "l2_model_runs",
    # L2.7.7's resolution claims (migration 0101). One row per (situation, message) M-4 judged —
    # the verbatim sentence somebody wrote, who wrote it, and what we concluded. It quotes the
    # tenant's own mail, so a deletion that skipped it would leave sentences from a deleted
    # customer's inbox behind in the one table built to keep them. Deleted BEFORE the situations
    # it names, so a claim never outlives the situation it was about. The org FK cascades on
    # account deletion; this entry is what makes /reset erase it too — and the loop below runs
    # with no try/except by design, so a name missing here leaks silently.
    "situation_resolution_claims",
    "cohort_membership", "cohort_definitions",
    # L2.1.4's authority view (migration 0097). `authority_rules` names the tenant's own people
    # as approvers by graph node id, quotes the policy document a rule was read from, and states
    # what each of them may sign for — a governance record about their staff, so a deletion that
    # skipped it would leave a deleted customer's approval hierarchy in the database. The org FK
    # cascades on account deletion; this entry is what makes /reset erase it too, and the loop
    # below runs with no try/except by design, so a name missing here leaks silently.
    "authority_rules",
    # L5.0's responsibility scope (migration 0131). `seat_responsibilities` names the tenant's
    # own staff and what each of them answers for — which region, which client, which project,
    # over which interval. That is an org chart in a table: a deletion that skipped it would
    # leave a deleted customer's reporting lines and territory assignments in the database,
    # for exactly the reason the entry above gives about approvers.
    "seat_responsibilities",
    # L5.0-U2 (migration 0130): what each of the tenant's people is working on. A judgement about
    # named staff, so a deletion that skipped it would leave a deleted customer's focus list
    # behind. Cascades from `orgs(id)`; this entry is what makes /reset erase it too.
    "seat_objectives",
    "source_identity_map", "graph_nodes", "graph_versions", "baselines",
    "raw_payloads", "prepared_content", "document_jobs", "resource_uploads",
    "l1_extraction_results", "l2_processing_runs", "event_trace", "parked_events",
    # L1.5.5's conflict record (migration 0087). It holds both sides of a disagreement VERBATIM —
    # contract amounts, renewal dates and the quoted sentences they were read from — so a tenant
    # deletion that skipped it would leave a deleted customer's contract terms in the database.
    # The org FK cascades on account deletion; this entry is what makes /reset erase it too.
    "signal_conflicts",
    # L1.4.5's open lane. It holds message QUOTES — the receipt behind an observation the
    # vocabulary had no word for — so a tenant deletion that skipped it would leave a deleted
    # customer's sentences in a cross-org discovery report. The org FK cascades on account
    # deletion; this row is what makes /reset erase it too.
    "unclassified_observations",
    # L1.1-U2's waitlist: which sources this tenant asked for and could not connect. Demand,
    # but demand attached to a named org — it leaves with the org.
    "source_waitlist",
    # L1.6.8's floor and its ledger (migration 0088). `qualification_drops` holds the tenant's
    # own subject keys and the importance components computed from their amounts and dates —
    # a record of what we decided NOT to show them, which is still their data. The floor row and
    # its changelog name the number a human set for this tenant and who set it. The org FK
    # cascades on account deletion; these entries are what make /reset erase them too.
    "qualification_drops", "qualification_floor_changes", "org_qualification_floors",
    # L1.6.10's rejection ledger (migration 0092). `reason` quotes the tenant's own values back —
    # the amount that was out of range, the kind that was not in the taxonomy, the sentence a
    # receipt-less claim was made in — and `payload_ref` points at a body kept 90 days on this
    # row's own promise. A deletion that skipped it would leave a deleted customer's words behind
    # in the table built to explain what we refused to tell them. The org FK cascades on account
    # deletion; this entry is what makes /reset erase it too.
    "publication_rejections",
    # L1.6.7 term 4 rung 1 (migration 0091). It names the tenant's own vendors and carries the
    # free-text reason a human gave for tagging each one, so it is theirs to have erased. The org
    # FK cascades on account deletion; this entry is what makes /reset erase it too.
    "org_mission_critical_entities",
    # L1.7.4's signal store (migration 0089) — everything Layer 1 CONCLUDED about this tenant.
    # It holds `evidence_refs`, which are verbatim quotes out of the tenant's own mail, plus the
    # subject keys, amounts and dates those quotes were about. A tenant deletion that skipped it
    # would leave a deleted customer's sentences in the database in the one table built to be
    # read by every downstream surface. The org FK cascades on account deletion; this entry is
    # what makes /reset erase it too — and the loop below runs with no try/except by design, so
    # a name missing from this list leaks silently rather than failing loudly.
    "qualified_signals",
    # L1.6.9's lifecycle rows (migration 0093). `subject_key` is ALG-22's derived subject and
    # carries the tenant's own counterparties and deal names, so a deletion that skipped it would
    # leave a deleted customer's subjects behind. The org FK cascades on account deletion; this
    # entry is what makes /reset erase it too.
    "signal_lifecycle",
    # W10/G10's pilot switch (migrations 0085 + 0090). It names a person (`enabled_by`,
    # `disabled_by`) and carries free text about the tenant (`notes`), so it is theirs to have
    # erased. It is also the one entry in this list whose removal changes BEHAVIOUR rather than
    # only deleting data — and it changes it in the safe direction: a tenant whose graph was just
    # wiped comes back on the OLD extraction path until somebody deliberately switches them on
    # again, which is the same default every tenant that never joined the pilot has. The org FK
    # cascades on account deletion; this entry is what makes /reset erase it too.
    "l1_semantic_activation",
    # L2.6's fire log (migration 0100), added by the wave that WIRED it. Until X8 put
    # `patterns.store.evaluate_org` on the drain these three tables were empty on every tenant, so
    # their absence from this list cost nothing; they now accumulate one row per matched anchor per
    # sweep. `pattern_fires.evidence` is the per-condition receipt — the tenant's own facts, quoted
    # — and `pattern_activation` names the person who cleared a pattern for them. Fires are deleted
    # BEFORE the activation row so a fire never outlives the switch that licensed it. All three org
    # FKs cascade on account deletion; these entries are what make /reset erase them too — and the
    # loop below runs with no try/except by design, so a name missing here leaks silently.
    "pattern_fires", "pattern_runs", "edge_coverage_declarations", "pattern_activation",
    # L2.5.8's boundary ledger contains the candidate BSO (including evidence quotes) and the
    # reason it was admitted, held or rejected.  It is tenant content even when the candidate
    # never crossed the boundary, so reset must erase it as deliberately as a published signal.
    "situation_admission_decisions",
    # X8/H8's Layer 2 pilot switch (migration 0106). Same argument as the row above it, and the
    # same behavioural direction: it names a person (`enabled_by`) and carries free text about the
    # tenant (`notes`), and removing it returns the tenant to the state every org that never
    # joined the pilot is in — the pattern shadow pass off, which is off for everyone. A tenant
    # whose graph was just wiped has no fire evidence left to accumulate against anyway. The org
    # FK cascades on account deletion; this entry is what makes /reset erase it too.
    "l2_v2_activation",
    # Y0/E-03's Layer 3 pilot switch (migration 0107). Same argument as the two rows above it and
    # the same behavioural direction: it names a person (`enabled_by`, `disabled_by`) and carries
    # free text about the tenant (`notes`), and removing it returns them to the state every org
    # that never joined the pilot is in — the domain compiler's live pass skipping every corpus,
    # which is where every tenant sits today. One row per activated (org, domain), so a tenant on
    # the Admin pilot leaves no Sales row behind either. The org FK cascades on account deletion;
    # this entry is what makes /reset erase it too — and the loop below runs with no try/except by
    # design, so a name missing here leaks silently.
    "l3_activation",
    # Z0/G-07's Layer 4 pilot switch (migration 0116). Same argument as the three rows above it
    # and the same behavioural direction: it names a person (`enabled_by`, `disabled_by`) and
    # carries free text about the tenant (`notes`), and removing it returns them to the state
    # every org that never joined the pilot is in — the six hardcoded units, the override
    # deciding, no narrative — which is where every tenant sits today. One row per activated
    # (org, feature), so a tenant on the roster pilot leaves no `bundle` row behind either. The
    # org FK cascades on account deletion; this entry is what makes /reset erase it too — and the
    # loop below runs with no try/except by design, so a name missing here leaks silently.
    "l4_activation",
    # N-3's discovery receipt (migration 0113). One row per canon document VERSION this tenant
    # has had read for org rules: which of their own policies and SOPs were opened, what was
    # proposed and what was refused. That is a record about the tenant's own documents, so it
    # dies with them — and clearing it on /reset is also the behaviour a reader expects, because
    # the graph it produced is being wiped and the documents will be read again. The org FK
    # cascades on account deletion; this entry is what makes /reset erase it too — and the loop
    # below runs with no try/except by design, so a name missing here leaks silently.
    "org_rule_discovery_runs",
    "source_coverage",
    # L2.5.5 / L-5 (migration 0104). `situation_absences` is a derived view of situations that
    # are about to be wiped, so leaving it would keep a finding about a deleted customer; and
    # `coverage_epochs` is the tenant's own connection history, which is theirs to have erased.
    # Both cascade on account deletion; these entries are what make /reset erase them too.
    "situation_absences", "coverage_epochs",
    # …and the situations themselves, which the line above assumed were "about to be wiped" and
    # which nothing here wiped. `context_situations` cascades from `orgs`, so ACCOUNT DELETION
    # erased it and `/reset` did not: a tenant that reset its workspace kept every situation the
    # previous graph had produced, and the next sweep's findings landed beside conclusions drawn
    # from facts that no longer exist. The absences were erased and the things they were absences
    # ABOUT survived.
    "context_situations",
    "sync_cursors", "l1_sync_runs", "source_events",
    "agent_events", "human_events",
    "onboarding_progress", "sync_jobs",          # sync progress + durable job queue (org-scoped)
    "integration_preferences",                    # per-tool source settings (Sources modal)
]

_UPLOAD_ROOT = (Path(__file__).resolve().parents[2] / "uploads").resolve()


def _lock_erasure_authority(c, org: str) -> None:
    """Serialize erasure against reasoning publication and every action/claim boundary."""
    c.execute(text("select graph_version from graph_versions where org_id=:o for update"),
              {"o": org})
    c.execute(text("select pack_id from tenant_packs where org_id=:o for update"), {"o": org})


def _remove_upload_files(paths) -> int:
    """Delete only files rooted in GeniOS's upload directory; fail the erasure on any ambiguity."""
    removed = 0
    for raw_path in sorted({str(path) for path in paths if path}):
        try:
            resolved = Path(raw_path).resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise HTTPException(503, "account upload erasure could not be completed safely") from exc
        if resolved == _UPLOAD_ROOT or _UPLOAD_ROOT not in resolved.parents:
            raise HTTPException(503, "account upload erasure refused an unsafe storage path")
        try:
            existed = resolved.exists()
            resolved.unlink(missing_ok=True)
            removed += int(existed)
        except OSError as exc:
            raise HTTPException(503, "account upload erasure could not be completed") from exc
    return removed


def _wipe(c, org: str) -> dict:
    wiped = {}
    for tbl in _ORG_SCOPED_TABLES:
        # The application boots only after all migrations succeed. An erasure that cannot delete a
        # required table must fail visibly and roll back; swallowing a PostgreSQL statement error
        # leaves the transaction aborted and makes a partial-delete response dangerously false.
        res = c.execute(text(f"delete from {tbl} where org_id=:o"), {"o": org})
        wiped[tbl] = res.rowcount
    return wiped


@router.post("/api/org/{org_id}/reset")
def reset_graph(org_id: str, org: str = Depends(_org)) -> dict:
    """Wipe this org's learned graph + signals + cards (keeps the account, connections, tasks).
    User-initiated from Settings with an explicit confirm."""
    with _graph.engine.begin() as c:
        _lock_erasure_authority(c, org)
        upload_paths = [row.storage_path for row in c.execute(text(
            "select storage_path from resource_uploads where org_id=:o "
            "and storage_path is not null"), {"o": org})]
        removed_files = _remove_upload_files(upload_paths)
        wiped = _wipe(c, org)
        # Learned offsets live inside the retained tenant-pack row, not a learning ledger. Clear
        # them under the same pack lock and revoke all prior signal authority in one epoch bump.
        c.execute(text(
            "update tenant_packs set lvl3_config='{}'::jsonb, "
            "authority_revision=authority_revision+1,updated_at=clock_timestamp() "
            "where org_id=:o"), {"o": org})
    from genios_engine.platform.audit import record
    record(org, "data_subject_erasure", actor_type="user", target_type="workspace", target_id=org,
           metadata={"audit_category": "update", "scope": "workspace_reset",
                     "rows_wiped": sum(v for v in wiped.values() if isinstance(v, int)),
                     "upload_files_removed": removed_files})
    return {"wiped": True, "rows": wiped, "upload_files_removed": removed_files}


@router.delete("/api/org/{org_id}/account")
def delete_account(org_id: str, org: str = Depends(_org)) -> dict:
    """Full account deletion — wipe all org data, then remove the org (cascades api_keys). Irreversible."""
    with _graph.engine.begin() as c:
        held = c.execute(text("select id from orgs where id=:o for update"), {"o": org}).first()
        if held is None:
            raise HTTPException(404, "org not found")
        _lock_erasure_authority(c, org)
        upload_paths = [row.storage_path for row in c.execute(text(
            "select storage_path from resource_uploads where org_id=:o and storage_path is not null "),
            {"o": org})]
        removed_files = _remove_upload_files(upload_paths)
        _wipe(c, org)
        # Retained financials (llm_costs / credit_ledger / subscriptions — deliberately absent from
        # _ORG_SCOPED_TABLES and un-cascaded in 0058) would be orphaned rows with an unresolvable
        # org_id once the tenant row goes. Keep identity-only fields so our own accounting stays
        # attributable; no graph, content or message data is carried over.
        c.execute(text(
            "insert into orgs_archive (org_id, name, company, email, subscription_tier, "
            "is_internal, created_at) select id, name, company, email, subscription_tier, "
            "is_internal, created_at from orgs where id=:o "
            "on conflict (org_id) do nothing"), {"o": org})
        deleted = c.execute(text("delete from orgs where id=:o"), {"o": org})
        if deleted.rowcount != 1:
            raise RuntimeError("account erasure did not delete exactly one organization")
    return {"deleted": True, "upload_files_removed": removed_files}
