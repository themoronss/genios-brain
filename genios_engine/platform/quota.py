"""The INGESTION meter: how many messages a tenant may capture in its billing period.

WHY THIS IS NOT CREDITS. One email costs more to ingest than one question costs to answer —
measured, not assumed: the Layer 2 extraction prompt is ~2,950 tokens because the pack vocabulary
is baked into it, so at Haiku list price one message is ~Rs 0.16 against a query's ~Rs 0.12, about
1.3 credits. If sync were charged to the credit pool:

  * connecting a 3,000-message mailbox would cost ~4,000 credits BEFORE the product said anything,
    which is more than the whole free plan;
  * the bill would be driven by how much mail other people send the customer — the one quantity
    they cannot control — so the same work would cost two tenants wildly different amounts;
  * every plan's headline number would stop meaning "questions you can ask", which is the only
    thing a credit is understood to be.

So ingestion is included in the plan and bounded by a COUNT instead. Two ceilings guard it and
they answer different questions: this one is "how much mail, this period" (a fairness and
capacity bound); `billing.plan_ingest_usd_cap` is "how much money, today" (a runaway bound). A
backfill can be inside the message quota and still be an emergency, and vice versa.

Counted from `source_events.captured_at`, which is the row that proves a message was actually
taken in — not from a connector's page count, which includes everything the dedup index threw
away. Every read fails OPEN: a meter that cannot be read must never stop a customer's mail.
"""

from __future__ import annotations

from sqlalchemy import text

from genios_engine.platform import billing as B
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.quota")

#: What a tenant is told when the meter is full. `sync` rather than `credits` on purpose: the fix
#: is a bigger plan, never a top-up pack, and sending them to Top-up would sell them the wrong
#: thing and still leave the mail unread.
REASON_SYNC_QUOTA = "sync_quota_exhausted"


def _is_first_period(conn, org_id: str) -> bool:
    """Was this account created inside the period it is in now? That is what makes this its
    history import rather than an ordinary month. Read off `created_at` rather than tracked in a
    column, so it is self-correcting: the allowance lapses on its own when the period rolls."""
    return bool(conn.execute(text(
        "select created_at >= coalesce(credit_period_start, plan_started_at, created_at) "
        "from orgs where id=:o"), {"o": org_id}).scalar())


def _period_start(conn, org_id: str):
    """The org's own billing period, falling back to the account's birth. NOT the calendar month:
    a plan bought on the 28th would otherwise get two days of quota for its first month."""
    return conn.execute(text(
        "select coalesce(credit_period_start, plan_started_at, created_at) "
        "from orgs where id=:o"), {"o": org_id}).scalar()


def messages_used(engine, org_id: str) -> int:
    """Messages captured for this org since its period began. 0 when it cannot be read."""
    try:
        with engine.connect() as conn:
            start = _period_start(conn, org_id)
            return int(conn.execute(text(
                "select count(*) from source_events where org_id=:o "
                "and captured_at >= coalesce(:s, '-infinity'::timestamptz)"),
                {"o": org_id, "s": start}).scalar() or 0)
    except Exception:                      # noqa: BLE001 — a meter must never block ingestion
        _log.warning("sync quota read failed for org=%s — treating as unused", org_id)
        return 0


def sync_status(engine, org_id: str) -> dict:
    """`{used, limit, remaining, exhausted, tier}` — the whole meter in one read, for the route
    that shows it and the gate that enforces it."""
    tier, first = None, False
    try:
        with engine.connect() as conn:
            tier = conn.execute(text("select subscription_tier from orgs where id=:o"),
                                {"o": org_id}).scalar()
            first = _is_first_period(conn, org_id)
    except Exception:                      # noqa: BLE001
        pass
    limit = B.plan_sync_messages(tier, first_period=first)
    used = messages_used(engine, org_id)
    return {"tier": B.normalize_plan(tier or "") or "trial", "used": used, "limit": limit,
            "remaining": max(0, limit - used), "exhausted": used >= limit,
            # True while the ONE-TIME history import allowance is still in play. Worth surfacing:
            # "you have 12,000 messages left" means something different in month one.
            "first_period": first,
            "backfill_included": B.plan_of(tier).backfill_messages if first else 0}


def sync_headroom(engine, org_id: str) -> int:
    """How many more messages may be captured right now. A CAPTURE-TIME number, so a backfill
    that would blow through the quota is trimmed to it instead of being refused whole — half a
    mailbox read is worth more to the customer than none, and the remainder is still there when
    they upgrade."""
    status = sync_status(engine, org_id)
    return status["remaining"]
