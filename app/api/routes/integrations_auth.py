"""
Integrations Auth Routes
Handles OAuth connect/callback for all tools:
  Gmail, Google Calendar, Slack, Jira, Notion, Google Sheets, Google Drive, Google Docs

Also exposes unified status endpoint and disconnect endpoint.
"""

import json
import os
import secrets
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.database import SessionLocal
from app.redis_client import redis_client
from app.ingestion.gmail_connector import create_oauth_flow, build_gmail_service, get_user_email
from app.config import GOOGLE_REDIRECT_URI
from app.tasks.gmail_sync import run_gmail_sync

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
INTEGRATIONS_REDIRECT = f"{FRONTEND_URL}/dashboard/integrations"


# ─── Gmail OAuth ─────────────────────────────────────────────────────────────

@router.get("/auth/gmail/connect")
def gmail_connect(org_id: str):
    flow = create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    flow_data = {
        "org_id": org_id,
        "code_verifier": flow.code_verifier if hasattr(flow, "code_verifier") else None,
    }
    redis_client.setex(f"oauth_state:{state}", 180, json.dumps(flow_data))
    return RedirectResponse(authorization_url)


@router.get("/auth/gmail/callback")
async def gmail_callback(state: str, code: str, background_tasks: BackgroundTasks):
    flow_data_json = redis_client.get(f"oauth_state:{state}")
    if not flow_data_json:
        return {"error": "Invalid OAuth state or session expired. Please try connecting again."}

    flow_data_json = (
        flow_data_json.decode("utf-8")
        if isinstance(flow_data_json, bytes)
        else flow_data_json
    )
    flow_data = json.loads(flow_data_json)
    org_id = flow_data["org_id"]
    code_verifier = flow_data.get("code_verifier")

    redis_client.delete(f"oauth_state:{state}")

    flow = create_oauth_flow()
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    if code_verifier:
        flow.code_verifier = code_verifier

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flow.fetch_token(code=code)

    credentials = flow.credentials
    access_token = credentials.token
    refresh_token = credentials.refresh_token
    expiry = credentials.expiry

    gmail_service = build_gmail_service(access_token, refresh_token)
    connected_email = get_user_email(gmail_service)

    db = SessionLocal()
    db.execute(
        text("""
            INSERT INTO oauth_tokens (
                org_id, account_email, access_token, refresh_token,
                token_expiry, last_synced_at, sync_status
            ) VALUES (
                :org_id, :account_email, :access_token, :refresh_token,
                :expiry, :now, 'running'
            )
            ON CONFLICT (org_id, account_email)
            DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                token_expiry = EXCLUDED.token_expiry,
                last_synced_at = EXCLUDED.last_synced_at,
                sync_status = 'running'
        """),
        {
            "org_id": org_id,
            "account_email": connected_email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expiry": expiry,
            "now": datetime.utcnow(),
        },
    )
    db.commit()
    db.close()

    from app.config import SYNC_MAX_EMAILS
    background_tasks.add_task(run_gmail_sync, org_id, SYNC_MAX_EMAILS, connected_email)

    return RedirectResponse(url=f"{FRONTEND_URL}/dashboard")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _store_oauth_state(state: str, org_id: str, extra: dict = None):
    """Store org_id + optional extras in Redis under oauth_state:{state}, TTL 180s."""
    data = {"org_id": org_id}
    if extra:
        data.update(extra)
    redis_client.setex(f"oauth_state:{state}", 180, json.dumps(data))


def _pop_oauth_state(state: str):
    """Retrieve and delete OAuth state from Redis. Returns dict or None."""
    raw = redis_client.get(f"oauth_state:{state}")
    if not raw:
        return None
    redis_client.delete(f"oauth_state:{state}")
    return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)


# ─── Google Calendar ─────────────────────────────────────────────────────────

@router.get("/auth/gcal/connect")
def gcal_connect(org_id: str):
    from app.ingestion.calendar_connector import create_calendar_oauth_flow

    flow = create_calendar_oauth_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    _store_oauth_state(state, org_id, {"code_verifier": getattr(flow, "code_verifier", None)})
    return RedirectResponse(auth_url)


