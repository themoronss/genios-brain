"""
Plan Enforcer — single source of truth for all plan-based limits.
Called by context.py, bundle_builder.py, and integration endpoints.

Plans: trial (5-day) | hustler (30-day) | startup (30-day)
Upgrades are done manually via DB — no payment gateway.
"""

from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

# ── Plan configuration (source of truth) ─────────────────────────────────────

PLAN_CONFIG: dict = {
    "trial": {
        "period_days": 5,
        "period_contexts": 500,
        "daily_contexts": 100,
        "daily_warn_pct": 0.80,            # warn at 80 → 80 calls/day
        "max_contacts": 100,
        "max_contacts_warn": 80,
        "max_interactions_per_entity": 20,
        "max_entities_per_query": 3,
        "max_output_tokens": 500,
        "max_input_tokens": 1024,
        "max_chain_depth": 2,
        "max_agent_ids": 1,
        "max_api_keys": 1,
        # Trial limits previously throttled real evaluation usage (10 rpm /
        # 50 rph is hit by just opening the dashboard a few times because
        # graph + side-panel each fire a context call). Bumped to match the
        # 100-calls/day quota: 20 rpm / 200 rph is enough headroom for a
        # full trial session without crippling abuse protection.
        "rpm_per_agent": 20,
        "rph_org": 200,
        "context_depth": "full",           # ship real product on every tier
        "overage_allowed": False,
        "integrations_allowed": {"gmail"},
        "operations_allowed": set(),       # no manual context, merge, etc.
        "mr_elite_modes": {"entity"},
        "sync_method": "manual",
        "louvain": False,
        "max_clusters": 1,
        "live_fetch_daily_cap": 10,        # Phase 7: live tool fetches/day
    },
    "hustler": {
        "period_days": 30,
        "period_contexts": 3000,
        "daily_contexts": 200,
        "daily_warn_pct": 0.80,            # warn at 160
        "max_contacts": 300,
        "max_contacts_warn": 240,
        "max_interactions_per_entity": 50,
        "max_entities_per_query": 5,
        "max_output_tokens": 500,
        "max_input_tokens": 2048,
        "max_chain_depth": 3,
        "max_agent_ids": 3,
        "max_api_keys": 1,
        "rpm_per_agent": 20,
        "rph_org": 200,
        "context_depth": "full",
        "overage_allowed": True,
        "overage_cost_per_1k": 500,
        "integrations_allowed": {"gmail", "calendar", "documents"},
        "operations_allowed": {"manual_context", "correct_context", "merge", "override_stage"},
        "mr_elite_modes": {"entity", "temporal"},
        "sync_method": "6h_cron",
        "louvain": True,
        "max_clusters": 3,
        "live_fetch_daily_cap": 100,       # Phase 7
    },
    "startup": {
        "period_days": 30,
        "period_contexts": 10000,
        "daily_contexts": 666,
        "daily_warn_pct": 0.80,            # warn at ~530
        "max_contacts": 2000,
        "max_contacts_warn": 1600,
        "max_interactions_per_entity": 200,
        "max_entities_per_query": 10,
        "max_output_tokens": 4000,
        "max_input_tokens": 4096,
        "max_chain_depth": 5,
        "max_agent_ids": 10,
        "max_api_keys": 3,
        "rpm_per_agent": 50,
        "rph_org": 500,
        "context_depth": "full",
        "overage_allowed": True,
        "overage_cost_per_1k": 400,
        "integrations_allowed": {"gmail", "calendar", "slack", "hubspot", "documents"},
        "operations_allowed": {
            "manual_context", "correct_context", "merge", "override_stage",
            "entity_tagging", "disclosure_control",
        },
        "mr_elite_modes": {"entity", "temporal", "semantic"},
        "sync_method": "realtime_webhook",
        "louvain": True,
        "max_clusters": 10,
        "live_fetch_daily_cap": 1000,      # Phase 7
    },
}

# Depth fields stripped for shallow plans
_SHALLOW_LOCKED_FIELDS = {"authority", "state", "precedents", "authority_score"}


def get_plan_config(tier: str) -> dict:
    """Return plan config for a given tier. Defaults to trial if unknown."""
    return PLAN_CONFIG.get(tier, PLAN_CONFIG["trial"])


# ── Org plan info ─────────────────────────────────────────────────────────────

# In-process 30s cache — plan/tier changes rarely (only on billing events).
# `period_context_count` and `period_reset_at` are cached too; consumers
# needing up-to-the-second quota must call `check_period_quota` directly.
_PLAN_CACHE: dict = {}
_PLAN_CACHE_TTL_S = 30


def _plan_cache_invalidate(org_id: str) -> None:
    """Drop cached plan for an org. Call from billing write paths."""
    _PLAN_CACHE.pop(org_id, None)


