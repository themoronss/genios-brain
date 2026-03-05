from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from sqlalchemy import text

from app.database import SessionLocal
from app.ingestion.gmail_connector import create_oauth_flow
from app.config import GOOGLE_REDIRECT_URI


router = APIRouter()


@router.get("/auth/gmail/connect")
def gmail_connect(org_id: str):

    flow = create_oauth_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )

    return RedirectResponse(authorization_url)


@router.get("/auth/gmail/callback")
async def gmail_callback(request: Request, code: str):

    flow = create_oauth_flow()

    flow.fetch_token(code=code)

    credentials = flow.credentials

    access_token = credentials.token
    refresh_token = credentials.refresh_token
    expiry = credentials.expiry

    # Example org id (for MVP)
    org_id = request.query_params.get("org_id")

    db = SessionLocal()

    db.execute(
        text("""
        INSERT INTO oauth_tokens (
            org_id,
            access_token,
            refresh_token,
            token_expiry
        )
        VALUES (
            :org_id,
            :access_token,
            :refresh_token,
            :expiry
        )
        ON CONFLICT (org_id)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            token_expiry = EXCLUDED.token_expiry
        """),
        {
            "org_id": org_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expiry": expiry
        }
    )

    db.commit()

    return {"status": "gmail connected"}