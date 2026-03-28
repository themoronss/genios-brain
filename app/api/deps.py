from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify API key and return org_id."""
    token = credentials.credentials
    if not token.startswith("gn_live_"):
        raise HTTPException(status_code=401, detail="Invalid API Key format")
    db = SessionLocal()
    try:
        result = db.execute(
            text("SELECT id FROM orgs WHERE api_key = :api_key"),
            {"api_key": token},
        ).fetchone()
    finally:
        db.close()
    if not result:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return str(result[0])
