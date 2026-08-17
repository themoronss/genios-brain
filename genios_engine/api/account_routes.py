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

from genios_engine.platform.auth import get_current_org, hash_key, hash_password, verify_password
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_log = get_logger("genios.account")
_graph = make_graph_store()

# seat allowance by plan (Settings shows "used / limit"). Trial is deliberately small.
_SEAT_LIMIT = {"trial": 2, "startup": 5, "growth": 15, "scale": 50}
# monthly credit allowance by plan — period_used counts billable /v1/intelligence/query decisions.
_CREDIT_LIMIT = {"trial": 10_000, "startup": 2000, "growth": 10000, "scale": 50000}


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _org_row(c, org_id: str):
    r = c.execute(text("select id, name, email, pass_hash, subscription_tier, plan_status, "
                       "first_name, last_name, company, role, notif_prefs, created_at "
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
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with _graph.engine.connect() as c:
        r = _org_row(c, org)
        used = c.execute(text("select count(*) from decisions where org_id=:o and created_at>=:s"),
                         {"o": org, "s": month_start}).scalar() or 0
        today = c.execute(text("select count(*) from decisions where org_id=:o and created_at>=:s"),
                          {"o": org, "s": day_start}).scalar() or 0
    tier = (r.subscription_tier or "trial").lower()
    limit = _CREDIT_LIMIT.get(tier, 100)
    today_limit = max(1, limit // 30)                       # a rough daily slice of the monthly credits
    return {"plan": tier, "plan_status": r.plan_status or "active",
            "today": int(today), "today_limit": today_limit,
            "period_used": int(used), "period_limit": limit,
            "used": int(today), "limit": today_limit,
            "days_remaining": None, "expires_at": None, "overage_allowed": False}


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
            "seat_limit": _SEAT_LIMIT.get(tier, 3), "plan": tier}


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
        seats = _SEAT_LIMIT.get(tier, 3)
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
    "card_feedback_verdicts", "card_events", "cards", "signals",
    # Layer 4 deletion order is load-bearing: signals reference runs; runs reference context +
    # config; context references capability. Payloads are explicit as defense in depth even though
    # the context FK also cascades them.
    "reasoning_runs", "reasoning_context_payloads", "reasoning_context_snapshots",
    "reasoning_capability_snapshots", "config_snapshots",
    "signal_suppression_log", "decisions", "approvals_queue",
    "rule_mutes", "calibration_nudges", "calibration_runs", "macv_ledger",
    "context_attention", "context_read_models", "graph_change_outbox",
    "discrepancies", "merge_history", "merge_proposals",
    "graph_source_refs", "graph_facts", "graph_edges", "graph_observations",
    "source_identity_map", "graph_nodes", "graph_versions", "baselines",
    "raw_payloads", "prepared_content", "document_jobs", "resource_uploads",
    "l2_extraction_results", "l2_processing_runs", "event_trace", "parked_events",
    "source_coverage", "sync_cursors", "l1_sync_runs", "source_events",
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
        deleted = c.execute(text("delete from orgs where id=:o"), {"o": org})
        if deleted.rowcount != 1:
            raise RuntimeError("account erasure did not delete exactly one organization")
    return {"deleted": True, "upload_files_removed": removed_files}