def get_org_plan(db: Session, org_id: str) -> dict:
    """
    Fetch org's current plan tier, expiry, and period usage.
    Returns a dict with keys: tier, config, expires_at, plan_status,
    period_context_count, period_reset_at.
    """
    import time as _time
    cached = _PLAN_CACHE.get(org_id)
    if cached and (_time.time() - cached[1]) < _PLAN_CACHE_TTL_S:
        return cached[0]

    row = db.execute(
        text("""
            SELECT
                COALESCE(subscription_tier, 'trial') AS tier,
                plan_expires_at,
                plan_status,
                COALESCE(period_context_count, 0) AS period_context_count,
                period_reset_at
            FROM orgs
            WHERE id = :org_id
        """),
        {"org_id": org_id},
    ).fetchone()

    if not row:
        result = {"tier": "trial", "config": PLAN_CONFIG["trial"], "plan_status": "active",
                  "expires_at": None, "period_context_count": 0, "period_reset_at": None}
    else:
        tier = row.tier or "trial"
        result = {
            "tier": tier,
            "config": get_plan_config(tier),
            "expires_at": row.plan_expires_at,
            "plan_status": row.plan_status or "active",
            "period_context_count": row.period_context_count or 0,
            "period_reset_at": row.period_reset_at,
        }
    _PLAN_CACHE[org_id] = (result, _time.time())
    return result


def is_plan_expired(plan_info: dict) -> bool:
    """Return True if the plan has expired."""
    if plan_info["plan_status"] == "expired":
        return True
    expires_at = plan_info.get("expires_at")
    if expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return now > expires_at


# ── Quota checks ──────────────────────────────────────────────────────────────

def check_period_quota(db: Session, org_id: str) -> dict:
    """
    Check period (daily + total period) context quota.
    Returns: {allowed, tier, daily_used, daily_limit, period_used, period_limit,
              warning, upgrade_required, expires_at}
    """
    plan_info = get_org_plan(db, org_id)
    config = plan_info["config"]
    tier = plan_info["tier"]

    # Plan expired → block
    if is_plan_expired(plan_info):
        return {
            "allowed": False,
            "tier": tier,
            "error_code": "PLAN_EXPIRED",
            "message": "Your plan has expired. Please upgrade to continue.",
            "upgrade_required": True,
        }

    daily_limit = config["daily_contexts"]
    period_limit = config["period_contexts"]

    # Count today's API calls
    daily_used = db.execute(
        text("""
            SELECT COUNT(*) FROM context_calls
            WHERE org_id = :org_id
              AND called_at >= CURRENT_DATE
              AND (source = 'api' OR source IS NULL)
        """),
        {"org_id": org_id},
    ).scalar() or 0

    # Count period API calls (since period_reset_at)
    period_reset_at = plan_info.get("period_reset_at")
    if period_reset_at:
        period_used = db.execute(
            text("""
                SELECT COUNT(*) FROM context_calls
                WHERE org_id = :org_id
                  AND called_at >= :reset_at
                  AND (source = 'api' OR source IS NULL)
            """),
            {"org_id": org_id, "reset_at": period_reset_at},
        ).scalar() or 0
    else:
        period_used = plan_info["period_context_count"]

    daily_warn_threshold = int(daily_limit * config["daily_warn_pct"])
    period_warn_threshold = int(period_limit * config["daily_warn_pct"])

    # Hard block: daily limit hit
    if daily_used >= daily_limit:
        return {
            "allowed": False,
            "tier": tier,
            "error_code": "DAILY_LIMIT_EXCEEDED",
            "message": f"Daily limit of {daily_limit} context calls exceeded.",
            "daily_used": daily_used,
            "daily_limit": daily_limit,
            "period_used": period_used,
            "period_limit": period_limit,
            "upgrade_required": not config["overage_allowed"],
        }

    # Hard block: period limit hit (trial = no overage)
    if period_used >= period_limit:
        if not config["overage_allowed"]:
            return {
                "allowed": False,
                "tier": tier,
                "error_code": "QUOTA_EXCEEDED",
                "message": f"Period limit of {period_limit} contexts reached. Upgrade to continue.",
                "daily_used": daily_used,
                "daily_limit": daily_limit,
                "period_used": period_used,
                "period_limit": period_limit,
                "upgrade_required": True,
            }
        # Hustler/Startup: overage allowed — still serve but flag it
        return {
            "allowed": True,
            "tier": tier,
            "overage": True,
            "daily_used": daily_used,
            "daily_limit": daily_limit,
            "period_used": period_used,
            "period_limit": period_limit,
            "warning": False,
            "expires_at": plan_info.get("expires_at"),
        }

    warning = daily_used >= daily_warn_threshold or period_used >= period_warn_threshold

    return {
        "allowed": True,
        "tier": tier,
        "daily_used": daily_used,
        "daily_limit": daily_limit,
        "period_used": period_used,
        "period_limit": period_limit,
        "warning": warning,
        "overage": False,
        "expires_at": plan_info.get("expires_at"),
    }


