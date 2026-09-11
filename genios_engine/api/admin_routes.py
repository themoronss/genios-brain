"""Admin console — the ONLY cross-org read surface in the engine.

Everything else in this API answers for exactly one tenant, resolved from the credential. These
routes deliberately do the opposite: they read every tenant's growth, spend and revenue so we can
answer "how is the business doing?" without exporting a database dump. That inversion is the entire
risk here, so the boundary is narrow and explicit:

  • `require_admin` — owner JWT (never a scoped API key) belonging to an org flagged `is_internal`
    in the database. No request path can set that flag.
  • Read-only. The single mutation (`/admin/accounts/{id}/internal`) toggles the exclusion flag,
    which changes reporting only, and is audited.
  • No message, email or graph *content* is ever returned — only counts, timestamps and money.
    An admin needs to know an account synced 4,000 events, never what those events said.

Numbers come from `platform.metrics`, never re-derived here, so the console and (later) PostHog
quote the same figure for the same question. Internal accounts are excluded from every aggregate;
they remain visible as rows in the accounts table (flagged) so we can still support ourselves.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform import metrics as M
from genios_engine.platform.auth import AuthCtx, require_admin
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store

router = APIRouter(prefix="/admin", tags=["admin"])
_log = get_logger("genios.admin")
_graph = make_graph_store()


def _engine():
    if _graph is None:
        raise HTTPException(503, "admin analytics unavailable (no database configured)")
    return _graph.engine


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pct_change(current: float, previous: float) -> float | None:
    """None (not 0, not ∞) when there is no baseline — an honest "no comparison yet" beats a
    fabricated +100% on the first week."""
    if not previous:
        return None
    return round((current - previous) / previous * 100.0, 1)


# ════════════════════════════════════════════════════════════════════════════════════════
# 1 ── GROWTH
# ════════════════════════════════════════════════════════════════════════════════════════
@router.get("/growth")
def growth(days: int = Query(90, ge=7, le=365), _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Signups, the activation funnel, active accounts and cohort retention — the investor view of
    'is this growing?'. Every count excludes internal accounts."""
    days = int(days)
    now = _now()
    since = now - timedelta(days=days)
    act = M.ACTIVITY_ACTIONS_SQL

    with _engine().connect() as c:
        # ── signups: window counts + the preceding window, so each number carries a trend
        counts = c.execute(text(f"""
            select
              count(*) filter (where o.created_at >= now() - interval '1 day')   as d1,
              count(*) filter (where o.created_at >= now() - interval '7 days')  as d7,
              count(*) filter (where o.created_at >= now() - interval '30 days') as d30,
              count(*) filter (where o.created_at >= now() - interval '14 days'
                                 and o.created_at <  now() - interval '7 days')  as prev7,
              count(*) filter (where o.created_at >= now() - interval '60 days'
                                 and o.created_at <  now() - interval '30 days') as prev30,
              count(*)                                                            as total
            from orgs o where {M.REAL_ORGS}""")).one()

        trend = [{"date": str(r.day), "signups": int(r.n)} for r in c.execute(text(f"""
            select date_trunc('day', o.created_at)::date as day, count(*) n
            from orgs o where {M.REAL_ORGS} and o.created_at >= :since
            group by 1 order by 1"""), {"since": since})]

        plan_mix = [{"plan": r.tier, "status": r.st, "accounts": int(r.n)}
                    for r in c.execute(text(f"""
            select o.subscription_tier tier, o.plan_status st, count(*) n
            from orgs o where {M.REAL_ORGS} group by 1,2 order by 3 desc"""))]

        # ── activation funnel. Each step is a superset test on the same population, so the steps
        # are monotonically non-increasing and the drop-off between them is meaningful.
        #
        # "Connected" deliberately accepts any evidence that a source was attached, not just a
        # `connections` row: that table is Composio-backed and is empty for accounts whose data
        # demonstrably synced (56 sync runs against 0 connection rows in production). Reading it
        # alone reported 0% connected above 100% synced — a funnel that climbs is a funnel nobody
        # can trust, and the fault was the measurement, not the accounts.
        funnel = c.execute(text(f"""
            select
              count(*) as signed_up,
              count(*) filter (where exists (select 1 from connections cn
                                             where cn.org_id = o.id and cn.status = 'connected')
                                  or exists (select 1 from workspace_accounts wa
                                             where wa.org_id = o.id and wa.is_active)
                                  or exists (select 1 from integration_preferences ip
                                             where ip.org_id = o.id)
                                  or exists (select 1 from l1_sync_runs sr0
                                             where sr0.org_id = o.id))
                       as connected,
              count(*) filter (where exists (select 1 from l1_sync_runs sr
                                             where sr.org_id = o.id and sr.emitted > 0))
                       as synced,
              count(*) filter (where o.activated_at is not null) as activated
            from orgs o where {M.REAL_ORGS}""")).one()

        # ── active accounts. DAU/WAU/MAU count DISTINCT orgs that performed a real action.
        active = c.execute(text(f"""
            select
              count(distinct al.org_id) filter (where al.timestamp >= now() - interval '1 day')   dau,
              count(distinct al.org_id) filter (where al.timestamp >= now() - interval '7 days')  wau,
              count(distinct al.org_id) filter (where al.timestamp >= now() - interval '30 days') mau
            from audit_log al join orgs o on o.id = al.org_id
            where {M.REAL_ORGS} and al.action in {act}
              and al.timestamp >= now() - interval '30 days'""")).one()

        # ── weekly cohort retention. Cohort = signup week; retained = active in week N after.
        cohort_since = now - timedelta(weeks=9)
        rows = c.execute(text(f"""
            with cohorts as (
                select o.id, date_trunc('week', o.created_at) as cohort
                from orgs o where {M.REAL_ORGS} and o.created_at >= :since
            ),
            weeks as (
                select distinct al.org_id, date_trunc('week', al.timestamp) as wk
                from audit_log al
                where al.action in {act} and al.timestamp >= :since
            )
            select ch.cohort,
                   floor(extract(epoch from (w.wk - ch.cohort)) / 604800)::int as week_no,
                   count(distinct ch.id) as retained
            from cohorts ch join weeks w on w.org_id = ch.id and w.wk >= ch.cohort
            group by 1, 2 order by 1, 2"""), {"since": cohort_since}).fetchall()
        sizes = {str(r.cohort.date()): int(r.n) for r in c.execute(text(f"""
            select date_trunc('week', o.created_at) cohort, count(*) n
            from orgs o where {M.REAL_ORGS} and o.created_at >= :since
            group by 1"""), {"since": cohort_since})}

        # ── attention lists: who needs a nudge this week
        expiring = [{"org_id": r.id, "name": r.name, "company": r.company, "email": r.email,
                     "expires_at": _iso(r.plan_expires_at)} for r in c.execute(text(f"""
            select o.id, o.name, o.company, o.email, o.plan_expires_at
            from orgs o where {M.REAL_ORGS} and o.subscription_tier = 'trial'
              and o.plan_expires_at between now() and now() + interval '7 days'
            order by o.plan_expires_at"""))]
        churned = int(c.execute(text(f"""
            select count(*) from orgs o where {M.REAL_ORGS}
              and (o.plan_status in ('suspended', 'cancelled', 'expired')
                   or (o.subscription_tier = 'trial' and o.plan_expires_at < now()))""")).scalar() or 0)

    cohorts: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = str(r.cohort.date())
        size = sizes.get(key, 0)
        entry = cohorts.setdefault(key, {"cohort_week": key, "size": size, "weeks": {}})
        if size:
            entry["weeks"][str(int(r.week_no))] = round(int(r.retained) / size * 100.0, 1)

    signed_up = int(funnel.signed_up or 0)
    # Guard the invariant rather than trusting it: if a future source table makes a later step
    # exceed an earlier one, clamp so the chart cannot climb, because a rising funnel silently
    # discredits every other number on the page.
    connected = int(funnel.connected or 0)
    synced = min(int(funnel.synced or 0), connected)
    activated = min(int(funnel.activated or 0), synced)
    return {
        "signups": {
            "today": int(counts.d1 or 0), "week": int(counts.d7 or 0),
            "month": int(counts.d30 or 0), "total": int(counts.total or 0),
            "week_change_pct": _pct_change(int(counts.d7 or 0), int(counts.prev7 or 0)),
            "month_change_pct": _pct_change(int(counts.d30 or 0), int(counts.prev30 or 0)),
        },
        "trend": trend,
        "plan_mix": plan_mix,
        "funnel": [
            {"step": step, "accounts": n,
             "pct": round(n / signed_up * 100, 1) if signed_up else 0.0}
            for step, n in (("Signed up", signed_up), ("Connected", connected),
                            ("Synced", synced), ("Asked GeniOS", activated))
        ],
        "active": {
            "dau": int(active.dau or 0), "wau": int(active.wau or 0), "mau": int(active.mau or 0),
            "stickiness_pct": round(int(active.dau or 0) / int(active.mau) * 100, 1)
            if active.mau else None,
        },
        "retention": sorted(cohorts.values(), key=lambda x: x["cohort_week"], reverse=True),
        "trials_expiring": expiring,
        "churned": churned,
        "window_days": days,
    }


