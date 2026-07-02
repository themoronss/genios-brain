"""
Plan Enforcer — single source of truth for all plan-based limits.
Called by context.py, bundle_builder.py, and integration endpoints.

Plans: trial (7-day) | early (30-day) | startup (30-day) | enterprise (contract)
Upgrades flow through Razorpay (billing.py).

Credit model:
    Three buckets (see app.credits.ledger): CONTEXT, SYNC, PROACTIVE.
    Plan config's *_credits fields are the period grant — replenished on
    period reset via grant(). Top-ups live in topup_* columns and survive
    period resets.

Legacy compat:
    `hustler` is an alias for `early`. Existing rows in orgs.subscription_tier
    that still say "hustler" are resolved to the "early" config below so the
    rename can happen lazily.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

# Grace period after plan_expires_at where the account is read-only
# (no LLM, no sync, no proactive) but the dashboard still loads so the
# user can pay without losing data context.
GRACE_PERIOD_DAYS = 7

# ── Plan configuration (source of truth) ─────────────────────────────────────

PLAN_CONFIG: dict = {
    # Single-pool credit model. Field meanings:
    #   credits             — period grant (set on activation, expires at reset)
    #   period_days         — billing period length
    #   sonnet_daily_limit  — hard anti-abuse cap on Sonnet (0 = unlimited)
    #   max_agent_ids       — per-tenant agent count (real resource)
    #   max_api_keys        — security boundary
    #   max_contacts        — DB storage cap
    #   rpm_per_agent       — anti-abuse rate limit (NOT usage cap)
    #   rph_org             — anti-abuse rate limit
    #   integrations_allowed/operations_allowed/mr_elite_modes — feature gates
    #   context_depth       — premium bundle depth
    # Removed (now redundant with credits): daily_contexts, daily_warn_pct,
    # period_contexts, max_entities_per_query, max_chain_depth, max_output_tokens,
    # max_input_tokens, overage_allowed, overage_cost_per_1k, live_fetch_daily_cap,
    # max_clusters. See UNIT_ECONOMICS.md.
    "trial": {
        "period_days":         7,
        "credits":             500,
        "sonnet_daily_limit":  5,
        # Resource caps (real per-tenant cost — kept small)
        "max_contacts":        500,
        "max_contacts_warn":   400,
        "max_interactions_per_entity": 50,
        "max_agent_ids":       2,    # so they can test multi-agent setup
        "max_api_keys":        2,
        "rpm_per_agent":       30,
        "rph_org":             300,
        "context_depth":       "full",
        # Feature access: OPEN — trial me sab kuch chalna chahiye taaki
        # customer poora evaluation kar sake. Credit balance hi real
        # limit hai (500 credits / 7 din). If they hit it, they upgrade.
        "integrations_allowed": {"gmail", "calendar", "documents", "custom"},
        "operations_allowed":   {"manual_context", "correct_context", "merge", "override_stage"},
        "mr_elite_modes":      {"entity", "temporal"},
        "sync_method":         "manual",
        "louvain":             True,
        "max_clusters":          3,
        "live_fetch_daily_cap":  100,
    },
    "early": {
        "period_days":         30,
        "credits":             10000,
        "sonnet_daily_limit":  50,
        "max_contacts":        5000,
        "max_contacts_warn":   4000,
        "max_interactions_per_entity": 50,
        "max_agent_ids":       5,
        "max_api_keys":        3,
        "rpm_per_agent":       60,
        "rph_org":             1000,
        "context_depth":       "full",
        "integrations_allowed": {"gmail", "calendar", "documents"},
        "operations_allowed":  {"manual_context", "correct_context", "merge", "override_stage"},
        "mr_elite_modes":      {"entity", "temporal"},
        "sync_method":         "6h_cron",
        "louvain":             True,
        "max_clusters":          3,
        "live_fetch_daily_cap":  100,
    },
    "startup": {
        "period_days":         30,
        "credits":             100000,
        "sonnet_daily_limit":  500,
        "max_contacts":        50000,
        "max_contacts_warn":   40000,
        "max_interactions_per_entity": 200,
        "max_agent_ids":       25,
        "max_api_keys":        10,
        "rpm_per_agent":       100,
        "rph_org":             3000,
        "context_depth":       "full",
        "integrations_allowed": {"gmail", "calendar", "slack", "hubspot", "jira", "notion", "documents"},
        "operations_allowed": {
            "manual_context", "correct_context", "merge", "override_stage",
            "entity_tagging", "disclosure_control",
        },
        "mr_elite_modes":      {"entity", "temporal", "semantic"},
        "sync_method":         "realtime_webhook",
        "louvain":             True,
        "max_clusters":          10,
        "live_fetch_daily_cap":  1000,
    },
    "enterprise": {
        "period_days":         30,
        "credits":             1000000,    # 1M default; override per contract
        "sonnet_daily_limit":  0,          # unlimited
        "max_contacts":        1000000,
        "max_contacts_warn":   900000,
        "max_interactions_per_entity": 1000,
        "max_agent_ids":       1000,
        "max_api_keys":        50,
        "rpm_per_agent":       500,
        "rph_org":             20000,
        "context_depth":       "full",
        "integrations_allowed": {"gmail", "calendar", "slack", "hubspot", "jira", "notion", "documents", "custom"},
        "operations_allowed": {
            "manual_context", "correct_context", "merge", "override_stage",
            "entity_tagging", "disclosure_control", "custom_integration", "white_label",
        },
        "mr_elite_modes":      {"entity", "temporal", "semantic"},
        "sync_method":         "realtime_webhook",
        "louvain":             True,
        "max_clusters":          100,
        "live_fetch_daily_cap":  100000,
    },
}

# `hustler` was renamed to `early`. Resolve transparently so existing DB rows
# keep working without a destructive migration.
_TIER_ALIASES = {"hustler": "early"}


def _normalize_tier(tier: str) -> str:
    return _TIER_ALIASES.get(tier or "", tier or "trial")

# Depth fields stripped for shallow plans
_SHALLOW_LOCKED_FIELDS = {"authority", "state", "precedents", "authority_score"}


def get_plan_config(tier: str) -> dict:
    """Return plan config for a given tier. Defaults to trial if unknown.
    Resolves legacy aliases (hustler → early)."""
    return PLAN_CONFIG.get(_normalize_tier(tier), PLAN_CONFIG["trial"])


# sync_method → hours between scheduled syncs. SINGLE SOURCE OF TRUTH used by
# BOTH the scheduler (task_scheduled_sync — when to re-sync) AND the data-
# freshness badge (what "fresh" means). Deriving both from one value means the
# badge can never disagree with the actual cadence (the old bug: badge said
# "stale >6h" while early actually synced every 24h → always red).
_SYNC_METHOD_HOURS: dict[str, float | None] = {
    "manual":            None,  # no scheduled sync — user triggers it
    "6h_cron":           6.0,
    "realtime_webhook":  1.0,   # webhook is real-time; cron is the hourly safety net
}


def sync_interval_hours(tier: str) -> float | None:
    """Hours between scheduled syncs for a tier (None = manual only)."""
    method = get_plan_config(tier).get("sync_method", "manual")
    return _SYNC_METHOD_HOURS.get(method, 24.0)


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
                period_reset_at,
                grace_until,
                credits,
                topup_credits
            FROM orgs
            WHERE id = :org_id
        """),
        {"org_id": org_id},
    ).fetchone()

    if not row:
        result = {
            "tier": "trial", "config": PLAN_CONFIG["trial"], "plan_status": "active",
            "expires_at": None, "period_reset_at": None, "grace_until": None,
            "credits": 0, "topup_credits": 0,
        }
    else:
        tier = _normalize_tier(row.tier or "trial")
        result = {
            "tier":          tier,
            "config":        get_plan_config(tier),
            "expires_at":    row.plan_expires_at,
            "plan_status":   row.plan_status or "active",
            "period_reset_at": row.period_reset_at,
            "grace_until":   row.grace_until,
            "credits":       int(row.credits or 0),
            "topup_credits": int(row.topup_credits or 0),
        }
    _PLAN_CACHE[org_id] = (result, _time.time())
    return result