@router.get("/auth/calendar/callback")
async def gcal_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.ingestion.calendar_connector import create_calendar_oauth_flow, get_calendar_user_email, build_calendar_service
    import warnings

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired. Please try connecting again."}

    org_id = state_data["org_id"]

    flow = create_calendar_oauth_flow()
    from app.config import GOOGLE_CALENDAR_REDIRECT_URI
    flow.redirect_uri = GOOGLE_CALENDAR_REDIRECT_URI
    if state_data.get("code_verifier"):
        flow.code_verifier = state_data["code_verifier"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flow.fetch_token(code=code)

    creds = flow.credentials

    # Get connected email
    cal_service = build_calendar_service(creds.token, creds.refresh_token)
    connected_email = get_calendar_user_email(cal_service)

    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO calendar_sync_state (org_id, calendar_id)
                VALUES (:org_id, 'primary')
                ON CONFLICT (org_id, calendar_id) DO NOTHING
            """),
            {"org_id": org_id},
        )
        # Store tokens in oauth_tokens with tool identifier
        db.execute(
            text("""
                INSERT INTO oauth_tokens (org_id, account_email, access_token, refresh_token,
                    token_expiry, last_synced_at, sync_status)
                VALUES (:org_id, :email, :access_token, :refresh_token, :expiry, :now, 'idle')
                ON CONFLICT (org_id, account_email) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_expiry = EXCLUDED.token_expiry,
                    last_synced_at = EXCLUDED.last_synced_at,
                    sync_status = 'idle'
            """),
            {
                "org_id": org_id,
                "email": f"gcal:{connected_email}",
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expiry": creds.expiry,
                "now": datetime.utcnow(),
            },
        )
        db.commit()
    finally:
        db.close()

    from app.tasks.calendar_sync import run_calendar_sync
    background_tasks.add_task(run_calendar_sync, org_id)

    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


# ─── Slack ───────────────────────────────────────────────────────────────────

@router.get("/auth/slack/connect")
def slack_connect(org_id: str):
    from app.ingestion.slack_connector import get_slack_authorize_url

    state = secrets.token_urlsafe(32)
    _store_oauth_state(state, org_id)
    auth_url = get_slack_authorize_url(state)
    return RedirectResponse(auth_url)


@router.get("/auth/slack/callback")
async def slack_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.ingestion.slack_connector import exchange_code_for_tokens

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired."}

    org_id = state_data["org_id"]
    token_data = exchange_code_for_tokens(code)

    workspace_id = token_data.get("team", {}).get("id")
    workspace_name = token_data.get("team", {}).get("name")
    bot_token = token_data.get("access_token")
    authed_user = token_data.get("authed_user", {})
    authed_user_id = authed_user.get("id")
    authed_user_token = authed_user.get("access_token")

    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO slack_workspaces
                    (org_id, workspace_id, workspace_name, bot_token, user_token,
                     authed_user_id, backfill_status)
                VALUES (:org_id, :workspace_id, :workspace_name, :bot_token, :user_token,
                        :authed_user_id, 'pending')
                ON CONFLICT (org_id, workspace_id) DO UPDATE SET
                    workspace_name = EXCLUDED.workspace_name,
                    bot_token = EXCLUDED.bot_token,
                    user_token = EXCLUDED.user_token,
                    authed_user_id = EXCLUDED.authed_user_id,
                    updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "workspace_id": workspace_id,
                "workspace_name": workspace_name,
                "bot_token": bot_token,
                "user_token": authed_user_token,
                "authed_user_id": authed_user_id,
            },
        )
        db.commit()
    finally:
        db.close()

    from app.tasks.slack_sync import run_slack_backfill
    background_tasks.add_task(run_slack_backfill, org_id)

    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


@router.post("/webhooks/slack/events")
async def slack_events_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    CRITICAL: Two-phase webhook handler.
    Phase 1: Validate signature → push to queue → return 200 in <200ms
    Phase 2: Process event asynchronously (background task)
    """
    from app.ingestion.slack_connector import validate_event_signature
    from app.config import SLACK_SIGNING_SECRET

    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if SLACK_SIGNING_SECRET and not validate_event_signature(body, timestamp, signature, SLACK_SIGNING_SECRET):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(body)

    # Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    # Enqueue for async processing — never block
    from app.tasks.slack_sync import process_slack_event_async
    background_tasks.add_task(process_slack_event_async, payload)

    return {"ok": True}


# ─── Jira ────────────────────────────────────────────────────────────────────

@router.get("/auth/jira/connect")
def jira_connect(org_id: str):
    from app.ingestion.jira_connector import get_jira_authorize_url
    from app.config import JIRA_CLIENT_ID, JIRA_REDIRECT_URI

    state = secrets.token_urlsafe(32)
    auth_url, code_verifier = get_jira_authorize_url(state, JIRA_REDIRECT_URI, JIRA_CLIENT_ID)
    _store_oauth_state(state, org_id, {"code_verifier": code_verifier})
    return RedirectResponse(auth_url)


@router.get("/auth/jira/callback")
async def jira_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.ingestion.jira_connector import exchange_code_for_tokens, get_accessible_resources
    from app.config import JIRA_CLIENT_ID, JIRA_CLIENT_SECRET, JIRA_REDIRECT_URI

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired."}

    org_id = state_data["org_id"]
    code_verifier = state_data.get("code_verifier")

    token_data = exchange_code_for_tokens(code, code_verifier, JIRA_REDIRECT_URI, JIRA_CLIENT_ID, JIRA_CLIENT_SECRET)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")

    # Get accessible cloud resources
    resources = get_accessible_resources(access_token)
    if not resources:
        return RedirectResponse(url=f"{INTEGRATIONS_REDIRECT}?error=no_jira_sites")

    # Use the first accessible site
    cloud_resource = resources[0]
    cloud_id = cloud_resource["id"]
    site_url = cloud_resource.get("url", "")

    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))

    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO jira_connections
                    (org_id, atlassian_cloud_id, site_url, access_token, refresh_token,
                     token_expires_at, backfill_status)
                VALUES (:org_id, :cloud_id, :site_url, :access_token, :refresh_token,
                        :expires_at, 'pending')
                ON CONFLICT (org_id, atlassian_cloud_id) DO UPDATE SET
                    site_url = EXCLUDED.site_url,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "cloud_id": cloud_id,
                "site_url": site_url,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
            },
        )
        db.commit()
    finally:
        db.close()

    from app.tasks.jira_sync import run_jira_sync
    background_tasks.add_task(run_jira_sync, org_id)

    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