# ════════════════════════════════════════════════════════════════════════════════════════
# 2 ── ACCOUNTS TABLE
# ════════════════════════════════════════════════════════════════════════════════════════
# Whitelisted sort columns. Never interpolate a client string into ORDER BY — the value is looked
# up here or the request is rejected.
_SORT = {
    "created_at": "o.created_at", "name": "o.name", "company": "o.company", "email": "o.email",
    "plan": "o.subscription_tier", "last_login": "last_login", "spend_usd": "spend_usd",
    "llm_calls": "llm_calls", "events": "events", "paid_inr": "paid_inr",
    "credits_left": "credits_left", "activated_at": "o.activated_at",
}


@router.get("/accounts")
def accounts(q: str = "", sort: str = "created_at", order: str = "desc",
             limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
             include_internal: bool = False,
             _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """One row per account with everything needed to judge it at a glance: who they are, whether
    they use it, what they cost us and what they pay. Internal accounts are hidden by default and
    flagged when shown."""
    if sort not in _SORT:
        raise HTTPException(422, f"sort must be one of {sorted(_SORT)}")
    direction = "asc" if str(order).lower() == "asc" else "desc"
    cost_sql = M.cost_usd_sql("lc")
    where = ["true"] if include_internal else [M.REAL_ORGS]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if q.strip():
        where.append("(lower(o.email) like :q or lower(coalesce(o.name,'')) like :q "
                     "or lower(coalesce(o.company,'')) like :q or o.id = :exact)")
        params["q"] = f"%{q.strip().lower()}%"
        params["exact"] = q.strip()
    where_sql = " and ".join(where)

    sql = f"""
        select o.id, o.name, o.company, o.email, o.subscription_tier, o.plan_status,
               o.created_at, o.activated_at, o.plan_expires_at, o.is_internal,
               coalesce(o.credits, 0) + coalesce(o.topup_credits, 0) as credits_left,
               (select max(al.timestamp) from audit_log al
                 where al.org_id = o.id and al.action = 'user_logged_in')          as last_login,
               (select count(distinct date_trunc('day', al.timestamp)) from audit_log al
                 where al.org_id = o.id and al.action in {M.ACTIVITY_ACTIONS_SQL}) as active_days,
               (select count(*) from connections cn
                 where cn.org_id = o.id and cn.status = 'connected')               as integrations,
               (select count(*) from source_events se where se.org_id = o.id)      as events,
               (select count(*) from graph_nodes gn where gn.org_id = o.id)        as nodes,
               (select count(*) from signals s where s.org_id = o.id)              as signals,
               (select count(*) from llm_costs lc where lc.org_id = o.id)          as llm_calls,
               (select coalesce({cost_sql}, 0) from llm_costs lc
                 where lc.org_id = o.id)                                           as spend_usd,
               (select coalesce(sum(sb.amount_paise), 0) / 100.0 from subscriptions sb
                 where sb.org_id = o.id and sb.status = 'active')                  as paid_inr
        from orgs o
        where {where_sql}
        order by {_SORT[sort]} {direction} nulls last
        limit :limit offset :offset"""

    with _engine().connect() as c:
        rows = c.execute(text(sql), params).fetchall()
        total = int(c.execute(text(f"select count(*) from orgs o where {where_sql}"),
                              {k: v for k, v in params.items()
                               if k not in {"limit", "offset"}}).scalar() or 0)

    out = []
    for r in rows:
        spend = float(r.spend_usd or 0.0)
        paid = float(r.paid_inr or 0.0)
        out.append({
            "org_id": r.id, "name": r.name, "company": r.company, "email": r.email,
            "plan": r.subscription_tier, "status": r.plan_status,
            "is_internal": bool(r.is_internal),
            "created_at": _iso(r.created_at), "activated_at": _iso(r.activated_at),
            "trial_expires_at": _iso(r.plan_expires_at),
            "last_login": _iso(r.last_login), "active_days": int(r.active_days or 0),
            "integrations": int(r.integrations or 0), "events": int(r.events or 0),
            "nodes": int(r.nodes or 0), "signals": int(r.signals or 0),
            "llm_calls": int(r.llm_calls or 0), "spend_usd": round(spend, 4),
            "credits_left": int(r.credits_left or 0), "paid_inr": round(paid, 2),
            # Margin in rupees: what they paid minus what their tokens cost us. Negative is the
            # normal, expected state for a trial — that is the number trial-burn is made of.
            "margin_inr": round(paid - spend * M.INR_PER_USD, 2),
        })
    return {"total": total, "limit": limit, "offset": offset, "accounts": out}


# ════════════════════════════════════════════════════════════════════════════════════════
# 3 ── ACCOUNT DETAIL
# ════════════════════════════════════════════════════════════════════════════════════════
@router.get("/accounts/{target_org}")
def account_detail(target_org: str, days: int = Query(90, ge=7, le=365),
                   _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Everything we know about one account's *usage* — never its content. Answers, in order:
    who are they, do they show up, is their data flowing, what did they cost, what did they pay."""
    since = _now() - timedelta(days=int(days))
    cost_sql = M.cost_usd_sql("lc")
    act = M.ACTIVITY_ACTIONS_SQL

    with _engine().connect() as c:
        org = c.execute(text("""
            select id, name, company, email, role, subscription_tier, plan_status, created_at,
                   activated_at, plan_started_at, plan_expires_at, grace_until, is_internal,
                   coalesce(credits,0) credits, coalesce(topup_credits,0) topup_credits
            from orgs where id = :o"""), {"o": target_org}).first()
        if org is None:
            # A deleted tenant keeps its retained financials; show the archived identity rather
            # than a 404 that makes real spend look like it never happened.
            arch = c.execute(text("select * from orgs_archive where org_id = :o"),
                             {"o": target_org}).first()
            if arch is None:
                raise HTTPException(404, "account not found")
            org = arch

        logins = [{"at": _iso(r.at), "actor": r.actor_id} for r in c.execute(text("""
            select al.timestamp as at, al.actor_id from audit_log al
            where al.org_id = :o and al.action = 'user_logged_in'
            order by al.timestamp desc limit 50"""), {"o": target_org})]

        # `timestamp` is also a type name — always qualify it, or `… ::date as day` parses as a
        # `timestamp day` interval qualifier and the statement fails.
        activity = [{"date": str(r.day), "actions": int(r.n)} for r in c.execute(text(f"""
            select date_trunc('day', al.timestamp)::date as day, count(*) n from audit_log al
            where al.org_id = :o and al.action in {act} and al.timestamp >= :since
            group by 1 order by 1"""), {"o": target_org, "since": since})]

        integrations = [{"source": r.source_type, "provider": r.provider, "status": r.status,
                         "connected_at": _iso(r.created_at)} for r in c.execute(text("""
            select source_type, provider, status, created_at from connections
            where org_id = :o order by created_at desc"""), {"o": target_org})]

        syncs = [{"source": r.source, "mode": r.mode, "scanned": int(r.scanned or 0),
                  "emitted": int(r.emitted or 0), "parked": int(r.parked or 0),
                  "error": r.error, "at": _iso(r.finished_at)} for r in c.execute(text("""
            select source, mode, scanned, emitted, parked, error, finished_at from l1_sync_runs
            where org_id = :o order by finished_at desc limit 20"""), {"o": target_org})]

        volume = c.execute(text("""
            select (select count(*) from source_events where org_id = :o) events,
                   (select count(*) from graph_nodes   where org_id = :o) nodes,
                   (select count(*) from graph_facts   where org_id = :o) facts,
                   (select count(*) from signals       where org_id = :o) signals,
                   (select count(*) from cards         where org_id = :o) cards,
                   (select count(*) from decisions     where org_id = :o) decisions"""),
            {"o": target_org}).one()

        llm_rows = [{"purpose": r.purpose, "model": r.model, "calls": int(r.n),
                     "input_tokens": int(r.it or 0), "output_tokens": int(r.ot or 0),
                     "failures": int(r.failed or 0), "cost_usd": round(float(r.usd or 0), 4)}
                    for r in c.execute(text(f"""
            select lc.purpose, lc.model, count(*) n, sum(lc.input_tokens) it,
                   sum(lc.output_tokens) ot, count(*) filter (where not lc.success) failed,
                   {cost_sql} usd
            from llm_costs lc where lc.org_id = :o
            group by 1, 2 order by usd desc nulls last"""), {"o": target_org})]

        spend_daily = [{"date": str(r.day), "calls": int(r.n),
                        "cost_usd": round(float(r.usd or 0), 4)} for r in c.execute(text(f"""
            select date_trunc('day', lc.created_at)::date as day, count(*) n, {cost_sql} usd
            from llm_costs lc where lc.org_id = :o and lc.created_at >= :since
            group by 1 order by 1"""), {"o": target_org, "since": since})]

        credits = [{"at": _iso(r.occurred_at), "kind": r.kind, "bucket": r.bucket,
                    "amount": int(r.amount), "balance_after": int(r.balance_after),
                    "reason": r.reason} for r in c.execute(text("""
            select occurred_at, kind, bucket, amount, balance_after, reason from credit_ledger
            where org_id = :o order by occurred_at desc limit 50"""), {"o": target_org})]

        payments = [{"at": _iso(r.created_at), "plan": r.plan, "type": r.invoice_type,
                     "status": r.status, "amount_inr": round(int(r.amount_paise or 0) / 100.0, 2),
                     "processor": r.processor} for r in c.execute(text("""
            select created_at, plan, invoice_type, status, amount_paise, processor
            from subscriptions where org_id = :o order by created_at desc limit 50"""),
            {"o": target_org})]

        engagement = c.execute(text("""
            select (select count(*) from llm_costs
                     where org_id = :o and purpose = 'intelligence_query')          queries,
                   (select count(*) from card_events where org_id = :o)             card_events,
                   (select count(*) from audit_log
                     where org_id = :o and action = 'decision_made')                decisions_made"""),
            {"o": target_org}).one()

    spend_usd = sum(r["cost_usd"] for r in llm_rows)
    paid_inr = sum(p["amount_inr"] for p in payments if p["status"] == "active")
    queries = int(engagement.queries or 0)
    return {
        "account": {
            "org_id": getattr(org, "id", None) or getattr(org, "org_id", target_org),
            "name": org.name, "company": org.company, "email": org.email,
            "plan": org.subscription_tier, "status": getattr(org, "plan_status", "deleted"),
            "is_internal": bool(org.is_internal), "created_at": _iso(org.created_at),
            "activated_at": _iso(getattr(org, "activated_at", None)),
            "trial_expires_at": _iso(getattr(org, "plan_expires_at", None)),
            "deleted_at": _iso(getattr(org, "deleted_at", None)),
            "credits_left": int(getattr(org, "credits", 0) or 0)
                            + int(getattr(org, "topup_credits", 0) or 0),
        },
        "logins": logins,
        "activity": activity,
        "integrations": integrations,
        "syncs": syncs,
        "volume": {"events": int(volume.events or 0), "nodes": int(volume.nodes or 0),
                   "facts": int(volume.facts or 0), "signals": int(volume.signals or 0),
                   "cards": int(volume.cards or 0), "decisions": int(volume.decisions or 0)},
        "llm": llm_rows,
        "spend_daily": spend_daily,
        "credits": credits,
        "payments": payments,
        "engagement": {"queries": queries, "card_events": int(engagement.card_events or 0),
                       "decisions_made": int(engagement.decisions_made or 0)},
        "economics": {
            "spend_usd": round(spend_usd, 4),
            "spend_inr": round(spend_usd * M.INR_PER_USD, 2),
            "paid_inr": round(paid_inr, 2),
            "margin_inr": round(paid_inr - spend_usd * M.INR_PER_USD, 2),
            "cost_per_query_usd": round(spend_usd / queries, 4) if queries else None,
        },
        "window_days": int(days),
    }


# ════════════════════════════════════════════════════════════════════════════════════════
# 4 ── MONEY & UNIT ECONOMICS
# ════════════════════════════════════════════════════════════════════════════════════════
@router.get("/money")
def money(days: int = Query(90, ge=7, le=365), _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Revenue, model spend and the gap between them. MRR is derived from the plan each active
    account is actually on — not from a stored field that can drift from what they pay."""
    since = _now() - timedelta(days=int(days))
    cost_sql = M.cost_usd_sql("lc")

    with _engine().connect() as c:
        # MRR counts a plan ONLY when money actually arrived for it. `orgs.subscription_tier` is a
        # provisioning field — it is set by hand when we open an account on a plan — so pricing it
        # directly reported ₹50,000 MRR against ₹0 revenue and a negative margin on the same screen.
        # A number an investor can disprove by looking at the tile beside it is worse than no number.
        paid_accounts = c.execute(text(f"""
            select o.subscription_tier tier, o.plan_status st, count(*) n
            from orgs o where {M.REAL_ORGS} and o.subscription_tier not in ('trial', '')
              and exists (select 1 from subscriptions sb
                          where sb.org_id = o.id and sb.status = 'active'
                            and sb.invoice_type = 'subscription')
            group by 1, 2""")).fetchall()

        # Shown separately, never folded into MRR: accounts we put on a paid plan that have not
        # paid. Comped, manual, or mid-negotiation — real information, just not revenue.
        unbilled = c.execute(text(f"""
            select o.subscription_tier tier, count(*) n
            from orgs o where {M.REAL_ORGS} and o.subscription_tier not in ('trial', '')
              and not exists (select 1 from subscriptions sb
                              where sb.org_id = o.id and sb.status = 'active'
                                and sb.invoice_type = 'subscription')
            group by 1 order by 2 desc""")).fetchall()

        revenue_monthly = [{"month": str(r.m.date()), "revenue_inr": round(float(r.inr), 2),
                            "invoices": int(r.n)} for r in c.execute(text(f"""
            select date_trunc('month', sb.created_at) m,
                   sum(sb.amount_paise) / 100.0 inr, count(*) n
            from subscriptions sb join orgs o on o.id = sb.org_id
            where {M.REAL_ORGS} and sb.status = 'active' and sb.created_at >= :since
            group by 1 order by 1"""), {"since": since})]

        spend_daily = [{"date": str(r.day), "calls": int(r.n),
                        "cost_usd": round(float(r.usd or 0), 4)} for r in c.execute(text(f"""
            select date_trunc('day', lc.created_at)::date as day, count(*) n, {cost_sql} usd
            from llm_costs lc join orgs o on o.id = lc.org_id
            where {M.REAL_ORGS} and lc.created_at >= :since
            group by 1 order by 1"""), {"since": since})]

        spend_by_model = [{"model": r.model, "calls": int(r.n),
                           "cost_usd": round(float(r.usd or 0), 4)} for r in c.execute(text(f"""
            select lc.model, count(*) n, {cost_sql} usd
            from llm_costs lc join orgs o on o.id = lc.org_id
            where {M.REAL_ORGS} and lc.created_at >= :since
            group by 1 order by usd desc nulls last"""), {"since": since})]

        spend_by_purpose = [{"purpose": r.purpose, "calls": int(r.n),
                             "cost_usd": round(float(r.usd or 0), 4)} for r in c.execute(text(f"""
            select lc.purpose, count(*) n, {cost_sql} usd
            from llm_costs lc join orgs o on o.id = lc.org_id
            where {M.REAL_ORGS} and lc.created_at >= :since
            group by 1 order by usd desc nulls last"""), {"since": since})]

        top_spenders = [{"org_id": r.id, "name": r.name, "company": r.company, "email": r.email,
                         "plan": r.subscription_tier, "calls": int(r.n),
                         "cost_usd": round(float(r.usd or 0), 4)} for r in c.execute(text(f"""
            select o.id, o.name, o.company, o.email, o.subscription_tier,
                   count(*) n, {cost_sql} usd
            from llm_costs lc join orgs o on o.id = lc.org_id
            where {M.REAL_ORGS} and lc.created_at >= :since
            group by 1,2,3,4,5 order by usd desc nulls last limit 10"""), {"since": since})]

        # Trial burn: what unconverted accounts cost us. This is the number that decides whether a
        # free trial is a marketing spend we can afford.
        burn = c.execute(text(f"""
            select coalesce({cost_sql}, 0) usd, count(distinct lc.org_id) accounts
            from llm_costs lc join orgs o on o.id = lc.org_id
            where {M.REAL_ORGS} and o.subscription_tier = 'trial'
              and lc.created_at >= :since"""), {"since": since}).one()

        totals = c.execute(text(f"""
            select coalesce({cost_sql}, 0) usd,
                   count(*) calls,
                   count(*) filter (where lc.purpose = 'intelligence_query') queries
            from llm_costs lc join orgs o on o.id = lc.org_id
            where {M.REAL_ORGS} and lc.created_at >= :since"""), {"since": since}).one()

        events_total = int(c.execute(text(f"""
            select count(*) from source_events se join orgs o on o.id = se.org_id
            where {M.REAL_ORGS}""")).scalar() or 0)

        revenue_window = float(c.execute(text(f"""
            select coalesce(sum(sb.amount_paise), 0) / 100.0
            from subscriptions sb join orgs o on o.id = sb.org_id
            where {M.REAL_ORGS} and sb.status = 'active' and sb.created_at >= :since"""),
            {"since": since}).scalar() or 0.0)

        conversion = c.execute(text(f"""
            select count(*) signups,
                   count(*) filter (where exists (select 1 from subscriptions sb
                                                  where sb.org_id = o.id and sb.status = 'active'
                                                    and sb.invoice_type = 'subscription')) converted,
                   avg(extract(epoch from (
                        (select min(sb.created_at) from subscriptions sb
                          where sb.org_id = o.id and sb.status = 'active') - o.created_at)) / 86400.0)
                     filter (where exists (select 1 from subscriptions sb
                                           where sb.org_id = o.id and sb.status = 'active'))
                     as avg_days
            from orgs o where {M.REAL_ORGS}""")).one()

    mrr = sum(M.mrr_inr(r.tier, r.st) * int(r.n) for r in paid_accounts)
    spend_usd = float(totals.usd or 0.0)
    spend_inr = spend_usd * M.INR_PER_USD
    signups = int(conversion.signups or 0)
    return {
        "mrr_inr": round(mrr, 2),
        "arr_inr": round(mrr * 12, 2),
        "unbilled_plans": [
            {"plan": r.tier, "accounts": int(r.n),
             "would_be_inr": round(M.plan_price_inr(r.tier) * int(r.n), 2)} for r in unbilled
        ],
        "revenue_window_inr": round(revenue_window, 2),
        "revenue_monthly": revenue_monthly,
        "spend": {"usd": round(spend_usd, 4), "inr": round(spend_inr, 2),
                  "calls": int(totals.calls or 0), "daily": spend_daily,
                  "by_model": spend_by_model, "by_purpose": spend_by_purpose},
        "margin": {"inr": round(revenue_window - spend_inr, 2),
                   "pct": round((revenue_window - spend_inr) / revenue_window * 100, 1)
                   if revenue_window else None},
        "top_spenders": top_spenders,
        "trial_burn": {"usd": round(float(burn.usd or 0), 4),
                       "inr": round(float(burn.usd or 0) * M.INR_PER_USD, 2),
                       "accounts": int(burn.accounts or 0)},
        "efficiency": {
            "cost_per_query_usd": round(spend_usd / int(totals.queries), 4)
            if totals.queries else None,
            "cost_per_1k_events_usd": round(spend_usd / events_total * 1000, 4)
            if events_total else None,
            "events_total": events_total,
        },
        "conversion": {
            "signups": signups, "converted": int(conversion.converted or 0),
            "rate_pct": round(int(conversion.converted or 0) / signups * 100, 1) if signups else 0.0,
            "avg_days_to_convert": round(float(conversion.avg_days), 1)
            if conversion.avg_days is not None else None,
        },
        "inr_per_usd": M.INR_PER_USD,
        "window_days": int(days),
    }


# ════════════════════════════════════════════════════════════════════════════════════════
# 5 ── the one mutation: exclude / include an account from reporting
# ════════════════════════════════════════════════════════════════════════════════════════
class InternalFlag(BaseModel):
    is_internal: bool


@router.post("/accounts/{target_org}/internal")
def set_internal(target_org: str, body: InternalFlag,
                 ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Flag (or unflag) an account as ours. Reporting-only: it changes no product behaviour and
    deletes nothing — but it silently removes an account from every investor number, so it is
    audited against the admin who did it."""
    with _engine().begin() as c:
        updated = c.execute(text("update orgs set is_internal = :v where id = :o"),
                            {"v": bool(body.is_internal), "o": target_org})
        if updated.rowcount != 1:
            raise HTTPException(404, "account not found")
    from genios_engine.platform.audit import record
    record(ctx.org_id, "config_changed", actor_type="user", actor_id=ctx.org_id,
           target_type="org", target_id=target_org,
           metadata={"audit_category": "admin", "field": "is_internal",
                     "value": bool(body.is_internal)})
    return {"org_id": target_org, "is_internal": bool(body.is_internal)}


# ════════════════════════════════════════════════════════════════════════════════════════
# 5 ── DISCOVERY (L1.4.5-U3 · the open lane's weekly report)
# ════════════════════════════════════════════════════════════════════════════════════════
@router.get("/discovery")
def discovery(days: int = Query(30, ge=1, le=365),
              min_occurrences: int = Query(5, ge=1, le=1000),
              examples: int = Query(0, ge=0, le=3),
              ctx: AuthCtx = Depends(require_admin)) -> dict:
    """What the extractor keeps noticing that the closed vocabulary has no name for.

    This is the artifact that decides what the 35th observation kind should be: a `proposed_kind`
    by frequency, how many orgs it spans, when it was first and last seen, and how much of that
    frequency is actually substantiated by a receipt. Promotion itself is a human act with a code
    change attached (L1.4.5-U2) — this endpoint proposes, it never edits the vocabulary.

    ON DEMAND, not on a beat. The Celery broker here is a quota-limited Upstash Redis, and this
    report is read by a person in a review, so it runs when that person asks for it.

    `examples` is the one exception to this console's no-content rule, and it costs an audit row.
    The rest of the admin surface returns counts and money only; a discovery review cannot be done
    on labels alone — "the model called it `budget_freeze` 41 times" is not enough to name a
    vocabulary member, and the sentences are what tell a reviewer whether it is one thing or
    three. Only VERIFIED quotes are ever returned, so nothing here is a sentence the model
    invented, and the ask is recorded against the admin who made it.
    """
    from genios_engine.capture.semantic import open_lane

    _engine()                       # the same 503 every other admin read gives with no database
    store = open_lane.PostgresOpenLaneStore(get_settings().database_url)
    report = open_lane.discovery_report(store, eval_time=_now(), window_days=int(days),
                                        min_occurrences=int(min_occurrences),
                                        examples=int(examples))
    if examples:
        from genios_engine.platform.audit import record
        record(ctx.org_id, "data_exported", actor_type="user", actor_id=ctx.org_id,
               target_type="workspace", target_id="cross_org",
               metadata={"audit_category": "admin", "report": "open_lane_discovery",
                         "example_quotes": int(examples), "window_days": int(days)})
    return {
        "generated_at": _iso(report.generated_at),
        "window_days": report.window_days,
        "min_occurrences": report.min_occurrences,
        "rows": [{"proposed_kind": row.proposed_kind, "occurrences": row.occurrences,
                  "verified_occurrences": row.verified_occurrences, "orgs": row.orgs,
                  "first_seen": _iso(row.first_seen), "last_seen": _iso(row.last_seen),
                  "promotable": row.promotable, "example_quotes": list(row.example_quotes)}
                 for row in report.rows],
    }


class PromotionBody(BaseModel):
    """A HUMAN's promotion decision, in full. Every field is one only a person can supply, which
    is `PromotionDecision`'s own rule restated at the edge: there is no `auto`, no threshold
    override and no "promote everything above N"."""

    proposed_kind: str
    vocabulary_member: str
    schema_version_before: str
    schema_version_after: str


@router.post("/discovery/promote")
def promote_discovery_kind(body: PromotionBody,
                           ctx: AuthCtx = Depends(require_admin)) -> dict:
    """L1.4.5-U2 · stamp the historical rows for a kind an admin has decided to promote.

    THE HUMAN GATE, WHICH HAD NO DOOR. `discovery` above proposes and `promote_kind` performs the
    data half, and `promote_kind` was reachable from nothing: the open lane could report for ever
    and the vocabulary could never grow from it, so every discovery review ended in a report
    nobody could act on. This is that door, and it is deliberately the only one — the endpoint
    refuses everything `promote_kind` refuses (an unnamed decider, a name that is not a
    snake_case member, a schema version that was not bumped, a kind already promoted, evidence
    below the bar), and it does NOT touch the closed vocabulary.

    `decided_by` is the AUTHENTICATED admin, never a field in the body. The whole point of the
    unit is that a promotion is an act somebody signed, and a signature the caller types is not
    one. The vocabulary edit the admin still has to make comes back in the response, because the
    data half without the code half is a promotion that changes nothing about what gets
    extracted.
    """
    from genios_engine.capture.semantic import open_lane

    _engine()
    decided_by = ctx.actor_id or ctx.org_id
    store = open_lane.PostgresOpenLaneStore(get_settings().database_url)
    decision = open_lane.PromotionDecision(
        proposed_kind=body.proposed_kind, vocabulary_member=body.vocabulary_member,
        decided_by=decided_by, schema_version_before=body.schema_version_before,
        schema_version_after=body.schema_version_after)
    try:
        promotion = open_lane.promote_kind(store, decision, eval_time=_now())
    except open_lane.PromotionRefused as exc:
        # 409, not 400: every refusal is about the STATE of the evidence or the vocabulary — too
        # few substantiated occurrences, an already-promoted kind, an un-bumped version — rather
        # than about a malformed request, and the remedy is to change that state.
        raise HTTPException(409, str(exc)) from exc

    from genios_engine.platform.audit import record
    record(ctx.org_id, "data_updated", actor_type="user", actor_id=decided_by,
           target_type="workspace", target_id="cross_org",
           metadata={"audit_category": "admin", "action": "open_lane_promotion",
                     "proposed_kind": promotion.decision.proposed_kind,
                     "vocabulary_member": promotion.decision.vocabulary_member,
                     "rows_marked": promotion.rows_marked})
    return {"proposed_kind": promotion.decision.proposed_kind,
            "vocabulary_member": promotion.decision.vocabulary_member,
            "decided_by": decided_by,
            "rows_marked": promotion.rows_marked,
            "promoted_at": _iso(promotion.promoted_at),
            "occurrences": promotion.candidate.occurrences,
            "verified_occurrences": promotion.candidate.verified_occurrences,
            "vocabulary_edit": promotion.vocabulary_edit}


@router.get("/whoami")
def admin_whoami(ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Cheap gate probe: the dashboard calls this to decide whether to render the Admin nav item.
    A 403 here is the normal answer for a customer, not an error."""
    return {"admin": True, "org_id": ctx.org_id}


# ════════════════════════════════════════════════════════════════════════════════════════
# 7 ── G10 · PILOT ACTIVATION (the L1 v2 semantic lane, one tenant at a time)
# ════════════════════════════════════════════════════════════════════════════════════════
# THE DEFECT THIS CLOSES. `platform/activation.py` and migration 0085 shipped the table, and
# `api/routes.py::_semantic_activated_orgs` reads it on every sweep — so the READ was wired and
# the WRITE was not. `activate_semantic` / `deactivate_semantic` had no caller anywhere outside
# their own unit test, which means the only way to start or stop a pilot was an operator typing
# INSERT into a psql session against the production tenant database. That is the same shape of
# failure the activation rule was written against (`use_domain_compiler=False`, set in no
# environment, 152 capabilities dark): a switch nothing can flip is a switch that is always off.
#
# WHY THESE THREE ROUTES LIVE ON THE ADMIN ROUTER. Activation is not a tenant preference. It
# changes which extraction path a customer's mail goes through and therefore what their sweep
# costs us, and the plan makes the decision ours by naming a pilot of one tenant. `require_admin`
# is the only boundary in the engine that means "is this us?" — an owner JWT whose email is in
# GENIOS_SUPERADMIN_EMAILS, never a scoped key. A customer-facing route here would let a tenant
# switch on their own unbudgeted model calls.
#
# These are the second and third MUTATIONS on this router (after the `is_internal` flag), so the
# module docstring's "read-only" claim is now "read-only except three audited switches". Both
# writes are audited against the admin who made them, for the reason the table stores
# `enabled_by` at all.
class PilotActivation(BaseModel):
    """The body of a switch-on. `notes` is the plan's printed fourth column — why this tenant."""

    notes: str | None = None


def _activation_row(record) -> dict:
    return {"org_id": record.org_id, "enabled_at": _iso(record.enabled_at),
            "enabled_by": record.enabled_by, "notes": record.notes,
            "disabled_at": _iso(record.disabled_at), "disabled_by": record.disabled_by,
            "live": record.live}


@router.get("/l1-activation")
def list_pilot_activation(include_disabled: bool = Query(False),
                          _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Who is on the L1 v2 semantic lane, and since when.

    `include_disabled=true` adds the tenants that were switched back off, which is the read
    `scripts/l1_shadow_diff.py` is interpreted against: a seven-day window over a tenant whose
    row was stamped on day four is a window in which the two paths ran side by side for four
    days and not seven.
    """
    from genios_engine.platform.activation import list_semantic_activations
    rows = list_semantic_activations(_engine(), include_disabled=bool(include_disabled))
    return {"activations": [_activation_row(r) for r in rows],
            "live": sum(1 for r in rows if r.live), "total": len(rows)}


@router.post("/l1-activation/{target_org}")
def activate_pilot(target_org: str, body: PilotActivation,
                   ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Put ONE tenant on the L1 v2 semantic lane. Idempotent, audited, reversible.

    The tenant must exist: without the check the org FK raises a 500 on a typo'd id, and an
    operator who mistypes a pilot tenant should be told which word was wrong rather than handed
    a stack trace. Idempotent because the failure mode of a double-click must not be a second
    pilot start date — `activate_semantic` keeps the original enabling record for a live row.
    """
    engine = _engine()
    with engine.connect() as c:
        if c.execute(text("select 1 from orgs where id=:o"), {"o": target_org}).first() is None:
            raise HTTPException(404, "account not found")
    from genios_engine.platform.activation import activate_semantic
    record = activate_semantic(engine, target_org, by=ctx.actor_id or ctx.org_id,
                               notes=body.notes)
    from genios_engine.platform.audit import record as audit
    audit(ctx.org_id, "config_changed", actor_type="user", actor_id=ctx.actor_id or ctx.org_id,
          target_type="org", target_id=target_org,
          metadata={"audit_category": "admin", "field": "l1_semantic_activation",
                    "value": True, "notes": body.notes})
    _log.info("L1 v2 semantic lane ACTIVATED for org=%s by=%s", target_org, record.enabled_by)
    return _activation_row(record)


@router.delete("/l1-activation/{target_org}")
def deactivate_pilot(target_org: str, ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Take ONE tenant back off the lane. The rollback half, and it is not optional — a migration
    you cannot reverse is a cutover with extra steps.

    Returns `switched_off: false` for a tenant that was already off rather than 404: the caller's
    intent ("this tenant must not be on the new lane") is satisfied either way, and a 404 would
    make a retry after a dropped connection look like a failure.
    """
    from genios_engine.platform.activation import (deactivate_semantic,
                                                   get_semantic_activation)
    engine = _engine()
    switched_off = deactivate_semantic(engine, target_org, by=ctx.actor_id or ctx.org_id)
    if switched_off:
        from genios_engine.platform.audit import record as audit
        audit(ctx.org_id, "config_changed", actor_type="user",
              actor_id=ctx.actor_id or ctx.org_id, target_type="org", target_id=target_org,
              metadata={"audit_category": "admin", "field": "l1_semantic_activation",
                        "value": False})
        _log.info("L1 v2 semantic lane DEACTIVATED for org=%s by=%s", target_org, ctx.actor_id)
    record = get_semantic_activation(engine, target_org)
    return {"org_id": target_org, "switched_off": switched_off,
            "activation": _activation_row(record) if record else None}


# =================================================================================================
# X8 / H8 · THE LAYER 2 v2 PILOT SWITCH — the write side, on a request path
# =================================================================================================
#
# THE SAME DEFECT, ONE LAYER UP. `l1_semantic_activation` shipped with a read on the sweep path and
# no writer outside its unit test, so the only way to start a pilot was an operator typing INSERT
# against the production tenant database — and doc 09's activation rule exists because a switch
# nothing can flip is a switch that is always off. `l2_v2_activation` (migration 0106) must not
# repeat it, so its two switches get their routes in the same wave the table lands.
#
# WHY ADMIN AND NOT TENANT. Same boundary as L1's, for a sharper reason: `patterns` turns on a
# graph read per sweep that nobody has budgeted for this tenant, and `analytic` declares a customer
# to be a pilot. Neither is a tenant preference. `require_admin` is the only boundary in the engine
# that means "is this us?".
#
# WHY THE RESPONSE CARRIES `effect`. The two switches are NOT symmetric — `patterns` gates a real
# pass, `analytic` gates nothing because the analytic stratum is already unconditional for every
# tenant. An operator who can see that a switch is live and cannot see what it turned on will
# assume it turned on everything, so `platform/l2_activation.EFFECTS` travels in every response.
class L2PilotActivation(BaseModel):
    """The body of a switch-on.

    `switch` is required and has no default: the two switches change different amounts of
    behaviour, and a default would let an operator turn on the one they were not thinking about.
    `"both"` is accepted because turning a tenant on for the pilot usually means both, and making
    that two requests invites a half-activated tenant nobody notices.
    """

    switch: str
    notes: str | None = None


def _l2_switches(switch: str) -> tuple[str, ...]:
    """`"both"` -> every switch; anything else is validated by the module that owns the names.

    Validation here rather than in a pydantic enum so the refusal is a 400 naming the legal
    values, not a 422 whose body an operator has to decode.
    """
    from genios_engine.platform.l2_activation import SWITCHES, require_switch
    if switch == "both":
        return SWITCHES
    try:
        return (require_switch(switch),)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/l2-activation")
def list_l2_pilot_activation(include_disabled: bool = Query(False),
                             _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Who is on the Layer 2 v2 pilot, which switches, since when, and WHAT EACH ONE TURNED ON.

    `include_disabled=true` adds the tenants whose switches were stamped off, which is the read
    `scripts/l2_shadow_diff.py` is interpreted against: a seven-day window over a tenant whose
    pattern pass stopped on day four is a window in which the two paths ran side by side for four
    days and not seven.
    """
    from genios_engine.platform.l2_activation import list_l2_activations
    rows = list_l2_activations(_engine(), include_disabled=bool(include_disabled))
    return {"activations": [r.as_record() for r in rows],
            "analytic_live": sum(1 for r in rows if r.analytic_live),
            "patterns_live": sum(1 for r in rows if r.patterns_live),
            "total": len(rows)}


@router.get("/l2-activation/{target_org}")
def get_l2_pilot_activation(target_org: str, _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """ONE tenant's pilot state — the "is this org activated, and what did that turn on" read.

    Distinct from the list for the reason `get_semantic_activation` is distinct from its own set
    read: this answers a question about a tenant somebody named, including a tenant who was
    switched back off, and `activated: false` with a record beside it is a different fact from
    `activated: false` with none.
    """
    from genios_engine.platform.l2_activation import EFFECTS, get_l2_activation
    record = get_l2_activation(_engine(), target_org)
    if record is None:
        return {"org_id": target_org, "in_pilot": False, "activation": None, "effects": EFFECTS}
    return {"org_id": target_org,
            "in_pilot": record.analytic_live or record.patterns_live,
            "activation": record.as_record(), "effects": EFFECTS}


@router.post("/l2-activation/{target_org}")
def activate_l2_pilot(target_org: str, body: L2PilotActivation,
                      ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Put ONE tenant on the Layer 2 v2 pilot. Idempotent, audited, reversible.

    IDEMPOTENT IN THE SENSE THAT MATTERS: activating twice does not re-date the pilot and does not
    start a second backfill. `platform/l2_activation.activate` keeps a live switch's original
    `enabled_at`, and nothing in the activation path launches work at all —
    `sampler.backfill_history_for_drain` owns the once-per-tenant 18-month reconstruction and
    guards it on history existence, so a second activation costs the same index probe every drain
    already pays.

    The tenant must exist: without the check the org FK raises a 500 on a typo'd id, and an
    operator who mistypes a pilot tenant should be told which word was wrong.
    """
    switches = _l2_switches(body.switch)
    engine = _engine()
    with engine.connect() as c:
        if c.execute(text("select 1 from orgs where id=:o"), {"o": target_org}).first() is None:
            raise HTTPException(404, "account not found")
    from genios_engine.platform.l2_activation import EFFECTS, activate
    record = None
    for switch in switches:
        record = activate(engine, target_org, switch=switch, by=ctx.actor_id or ctx.org_id,
                          notes=body.notes)
    from genios_engine.platform.audit import record as audit
    audit(ctx.org_id, "config_changed", actor_type="user", actor_id=ctx.actor_id or ctx.org_id,
          target_type="org", target_id=target_org,
          metadata={"audit_category": "admin", "field": "l2_v2_activation",
                    "switches": list(switches), "value": True, "notes": body.notes})
    _log.info("L2 v2 pilot ACTIVATED for org=%s switches=%s by=%s",
              target_org, ",".join(switches), ctx.actor_id)
    return {"org_id": target_org, "switched_on": list(switches),
            "activation": record.as_record() if record else None,
            "effects": {s: EFFECTS[s] for s in switches}}


@router.delete("/l2-activation/{target_org}")
def deactivate_l2_pilot(target_org: str, switch: str = Query("both"),
                        ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Take ONE tenant back off. The rollback half, and it is not optional — a cutover you cannot
    reverse is a cutover with extra steps.

    Returns `switched_off: []` for a tenant that was already off rather than 404: the caller's
    intent ("this tenant must not be running the L2 v2 pilot") is satisfied either way, and a 404
    would make a retry after a dropped connection look like a failure.
    """
    switches = _l2_switches(switch)
    engine = _engine()
    from genios_engine.platform.l2_activation import deactivate, get_l2_activation
    switched_off = [s for s in switches
                    if deactivate(engine, target_org, switch=s,
                                  by=ctx.actor_id or ctx.org_id)]
    if switched_off:
        from genios_engine.platform.audit import record as audit
        audit(ctx.org_id, "config_changed", actor_type="user",
              actor_id=ctx.actor_id or ctx.org_id, target_type="org", target_id=target_org,
              metadata={"audit_category": "admin", "field": "l2_v2_activation",
                        "switches": switched_off, "value": False})
        _log.info("L2 v2 pilot DEACTIVATED for org=%s switches=%s by=%s",
                  target_org, ",".join(switched_off), ctx.actor_id)
    record = get_l2_activation(engine, target_org)
    return {"org_id": target_org, "switched_off": switched_off,
            "activation": record.as_record() if record else None}


# =================================================================================================
# LAYER 3 v2 PILOT — per (tenant, DOMAIN), because the corpus is three domains and V1 is one
# =================================================================================================
#
# WHY THIS BLOCK EXISTS AT ALL. `platform/l3_activation.activate` had no request path, so the only
# way to start an L3 pilot was a hand-written INSERT into `l3_activation` — which is the exact
# defect `tests/test_l2_pilot_activation.py` was written against one layer down. A pilot begun by
# SQL has no `enabled_by` anybody trusts and no audit row at all.
#
# PER DOMAIN, NOT PER TENANT. L3's activation key is (org_id, domain) and that is not decoration:
# the corpus carries three domains (Admin 371 files, Customer Support 604, Sales 418) and doc 00's
# scope rule is "Admin domain first ... Sales and CS corpora stay compiled and stamped but
# activate later". A per-tenant boolean would turn on 1,394 files' worth of expertise in one
# request, which is the `use_domain_compiler` mistake with a nicer name.
#
# NO "all" SHORTHAND, deliberately unlike L2's `switch="both"`. There, both switches gate passes
# that were designed to run together. Here a domain is a whole authored corpus with its own V1
# readiness, and the plan activates exactly one first. An operator who wants three domains should
# have to say so three times.
class L3PilotActivation(BaseModel):
    """The body of a domain switch-on. `domain` is required and has no default — the whole point
    of the key is that turning on Admin is not turning on Sales."""

    domain: str
    notes: str | None = None
    #: Authored business-model / offering variant ids (full corpus ids preferred; a bare alias
    #: is accepted and reported as unresolved if ambiguous). Optional; absent means unchanged.
    variant_ids: list[str] | None = None


def _l3_domain(domain: str) -> str:
    """Validated by the module that owns the names, so the refusal is a 400 naming the legal
    domains rather than a 422 whose body an operator has to decode."""
    from genios_engine.platform.l3_activation import require_domain
    try:
        return require_domain(domain)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/l3-activation")
def list_l3_pilot_activation(include_disabled: bool = Query(False),
                             _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Who is on the Layer 3 pilot, for WHICH DOMAIN, since when, and what that turned on.

    `include_disabled=true` adds the (tenant, domain) pairs that were stamped off, for the same
    reason L2's list does: `scripts/l3_pilot_report.py --days 7` is interpreted against this read,
    and a seven-day window over a domain that was switched off on day four is four days of
    compiled packages and three of nothing.
    """
    from genios_engine.platform.l3_activation import EFFECTS, list_l3_activations
    rows = list_l3_activations(_engine(), include_disabled=bool(include_disabled))
    live = [r for r in rows if r.live]
    return {"activations": [r.as_record() for r in rows],
            "live": len(live),
            "live_domains": sorted({r.domain for r in live}),
            "total": len(rows),
            "effects": EFFECTS}


@router.get("/l3-activation/{target_org}")
def get_l3_pilot_activation(target_org: str, _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """ONE tenant's L3 state, across every domain.

    Returns the domains rather than a boolean because "is this org on the L3 pilot" is not a
    question with a yes/no answer once the key is (org, domain) — a tenant can be compiling Admin
    and not Sales, and an operator told only "activated: true" will assume both.
    """
    from genios_engine.platform.l3_activation import (EFFECTS, L3_DOMAINS, activated_domains,
                                                      get_l3_activation)
    records = [r for r in (get_l3_activation(_engine(), target_org, d) for d in L3_DOMAINS)
               if r is not None]
    live = sorted(activated_domains(_engine(), target_org))
    return {"org_id": target_org,
            "in_pilot": bool(live),
            "live_domains": live,
            "activations": [r.as_record() for r in records],
            "effects": EFFECTS}


@router.post("/l3-activation/{target_org}")
def activate_l3_pilot(target_org: str, body: L3PilotActivation,
                      ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Put ONE tenant's ONE domain on the Layer 3 pilot. Idempotent, audited, reversible.

    THE ORDERING THIS ROUTE MUST NOT BE USED TO VIOLATE. Doc 06: "the one ordering that must not
    be violated is Y1 before Y5", because flipping activation without the typed consumers produces
    the fake success the adapter's own docstring warns about — "activation would LOOK successful
    while producing generic output". Y1 has landed and J1 passed, so this route is now safe to
    exist; it was deliberately not built before that.

    IDEMPOTENT IN THE SENSE THAT MATTERS: activating a live domain twice keeps the original
    `enabled_at`, so a retry after a dropped connection does not re-date a pilot whose whole
    purpose is a seven-day window. Nothing here launches work — the compiler's live pass reads
    this table on its next sweep.

    The tenant must exist: without the check the org FK raises a 500 on a typo'd id, and an
    operator who mistypes a pilot tenant should be told which word was wrong.
    """
    domain = _l3_domain(body.domain)
    engine = _engine()
    with engine.connect() as c:
        if c.execute(text("select 1 from orgs where id=:o"), {"o": target_org}).first() is None:
            raise HTTPException(404, "account not found")
    # THE PLAN'S DOMAIN BOUND. Individual buys one domain, Startup three, Growth ten — a domain
    # is a whole compiled corpus per tenant, so it is the expensive axis of the product and the
    # one the pricing page sells on. Re-activating a domain the tenant already has live is not a
    # new one and must not be refused, or a double-click would read as an upsell.
    from genios_engine.platform.billing import plan_domain_limit
    from genios_engine.platform.l3_activation import EFFECTS, activate, activated_domains
    live = activated_domains(engine, target_org)
    if domain not in live:
        with engine.connect() as c:
            tier = c.execute(text("select subscription_tier from orgs where id=:o"),
                             {"o": target_org}).scalar()
        allowed = plan_domain_limit(tier)
        if len(live) >= allowed:
            raise HTTPException(402, {
                "code": "DOMAIN_LIMIT_REACHED",
                "message": f"This plan includes {allowed} expertise "
                           f"{'domain' if allowed == 1 else 'domains'} and "
                           f"{len(live)} {'is' if len(live) == 1 else 'are'} already live. "
                           f"Upgrade to add another.",
                "live": sorted(live), "limit": allowed})
    record = activate(engine, target_org, domain=domain, by=ctx.actor_id or ctx.org_id,
                      notes=body.notes, variant_ids=body.variant_ids)
    from genios_engine.platform.audit import record as audit
    audit(ctx.org_id, "config_changed", actor_type="user", actor_id=ctx.actor_id or ctx.org_id,
          target_type="org", target_id=target_org,
          metadata={"audit_category": "admin", "field": "l3_activation",
                    "domain": domain, "value": True, "notes": body.notes})
    _log.info("L3 pilot ACTIVATED for org=%s domain=%s by=%s",
              target_org, domain, ctx.actor_id)
    return {"org_id": target_org, "switched_on": domain,
            "activation": record.as_record(),
            "effect": EFFECTS.get(domain)}


@router.delete("/l3-activation/{target_org}")
def deactivate_l3_pilot(target_org: str, domain: str = Query(...),
                        ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Take ONE tenant's ONE domain back off. The rollback half, and it is not optional.

    `domain` is a REQUIRED query parameter with no default. Everywhere else in this file a
    reversal defaults to the widest reading, because taking something off is the safe direction —
    but here the widest reading would silently end two other domains' pilots, and a pilot ended by
    accident is a seven-day window nobody can read afterwards.

    Returns `switched_off: null` for a domain that was already off rather than 404: the caller's
    intent ("this tenant must not be compiling Admin") is satisfied either way, and a 404 would
    make a retry after a dropped connection look like a failure.
    """
    domain = _l3_domain(domain)
    engine = _engine()
    from genios_engine.platform.l3_activation import deactivate, get_l3_activation
    turned_off = deactivate(engine, target_org, domain=domain, by=ctx.actor_id or ctx.org_id)
    if turned_off:
        from genios_engine.platform.audit import record as audit
        audit(ctx.org_id, "config_changed", actor_type="user",
              actor_id=ctx.actor_id or ctx.org_id, target_type="org", target_id=target_org,
              metadata={"audit_category": "admin", "field": "l3_activation",
                        "domain": domain, "value": False})
        _log.info("L3 pilot DEACTIVATED for org=%s domain=%s by=%s",
                  target_org, domain, ctx.actor_id)
    record = get_l3_activation(engine, target_org, domain)
    return {"org_id": target_org, "switched_off": domain if turned_off else None,
            "activation": record.as_record() if record else None}


# ════════════════════════════════════════════════════════════════════════════════════════
# Z0 / G-07 · Layer 4 pilot activation — five features, per tenant
#
# BUILT IN THE SAME WAVE AS THE TABLE, DELIBERATELY, AND FOR THE FOURTH TIME.
# `l1_semantic_activation` shipped with a reader and no writer anything could reach.
# `l2_v2_activation` landed its routes in the same wave because of that. `l3_activation` shipped
# in Y0 with a reader, a fail-closed gate and an erasure row — and `activate`/`deactivate`
# reachable from nothing, so the only way to start a pilot was a hand-written INSERT, and a pilot
# begun by SQL has no `enabled_by` anybody trusts and no audit row at all. Doc 07 says not to
# repeat that a fourth time, so these four routes exist before the first feature does.
# ════════════════════════════════════════════════════════════════════════════════════════


class L4PilotActivation(BaseModel):
    """The body of a feature switch-on. `feature` is required and has no default — the whole point
    of the key is that turning on the roster is not turning on the narrative."""

    feature: str
    notes: str | None = None


def _l4_feature(feature: str) -> str:
    """Validated by the module that owns the names, so the refusal is a 400 naming the legal
    features rather than a 422 whose body an operator has to decode."""
    from genios_engine.platform.l4_activation import require_feature
    try:
        return require_feature(feature)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/l4-activation")
def list_l4_pilot_activation(include_disabled: bool = Query(False),
                             _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Who is on the Layer 4 pilot, for WHICH FEATURES, since when, and what that turned on.

    `include_disabled=true` adds the (tenant, feature) pairs that were stamped off, for the same
    reason L2's and L3's lists do: a seven-day K7 window over a feature that was switched off on
    day four is four days of the new behaviour and three of the old one, and a read that hid the
    stamped rows would present that as seven.
    """
    from genios_engine.platform.l4_activation import EFFECTS, FEATURE_WAVES, list_l4_activations
    rows = list_l4_activations(_engine(), include_disabled=bool(include_disabled))
    live = [r for r in rows if r.live]
    return {"activations": [r.as_record() for r in rows],
            "live": len(live),
            "live_features": sorted({r.feature for r in live}),
            "total": len(rows),
            "waves": FEATURE_WAVES,
            "effects": EFFECTS}


@router.get("/l4-activation/{target_org}")
def get_l4_pilot_activation(target_org: str, _ctx: AuthCtx = Depends(require_admin)) -> dict:
    """ONE tenant's L4 state, across every feature.

    Returns the features rather than a boolean because "is this org on the L4 pilot" is not a
    question with a yes/no answer once the key is (org, feature) — a tenant can have the roster
    awake and no narrative at all, and an operator told only "activated: true" will assume both.

    `missing_preconditions` is reported per live feature, not enforced: doc 08's wave order is
    real, and a tenant running `bundle` with `ranking_v2` off is narrating a decision the formula
    never made. This read is where that is visible before a gate report says it a fortnight later.
    """
    from genios_engine.platform.l4_activation import (CROSS_LAYER_EFFECTS, EFFECTS, L4_FEATURES,
                                                      activated_features, get_l4_activation,
                                                      missing_cross_layer_preconditions,
                                                      missing_preconditions)
    engine = _engine()
    records = [r for r in (get_l4_activation(engine, target_org, f) for f in L4_FEATURES)
               if r is not None]
    live = sorted(activated_features(engine, target_org))
    # THE ORDERING THAT CROSSES A LAYER, reported beside the one that does not. `ranking_v2` live
    # on a tenant whose Layer 1 was never activated is the six-weight model permanently reweighing
    # five — true, receipted on every decision, and completely invisible on a console that showed
    # only `live: true`. See `l4_activation.CROSS_LAYER_PRECONDITIONS`.
    cross = {f: list(missing_cross_layer_preconditions(engine, target_org, f)) for f in live}
    return {"org_id": target_org,
            "in_pilot": bool(live),
            "live_features": live,
            "missing_preconditions": {f: list(missing_preconditions(engine, target_org, f))
                                      for f in live},
            "missing_cross_layer_preconditions": cross,
            "activations": [r.as_record() for r in records],
            "effects": EFFECTS,
            # Only the ones actually unmet: an operator reading a console needs the explanation for
            # the state they are in, not a glossary of every state they are not.
            "cross_layer_effects": {item: CROSS_LAYER_EFFECTS[item]
                                    for items in cross.values() for item in items}}


@router.post("/l4-activation/{target_org}")
def activate_l4_pilot(target_org: str, body: L4PilotActivation,
                      ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Put ONE tenant's ONE feature on the Layer 4 pilot. Idempotent, audited, reversible.

    IDEMPOTENT IN THE SENSE THAT MATTERS: activating a live feature twice keeps the original
    `enabled_at`, so a retry after a dropped connection does not re-date a pilot whose whole
    purpose is a seven-day window. Nothing here launches work — the next ordinary reasoning run
    reads the switch.

    THE WAVE ORDER IS REPORTED, NOT ENFORCED. `missing_preconditions` comes back on the response
    naming the features this one expects to be live and are not. Refusing here would stop an
    operator switching one thing on in isolation to debug it; saying nothing would let `bundle`
    reach a tenant whose formula has not been woken. So it is said, on the way in.

    The tenant must exist: without the check the org FK raises a 500 on a typo'd id, and an
    operator who mistypes a pilot tenant should be told which word was wrong.
    """
    feature = _l4_feature(body.feature)
    engine = _engine()
    with engine.connect() as c:
        if c.execute(text("select 1 from orgs where id=:o"), {"o": target_org}).first() is None:
            raise HTTPException(404, "account not found")
    from genios_engine.platform.l4_activation import (CROSS_LAYER_EFFECTS, EFFECTS, activate,
                                                      missing_cross_layer_preconditions,
                                                      missing_preconditions)
    record = activate(engine, target_org, feature=feature, by=ctx.actor_id or ctx.org_id,
                      notes=body.notes)
    pending = missing_preconditions(engine, target_org, feature)
    # Said on the way IN, where it can still change the operator's mind — see the docstring. This
    # is the ordering that used to be unsayable: switching `ranking_v2` on for a tenant whose
    # Layer 1 is dark returned an unqualified success.
    cross = missing_cross_layer_preconditions(engine, target_org, feature)
    from genios_engine.platform.audit import record as audit
    audit(ctx.org_id, "config_changed", actor_type="user", actor_id=ctx.actor_id or ctx.org_id,
          target_type="org", target_id=target_org,
          metadata={"audit_category": "admin", "field": "l4_activation",
                    "feature": feature, "value": True, "notes": body.notes,
                    "missing_preconditions": list(pending),
                    "missing_cross_layer_preconditions": list(cross)})
    _log.info("L4 pilot ACTIVATED for org=%s feature=%s by=%s (missing preconditions: %s; "
              "cross-layer: %s)", target_org, feature, ctx.actor_id,
              ", ".join(pending) or "none", ", ".join(cross) or "none")
    return {"org_id": target_org, "switched_on": feature,
            "activation": record.as_record(),
            "missing_preconditions": list(pending),
            "missing_cross_layer_preconditions": list(cross),
            "cross_layer_effects": {item: CROSS_LAYER_EFFECTS[item] for item in cross},
            "effect": EFFECTS.get(feature)}


@router.delete("/l4-activation/{target_org}")
def deactivate_l4_pilot(target_org: str, feature: str = Query(...),
                        ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Take ONE tenant's ONE feature back off. The rollback half, and it is not optional.

    `feature` is a REQUIRED query parameter with no default, for the reason L3's `domain` is:
    everywhere else in this file a reversal defaults to the widest reading, because taking
    something off is the safe direction — but the widest reading here would silently end four
    other features' pilots, and a pilot ended by accident is a seven-day window nobody can read
    afterwards.

    Returns `switched_off: null` for a feature that was already off rather than 404: the caller's
    intent ("this tenant must not be narrating") is satisfied either way, and a 404 would make a
    retry after a dropped connection look like a failure.
    """
    feature = _l4_feature(feature)
    engine = _engine()
    from genios_engine.platform.l4_activation import deactivate, get_l4_activation
    turned_off = deactivate(engine, target_org, feature=feature, by=ctx.actor_id or ctx.org_id)
    if turned_off:
        from genios_engine.platform.audit import record as audit
        audit(ctx.org_id, "config_changed", actor_type="user",
              actor_id=ctx.actor_id or ctx.org_id, target_type="org", target_id=target_org,
              metadata={"audit_category": "admin", "field": "l4_activation",
                        "feature": feature, "value": False})
        _log.info("L4 pilot DEACTIVATED for org=%s feature=%s by=%s",
                  target_org, feature, ctx.actor_id)
    record = get_l4_activation(engine, target_org, feature)
    return {"org_id": target_org, "switched_off": feature if turned_off else None,
            "activation": record.as_record() if record else None}