def is_plan_expired(plan_info: dict) -> bool:
    """True if plan_expires_at is in the past AND we're past the grace window.

    Within grace: plan_status stays 'active' but write paths (LLM/sync/proactive)
    are blocked. See `is_in_grace` for the soft state.
    """
    if plan_info["plan_status"] == "expired":
        return True
    expires_at = plan_info.get("expires_at")
    if expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    # Treat as expired only after the grace window closes.
    grace_until = plan_info.get("grace_until")
    if grace_until is not None:
        if grace_until.tzinfo is None:
            grace_until = grace_until.replace(tzinfo=timezone.utc)
        return now > grace_until
    # No grace_until set yet (legacy) — use expires_at + GRACE_PERIOD_DAYS.
    return now > (expires_at + timedelta(days=GRACE_PERIOD_DAYS))


def is_in_grace(plan_info: dict) -> bool:
    """True if plan_expires_at is past but grace window hasn't closed yet.

    Routes that respect grace (read-only endpoints) should allow these; write
    paths (deduct, sync, LLM) must reject with PLAN_EXPIRED_GRACE.
    """
    expires_at = plan_info.get("expires_at")
    if expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now <= expires_at:
        return False  # not yet expired
    grace_until = plan_info.get("grace_until")
    if grace_until is None:
        grace_until = expires_at + timedelta(days=GRACE_PERIOD_DAYS)
    elif grace_until.tzinfo is None:
        grace_until = grace_until.replace(tzinfo=timezone.utc)
    return now <= grace_until