@router.post("/webhooks/jira/events")
async def jira_events_webhook(request: Request, background_tasks: BackgroundTasks):
    """Jira webhook receiver — validate then process async."""
    payload = await request.json()
    from app.tasks.jira_sync import process_jira_event_async
    background_tasks.add_task(process_jira_event_async, payload)
    return {"ok": True}


# ─── Notion ──────────────────────────────────────────────────────────────────

@router.get("/auth/notion/connect")
def notion_connect(org_id: str):
    from app.ingestion.notion_connector import get_notion_authorize_url
    from app.config import NOTION_CLIENT_ID, NOTION_REDIRECT_URI

    state = secrets.token_urlsafe(32)
    _store_oauth_state(state, org_id)
    auth_url = get_notion_authorize_url(NOTION_CLIENT_ID, NOTION_REDIRECT_URI, state)
    return RedirectResponse(auth_url)


@router.get("/auth/notion/callback")
async def notion_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.ingestion.notion_connector import exchange_code_for_token
    from app.config import NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, NOTION_REDIRECT_URI

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired."}

    org_id = state_data["org_id"]
    token_data = exchange_code_for_token(code, NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, NOTION_REDIRECT_URI)

    workspace_id = token_data.get("workspace_id")
    workspace_name = token_data.get("workspace_name")
    access_token = token_data.get("access_token")
    bot_id = token_data.get("bot_id")

    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO notion_connections
                    (org_id, workspace_id, workspace_name, access_token, bot_id, backfill_status)
                VALUES (:org_id, :workspace_id, :workspace_name, :access_token, :bot_id, 'pending')
                ON CONFLICT (org_id, workspace_id) DO UPDATE SET
                    workspace_name = EXCLUDED.workspace_name,
                    access_token = EXCLUDED.access_token,
                    bot_id = EXCLUDED.bot_id,
                    updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "workspace_id": workspace_id,
                "workspace_name": workspace_name,
                "access_token": access_token,
                "bot_id": bot_id,
            },
        )
        db.commit()
    finally:
        db.close()

    from app.tasks.notion_sync import run_notion_sync
    background_tasks.add_task(run_notion_sync, org_id)

    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


# ─── Google Sheets ───────────────────────────────────────────────────────────

