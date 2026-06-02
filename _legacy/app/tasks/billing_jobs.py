"""
Billing background jobs.
  run_trial_expiry_emails(db) — send warning email at day 3, expiry email at day 5
  run_overage_invoices(db)    — create overage subscription records at period end
  send_invite_email(...)      — send seat invite email

All email sending uses SMTP env vars:
  SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM
  FRONTEND_URL — base URL for invite accept links

If SMTP env vars are not set, email steps are silently skipped.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM", "noreply@thegenios.com")
FRONTEND_URL  = os.getenv("FRONTEND_URL", "https://app.thegenios.com")


def _send_email(to: str, subject: str, html: str):
    """Send email via SMTP. Silently skipped if SMTP_HOST not configured."""
    if not SMTP_HOST:
        logger.debug(f"SMTP not configured — skipping email to {to}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to], msg.as_string())
        logger.info(f"Email sent: {subject!r} → {to}")
    except Exception as e:
        logger.warning(f"Email send failed to {to}: {e}")


# ── Trial expiry emails ───────────────────────────────────────────────────────

def run_trial_expiry_emails(db: Session):
    """
    Scan all trial orgs and send:
      - Day-3 warning: trial expires in 2 days (plan_expires_at between 1d and 3d from now)
      - Day-5 expiry:  trial just expired (plan_expires_at within last 24h, status just flipped)
    """
    # Warning: expires in ~2 days (48–72h window)
    warning_orgs = db.execute(
        text("""
            SELECT id, email, name
            FROM orgs
            WHERE subscription_tier = 'trial'
              AND plan_status = 'active'
              AND plan_expires_at BETWEEN NOW() + INTERVAL '1 day' AND NOW() + INTERVAL '3 days'
              AND (trial_warning_sent_at IS NULL OR trial_warning_sent_at < NOW() - INTERVAL '4 days')
        """)
    ).fetchall()

    for org in warning_orgs:
        _send_trial_warning(str(org.id), org.email, org.name or "there")
        try:
            db.execute(
                text("UPDATE orgs SET trial_warning_sent_at = NOW() WHERE id = :oid"),
                {"oid": str(org.id)},
            )
        except Exception:
            pass  # column may not exist yet — safe to skip

    # Expired: fired in last 24h
    expired_orgs = db.execute(
        text("""
            SELECT id, email, name
            FROM orgs
            WHERE subscription_tier = 'trial'
              AND plan_status = 'expired'
              AND plan_expires_at > NOW() - INTERVAL '24 hours'
              AND (trial_expired_sent_at IS NULL OR trial_expired_sent_at < NOW() - INTERVAL '7 days')
        """)
    ).fetchall()

    for org in expired_orgs:
        _send_trial_expired(str(org.id), org.email, org.name or "there")
        try:
            db.execute(
                text("UPDATE orgs SET trial_expired_sent_at = NOW() WHERE id = :oid"),
                {"oid": str(org.id)},
            )
        except Exception:
            pass

    db.commit()
    total = len(warning_orgs) + len(expired_orgs)
    if total:
        logger.info(f"Trial emails: {len(warning_orgs)} warnings, {len(expired_orgs)} expired notices")
    return total


def _send_trial_warning(org_id: str, email: str, name: str):
    upgrade_url = f"{FRONTEND_URL}/dashboard/upgrade"
    _send_email(
        to=email,
        subject="Your GeniOS trial expires in 2 days",
        html=f"""
        <p>Hi {name},</p>
        <p>Your GeniOS trial expires in <strong>2 days</strong>.</p>
        <p>Upgrade now to keep access to your relationship graph and context history.</p>
        <p>
          <a href="{upgrade_url}" style="display:inline-block;padding:10px 20px;
            background:#c8962e;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
            Upgrade to Hustler — ₹2,500/mo
          </a>
        </p>
        <p style="color:#999;font-size:12px;">GeniOS · <a href="{FRONTEND_URL}">thegenios.com</a></p>
        """,
    )


def _send_trial_expired(org_id: str, email: str, name: str):
    upgrade_url = f"{FRONTEND_URL}/dashboard/upgrade"
    _send_email(
        to=email,
        subject="Your GeniOS trial has ended",
        html=f"""
        <p>Hi {name},</p>
        <p>Your GeniOS trial has <strong>expired</strong>. Your context graph is preserved —
           upgrade to regain access.</p>
        <p>
          <a href="{upgrade_url}" style="display:inline-block;padding:10px 20px;
            background:#c8962e;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
            Reactivate — from ₹2,500/mo
          </a>
        </p>
        <p style="color:#999;font-size:12px;">GeniOS · <a href="{FRONTEND_URL}">thegenios.com</a></p>
        """,
    )


# ── Overage invoice creation ──────────────────────────────────────────────────

def run_overage_invoices(db: Session):
    """No-op since v099.

    Post-099 model: customers who exhaust credits buy top-up packs
    (see TOPUP_PACKS in billing.py) — there is no automatic overage
    invoice. This function is kept as a safe stub so the Celery beat
    schedule (`task_billing_jobs`) doesn't break, and so external
    callers that imported it continue to work.

    To restore overage billing, query orgs whose recent activity exceeds
    plan credits and create overage `subscriptions` rows here. See git
    history before commit-of-this-change for the original implementation.
    """
    return 0
    # Legacy code retained below for reference only — never reached.
    from app.plan_enforcer import PLAN_CONFIG
    rows = db.execute(
        text("""
            SELECT id, email, name, subscription_tier, period_reset_at
            FROM orgs
            WHERE subscription_tier IN ('hustler', 'startup')
              AND plan_status = 'active'
              AND period_reset_at BETWEEN NOW() - INTERVAL '24 hours' AND NOW()
        """)
    ).fetchall()

    created = 0
    for org in rows:
        tier   = org.subscription_tier
        config = PLAN_CONFIG.get(tier, {})
        limit  = config.get("period_contexts", 0)
        rate   = config.get("overage_cost_per_1k", 0)

        if not rate:
            continue

        # Count contexts in the period that just ended
        used = db.execute(
            text("""
                SELECT COUNT(*) FROM context_calls
                WHERE org_id = :oid
                  AND called_at >= :reset - INTERVAL '30 days'
                  AND called_at < :reset
                  AND (source = 'api' OR source IS NULL)
            """),
            {"oid": str(org.id), "reset": org.period_reset_at},
        ).scalar() or 0

        overage = max(0, used - limit)
        if overage == 0:
            continue

        # Round up to nearest 1000
        overage_units = -(-overage // 1000)  # ceiling division
        amount_inr    = overage_units * rate
        amount_paise  = amount_inr * 100

        # Check no duplicate invoice for this period
        existing = db.execute(
            text("""
                SELECT id FROM subscriptions
                WHERE org_id = :oid AND invoice_type = 'overage'
                  AND created_at >= :reset - INTERVAL '1 day'
            """),
            {"oid": str(org.id), "reset": org.period_reset_at},
        ).fetchone()

        if existing:
            continue

        db.execute(
            text("""
                INSERT INTO subscriptions
                    (org_id, plan, status, amount_paise, overage_units, invoice_type,
                     period_start, period_end)
                VALUES
                    (:org_id, :plan, 'pending', :amount, :units, 'overage',
                     :reset - INTERVAL '30 days', :reset)
            """),
            {
                "org_id": str(org.id), "plan": tier, "amount": amount_paise,
                "units": overage, "reset": org.period_reset_at,
            },
        )
        created += 1
        logger.info(f"Overage invoice: org={org.id} tier={tier} units={overage} ₹{amount_inr}")

        # Send overage email
        _send_overage_email(org.email, org.name or "there", amount_inr, overage, tier)

    db.commit()
    return created


def _send_overage_email(email: str, name: str, amount_inr: int, overage_units: int, tier: str):
    billing_url = f"{FRONTEND_URL}/dashboard/settings?tab=billing"
    _send_email(
        to=email,
        subject=f"GeniOS overage invoice — ₹{amount_inr:,}",
        html=f"""
        <p>Hi {name},</p>
        <p>You used <strong>{overage_units:,} extra context calls</strong> beyond your
           {tier.capitalize()} plan limit this period.</p>
        <p>An overage charge of <strong>₹{amount_inr:,}</strong> has been queued.</p>
        <p>
          <a href="{billing_url}" style="display:inline-block;padding:10px 20px;
            background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
            View Billing
          </a>
        </p>
        <p style="color:#999;font-size:12px;">GeniOS · <a href="{FRONTEND_URL}">thegenios.com</a></p>
        """,
    )


# ── Seat invite email ─────────────────────────────────────────────────────────

def send_invite_email(to_email: str, org_id: str, role: str, token: str):
    accept_url = f"{FRONTEND_URL}/invite/accept/{token}"
    # Fetch org name
    try:
        from app.database import SessionLocal
        with SessionLocal() as db:
            row = db.execute(
                text("SELECT name FROM orgs WHERE id = :oid"), {"oid": org_id}
            ).fetchone()
            org_name = row.name if row else "GeniOS"
    except Exception:
        org_name = "GeniOS"

    _send_email(
        to=to_email,
        subject=f"You've been invited to {org_name} on GeniOS",
        html=f"""
        <p>Hi,</p>
        <p>You've been invited to join <strong>{org_name}</strong>'s GeniOS workspace
           as a <strong>{role}</strong>.</p>
        <p>
          <a href="{accept_url}" style="display:inline-block;padding:10px 20px;
            background:#c8962e;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
            Accept Invitation
          </a>
        </p>
        <p style="color:#999;font-size:12px;">This invite expires in 7 days.
           GeniOS · <a href="{FRONTEND_URL}">thegenios.com</a></p>
        """,
    )