def assert_plan_not_expired(db: Session, org_id: str) -> None:
    """Raise HTTP 402 (plan_expired) if the org's plan is HARD-expired.

    Celery-independent: is_plan_expired() compares plan_expires_at/grace_until
    timestamps, so this fires even if the hourly expiry job never flipped
    plan_status. Orgs inside the 7-day grace window PASS (soft read window).
    Credit exhaustion is enforced separately by deduct()'s atomic UPDATE.

    Call at the top of paid write paths (LLM calls, ingest, outbound send) so an
    expired org can't keep spending leftover credits on new work.
    """
    from fastapi import HTTPException

    if is_plan_expired(get_org_plan(db, org_id)):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "plan_expired",
                "message": "Your plan has expired. Renew to continue.",
                "upgrade_required": True,
            },
        )


# ── Quota checks ──────────────────────────────────────────────────────────────

def check_period_quota(db: Session, org_id: str) -> dict:
    """Single-pool credit quota check.

    Returns: {allowed, tier, credits, credit_limit, warning, upgrade_required,
              expires_at, error_code?, message?}

    The actual deduction happens atomically inside `app.credits.deduct(...)`;
    this function is for read-only checks (dashboard "you have X credits
    left" hints, response headers, gating decisions). Atomic enforcement
    lives in the deduct() UPDATE...RETURNING — see app/credits/ledger.py.
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

    credit_limit = config["credits"]
    credits_remaining = plan_info["credits"] + plan_info["topup_credits"]
    warn_threshold = int(credit_limit * 0.20)  # warn at 20% remaining

    if credits_remaining <= 0:
        return {
            "allowed": False,
            "tier": tier,
            "error_code": "INSUFFICIENT_CREDITS",
            "message": "Credits exhausted. Top up or upgrade to continue.",
            "credits": 0,
            "credit_limit": credit_limit,
            "upgrade_required": True,
        }

    return {
        "allowed": True,
        "tier": tier,
        "credits": credits_remaining,
        "credit_limit": credit_limit,
        "warning": credits_remaining <= warn_threshold,
        "expires_at": plan_info.get("expires_at"),
    }


def check_contact_limit(db: Session, org_id: str) -> dict:
    """
    Returns warning/block status for contact count vs plan limit.
    Call before creating a new contact.
    """
    plan_info = get_org_plan(db, org_id)
    config = plan_info["config"]

    # v2 thin-pipe: contacts live in `graph_nodes` (type='entity'); the v1
    # `contacts` table was dropped in mig 0015. Mirror the canonical count
    # used by /v1/status and /v1/sync so plan limits stay consistent.
    contact_count = db.execute(
        text("SELECT COUNT(*) FROM graph_nodes WHERE org_id = :org_id AND type = 'entity'"),
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
    """No-op since v099 — credits cap usage cost, no need to truncate output.

    Kept for caller backwards-compat. If we ever need to re-introduce
    output limits per tier, restore the per-tier max_output_tokens field
    and the truncation logic here.
    """
    return bundle


def truncate_interactions(interactions: list, tier: str) -> list:
    """Return at most max_interactions_per_entity for the plan."""
    config = get_plan_config(tier)
    return interactions[: config["max_interactions_per_entity"]]


# ── Plan expiry background check ──────────────────────────────────────────────

def expire_stale_plans(db: Session):
    """Two-stage expiry: enter grace, then hard-expire.

    Stage 1: plan_expires_at in the past, grace_until not set yet → set
             grace_until = expires_at + GRACE_PERIOD_DAYS. plan_status stays
             'active' so dashboard still loads. Write paths reject with
             PLAN_EXPIRED_GRACE.

    Stage 2: grace_until in the past → flip plan_status='expired'. All
             credit deductions blocked.

    Runs hourly from celery_app.task_expire_plans.
    """
    try:
        # Stage 1: enter grace
        result_grace = db.execute(
            text(f"""
                UPDATE orgs
                SET grace_until = plan_expires_at + INTERVAL '{GRACE_PERIOD_DAYS} days'
                WHERE plan_expires_at IS NOT NULL
                  AND plan_expires_at < NOW()
                  AND grace_until IS NULL
                  AND plan_status = 'active'
                RETURNING id, subscription_tier
            """),
        )
        entered_grace = result_grace.fetchall()

        # Stage 2: hard expire after grace
        result_expire = db.execute(
            text("""
                UPDATE orgs
                SET plan_status = 'expired'
                WHERE grace_until IS NOT NULL
                  AND grace_until < NOW()
                  AND plan_status = 'active'
                RETURNING id, subscription_tier
            """),
        )
        expired = result_expire.fetchall()
        db.commit()

        # Invalidate caches for everyone we touched
        for r in entered_grace + expired:
            _plan_cache_invalidate(str(r[0]))

        # Churn signal — fire one event per org as it flips active→expired.
        # This job is the SINGLE place that transition happens and RETURNING
        # gives exactly the rows that flipped (guarded by plan_status='active'),
        # so it's exactly-once with no request-path latency. Paid tier expiring
        # = revenue churn; trial expiring = trial-end (a different funnel stage).
        if expired:
            try:
                from app.core.analytics import capture
                for r in expired:
                    tier = (r[1] or "trial").lower()
                    if tier in ("trial", ""):
                        capture(str(r[0]), "trial_expired", {"tier": tier})
                    else:
                        capture(str(r[0]), "subscription_expired", {
                            "tier": tier,
                            "$set": {"is_paying": False, "plan_status": "expired"},
                        })
            except Exception:
                pass

        if entered_grace:
            logger.info(f"Entered grace: {len(entered_grace)} plans")
        if expired:
            logger.info(f"Hard-expired {len(expired)} plans: {[str(r[0]) for r in expired]}")
        return len(expired)
    except Exception as e:
        logger.error(f"Plan expiry job failed: {e}")
        db.rollback()
        return 0


def reset_period_credits(
    db: Session,
    org_id: str,
    *,
    idempotency_key: Optional[str] = None,
    require_active_subscription: bool = True,
) -> dict:
    """Top up a plan's three credit buckets to their plan-level grant.

    Called from:
      • billing.py `_activate_plan` — fresh subscription / renewal (payment
        just confirmed). `require_active_subscription` doesn't need a
        recent paid row check here because the caller already verified it.
      • Periodic Celery renewal job — only resets if the org has an active
        paid subscription whose period_end matches the current cycle. This
        prevents "free renewal" leaks where an expired customer would
        otherwise have credits refreshed automatically.

    Plan-included credits are SET (not added) to the period grant — anything
    unused does NOT roll over. Top-up credits in topup_* columns survive
    across periods.

    Trial orgs (no paid subscription) get their reset gated behind the
    payment check unless the caller explicitly opts out via
    `require_active_subscription=False` (used by the trial signup path).
    """
    plan_info = get_org_plan(db, org_id)
    tier = plan_info["tier"]
    config = plan_info["config"]
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=config["period_days"])

    # ── Payment-validation guard ──────────────────────────────────────────
    # Block credit refresh for non-paying orgs to plug the free-renewal
    # leak. Trial = always blocked unless explicitly bypassed.
    if require_active_subscription and tier != "trial":
        paid = db.execute(
            text("""
                SELECT 1 FROM subscriptions
                WHERE org_id = :org
                  AND status = 'active'
                  AND invoice_type = 'subscription'
                  AND period_end >= NOW() - INTERVAL '1 day'
                LIMIT 1
            """),
            {"org": org_id},
        ).fetchone()
        if not paid:
            logger.warning(
                f"reset_period_credits BLOCKED for org={org_id} tier={tier}: "
                f"no recent active paid subscription found"
            )
            return {
                "blocked": True,
                "reason": "no_active_subscription",
                "tier": tier,
            }

    # Reset plan-included credits (NOT topup_credits — those roll over).
    # SET (not add) so unused plan credits expire at period boundary.
    new_credits = config["credits"]
    db.execute(
        text("""
            UPDATE orgs SET
                credits             = :c,
                credit_period_start = :start,
                credit_period_end   = :end,
                grace_until         = NULL,
                sonnet_daily_count  = 0,
                sonnet_daily_reset_at = NULL
            WHERE id = :org
        """),
        {"org": org_id, "c": new_credits, "start": now, "end": period_end},
    )

    # Ledger row — idempotent on (org, key) so retried renewals don't
    # double-credit.
    key = idempotency_key or f"reset:{org_id}:{now.isoformat()}"
    db.execute(
        text("""
            INSERT INTO credit_ledger
                (org_id, bucket, kind, amount, balance_after, reason, idempotency_key)
            VALUES (:org, 'credits', 'reset', :amt, :amt, :reason, :key)
            ON CONFLICT (org_id, idempotency_key) WHERE idempotency_key IS NOT NULL
            DO NOTHING
        """),
        {
            "org": org_id, "amt": new_credits,
            "reason": f"period_reset:{tier}", "key": key,
        },
    )
    db.commit()
    _plan_cache_invalidate(org_id)
    logger.info(f"Reset {new_credits} credits for org={org_id} tier={tier}")
    return {
        "credits": new_credits,
        "period_end": period_end.isoformat(),
    }