@router.get("/auth/gsheets/connect")
def gsheets_connect(org_id: str):
    from app.ingestion.sheets_connector import create_sheets_oauth_flow

    flow = create_sheets_oauth_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    _store_oauth_state(state, org_id, {"code_verifier": getattr(flow, "code_verifier", None)})
    return RedirectResponse(auth_url)


@router.get("/auth/gsheets/callback")
async def gsheets_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.ingestion.sheets_connector import create_sheets_oauth_flow, build_drive_service, get_sheets_user_email
    import warnings, os

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired."}

    org_id = state_data["org_id"]
    flow = create_sheets_oauth_flow()
    flow.redirect_uri = os.getenv("GOOGLE_SHEETS_REDIRECT_URI", "http://localhost:8000/auth/gsheets/callback")
    if state_data.get("code_verifier"):
        flow.code_verifier = state_data["code_verifier"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flow.fetch_token(code=code)

    creds = flow.credentials
    drive_service = build_drive_service(creds.token, creds.refresh_token)
    connected_email = get_sheets_user_email(drive_service)

    from datetime import timedelta
    expires_at = creds.expiry

    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO sheets_connections
                    (org_id, access_token, refresh_token, token_expires_at, last_sync_at)
                VALUES (:org_id, :access_token, :refresh_token, :expires_at, :now)
                ON CONFLICT (org_id) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    last_sync_at = EXCLUDED.last_sync_at,
                    updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expires_at": expires_at,
                "now": datetime.utcnow(),
            },
        )
        db.commit()
    finally:
        db.close()

    from app.tasks.sheets_sync import run_sheets_sync
    background_tasks.add_task(run_sheets_sync, org_id)

    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


# ─── Google Drive ─────────────────────────────────────────────────────────────

@router.get("/auth/gdrive/connect")
def gdrive_connect(org_id: str):
    from app.ingestion.drive_connector import create_drive_oauth_flow

    flow = create_drive_oauth_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    _store_oauth_state(state, org_id, {"code_verifier": getattr(flow, "code_verifier", None)})
    return RedirectResponse(auth_url)


@router.get("/auth/drive/callback")
async def gdrive_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.ingestion.drive_connector import create_drive_oauth_flow, build_drive_service, get_drive_user_email, get_start_page_token
    import warnings

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired."}

    org_id = state_data["org_id"]
    flow = create_drive_oauth_flow()
    from app.config import GOOGLE_DRIVE_REDIRECT_URI
    flow.redirect_uri = GOOGLE_DRIVE_REDIRECT_URI
    if state_data.get("code_verifier"):
        flow.code_verifier = state_data["code_verifier"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flow.fetch_token(code=code)

    creds = flow.credentials
    drive_service = build_drive_service(creds.token, creds.refresh_token)
    connected_email = get_drive_user_email(drive_service)

    # Initialize the changes page token immediately
    start_page_token = get_start_page_token(drive_service)
    expires_at = creds.expiry

    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO gdrive_connections
                    (org_id, access_token, refresh_token, token_expires_at,
                     changes_page_token, last_full_metadata_sync_at)
                VALUES (:org_id, :access_token, :refresh_token, :expires_at,
                        :page_token, :now)
                ON CONFLICT (org_id) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    changes_page_token = EXCLUDED.changes_page_token,
                    last_full_metadata_sync_at = EXCLUDED.last_full_metadata_sync_at,
                    updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expires_at": expires_at,
                "page_token": start_page_token,
                "now": datetime.utcnow(),
            },
        )
        db.commit()
    finally:
        db.close()

    from app.tasks.drive_sync import run_drive_sync
    background_tasks.add_task(run_drive_sync, org_id)

    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


@router.post("/webhooks/gdrive/changes")
async def gdrive_changes_webhook(request: Request, background_tasks: BackgroundTasks):
    """Drive push notification receiver."""
    from app.tasks.drive_sync import process_drive_webhook_async
    headers = dict(request.headers)
    background_tasks.add_task(process_drive_webhook_async, headers)
    return {}


# ─── Google Docs ─────────────────────────────────────────────────────────────

@router.get("/auth/gdocs/connect")
def gdocs_connect(org_id: str):
    from app.ingestion.docs_connector import create_docs_oauth_flow

    flow = create_docs_oauth_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    _store_oauth_state(state, org_id, {"code_verifier": getattr(flow, "code_verifier", None)})
    return RedirectResponse(auth_url)


