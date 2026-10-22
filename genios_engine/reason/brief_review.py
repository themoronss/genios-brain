"""The weekly company-brief review — what the brief is missing, proposed once a week (STEP-07 §3.6).

A brief written once goes stale: a new application goes live, a program ends, a new intro agent starts
writing. Once per ISO week, for every tenant, the drafter (`reason/brief_drafter`) is asked again — with
the brief in force in its prompt — for what is missing. What it returns is written as proposals, by
`weekly`; nothing changes until the founder accepts.

⛔ EVERY TENANT, NOT ONLY ONE THAT ACCEPTED A LINE (GeniOS-011 S27.U1, audit
`goals-antler-cannot-appear-today`). The review ran only for a tenant with at least one accepted line, and
the only other door to a first draft is the operator's `scripts/draft_company_brief.py` — so a founder
whose brief was never drafted had to type every goal by hand, and the work he was pursuing never became
one. Now a tenant with no accepted line gets its first draft here, the week it has memory to read; a
tenant with none is `no_patterns`, and no model is called.

ITS OWN CLAIM, ITS OWN TRANSACTIONS. The week is claimed in `company_brief_reviews` (migration 0195), so
every replica may call this on every heavy tick and a week is reviewed once. ⛔ A FAILED WEEK IS CLAIMED
AGAIN (GeniOS-011 S27.U1): a week whose draft the model failed (`model:…`) or that raised (`error:…`)
was lost until the next ISO week; the next heavy tick now claims it again, and only one replica does —
the claim's update re-reads the row it waited on, which no longer says failed once one replica holds it.
A week that ran — proposing something or nothing — is never claimed again. The model call is made
outside any transaction: the learning sweep holds one transaction per tenant, and a network call does
not belong inside it (STEP-07 §8.2).
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.company_brief.review")

#: Every tenant — not only one that accepted a line (GeniOS-011 S27.U1).
_ORGS = text("select id from orgs order by id")
#: What a failed week's outcome starts with: the model failed the draft, or the review raised.
FAILED = ("model:", "error:")
#: The week's claim — a new week, or a week that failed (GeniOS-011 S27.U1); never one that ran.
_CLAIM = text("insert into company_brief_reviews (org_id, week_key, started_at) "
              "values (:o, :wk, :at) "
              "on conflict (org_id, week_key) do update set started_at = excluded.started_at, "
              "    finished_at = null, outcome = null, proposed = 0 "
              " where company_brief_reviews.outcome like any(cast(:failed as text[])) "
              "returning week_key")
_FINISH = text("update company_brief_reviews set finished_at = :at, outcome = :out, "
               "proposed = :n where org_id = :o and week_key = :wk")


def week_key(now: datetime) -> str:
    """The ISO week a review belongs to — `2026-W41`."""
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def tenants(conn) -> list[str]:
    """Every tenant the weekly review drafts for — one with no accepted line too (GeniOS-011 S27.U1)."""
    return [r[0] for r in conn.execute(_ORGS)]


def run_company_brief_reviews(engine, *, now: datetime, llm: Any, cost_sink=None,
                              orgs: Iterable[str] | None = None) -> dict:
    """One review per tenant per ISO week, and a failed week again on the next tick. Never raises for
    one tenant. `orgs` names the tenants to review — every tenant (`tenants`) when None, as the heavy
    tick calls it; an operator or a test names its own."""
    from genios_engine.reason.brief_drafter import draft_company_brief

    if llm is None:
        return {"orgs": 0, "reviewed": 0, "skipped": "no_model"}
    if orgs is None:
        with engine.connect() as c:
            orgs = tenants(c)
    orgs = list(orgs)
    wk = week_key(now)
    reviewed = already = proposed = failed = 0
    for org in orgs:
        with engine.begin() as c:
            claimed = c.execute(_CLAIM, {"o": org, "wk": wk, "at": now,
                                         "failed": [f"{p}%" for p in FAILED]}).first()
        if claimed is None:
            already += 1
            continue
        try:
            out = draft_company_brief(engine, org, llm, now=now, cost_sink=cost_sink,
                                      proposed_by="weekly")
            outcome, n = (out.skipped or "proposed"), out.proposed
            # ⛔ A DRAFT THE MODEL FAILED IS A FAILED WEEK (`yc2_w27_s18` M50.C3.L-logic.V2.U07, s5t-F5):
            # cut, not JSON or unreachable — never counted `reviewed`, and claimed again on the next
            # tick (GeniOS-011 S27.U1).
            failed_week = outcome.startswith(FAILED[0])
        except Exception as exc:                          # noqa: BLE001 — one tenant ≠ the rest
            _log.exception("company brief review failed org=%s", org)
            outcome, n = f"{FAILED[1]}{type(exc).__name__}", 0
            failed_week = True
        with engine.begin() as c:
            c.execute(_FINISH, {"o": org, "wk": wk, "at": now, "out": outcome[:200], "n": n})
        if failed_week:
            failed += 1
        else:
            reviewed += 1
        proposed += n
    return {"orgs": len(orgs), "reviewed": reviewed, "already_this_week": already,
            "proposed": proposed, "failed": failed, "week": wk}


__all__ = ["FAILED", "run_company_brief_reviews", "tenants", "week_key"]