def check_contact_limit(db: Session, org_id: str) -> dict:
    """
    Returns warning/block status for contact count vs plan limit.
    Call before creating a new contact.
    """
    plan_info = get_org_plan(db, org_id)
    config = plan_info["config"]

    contact_count = db.execute(
        text("SELECT COUNT(*) FROM contacts WHERE org_id = :org_id AND (is_archived IS FALSE OR is_archived IS NULL)"),
        {"org_id": org_id},
    ).scalar() or 0

    max_c = config["max_contacts"]
    warn_c = config["max_contacts_warn"]

    if contact_count >= max_c:
        return {"allowed": False, "count": contact_count, "limit": max_c,
                "message": f"Contact limit of {max_c} reached for {plan_info['tier']} plan."}
    return {
        "allowed": True, "count": contact_count, "limit": max_c,
        "warning": contact_count >= warn_c,
    }


# ── Integration / operation access ───────────────────────────────────────────

def require_integration(db: Session, org_id: str, tool: str):
    """
    Raise HTTP 403 if `tool` is not available on the org's current plan.
    tool values: gmail | calendar | slack | hubspot | documents
    """
    plan_info = get_org_plan(db, org_id)
    config = plan_info["config"]
    if tool not in config["integrations_allowed"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PLAN_LIMIT",
                "message": f"'{tool}' integration requires a higher plan. Current plan: {plan_info['tier']}.",
                "current_plan": plan_info["tier"],
                "upgrade_required": True,
            },
        )


def require_operation(db: Session, org_id: str, operation: str):
    """
    Raise HTTP 403 if `operation` is not available on the org's current plan.
    operation values: manual_context | correct_context | merge | override_stage |
                      entity_tagging | disclosure_control
    """
    plan_info = get_org_plan(db, org_id)
    config = plan_info["config"]
    if operation not in config["operations_allowed"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PLAN_LIMIT",
                "message": f"'{operation}' requires Hustler plan or higher. Current plan: {plan_info['tier']}.",
                "current_plan": plan_info["tier"],
                "upgrade_required": True,
            },
        )


def require_mr_elite_mode(db: Session, org_id: str, mode: str):
    """
    Raise HTTP 403 if Mr. Elite query mode is not on this plan.
    mode values: entity | temporal | semantic
    """
    plan_info = get_org_plan(db, org_id)
    config = plan_info["config"]
    if mode not in config["mr_elite_modes"]:
        required = {"temporal": "hustler", "semantic": "startup"}.get(mode, "startup")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PLAN_LIMIT",
                "message": f"'{mode}' queries require {required.capitalize()} plan or higher.",
                "current_plan": plan_info["tier"],
                "upgrade_required": True,
            },
        )


# ── Bundle depth gating ───────────────────────────────────────────────────────

def apply_bundle_depth(bundle: dict, tier: str) -> dict:
    """
    Strip locked fields from context bundle for shallow-depth plans (trial/hustler).
    Startup gets full depth.
    """
    config = get_plan_config(tier)
    if config["context_depth"] == "full":
        bundle["depth"] = "full"
        return bundle

    # Shallow: remove authority/state/precedent fields
    for field in _SHALLOW_LOCKED_FIELDS:
        bundle.pop(field, None)

    entity = bundle.get("entity") or {}
    for field in _SHALLOW_LOCKED_FIELDS:
        entity.pop(field, None)
    if entity:
        bundle["entity"] = entity

    bundle["depth"] = "shallow"
    bundle["locked_fields"] = sorted(_SHALLOW_LOCKED_FIELDS)
    return bundle


def truncate_bundle_tokens(bundle: dict, tier: str) -> dict:
    """
    Truncate context_for_agent text to max_output_tokens for the plan.
    Approximation: 1 token ≈ 4 characters.
    """
    config = get_plan_config(tier)
    max_tokens = config["max_output_tokens"]
    max_chars = max_tokens * 4

    ctx = bundle.get("context_for_agent", "")
    if len(ctx) > max_chars:
        bundle["context_for_agent"] = ctx[:max_chars] + "…"
        bundle["truncated"] = True
        bundle["max_tokens"] = max_tokens

    return bundle


def truncate_interactions(interactions: list, tier: str) -> list:
    """Return at most max_interactions_per_entity for the plan."""
    config = get_plan_config(tier)
    return interactions[: config["max_interactions_per_entity"]]


# ── Plan expiry background check ──────────────────────────────────────────────

def expire_stale_plans(db: Session):
    """
    Mark expired trial/paid plans as 'expired'.
    Run this from the nightly scheduler.
    """
    try:
        result = db.execute(
            text("""
                UPDATE orgs
                SET plan_status = 'expired'
                WHERE plan_expires_at IS NOT NULL
                  AND plan_expires_at < NOW()
                  AND plan_status = 'active'
                RETURNING id, subscription_tier
            """),
        )
        expired = result.fetchall()
        db.commit()
        if expired:
            logger.info(f"Expired {len(expired)} plans: {[str(r[0]) for r in expired]}")
        return len(expired)
    except Exception as e:
        logger.error(f"Plan expiry job failed: {e}")
        db.rollback()
        return 0
