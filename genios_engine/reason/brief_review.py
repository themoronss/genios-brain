"""The weekly company-brief review — what the brief is missing, proposed once a week (STEP-07 §3.6).

A brief written once goes stale: a new application goes live, a program ends, a new intro agent starts
writing. Once per ISO week, for every tenant whose founder has accepted at least one line, the drafter
(`reason/brief_drafter`) is asked again — with the brief in force in its prompt — for what is missing.
What it returns is written as proposals, by `weekly`; nothing changes until the founder accepts.

ITS OWN CLAIM, ITS OWN TRANSACTIONS. The week is claimed in `company_brief_reviews` (migration 0195,
`on conflict do nothing`), so every replica may call this on every heavy tick and a week is reviewed
once. The model call is made outside any transaction: the learning sweep holds one transaction per
tenant, and a network call does not belong inside it (STEP-07 §8.2).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.company_brief.review")

_ORGS = text("select distinct org_id from company_brief_lines where status = 'accepted' "
             "order by org_id")
_CLAIM = text("insert into company_brief_reviews (org_id, week_key, started_at) "
              "values (:o, :wk, :at) on conflict do nothing returning week_key")
_FINISH = text("update company_brief_reviews set finished_at = :at, outcome = :out, "
               "proposed = :n where org_id = :o and week_key = :wk")


def week_key(now: datetime) -> str:
    """The ISO week a review belongs to — `2026-W41`."""
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def run_company_brief_reviews(engine, *, now: datetime, llm: Any, cost_sink=None) -> dict:
    """One review per tenant with an accepted brief, per ISO week. Never raises for one tenant."""
    from genios_engine.reason.brief_drafter import draft_company_brief

    if llm is None:
        return {"orgs": 0, "reviewed": 0, "skipped": "no_model"}
    with engine.connect() as c:
        orgs = [r[0] for r in c.execute(_ORGS)]
    wk = week_key(now)
    reviewed = already = proposed = failed = 0
    for org in orgs:
        with engine.begin() as c:
            claimed = c.execute(_CLAIM, {"o": org, "wk": wk, "at": now}).first()
        if claimed is None:
            already += 1
            continue
        try:
            out = draft_company_brief(engine, org, llm, now=now, cost_sink=cost_sink,
                                      proposed_by="weekly")
            outcome, n = (out.skipped or "proposed"), out.proposed
        except Exception as exc:                          # noqa: BLE001 — one tenant ≠ the rest
            _log.exception("company brief review failed org=%s", org)
            outcome, n = f"error:{type(exc).__name__}", 0
            failed += 1
        with engine.begin() as c:
            c.execute(_FINISH, {"o": org, "wk": wk, "at": now, "out": outcome[:200], "n": n})
        reviewed += 1
        proposed += n
    return {"orgs": len(orgs), "reviewed": reviewed, "already_this_week": already,
            "proposed": proposed, "failed": failed, "week": wk}


__all__ = ["run_company_brief_reviews", "week_key"]
