"""Onboarding / sync progress — DB-backed, human-readable, refresh + restart proof.

One row per org in `onboarding_progress`. The sync background chain calls set_phase() as it moves
through the work; the dashboard polls read() and renders the phase list. Labels here are the ONLY
thing the user sees — deliberately plain language, never "L1/L2/L3" or "reason/context/capture".

Single logical writer per org (the sync orchestrator runs one background chain at a time), so a
read-modify-write of the phases JSON is safe without locking.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

# Ordered phases + user-facing labels + a coarse weight for the overall bar. `src` gates a phase to
# a connected source (emails→gmail, calendar→gcal); cross-cutting phases have src=None.
_PHASES: list[dict] = [
    {"key": "connecting",   "label": "Connecting your accounts",       "weight": 5,  "src": None},
    {"key": "emails",       "label": "Syncing your emails",            "weight": 30, "src": "gmail"},
    {"key": "calendar",     "label": "Syncing your calendar",          "weight": 10, "src": "gcal"},
    {"key": "processing",   "label": "Understanding your conversations", "weight": 25, "src": None},
    {"key": "graph",        "label": "Building your relationship graph", "weight": 10, "src": None},
    {"key": "intelligence", "label": "Finding intelligence",           "weight": 20, "src": None},
]
_LABEL = {p["key"]: p["label"] for p in _PHASES}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fraction(ph: dict) -> float:
    """How 'done' one phase is, 0..1 — used to weight the overall bar."""
    st = ph.get("state")
    if st == "done":
        return 1.0
    if st == "running":
        total, done = ph.get("total"), ph.get("done") or 0
        if total:
            return max(0.0, min(1.0, done / total))
        return 0.5                      # running but no known total → show half
    return 0.0                          # pending / error


def _overall(phases: list[dict]) -> int:
    tw = sum(p.get("weight", 1) for p in phases) or 1
    got = sum(p.get("weight", 1) * _fraction(p) for p in phases)
    return int(round(100 * got / tw))


def start(engine, org_id: str, sources: list[str]) -> None:
    """Begin a fresh sync run: build the phase list for the connected sources, reset to running."""
    srcs = set(sources or [])
    phases = [
        {"key": p["key"], "label": p["label"], "weight": p["weight"],
         "state": "pending", "done": 0, "total": None, "detail": None}
        for p in _PHASES if p["src"] is None or p["src"] in srcs
    ]
    now = _now()
    with engine.begin() as c:
        c.execute(text(
            "insert into onboarding_progress (org_id, state, current_phase, overall_percent, "
            "phases, started_at, updated_at) "
            "values (:o,'running',:cp,0,cast(:ph as jsonb),:ts,:ts) "
            "on conflict (org_id) do update set state='running', current_phase=:cp, "
            "overall_percent=0, phases=cast(:ph as jsonb), started_at=:ts, updated_at=:ts"),
            {"o": org_id, "cp": phases[0]["key"] if phases else None,
             "ph": json.dumps(phases), "ts": now})


def set_phase(engine, org_id: str, key: str, *, state: str | None = None,
              done: int | None = None, total: int | None = None, detail: str | None = None) -> None:
    """Update one phase. Marks it current when it goes running; recomputes the overall bar. A no-op
    if there is no run row yet (progress is best-effort and must never break the sync)."""
    with engine.begin() as c:
        row = c.execute(text("select phases from onboarding_progress where org_id=:o"),
                        {"o": org_id}).first()
        if row is None:
            return
        phases = row.phases if isinstance(row.phases, list) else json.loads(row.phases or "[]")
        found = False
        for ph in phases:
            if ph.get("key") == key:
                found = True
                if state is not None:
                    ph["state"] = state
                if done is not None:
                    ph["done"] = done
                if total is not None:
                    ph["total"] = total
                if detail is not None:
                    ph["detail"] = detail
                break
        if not found:
            return
        current = key if state == "running" else None
        pct = _overall(phases)
        params = {"o": org_id, "ph": json.dumps(phases), "pct": pct, "ts": _now()}
        if current:
            c.execute(text("update onboarding_progress set phases=cast(:ph as jsonb), "
                           "overall_percent=:pct, current_phase=:cp, updated_at=:ts where org_id=:o"),
                      {**params, "cp": current})
        else:
            c.execute(text("update onboarding_progress set phases=cast(:ph as jsonb), "
                           "overall_percent=:pct, updated_at=:ts where org_id=:o"), params)


def finish(engine, org_id: str, *, error: bool = False, detail: str | None = None) -> None:
    """Close the run. Success → every phase done, 100%. Failure → mark the phase that was RUNNING
    as 'error' (with the reason in its detail) and LEAVE later phases pending, so the bar shows
    exactly where it stopped instead of lying with a green 100%."""
    with engine.begin() as c:
        row = c.execute(text("select phases, current_phase from onboarding_progress where org_id=:o"),
                        {"o": org_id}).first()
        if row is None:
            return
        phases = row.phases if isinstance(row.phases, list) else json.loads(row.phases or "[]")
        if error:
            for ph in phases:                       # only the in-flight phase failed; rest stay pending
                if ph.get("state") == "running":
                    ph["state"] = "error"
                    if detail:
                        ph["detail"] = detail
            pct = _overall(phases)                  # real progress, NOT 100
            cur = row.current_phase
        else:
            for ph in phases:
                ph["state"] = "done"
            pct = 100
            cur = "ready"
        c.execute(text("update onboarding_progress set state=:st, current_phase=:cur, "
                       "overall_percent=:pct, phases=cast(:ph as jsonb), updated_at=:ts where org_id=:o"),
                  {"o": org_id, "st": "error" if error else "done", "cur": cur, "pct": pct,
                   "ph": json.dumps(phases), "ts": _now()})


def read(engine, org_id: str) -> dict:
    """Current progress for the dashboard. Returns a safe idle shape if no run has started."""
    with engine.connect() as c:
        row = c.execute(text("select state, current_phase, overall_percent, phases, started_at, "
                             "updated_at from onboarding_progress where org_id=:o"),
                        {"o": org_id}).first()
    if row is None:
        return {"state": "idle", "current_phase": None, "current_label": None,
                "overall_percent": 0, "phases": [], "started_at": None, "updated_at": None}
    phases = row.phases if isinstance(row.phases, list) else json.loads(row.phases or "[]")
    # strip the internal weight from the client payload
    out_phases = [{"key": p.get("key"), "label": p.get("label") or _LABEL.get(p.get("key"), ""),
                   "state": p.get("state", "pending"), "done": p.get("done") or 0,
                   "total": p.get("total"), "detail": p.get("detail")} for p in phases]
    return {"state": row.state, "current_phase": row.current_phase,
            "current_label": _LABEL.get(row.current_phase),
            "overall_percent": int(row.overall_percent or 0), "phases": out_phases,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None}