@router.get("/auth/gdocs/callback")
async def gdocs_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.ingestion.docs_connector import create_docs_oauth_flow, build_drive_service, get_docs_user_email
    import warnings, os

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired."}

    org_id = state_data["org_id"]
    flow = create_docs_oauth_flow()
    flow.redirect_uri = os.getenv("GOOGLE_DOCS_REDIRECT_URI", "http://localhost:8000/auth/gdocs/callback")
    if state_data.get("code_verifier"):
        flow.code_verifier = state_data["code_verifier"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flow.fetch_token(code=code)

    creds = flow.credentials
    drive_service = build_drive_service(creds.token, creds.refresh_token)
    connected_email = get_docs_user_email(drive_service)
    expires_at = creds.expiry

    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO gdocs_connections
                    (org_id, access_token, refresh_token, token_expires_at, backfill_status)
                VALUES (:org_id, :access_token, :refresh_token, :expires_at, 'pending')
                ON CONFLICT (org_id) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expires_at": expires_at,
            },
        )
        db.commit()
    finally:
        db.close()

    from app.tasks.docs_sync import run_docs_sync
    background_tasks.add_task(run_docs_sync, org_id)

    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


# ─── Unified Integrations Status ─────────────────────────────────────────────

@router.get("/api/org/{org_id}/integrations/status")
def get_integrations_status(org_id: str):
    """
    Returns real-time connection status for all tools.
    Frontend polls this every 30s to drive the dynamic integrations page.
    """
    db = SessionLocal()
    try:
        status = {}

        # Gmail — from oauth_tokens where email doesn't start with tool: prefix
        gmail_rows = db.execute(
            text("""
                SELECT account_email, last_synced_at, sync_status
                FROM oauth_tokens
                WHERE org_id = :oid
                AND account_email NOT LIKE '%:%'
            """),
            {"oid": org_id},
        ).fetchall()
        if gmail_rows:
            status["gmail"] = {
                "connected": True,
                "syncStatus": gmail_rows[0].sync_status or "idle",
                "lastSyncAt": gmail_rows[0].last_synced_at.isoformat() if gmail_rows[0].last_synced_at else None,
                "metadata": {"accounts": [r.account_email for r in gmail_rows]},
            }
        else:
            status["gmail"] = {"connected": False}

        # Google Calendar — from calendar_sync_state + event/attendee counts
        gcal_row = db.execute(
            text("""
                SELECT last_full_sync_at, last_sync_events_added,
                       last_sync_events_filtered, total_events_synced
                FROM calendar_sync_state WHERE org_id = :oid LIMIT 1
            """),
            {"oid": org_id},
        ).fetchone()
        if gcal_row:
            gcal_counts = db.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE NOT is_cancelled) AS active_events,
                        COUNT(*) FILTER (WHERE NOT is_cancelled AND start_time > NOW()) AS upcoming_events
                    FROM calendar_events WHERE org_id = :oid
                """),
                {"oid": org_id},
            ).fetchone()
            gcal_attendees = db.execute(
                text("""
                    SELECT COUNT(DISTINCT cea.email) AS unique_attendees
                    FROM calendar_event_attendees cea
                    JOIN calendar_events ce ON ce.id = cea.event_id
                    WHERE ce.org_id = :oid AND cea.is_external = TRUE
                """),
                {"oid": org_id},
            ).scalar() or 0
            status["gcal"] = {
                "connected": True,
                "syncStatus": "idle",
                "lastSyncAt": gcal_row.last_full_sync_at.isoformat() if gcal_row.last_full_sync_at else None,
                "metadata": {
                    "eventsTotal": gcal_counts.active_events or 0,
                    "upcomingEvents": gcal_counts.upcoming_events or 0,
                    "uniqueAttendees": gcal_attendees,
                    "lastSyncAdded": gcal_row.last_sync_events_added or 0,
                    "lastSyncFiltered": gcal_row.last_sync_events_filtered or 0,
                    "totalSynced": gcal_row.total_events_synced or 0,
                },
            }
        else:
            status["gcal"] = {"connected": False}

        # Slack — from slack_workspaces
        slack_row = db.execute(
            text("SELECT workspace_name, last_event_at, backfill_status FROM slack_workspaces WHERE org_id = :oid LIMIT 1"),
            {"oid": org_id},
        ).fetchone()
        if slack_row:
            status["slack"] = {
                "connected": True,
                "syncStatus": "syncing" if slack_row.backfill_status == "running" else "idle",
                "lastSyncAt": slack_row.last_event_at.isoformat() if slack_row.last_event_at else None,
                "metadata": {"workspaceName": slack_row.workspace_name},
            }
        else:
            status["slack"] = {"connected": False}

        # Jira — from jira_connections
        jira_row = db.execute(
            text("SELECT site_url, backfill_status FROM jira_connections WHERE org_id = :oid LIMIT 1"),
            {"oid": org_id},
        ).fetchone()
        if jira_row:
            status["jira"] = {
                "connected": True,
                "syncStatus": "syncing" if jira_row.backfill_status == "running" else "idle",
                "metadata": {"siteUrl": jira_row.site_url},
            }
        else:
            status["jira"] = {"connected": False}

        # Notion — from notion_connections
        notion_row = db.execute(
            text("SELECT workspace_name, last_full_sync_at, backfill_status FROM notion_connections WHERE org_id = :oid LIMIT 1"),
            {"oid": org_id},
        ).fetchone()
        if notion_row:
            status["notion"] = {
                "connected": True,
                "syncStatus": "syncing" if notion_row.backfill_status == "running" else "idle",
                "lastSyncAt": notion_row.last_full_sync_at.isoformat() if notion_row.last_full_sync_at else None,
                "metadata": {"workspaceName": notion_row.workspace_name},
            }
        else:
            status["notion"] = {"connected": False}

        # Google Sheets — from sheets_connections
        sheets_row = db.execute(
            text("SELECT last_sync_at FROM sheets_connections WHERE org_id = :oid LIMIT 1"),
            {"oid": org_id},
        ).fetchone()
        if sheets_row:
            status["gsheets"] = {
                "connected": True,
                "syncStatus": "idle",
                "lastSyncAt": sheets_row.last_sync_at.isoformat() if sheets_row.last_sync_at else None,
            }
        else:
            status["gsheets"] = {"connected": False}

        # Google Drive — from gdrive_connections
        drive_row = db.execute(
            text("SELECT last_changes_sync_at FROM gdrive_connections WHERE org_id = :oid LIMIT 1"),
            {"oid": org_id},
        ).fetchone()
        if drive_row:
            status["gdrive"] = {
                "connected": True,
                "syncStatus": "idle",
                "lastSyncAt": drive_row.last_changes_sync_at.isoformat() if drive_row.last_changes_sync_at else None,
            }
        else:
            status["gdrive"] = {"connected": False}

        # Google Docs — from gdocs_connections
        docs_row = db.execute(
            text("SELECT last_full_sync_at, backfill_status FROM gdocs_connections WHERE org_id = :oid LIMIT 1"),
            {"oid": org_id},
        ).fetchone()
        if docs_row:
            status["gdocs"] = {
                "connected": True,
                "syncStatus": "syncing" if docs_row.backfill_status == "running" else "idle",
                "lastSyncAt": docs_row.last_full_sync_at.isoformat() if docs_row.last_full_sync_at else None,
            }
        else:
            status["gdocs"] = {"connected": False}

        return status

    finally:
        db.close()


# ─── Disconnect ───────────────────────────────────────────────────────────────
# Two modes:
#   wipe_data=False  → remove only the OAuth connection / sync state (keep data)
#   wipe_data=True   → also delete all synced data tables (fresh-start next time)

# Connection-only deletes (token / connection record, no data tables)
TOOL_CONNECTION_SQL: dict[str, list[str]] = {
    "gmail":   ["DELETE FROM oauth_tokens WHERE org_id = :oid AND account_email NOT LIKE '%:%'"],
    "gcal":    [
        "DELETE FROM oauth_tokens WHERE org_id = :oid AND account_email LIKE 'gcal:%'",
        "DELETE FROM calendar_sync_state WHERE org_id = :oid",
    ],
    "slack":   ["DELETE FROM slack_workspaces WHERE org_id = :oid"],
    "jira":    ["DELETE FROM jira_connections WHERE org_id = :oid"],
    "notion":  ["DELETE FROM notion_connections WHERE org_id = :oid"],
    "gsheets": ["DELETE FROM sheets_connections WHERE org_id = :oid"],
    "gdrive":  ["DELETE FROM gdrive_connections WHERE org_id = :oid"],
    "gdocs":   ["DELETE FROM gdocs_connections WHERE org_id = :oid"],
}

# Full wipe — deletes connection AND all synced data for a fresh start
TOOL_CLEANUP_SQL: dict[str, list[str]] = {
    "gmail": [
        # Tokens only — email interactions stay (they represent real relationships)
        "DELETE FROM oauth_tokens WHERE org_id = :oid AND account_email NOT LIKE '%:%'",
    ],
    "gcal": [
        "DELETE FROM oauth_tokens WHERE org_id = :oid AND account_email LIKE 'gcal:%'",
        "DELETE FROM upcoming_meetings WHERE org_id = :oid",
        # calendar_event_attendees cascades from calendar_events
        "DELETE FROM calendar_events WHERE org_id = :oid",
        "DELETE FROM calendar_sync_state WHERE org_id = :oid",
    ],
    "slack": [
        "DELETE FROM slack_messages WHERE org_id = :oid",
        "DELETE FROM slack_user_cache WHERE org_id = :oid",
        "DELETE FROM slack_channel_config WHERE org_id = :oid",
        "DELETE FROM slack_workspaces WHERE org_id = :oid",
    ],
    "jira": [
        "DELETE FROM jira_issues WHERE org_id = :oid",
        "DELETE FROM jira_user_cache WHERE org_id = :oid",
        "DELETE FROM jira_project_config WHERE org_id = :oid",
        "DELETE FROM jira_connections WHERE org_id = :oid",
    ],
    "notion": [
        "DELETE FROM notion_pages WHERE org_id = :oid",
        "DELETE FROM notion_connections WHERE org_id = :oid",
    ],
    "gsheets": [
        "DELETE FROM sheets_tab_config WHERE org_id = :oid",
        "DELETE FROM sheets_spreadsheets WHERE org_id = :oid",
        "DELETE FROM sheets_connections WHERE org_id = :oid",
    ],
    "gdrive": [
        "DELETE FROM gdrive_files WHERE org_id = :oid",
        "DELETE FROM gdrive_shared_drive_members WHERE org_id = :oid",
        "DELETE FROM gdrive_shared_drives WHERE org_id = :oid",
        "DELETE FROM gdrive_connections WHERE org_id = :oid",
    ],
    "gdocs": [
        "DELETE FROM gdocs_documents WHERE org_id = :oid",
        "DELETE FROM gdocs_connections WHERE org_id = :oid",
    ],
}


@router.delete("/api/org/{org_id}/integrations/{tool}/disconnect")
def disconnect_tool(
    org_id: str,
    tool: str,
    wipe_data: bool = Query(False, description="Also delete all synced data for a fresh start"),
):
    """
    Disconnect a tool.
    - wipe_data=false (default): removes only the OAuth tokens / connection record.
      All synced data stays in the database.
    - wipe_data=true: removes the connection AND all synced data tables.
      Next OAuth connect starts a completely fresh sync.
    """
    if tool not in TOOL_CONNECTION_SQL:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool}")

    statements = TOOL_CLEANUP_SQL[tool] if wipe_data else TOOL_CONNECTION_SQL[tool]

    db = SessionLocal()
    try:
        for sql in statements:
            db.execute(text(sql), {"oid": org_id})
        db.commit()
        return {"disconnected": True, "tool": tool, "data_wiped": wipe_data}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ─── Manual Sync Trigger ─────────────────────────────────────────────────────

TOOL_SYNC_TASKS = {
    "gcal": "app.tasks.calendar_sync.run_calendar_sync",
    "slack": "app.tasks.slack_sync.run_slack_backfill",
    "jira": "app.tasks.jira_sync.run_jira_sync",
    "notion": "app.tasks.notion_sync.run_notion_sync",
    "gsheets": "app.tasks.sheets_sync.run_sheets_sync",
    "gdrive": "app.tasks.drive_sync.run_drive_sync",
    "gdocs": "app.tasks.docs_sync.run_docs_sync",
}


@router.post("/api/org/{org_id}/integrations/{tool}/sync")
async def trigger_tool_sync(org_id: str, tool: str, background_tasks: BackgroundTasks):
    """Manually trigger a sync for a connected tool."""
    if tool not in TOOL_SYNC_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool}")

    import importlib
    module_path, func_name = TOOL_SYNC_TASKS[tool].rsplit(".", 1)
    module = importlib.import_module(module_path)
    sync_func = getattr(module, func_name)

    background_tasks.add_task(sync_func, org_id)
    return {"started": True, "tool": tool}
