"""Atomic single-pool credit deduction + immutable ledger.

Single visible pool — every operation drains from `orgs.credits` (and
`orgs.topup_credits` first when draining, so plan-included credits expire
at period reset but paid top-ups roll over).

Background system work (proactive scans, ingest-time extraction, nightly
refresh) bills 0 credits to the user — see app.credits.billing_context.
`llm_client.call()` short-circuits when billing is disabled.

The ledger keeps a `bucket` field for analytics ("how much did ingest cost
vs chat?") but the BALANCE columns are unified into a single pool. Pre-099
schema had three separate balance columns; that schema is deprecated and
will be dropped after a deprecation window.

Why atomic:
    SELECT-then-UPDATE quota patterns are TOCTOU-vulnerable — 100 parallel
    requests with 1 credit left would all read "credits=1" before any of
    them write back. `UPDATE ... WHERE balance >= cost RETURNING balance`
    collapses check + decrement into one statement Postgres serializes
    per-row.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Bucket tags (ANALYTICS ONLY — all share the single `credits` pool) ────
# Kept as named constants so call sites still read naturally; the bucket
# value lands in `credit_ledger.bucket` for cost analysis but does NOT
# select a different balance column.
CONTEXT = "context"
SYNC = "sync"
PROACTIVE = "proactive"
GENERIC = "credits"

_VALID_BUCKETS = {CONTEXT, SYNC, PROACTIVE, GENERIC}

# ── Cost map ─────────────────────────────────────────────────────────────────
# Hybrid model: single visible pool, weighted operations, background = 0.
#
# Why these specific weights:
#   • chat is on Gemini Flash (₹0.033/call real cost) — anchored at 1
#   • draft uses Haiku (~₹0.46) — 2 credits ≈ 12x chat margin
#   • reason_sonnet is ~3-5x Haiku price — 3 credits per call
#   • ingest = 1 credit; the LLM-extract cascade it triggers is FREE to
#     user (eaten by us — see UNIT_ECONOMICS.md §2)
#   • background ops = 0 (proactive scans, ingest-time classify/extract)
#   • cache hits = 0
#
# Override per-deployment via env: CREDIT_COST_LLM_CALL_CHAT=2 etc.

DEFAULT_COSTS = {
    # ── User-triggered LLM (reactive) ──────────────────────────────────────
    "llm_call:chat":              1,    # Gemini Flash
    "llm_call:draft":             2,    # Haiku, longer output
    "llm_call:reason_haiku":      1,
    "llm_call:reason_sonnet":     3,    # Sonnet 3-5x Haiku
    "llm_call:narrative":         1,
    "llm_call:shape_response":    1,
    "llm_call:classify_intent":   1,
    "llm_call:compose_retention_offer": 2,
    "llm_call:embed":             0,    # Gemini free tier
    "llm_call:default":           1,    # any new purpose

    # ── Inbound data ingest (per item, NOT per webhook) ───────────────────
    "ingest:email":               1,
    "ingest:sms":                 1,
    "ingest:call":                2,    # call includes transcript
    # ── Outbound sends ────────────────────────────────────────────────────
    "send:email":                 2,    # provider fee + persist
    "send:sms":                   2,    # Twilio fee
    # ── Background sync record fetches ────────────────────────────────────
    "sync:gmail_record":          1,
    "sync:calendar_record":       1,
    "sync:slack_record":          1,
    "sync:hubspot_record":        1,
    "sync:jira_record":           1,
    "sync:notion_record":         1,
    "sync:docs_record":           1,
    "sync:drive_record":          1,
    "sync:sheets_record":         1,
    "sync:inkbox_record":         1,
    "sync:imap_record":           1,
    "sync:generic_record":        1,
    "sync:default":               1,

    # ── Resources tab (manual + upload) ───────────────────────────────────
    # 1 cr per input item, matching the sync model. Manual = 1 typed
    # entry. Upload = 1 cr per chunk emitted (so a 1-page note is 1 cr,
    # a 50-page contract is ~25 cr — predictable for the customer and
    # the LLM cost is genuinely linear in chunks).
    "resources:manual_entry":     1,
    "resources:upload_chunk":     1,

    # ── Gmail email attachments ──────────────────────────────────────────
    # The email itself bills under sync:gmail_record. Each attachment we
    # parse + extract from is a separate item — same 1 cr rate.
    "sync:gmail_attachment":      1,

    # ── Custom adapter mapping (Sonnet, one-time) ────────────────────────
    # Rare but pricey (~$0.10-0.30 of model spend). 3 cr matches the
    # Sonnet-decision rate — same model class, same fairness signal.
    # Margin on this single row is thin (sometimes negative on cheaper
    # plans) but the source then unlocks unlimited 1cr/record sync, so
    # the lifetime economics work out. Trial users get the first one free
    # via the grace check in core/api/mapping.py.
    "custom_adapter:mapping":     3,

    # ── Background ops (free to user, cost eaten internally) ───────────────
    # Listed for completeness; llm/client.py skips deduct when
    # billing_disabled() context is active, so these are 0-charged in
    # practice. The keys exist so future code with bill_credits=True
    # can charge them if needed.
    "proactive:llm_call:classify_email":          0,
    "proactive:llm_call:extract_entities":        0,
    "proactive:llm_call:calendar_extract":        0,
    "proactive:llm_call:judge_insight":           0,
    "proactive:llm_call:compose_retention_offer": 0,
    "proactive:llm_call:embed":                   0,
    "proactive:llm_call:default":                 0,
    "proactive:default":                          0,
}


def _cost_override(key: str) -> Optional[int]:
    """Allow per-deployment overrides via env: CREDIT_COST_LLM_CALL_CHAT=2."""
    env_key = "CREDIT_COST_" + key.upper().replace(":", "_").replace("-", "_")
    raw = os.getenv(env_key)
    if raw is None:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning(f"{env_key}={raw!r} ignored — must be a non-negative int")
        return None


def estimate_cost(reason: str, *, units: int = 1) -> int:
    """Look up the credit cost for a reason. `units` multiplies (e.g. tokens).

    Lookup order:
      1. Env override CREDIT_COST_<UPPER_REASON>=N
      2. Exact key in DEFAULT_COSTS
      3. Cascading family fallback (e.g. 'llm_call:new_purpose' →
         'llm_call:default')
      4. Final fallback: 1

    Family fallback makes new LLM purposes safely chargeable without code
    grep — they bill the family default until tuned explicitly.
    """
    override = _cost_override(reason)
    if override is not None:
        return override * max(1, units)

    if reason in DEFAULT_COSTS:
        return DEFAULT_COSTS[reason] * max(1, units)

    parts = reason.split(":")
    while len(parts) > 1:
        parts.pop()
        family_key = ":".join(parts + ["default"])
        if family_key in DEFAULT_COSTS:
            return DEFAULT_COSTS[family_key] * max(1, units)

    return 1 * max(1, units)


# ── Errors ───────────────────────────────────────────────────────────────────
class InsufficientCredits(Exception):
    """Raised when the atomic deduct returns 0 rows (balance < cost).

    Carries the requested + available so route handlers can format a 402
    Payment Required response pointing the user at top-up / upgrade.
    """

    def __init__(self, *, org_id: str, bucket: str, requested: int, available: int):
        self.org_id = org_id
        self.bucket = bucket
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient credits for org={org_id}: "
            f"need {requested}, have {available} (reason tag: {bucket})"
        )


@dataclass
class DeductResult:
    ledger_id: int
    balance_after: int
    bucket: str
    amount: int
    idempotent_hit: bool = False


# ── Core operations (single pool) ────────────────────────────────────────────
def deduct(
    db: Session,
    *,
    org_id: str,
    bucket: str = GENERIC,
    reason: str,
    amount: Optional[int] = None,
    units: int = 1,
    idempotency_key: Optional[str] = None,
    related_kind: Optional[str] = None,
    related_id: Optional[str] = None,
    agent_uuid: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> DeductResult:
    """Atomically deduct credits and write an immutable ledger row.

    Single-pool semantics: every deduction drains `orgs.topup_credits`
    first (paid top-ups), then `orgs.credits` (plan-included). The
    `bucket` arg is a free-form analytics tag — it lands in the ledger
    row but does NOT pick a different balance column.

    Returns DeductResult on success. Raises InsufficientCredits if the
    pool is below `amount`. Caller owns the transaction — pass a session
    that has not yet committed.

    Idempotency: if `idempotency_key` is provided and a ledger row exists
    for (org_id, key), returns the existing row and skips the deduct.
    Safe for Celery retries / Razorpay webhook replays.
    """
    if bucket not in _VALID_BUCKETS:
        # Accept anyway as analytics tag — log so we notice unmapped buckets.
        logger.debug(f"deduct() got non-standard bucket tag {bucket!r}")

    cost = amount if amount is not None else estimate_cost(reason, units=units)
    if cost <= 0:
        # Free op (cached embed, background work). Skip ledger entirely.
        return DeductResult(ledger_id=0, balance_after=-1, bucket=bucket, amount=0)

    # ── Idempotency short-circuit ────────────────────────────────────────
    if idempotency_key:
        existing = db.execute(
            text("""
                SELECT id, balance_after, amount FROM credit_ledger
                WHERE org_id = :org AND idempotency_key = :key
                LIMIT 1
            """),
            {"org": org_id, "key": idempotency_key},
        ).fetchone()
        if existing:
            return DeductResult(
                ledger_id=int(existing.id),
                balance_after=int(existing.balance_after),
                bucket=bucket,
                amount=abs(int(existing.amount)),
                idempotent_hit=True,
            )

    # ── Atomic deduct ────────────────────────────────────────────────────
    # Drain topup_credits first (so plan credits expire at period reset
    # while paid top-ups roll over). Atomicity comes from Postgres
    # per-row serialization on the UPDATE WHERE clause — no SELECT-then-
    # UPDATE TOCTOU window.
    row = db.execute(
        text("""
            UPDATE orgs
            SET
                topup_credits = GREATEST(topup_credits - :cost, 0),
                credits       = credits
                              - GREATEST(:cost - topup_credits, 0)
            WHERE id = :org
              AND (credits + topup_credits) >= :cost
            RETURNING credits AS plan_left, topup_credits AS topup_left
        """),
        {"org": org_id, "cost": cost},
    ).fetchone()

    if row is None:
        avail_row = db.execute(
            text("""
                SELECT COALESCE(credits, 0) + COALESCE(topup_credits, 0) AS total
                FROM orgs WHERE id = :org
            """),
            {"org": org_id},
        ).fetchone()
        available = int(avail_row.total) if avail_row else 0
        raise InsufficientCredits(
            org_id=org_id, bucket=bucket, requested=cost, available=available,
        )

    new_balance = int(row.plan_left) + int(row.topup_left)

    # ── Immutable ledger row ─────────────────────────────────────────────
    try:
        ledger_row = db.execute(
            text("""
                INSERT INTO credit_ledger
                    (org_id, bucket, kind, amount, balance_after,
                     reason, related_kind, related_id, agent_uuid,
                     idempotency_key, metadata)
                VALUES
                    (:org, :bucket, 'deduct', :amount, :balance,
                     :reason, :rkind, :rid, :agent,
                     :key, CAST(:meta AS JSONB))
                RETURNING id
            """),
            {
                "org": org_id, "bucket": bucket, "amount": -cost,
                "balance": new_balance, "reason": reason,
                "rkind": related_kind, "rid": related_id, "agent": agent_uuid,
                "key": idempotency_key,
                "meta": _to_json(metadata),
            },
        ).fetchone()
    except IntegrityError:
        # Lost a race to a parallel worker writing the same idempotency
        # key between our short-circuit and the INSERT. Roll back the
        # decrement so we don't double-charge, return the winning row.
        db.rollback()
        if idempotency_key:
            existing = db.execute(
                text("""
                    SELECT id, balance_after, amount FROM credit_ledger
                    WHERE org_id = :org AND idempotency_key = :key
                """),
                {"org": org_id, "key": idempotency_key},
            ).fetchone()
            if existing:
                return DeductResult(
                    ledger_id=int(existing.id),
                    balance_after=int(existing.balance_after),
                    bucket=bucket,
                    amount=abs(int(existing.amount)),
                    idempotent_hit=True,
                )
        raise

    # ── Analytics — credit consumption by bucket (sync / context / proactive) ──
    # Fires only on a real deduction (idempotent hits returned earlier), so
    # PostHog can show "credits used / day" and where they go.
    try:
        from app.core.analytics import capture
        capture(org_id, "credits_used", {
            "credits": cost,
            "bucket": bucket,
            "reason": reason,
            "balance_after": new_balance,
        })
    except Exception:
        pass

    # Push the new balance to any open dashboard SSE stream (no client polling).
    try:
        from app.credits.stream_hub import hub
        hub.publish(org_id)
    except Exception:
        pass

    return DeductResult(
        ledger_id=int(ledger_row.id),
        balance_after=new_balance,
        bucket=bucket,
        amount=cost,
    )


def try_deduct(
    db: Session,
    *,
    org_id: str,
    bucket: str = GENERIC,
    reason: str,
    idempotency_key: Optional[str] = None,
    agent_uuid: Optional[str] = None,
    related_kind: Optional[str] = None,
    units: int = 1,
) -> tuple[bool, str]:
    """Non-raising wrapper for sync-loop callers.

    Returns (ok, code):
      • (True,  "ok")
      • (False, "exhausted") — caller should stop the loop
      • (False, "infra")     — DB/credit error, fail-open per call
    """
    try:
        deduct(
            db, org_id=org_id, bucket=bucket, reason=reason,
            idempotency_key=idempotency_key, agent_uuid=agent_uuid,
            related_kind=related_kind, units=units,
        )
        return True, "ok"
    except InsufficientCredits:
        return False, "exhausted"
    except Exception as e:
        logger.warning(f"try_deduct infra error (fail-open): {e}")
        return False, "infra"


def refund(
    db: Session,
    *,
    org_id: str,
    ledger_id: int,
    reason: Optional[str] = None,
) -> Optional[DeductResult]:
    """Reverse a previous deduction. Returns None if not found / already
    refunded / not a deduct. Use when an LLM call fails after credits
    were billed."""
    orig = db.execute(
        text("""
            SELECT id, bucket, amount, kind FROM credit_ledger
            WHERE id = :id AND org_id = :org
        """),
        {"id": ledger_id, "org": org_id},
    ).fetchone()
    if not orig or orig.kind != "deduct":
        return None

    reversed_already = db.execute(
        text("SELECT 1 FROM credit_ledger WHERE reverses_ledger_id = :id LIMIT 1"),
        {"id": ledger_id},
    ).fetchone()
    if reversed_already:
        return None

    refund_amount = abs(int(orig.amount))

    # Refunds credit the plan-pool (not topup) since topup is drained
    # first on deduct; reversing into plan-pool keeps top-ups intact.
    new_row = db.execute(
        text("""
            UPDATE orgs SET credits = credits + :amt
            WHERE id = :org
            RETURNING credits + topup_credits AS total
        """),
        {"org": org_id, "amt": refund_amount},
    ).fetchone()
    if not new_row:
        return None

    new_balance = int(new_row.total)
    ledger_row = db.execute(
        text("""
            INSERT INTO credit_ledger
                (org_id, bucket, kind, amount, balance_after,
                 reason, reverses_ledger_id)
            VALUES (:org, :bucket, 'refund', :amount, :balance,
                    :reason, :rev)
            RETURNING id
        """),
        {
            "org": org_id, "bucket": orig.bucket, "amount": refund_amount,
            "balance": new_balance,
            "reason": reason or f"refund_of_{ledger_id}", "rev": ledger_id,
        },
    ).fetchone()

    return DeductResult(
        ledger_id=int(ledger_row.id),
        balance_after=new_balance,
        bucket=orig.bucket,
        amount=refund_amount,
    )


def grant(
    db: Session,
    *,
    org_id: str,
    bucket: str = GENERIC,
    amount: int,
    reason: str,
    idempotency_key: Optional[str] = None,
) -> DeductResult:
    """Add plan-included credits. Called on plan activation / period reset."""
    if amount <= 0:
        raise ValueError("grant amount must be positive")

    row = db.execute(
        text("""
            UPDATE orgs SET credits = credits + :amt
            WHERE id = :org
            RETURNING credits + topup_credits AS total
        """),
        {"org": org_id, "amt": amount},
    ).fetchone()
    if not row:
        raise ValueError(f"org {org_id} not found")

    ledger_row = db.execute(
        text("""
            INSERT INTO credit_ledger
                (org_id, bucket, kind, amount, balance_after, reason, idempotency_key)
            VALUES (:org, :bucket, 'grant', :amount, :balance, :reason, :key)
            ON CONFLICT (org_id, idempotency_key) WHERE idempotency_key IS NOT NULL
            DO NOTHING
            RETURNING id
        """),
        {
            "org": org_id, "bucket": bucket, "amount": amount,
            "balance": int(row.total), "reason": reason, "key": idempotency_key,
        },
    ).fetchone()

    try:
        from app.credits.stream_hub import hub
        hub.publish(org_id)
    except Exception:
        pass

    return DeductResult(
        ledger_id=int(ledger_row.id) if ledger_row else 0,
        balance_after=int(row.total),
        bucket=bucket,
        amount=amount,
    )


def topup(
    db: Session,
    *,
    org_id: str,
    bucket: str = GENERIC,
    amount: int,
    reason: str,
    related_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> DeductResult:
    """Add paid top-up credits. These land in `topup_credits` so they
    survive period resets, while plan-included `credits` zero out."""
    if amount <= 0:
        raise ValueError("topup amount must be positive")

    row = db.execute(
        text("""
            UPDATE orgs SET topup_credits = topup_credits + :amt
            WHERE id = :org
            RETURNING credits + topup_credits AS total
        """),
        {"org": org_id, "amt": amount},
    ).fetchone()
    if not row:
        raise ValueError(f"org {org_id} not found")

    ledger_row = db.execute(
        text("""
            INSERT INTO credit_ledger
                (org_id, bucket, kind, amount, balance_after,
                 reason, related_kind, related_id, idempotency_key)
            VALUES (:org, :bucket, 'topup', :amount, :balance,
                    :reason, 'subscription', :rid, :key)
            ON CONFLICT (org_id, idempotency_key) WHERE idempotency_key IS NOT NULL
            DO NOTHING
            RETURNING id
        """),
        {
            "org": org_id, "bucket": bucket, "amount": amount,
            "balance": int(row.total), "reason": reason,
            "rid": related_id, "key": idempotency_key,
        },
    ).fetchone()

    try:
        from app.credits.stream_hub import hub
        hub.publish(org_id)
    except Exception:
        pass

    return DeductResult(
        ledger_id=int(ledger_row.id) if ledger_row else 0,
        balance_after=int(row.total),
        bucket=bucket,
        amount=amount,
    )


def balance(db: Session, org_id: str) -> dict:
    """Snapshot for dashboards / billing APIs. Single visible meter +
    breakdown by plan/topup so the UI can show "X of Y remaining"."""
    row = db.execute(
        text("""
            SELECT credits, topup_credits,
                   credit_period_start, credit_period_end, grace_until
            FROM orgs WHERE id = :org
        """),
        {"org": org_id},
    ).fetchone()
    if not row:
        return {
            "total": 0, "plan": 0, "topup": 0,
            "period_start": None, "period_end": None, "grace_until": None,
        }
    return {
        "total":        int(row.credits or 0) + int(row.topup_credits or 0),
        "plan":         int(row.credits or 0),
        "topup":        int(row.topup_credits or 0),
        "period_start": row.credit_period_start.isoformat() if row.credit_period_start else None,
        "period_end":   row.credit_period_end.isoformat() if row.credit_period_end else None,
        "grace_until":  row.grace_until.isoformat() if row.grace_until else None,
    }


# ── Sonnet daily cap (anti-abuse for expensive Sonnet calls) ────────────────
def check_and_increment_sonnet_quota(db: Session, org_id: str, daily_limit: int) -> bool:
    """Atomic daily counter for Sonnet calls. Wraps at midnight UTC.

    Returns True if the call is allowed (counter incremented), False if
    the daily cap is exhausted. Called from llm/client.py before any
    Sonnet invocation; cheaper Haiku/Gemini calls are not gated here.

    daily_limit=0 disables the cap entirely (Enterprise tier).
    """
    if daily_limit <= 0:
        return True

    # Single UPDATE handles both reset and increment atomically. The
    # CASE WHEN compares reset_at to today's midnight UTC — if older,
    # reset count to 1; otherwise increment. The WHERE clause blocks
    # the increment if we'd exceed the limit (count would become > N).
    row = db.execute(
        text("""
            UPDATE orgs
            SET
                sonnet_daily_count = CASE
                    WHEN sonnet_daily_reset_at IS NULL
                      OR sonnet_daily_reset_at < date_trunc('day', NOW() AT TIME ZONE 'UTC')
                    THEN 1
                    ELSE sonnet_daily_count + 1
                END,
                sonnet_daily_reset_at = CASE
                    WHEN sonnet_daily_reset_at IS NULL
                      OR sonnet_daily_reset_at < date_trunc('day', NOW() AT TIME ZONE 'UTC')
                    THEN date_trunc('day', NOW() AT TIME ZONE 'UTC')
                    ELSE sonnet_daily_reset_at
                END
            WHERE id = :org
              AND (
                  sonnet_daily_reset_at IS NULL
                  OR sonnet_daily_reset_at < date_trunc('day', NOW() AT TIME ZONE 'UTC')
                  OR sonnet_daily_count < :limit
              )
            RETURNING sonnet_daily_count
        """),
        {"org": org_id, "limit": daily_limit},
    ).fetchone()
    return row is not None


# ── Internal helpers ─────────────────────────────────────────────────────────
def _to_json(meta: Optional[dict]) -> Optional[str]:
    if meta is None:
        return None
    import json
    try:
        return json.dumps(meta, default=str)
    except Exception:
        return None
