"""User tasks — Manager Mode ledger + nag.

"GeniOS, remember: message Isha next week" → stored here → surfaces in the
morning brief / extension Today section, and NAGS when overdue ("you said
you'd do this — 6 days, still not done").

Dashboard-shape routes (`/api/org/{org_id}/tasks`), same auth as the other
dashboard routes. Defensive CREATE TABLE IF NOT EXISTS on first use so the
feature works even before alembic 0031 runs in an environment.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter()

_ENSURED = False


def _ensure_table(db: Session) -> None:
    global _ENSURED
    if _ENSURED:
        return
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS user_tasks (
            id TEXT PRIMARY KEY, org_id VARCHAR(64) NOT NULL, user_id VARCHAR(64),
            text TEXT NOT NULL, target_entity TEXT, due_at TIMESTAMPTZ,
            status VARCHAR(16) NOT NULL DEFAULT 'open',
            source VARCHAR(16) NOT NULL DEFAULT 'user',
            snoozed_until TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    db.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_user_tasks_org_status ON user_tasks (org_id, status, due_at)"
    ))
    db.commit()
    _ENSURED = True


# Light natural-date parsing for quick-add ("remember: msg Isha next week",
# "remind me in 1 min"). Minute/hour patterns are checked BEFORE day patterns
# so short-fuse reminders get a real due time instead of being stored NULL.
_MIN_RX = re.compile(r"\bin\s+(\d{1,3})\s*min(?:ute)?s?\b", re.I)
_HR_RX = re.compile(r"\bin\s+(\d{1,2})\s*h(?:ou)?rs?\b", re.I)
_REL_DAYS = [
    (re.compile(r"\btoday\b", re.I), 0),
    (re.compile(r"\btomorrow\b", re.I), 1),
    (re.compile(r"\bnext week\b", re.I), 7),
    (re.compile(r"\bin\s+(\d{1,3})\s*days?\b", re.I), None),  # captured
]


def parse_due(task_text: str) -> datetime | None:
    now = datetime.now(UTC)
    m = _MIN_RX.search(task_text)
    if m:
        return now + timedelta(minutes=int(m.group(1)))
    m = _HR_RX.search(task_text)
    if m:
        return now + timedelta(hours=int(m.group(1)))
    for rx, days in _REL_DAYS:
        m = rx.search(task_text)
        if m:
            d = days if days is not None else int(m.group(1))
            return now + timedelta(days=d)
    return None


class TaskCreate(BaseModel):
    text: str = Field(..., min_length=2, max_length=500)
    target_entity: str | None = None
    due_at: datetime | None = None
    source: str = "user"


@router.post("/api/org/{org_id}/tasks", status_code=201)
def create_task(org_id: str, body: TaskCreate, db: Session = Depends(get_db)):
    _ensure_table(db)
    raw = body.text.strip()
    # accept "remember:" / "remind me to" prefixes verbatim from quick-add
    cleaned = re.sub(r"^(remember( to)?|remind me( to)?)[:,]?\s*", "", raw, flags=re.I).strip() or raw
    due = body.due_at or parse_due(raw)
    tid = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO user_tasks (id, org_id, text, target_entity, due_at, source)
            VALUES (:id, :org, :txt, :ent, :due, :src)
        """),
        {"id": tid, "org": org_id, "txt": cleaned, "ent": body.target_entity,
         "due": due, "src": body.source if body.source in ("user", "auto") else "user"},
    )
    db.commit()
    return {"id": tid, "text": cleaned, "due_at": due.isoformat() if due else None, "status": "open"}


@router.get("/api/org/{org_id}/tasks")
def list_tasks(org_id: str, status: str = "open", limit: int = 50, db: Session = Depends(get_db)):
    _ensure_table(db)
    rows = db.execute(
        text("""
            SELECT id, text, target_entity, due_at, status, source, snoozed_until, created_at
            FROM user_tasks
            WHERE org_id = :org AND (:st = 'all' OR status = :st)
            ORDER BY due_at NULLS LAST, created_at DESC
            LIMIT :lim
        """),
        {"org": org_id, "st": status, "lim": min(limit, 200)},
    ).fetchall()
    now = datetime.now(UTC)

    def _shape(r):
        due = r.due_at
        overdue_days = None
        if due is not None and r.status == "open":
            dd = (now - (due if due.tzinfo else due.replace(tzinfo=UTC))).days
            overdue_days = dd if dd > 0 else None
        return {
            "id": r.id, "text": r.text, "target_entity": r.target_entity,
            "due_at": due.isoformat() if due else None,
            "status": r.status, "source": r.source,
            "overdue_days": overdue_days,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }

    return {"tasks": [_shape(r) for r in rows]}


class TaskUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|done|snoozed|dropped)$")
    snooze_days: int | None = None


@router.patch("/api/org/{org_id}/tasks/{task_id}")
def update_task(org_id: str, task_id: str, body: TaskUpdate, db: Session = Depends(get_db)):
    _ensure_table(db)
    snooze_until = (
        datetime.now(UTC) + timedelta(days=body.snooze_days or 2)
        if body.status == "snoozed" else None
    )
    n = db.execute(
        text("""
            UPDATE user_tasks
            SET status = :st, snoozed_until = :sn, updated_at = NOW()
            WHERE id = :id AND org_id = :org
        """),
        {"st": body.status, "sn": snooze_until, "id": task_id, "org": org_id},
    ).rowcount
    db.commit()
    if not n:
        raise HTTPException(status_code=404, detail="task not found")
    return {"ok": True, "status": body.status}


# ── /v1 variants for API-key callers (the extension) ─────────────────────────
from app.api.deps import verify_api_key  # noqa: E402


@router.post("/v1/tasks", status_code=201)
def create_task_v1(
    body: TaskCreate,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Extension quick-add: 'remember: msg Isha next week' with the gn_live key."""
    return create_task(org_id, body, db)


@router.patch("/v1/tasks/{task_id}")
def update_task_v1(
    task_id: str,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    return update_task(org_id, task_id, body, db)


@router.get("/v1/morning-brief")
def morning_brief_v1(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Extension 'Today' section: nags + top priorities via the gn_live key."""
    from app.api.routes.insights import build_morning_brief

    return build_morning_brief(db, org_id)


def overdue_nags(db: Session, org_id: str, limit: int = 5) -> list[dict]:
    """Open overdue (or due-today) tasks for the manager's nag voice. Snoozed
    tasks wake up when snoozed_until passes."""
    _ensure_table(db)
    rows = db.execute(
        text("""
            SELECT id, text, target_entity, due_at,
                   GREATEST(0, EXTRACT(DAY FROM NOW() - due_at))::int AS overdue_days
            FROM user_tasks
            WHERE org_id = :org
              AND (status = 'open' OR (status = 'snoozed' AND snoozed_until <= NOW()))
              AND due_at IS NOT NULL AND due_at <= NOW() + INTERVAL '12 hours'
            ORDER BY due_at ASC
            LIMIT :lim
        """),
        {"org": org_id, "lim": limit},
    ).fetchall()
    out = []
    for r in rows:
        who = f" ({r.target_entity})" if r.target_entity else ""
        days = int(r.overdue_days or 0)
        nag = (
            f"You said you'd {r.text}{who} — {days} day(s), still not done."
            if days > 0 else f"Due today: {r.text}{who}."
        )
        out.append({"id": r.id, "text": r.text, "target_entity": r.target_entity,
                    "overdue_days": days, "nag": nag})
    return out
