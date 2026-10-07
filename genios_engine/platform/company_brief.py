"""A tenant's company brief, composed — the one place a model site asks for it (STEP-07).

`brief_for(conn, org_id)` reads three things and composes them deterministically
(`contracts/company_brief.compose`): the company and its founder (`orgs.company`, `orgs.name`, as
signup stores them), the people who are us (`platform/self_identity`, STEP-04), and the lines the
founder accepted (`platform/company_brief_store`). `at` rebuilds the brief in force at any past
instant, because nothing in the table is ever deleted.

`current(source, org_id)` is what a model site calls: the same brief, held for a minute per process,
and dropped the moment the store writes a line for that tenant. It FAILS OPEN to the empty brief — a
brief that cannot be read is no brief, and every prompt is then exactly what it was before STEP-07,
which is the safe direction; the failure is logged, never raised into a judgment.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from sqlalchemy import text

from genios_engine.contracts.company_brief import CompanyBrief, compose
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.company_brief")

#: How long one process trusts a brief it read. The store invalidates on every write it makes in this
#: process; another replica's write is seen within this long.
TTL_SECONDS = 60.0

_CACHE: dict[str, tuple[float, CompanyBrief]] = {}
_LOCK = threading.Lock()


def brief_for(conn, org_id: str, *, at: datetime | None = None) -> CompanyBrief:
    """The tenant's brief, now or at `at`. Empty when no line is accepted."""
    from genios_engine.platform.company_brief_store import accepted
    from genios_engine.platform.self_identity import identity_for

    lines = accepted(conn, org_id, at=at)
    if not lines:
        return CompanyBrief(org_id=org_id)
    org = conn.execute(text("select name, company from orgs where id = :o"),
                       {"o": org_id}).first()
    us = identity_for(conn, org_id)
    return compose(org_id=org_id, company=getattr(org, "company", None),
                   founder=getattr(org, "name", None),
                   us=sorted(us.addresses) + sorted(us.domains), lines=lines)


def _engine(source):
    return getattr(source, "engine", source)


def current(source, org_id: str) -> CompanyBrief:
    """The tenant's brief for a model site: cached for `TTL_SECONDS`, empty on any failure.

    `source` is an engine, or anything with `.engine` (a store). A connection is accepted too, and
    read through without the cache — a caller inside a transaction sees its own writes."""
    if not org_id:
        return CompanyBrief(org_id="")
    now = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(org_id)
        if hit is not None and now - hit[0] < TTL_SECONDS:
            return hit[1]
    try:
        engine = _engine(source)
        if hasattr(engine, "connect"):
            with engine.connect() as conn:
                brief = brief_for(conn, org_id)
        else:                                            # a connection
            return brief_for(engine, org_id)
    except Exception:      # noqa: BLE001 — no brief is the safe direction; never a lost judgment
        _log.warning("company brief unreadable for org=%s — prompts go without it", org_id,
                     exc_info=True)
        return CompanyBrief(org_id=org_id)
    with _LOCK:
        _CACHE[org_id] = (now, brief)
    return brief


def invalidate(org_id: str | None = None) -> None:
    """Forget this process's copy of one tenant's brief — or of every tenant's."""
    with _LOCK:
        if org_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(org_id, None)


def named_sender(source, org_id: str, email: str | None) -> str | None:
    """Whether the tenant's brief names this sender, and why — `connector:…`, `person:…`,
    `watchlist:…` — or None. Fails open to None, like `current`."""
    return current(source, org_id).named_sender(email)


__all__ = ["TTL_SECONDS", "brief_for", "current", "invalidate", "named_sender"]
