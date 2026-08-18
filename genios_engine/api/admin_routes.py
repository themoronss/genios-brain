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


@router.get("/whoami")
def admin_whoami(ctx: AuthCtx = Depends(require_admin)) -> dict:
    """Cheap gate probe: the dashboard calls this to decide whether to render the Admin nav item.
    A 403 here is the normal answer for a customer, not an error."""
    return {"admin": True, "org_id": ctx.org_id}
