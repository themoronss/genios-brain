from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from datetime import datetime, timezone
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SessionStartRequest(BaseModel):
    org_id: str
    agent_id: str
    session_id: str = None  # auto-generate if not provided


class SessionEndRequest(BaseModel):
    org_id: str
    session_id: str
    status: str = "COMPLETED"  # COMPLETED or FAILED


@router.post("/v1/agents/session/start")
def start_agent_session(request: SessionStartRequest, db: Session = Depends(get_db)):
    """Open an agent session for cross-agent conflict detection."""
    session_id = request.session_id or str(uuid.uuid4())

    try:
        db.execute(
            text("""
                INSERT INTO agent_sessions (org_id, agent_id, session_id, status, started_at)
                VALUES (:org_id, :agent_id, :session_id, 'ACTIVE', NOW())
                ON CONFLICT (org_id, session_id) DO UPDATE SET
                    status = 'ACTIVE',
                    agent_id = :agent_id,
                    started_at = NOW(),
                    ended_at = NULL
            """),
            {"org_id": request.org_id, "agent_id": request.agent_id, "session_id": session_id}
        )
        db.commit()

        return {
            "session_id": session_id,
            "agent_id": request.agent_id,
            "status": "ACTIVE",
            "started_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to start agent session: {e}")
        raise HTTPException(status_code=500, detail="Failed to start session")


@router.post("/v1/agents/session/end")
def end_agent_session(request: SessionEndRequest, db: Session = Depends(get_db)):
    """Close an agent session after task completion."""
    status = request.status if request.status in ("COMPLETED", "FAILED") else "COMPLETED"

    try:
        result = db.execute(
            text("""
                UPDATE agent_sessions
                SET status = :status, ended_at = NOW()
                WHERE org_id = :org_id AND session_id = :session_id AND status = 'ACTIVE'
                RETURNING id, agent_id
            """),
            {"org_id": request.org_id, "session_id": request.session_id, "status": status}
        )
        db.commit()

        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Active session not found")

        return {
            "session_id": request.session_id,
            "agent_id": row[1],
            "status": status,
            "ended_at": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to end agent session: {e}")
        raise HTTPException(status_code=500, detail="Failed to end session")
