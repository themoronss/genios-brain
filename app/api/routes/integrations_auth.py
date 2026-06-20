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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import GOOGLE_REDIRECT_URI
from app.database import SessionLocal
from app.ingestion.gmail_connector import build_gmail_service, create_oauth_flow, get_user_email
from app.plan_enforcer import require_integration
from app.redis_client import redis_client

# run_gmail_sync (v1 heavy ingestion) removed — Gmail sync now flows through
# core.memory.sync_runner per g-i-1 plan. v1 ingestion code in app/ingestion/
# becomes orphaned after all sources migrated (cleanup sweep follows).

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

    from app.core.analytics import capture
    capture(org_id, "integration_connected", {"tool": "gmail"})

    # Per g-i-1 plan: memory is a thin pipe — Connection + encrypted SecretRefs
    # via core/memory/, sync via core.memory.sync_runner, fan-out via emit().
    # The v1 heavy ingestion path (gmail_connector → email_parser → classifier
    # → graph_builder + writes to interactions/contacts/event_log) is GONE.
    from core.memory.adapters.known.gmail import register_v2_gmail_connection
    v2_connection_id = register_v2_gmail_connection(
        org_id=org_id,
        account_email=connected_email,
        access_token=access_token,
        refresh_token=refresh_token,
        created_by=org_id,
    )

    from core.foundations.db import get_session as _v2_session
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_gmail() -> None:
        try:
            # Per-plan initial-sync limit. Trial orgs no longer get a
            # 50-record blast that consumes most of their starter pool
            # on day-one connect; tiered via env (see app/config.py).
            #
            # get_org_plan(db, org_id) takes the v1 DB session, not just
            # the org_id — earlier draft of this block had the wrong
            # signature and 500'd the post-OAuth background task. We open
            # a short v1 session just for the plan lookup, then close it
            # so it doesn't outlive the limit calc.
            from app.config import initial_sync_limit_for_plan
            from app.database import SessionLocal as _v1_session
            from app.plan_enforcer import get_org_plan
            _plan = None
            _pdb = _v1_session()
            try:
                _plan = (get_org_plan(_pdb, org_id) or {}).get("tier")
            except Exception as _pe:
                import logging
                logging.getLogger(__name__).warning(
                    f"plan lookup failed (defaulting to trial limit): {_pe}"
                )
            finally:
                _pdb.close()
            _limit = initial_sync_limit_for_plan(_plan)
            with _v2_session() as s:
                result = run_sync_for_connection(s, connection_id=v2_connection_id, limit=_limit)
                import logging
                logging.getLogger(__name__).info(
                    f"gmail sync done: plan={_plan} limit={_limit} "
                    f"emitted={result.items_emitted} "
                    f"dropped_scope={result.items_dropped_scope} "
                    f"dropped_noise={result.items_dropped_noise}"
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"gmail sync failed: {e}")

    background_tasks.add_task(_sync_gmail)

    # Startup plan: subscribe to Gmail push notifications (per-message delta).
    # Push notifications still rely on v1's watch + webhook handler for now —
    # next sweep moves that to a v2 webhook adapter wired via emit().
    from app.plan_enforcer import get_org_plan
    plan_db = SessionLocal()
    try:
        plan_info = get_org_plan(plan_db, org_id)
        if plan_info["tier"] == "startup":
            background_tasks.add_task(_setup_gmail_watch, org_id, connected_email, access_token, refresh_token)
    finally:
        plan_db.close()

    return RedirectResponse(url=f"{FRONTEND_URL}/dashboard")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _setup_gmail_watch(org_id: str, email: str, access_token: str, refresh_token: str):
    """
    Subscribe the connected Gmail account to push notifications via Gmail watch API.
    Called as a background task after OAuth connect for Startup plan orgs.
    Requires GMAIL_PUBSUB_TOPIC env var (e.g. projects/my-project/topics/genios-gmail).
    """
    import logging
    logger = logging.getLogger(__name__)

    topic = os.getenv("GMAIL_PUBSUB_TOPIC")
    if not topic:
        logger.warning(f"Gmail watch skipped for org {org_id}: GMAIL_PUBSUB_TOPIC not set")
        return

    try:
        gmail_service = build_gmail_service(access_token, refresh_token)
        watch_request = {"labelIds": ["INBOX"], "topicName": topic}
        result = gmail_service.users().watch(userId="me", body=watch_request).execute()
        logger.info(f"Gmail watch established for org {org_id} ({email}): historyId={result.get('historyId')}")
    except Exception as e:
        logger.error(f"Gmail watch setup failed for org {org_id} ({email}): {e}")


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
def gcal_connect(org_id: str, db: Session = Depends(get_db)):
    require_integration(db, org_id, "calendar")
    from app.ingestion.calendar_connector import create_calendar_oauth_flow

    flow = create_calendar_oauth_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    _store_oauth_state(state, org_id, {"code_verifier": getattr(flow, "code_verifier", None)})
    return RedirectResponse(auth_url)


@router.get("/auth/calendar/callback")
async def gcal_callback(state: str, code: str, background_tasks: BackgroundTasks):
    import warnings

    from app.ingestion.calendar_connector import (
        build_calendar_service,
        create_calendar_oauth_flow,
        get_calendar_user_email,
    )

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

    from app.core.analytics import capture
    capture(org_id, "integration_connected", {"tool": "gcal"})

    # Per g-i-1 plan: thin pipe via core.memory.adapters.known.calendar.
    from core.memory.adapters.known.calendar import register_v2_calendar_connection
    v2_cid = register_v2_calendar_connection(
        org_id=org_id,
        account_email=connected_email,
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        created_by=org_id,
    )

    from core.foundations.db import get_session as _v2s
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_cal() -> None:
        import logging
        try:
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=v2_cid, limit=50)
                logging.getLogger(__name__).info(
                    f"calendar sync done: emitted={r.items_emitted} dropped={r.items_dropped_scope}"
                )
        except Exception as e:
            logging.getLogger(__name__).exception(f"calendar sync failed: {e}")

    background_tasks.add_task(_sync_cal)
    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


# ─── Slack ───────────────────────────────────────────────────────────────────

@router.get("/auth/slack/connect")
def slack_connect(org_id: str, db: Session = Depends(get_db)):
    require_integration(db, org_id, "slack")
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

    from app.core.analytics import capture
    capture(org_id, "integration_connected", {"tool": "slack"})

    # Per g-i-1 plan: thin pipe via core.memory.adapters.known.slack.
    from core.memory.adapters.known.slack import register_v2_slack_connection
    v2_cid = register_v2_slack_connection(
        org_id=org_id,
        workspace_id=workspace_id or "default",
        access_token=bot_token or authed_user_token or "",
        created_by=org_id,
    )

    from core.foundations.db import get_session as _v2s
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_slack() -> None:
        import logging
        try:
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=v2_cid, limit=50)
                logging.getLogger(__name__).info(
                    f"slack sync done: emitted={r.items_emitted} dropped={r.items_dropped_scope}"
                )
        except Exception as e:
            logging.getLogger(__name__).exception(f"slack sync failed: {e}")

    background_tasks.add_task(_sync_slack)
    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


@router.post("/webhooks/slack/events")
async def slack_events_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    CRITICAL: Two-phase webhook handler.
    Phase 1: Validate signature → push to queue → return 200 in <200ms
    Phase 2: Process event asynchronously (background task)
    """
    from app.config import SLACK_SIGNING_SECRET
    from app.ingestion.slack_connector import validate_event_signature

    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if SLACK_SIGNING_SECRET and not validate_event_signature(body, timestamp, signature, SLACK_SIGNING_SECRET):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(body)

    # Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    # Per g-i-1 plan: webhook → run v2 sync_runner for this workspace's Slack
    # connection. Skips the deleted v1 process_slack_event_async path.
    team_id = (payload.get("team_id") or "").strip()
    if team_id:
        def _run_slack_sync():
            try:
                from sqlalchemy import select as _sel

                from core.foundations.db import get_session as _v2s
                from core.memory.store import Connection
                from core.memory.sync_runner import run_sync_for_connection

                with _v2s() as _s:
                    conn = _s.execute(
                        _sel(Connection)
                        .where(Connection.source_type == "slack")
                        .where(Connection.source_id == team_id)
                        .where(Connection.status == "active")
                        .limit(1)
                    ).scalar_one_or_none()
                    if conn is not None:
                        run_sync_for_connection(_s, connection_id=conn.id, limit=50)
            except Exception as e:
                logger.warning(f"slack webhook v2 sync failed: {e}")
        background_tasks.add_task(_run_slack_sync)

    return {"ok": True}


# ─── Jira ────────────────────────────────────────────────────────────────────

@router.get("/auth/jira/connect")
def jira_connect(org_id: str):
    from app.config import JIRA_CLIENT_ID, JIRA_REDIRECT_URI
    from app.ingestion.jira_connector import get_jira_authorize_url

    state = secrets.token_urlsafe(32)
    auth_url, code_verifier = get_jira_authorize_url(state, JIRA_REDIRECT_URI, JIRA_CLIENT_ID)
    _store_oauth_state(state, org_id, {"code_verifier": code_verifier})
    return RedirectResponse(auth_url)


@router.get("/auth/jira/callback")
async def jira_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.config import JIRA_CLIENT_ID, JIRA_CLIENT_SECRET, JIRA_REDIRECT_URI
    from app.ingestion.jira_connector import exchange_code_for_tokens, get_accessible_resources

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

    from app.core.analytics import capture
    capture(org_id, "integration_connected", {"tool": "jira"})

    from core.memory.adapters.known.jira import register_v2_jira_connection
    v2_cid = register_v2_jira_connection(
        org_id=org_id, cloud_id=cloud_id, access_token=access_token,
        refresh_token=refresh_token, created_by=org_id,
    )
    from core.foundations.db import get_session as _v2s
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_jira() -> None:
        import logging
        try:
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=v2_cid, limit=50)
                logging.getLogger(__name__).info(f"jira sync done: emitted={r.items_emitted}")
        except Exception as e:
            logging.getLogger(__name__).exception(f"jira sync failed: {e}")

    background_tasks.add_task(_sync_jira)
    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


@router.post("/webhooks/jira/events")
async def jira_events_webhook(request: Request, background_tasks: BackgroundTasks):
    """Jira webhook receiver — fan out to v2 sync_runner for the cloud_id's
    Jira connection (replaces deleted v1 process_jira_event_async path)."""
    payload = await request.json()
    cloud_id = (
        payload.get("cloud_id")
        or payload.get("cloudId")
        or (payload.get("matchedWebhookIds") and payload.get("matchedWebhookIds")[0])
        or ""
    )
    if cloud_id:
        def _run_jira_sync():
            try:
                from sqlalchemy import select as _sel

                from core.foundations.db import get_session as _v2s
                from core.memory.store import Connection
                from core.memory.sync_runner import run_sync_for_connection

                with _v2s() as _s:
                    conn = _s.execute(
                        _sel(Connection)
                        .where(Connection.source_type == "jira")
                        .where(Connection.source_id == cloud_id)
                        .where(Connection.status == "active")
                        .limit(1)
                    ).scalar_one_or_none()
                    if conn is not None:
                        run_sync_for_connection(_s, connection_id=conn.id, limit=50)
            except Exception as e:
                logger.warning(f"jira webhook v2 sync failed: {e}")
        background_tasks.add_task(_run_jira_sync)
    return {"ok": True}


# ─── Notion ──────────────────────────────────────────────────────────────────

@router.get("/auth/notion/connect")
def notion_connect(org_id: str):
    from app.config import NOTION_CLIENT_ID, NOTION_REDIRECT_URI
    from app.ingestion.notion_connector import get_notion_authorize_url

    state = secrets.token_urlsafe(32)
    _store_oauth_state(state, org_id)
    auth_url = get_notion_authorize_url(NOTION_CLIENT_ID, NOTION_REDIRECT_URI, state)
    return RedirectResponse(auth_url)


@router.get("/auth/notion/callback")
async def notion_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.config import NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, NOTION_REDIRECT_URI
    from app.ingestion.notion_connector import exchange_code_for_token

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired."}

    org_id = state_data["org_id"]
    token_data = exchange_code_for_token(code, NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, NOTION_REDIRECT_URI)

    workspace_id = token_data.get("workspace_id")
    workspace_name = token_data.get("workspace_name")
    access_token = token_data.get("access_token")
    bot_id = token_data.get("bot_id")

    # Token storage + sync handled by v2 register_v2_notion_connection below
    # (SecretRef + Connection). Legacy notion_connections table dropped in 0015.
    from app.core.analytics import capture
    capture(org_id, "integration_connected", {"tool": "notion"})

    # Per g-i-1 plan: thin pipe via core.memory.adapters.known.notion.
    from core.memory.adapters.known.notion import register_v2_notion_connection
    v2_cid = register_v2_notion_connection(
        org_id=org_id,
        workspace_id=workspace_id or "default",
        access_token=access_token or "",
        created_by=org_id,
    )

    from core.foundations.db import get_session as _v2s
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_notion() -> None:
        import logging
        try:
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=v2_cid, limit=50)
                logging.getLogger(__name__).info(
                    f"notion sync done: emitted={r.items_emitted} dropped={r.items_dropped_scope}"
                )
        except Exception as e:
            logging.getLogger(__name__).exception(f"notion sync failed: {e}")

    background_tasks.add_task(_sync_notion)
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
    import os
    import warnings

    from app.ingestion.sheets_connector import (
        build_drive_service,
        create_sheets_oauth_flow,
        get_sheets_user_email,
    )

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

    # Token storage + sync handled by v2 register_v2_gsheets_connection below
    # (SecretRef + Connection). Legacy sheets_connections table dropped in 0015.
    from app.core.analytics import capture
    capture(org_id, "integration_connected", {"tool": "gsheets"})

    from core.memory.adapters.known.gsheets import register_v2_gsheets_connection
    v2_cid = register_v2_gsheets_connection(
        org_id=org_id, account_email=connected_email, access_token=creds.token,
        refresh_token=creds.refresh_token, created_by=org_id,
    )
    from core.foundations.db import get_session as _v2s
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_sh() -> None:
        import logging
        try:
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=v2_cid, limit=20)
                logging.getLogger(__name__).info(f"gsheets sync done: emitted={r.items_emitted}")
        except Exception as e:
            logging.getLogger(__name__).exception(f"gsheets sync failed: {e}")

    background_tasks.add_task(_sync_sh)
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
    import warnings

    from app.ingestion.drive_connector import (
        build_drive_service,
        create_drive_oauth_flow,
        get_drive_user_email,
        get_start_page_token,
    )

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

    # Token storage + delta cursor + sync are handled by the v2
    # register_v2_drive_connection below (SecretRef + Connection + CursorRow).
    # The legacy gdrive_connections table was dropped in migration 0015; its
    # plaintext-token INSERT was removed.
    from app.core.analytics import capture
    capture(org_id, "integration_connected", {"tool": "gdrive"})

    from core.memory.adapters.known.drive import register_v2_drive_connection
    v2_cid = register_v2_drive_connection(
        org_id=org_id, account_email=connected_email, access_token=creds.token,
        refresh_token=creds.refresh_token, created_by=org_id,
    )
    from core.foundations.db import get_session as _v2s
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_drv() -> None:
        import logging
        try:
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=v2_cid, limit=50)
                logging.getLogger(__name__).info(f"drive sync done: emitted={r.items_emitted}")
        except Exception as e:
            logging.getLogger(__name__).exception(f"drive sync failed: {e}")

    background_tasks.add_task(_sync_drv)
    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


@router.post("/webhooks/gdrive/changes")
async def gdrive_changes_webhook(request: Request, background_tasks: BackgroundTasks):
    """Drive push receiver — per g-i-1 plan, triggers v2 sync_runner against
    the Drive connection for the org identified by the X-Goog-Channel-Token.

    Token format encodes the connection_id at watch-registration time.
    Headers also include resource state (sync|add|update|remove|trash).
    """
    headers = dict(request.headers)
    channel_token = headers.get("x-goog-channel-token", "")
    resource_state = headers.get("x-goog-resource-state", "")
    if not channel_token or resource_state == "sync":
        # Initial sync ping — Google sends this on watch registration
        return {}

    def _v2_drive_pull(connection_id: str) -> None:
        try:
            from core.foundations.db import get_session as _v2s
            from core.memory.sync_runner import run_sync_for_connection
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=connection_id, limit=50)
                import logging as _lg
                _lg.getLogger(__name__).info(
                    f"Drive webhook v2 sync done: emitted={r.items_emitted}"
                )
        except Exception as e:
            import logging as _lg
            _lg.getLogger(__name__).exception(f"Drive webhook v2 sync failed: {e}")

    background_tasks.add_task(_v2_drive_pull, channel_token)
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
    import os
    import warnings

    from app.ingestion.docs_connector import (
        build_drive_service,
        create_docs_oauth_flow,
        get_docs_user_email,
    )

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
    # Token storage + sync handled by v2 register_v2_gdocs_connection below
    # (SecretRef + Connection). Legacy gdocs_connections table dropped in 0015.
    from app.core.analytics import capture
    capture(org_id, "integration_connected", {"tool": "gdocs"})

    from core.memory.adapters.known.gdocs import register_v2_gdocs_connection
    v2_cid = register_v2_gdocs_connection(
        org_id=org_id, account_email=connected_email, access_token=creds.token,
        refresh_token=creds.refresh_token, created_by=org_id,
    )
    from core.foundations.db import get_session as _v2s
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_docs() -> None:
        import logging
        try:
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=v2_cid, limit=20)
                logging.getLogger(__name__).info(f"gdocs sync done: emitted={r.items_emitted}")
        except Exception as e:
            logging.getLogger(__name__).exception(f"gdocs sync failed: {e}")

    background_tasks.add_task(_sync_docs)
    return RedirectResponse(url=INTEGRATIONS_REDIRECT)


# ─── Unified Integrations Status ─────────────────────────────────────────────

_TOOL_KEYS = ("gmail", "gcal", "slack", "jira", "notion", "gsheets", "gdrive", "gdocs", "hubspot")
_TOOL_TO_V2_SOURCE = {
    "gmail":   "gmail",
    "gcal":    "gcal",
    "slack":   "slack",
    "jira":    "jira",
    "notion":  "notion",
    "gsheets": "gsheets",
    "gdrive":  "gdrive",
    "gdocs":   "gdocs",
    "hubspot": "hubspot",
}


@router.get("/api/org/{org_id}/integrations/status")
def get_integrations_status(org_id: str):
    """Real-time connection status sourced from the v2 thin-pipe tables.

    Reads:
      connections        — connected status + source_id (mailbox/workspace)
      cursors            — last successful sync timestamp per connection
      graph_nodes/facts  — per-source extracted entity + fact counts

    Replaces 15+ dropped v1 tables (oauth_tokens read-only kept where useful
    for the Gmail account list).
    """
    db = SessionLocal()
    try:
        # One pass over v2 connections + cursors for this org. Also pull the
        # v1 oauth_tokens.last_synced_at as a fallback when a Connection has
        # no cursor row yet (first sync still in flight, or the OAuth callback
        # only wrote oauth_tokens before the v2 thin pipe started recording cursors).
        # items_pulled = cumulative records this connection has ever fetched
        # (= count of credits ever spent on it). Surfaced so the user can see
        # how many emails got synced vs the abstract entity count.
        rows = db.execute(
            text("""
                SELECT c.id, c.source_type, c.source_id, c.status, c.health_status,
                       c.last_health_check_at, c.last_error,
                       COALESCE(
                           (SELECT MAX(last_sync_at) FROM cursors WHERE connection_id = c.id),
                           (SELECT MAX(last_synced_at) FROM oauth_tokens
                              WHERE org_id::text = c.org_id
                                AND (account_email = c.source_id
                                  OR account_email = c.source_type || ':' || c.source_id))
                       ) AS last_sync_at,
                       COALESCE(
                           (SELECT items_pulled_count FROM cursors WHERE connection_id = c.id),
                           0
                       ) AS items_pulled
                FROM connections c
                WHERE c.org_id = :oid
                ORDER BY c.source_type, c.created_at DESC
            """),
            {"oid": org_id},
        ).fetchall()

        by_source: dict[str, list] = {}
        for r in rows:
            by_source.setdefault(r.source_type, []).append(r)

        # Per-source extracted entity counts. source_item_ids is JSONB
        # containing strings shaped like "<source_type>:<native_id>".
        node_counts = db.execute(
            text("""
                SELECT split_part(item::text, ':', 1) AS source_type, COUNT(*) AS n
                FROM (
                    SELECT jsonb_array_elements_text(
                             CASE jsonb_typeof(source_item_ids::jsonb)
                                  WHEN 'array' THEN source_item_ids::jsonb
                                  ELSE '[]'::jsonb
                             END
                           ) AS item
                    FROM graph_nodes
                    WHERE org_id = :oid AND type = 'entity'
                ) x
                GROUP BY 1
            """),
            {"oid": org_id},
        ).fetchall()
        nodes_by_source = {row.source_type.strip('"'): int(row.n or 0) for row in node_counts}

        fact_count = db.execute(
            text("SELECT COUNT(*) FROM facts WHERE org_id = :oid"),
            {"oid": org_id},
        ).scalar() or 0

        # Per-source fact counts — facts carry a "<source_type>:<id>" prefix in
        # source_item_id, so we can attribute each fact to the tool that produced
        # it (instead of only showing the global total for gmail).
        fact_rows = db.execute(
            text("""
                SELECT split_part(source_item_id, ':', 1) AS source_type, COUNT(*) AS n
                FROM facts WHERE org_id = :oid AND source_item_id LIKE '%:%'
                GROUP BY 1
            """),
            {"oid": org_id},
        ).fetchall()
        facts_by_source = {row.source_type: int(row.n or 0) for row in fact_rows}

        # Active-sync flags written by core.memory.sync_runner while a pull
        # is in flight. Surfaced to UI as syncStatus="syncing" so the user
        # sees an actual progress signal instead of a frozen "idle".
        active_now: set[str] = set()
        try:
            from app.redis_client import redis_client as _r
            for src in {c.source_type for c in rows}:
                if _r.get(f"sync_active:org:{org_id}:{src}"):
                    active_now.add(src)
        except Exception:
            pass

        # Plan cadence drives the freshness band so the badge reflects the
        # ACTUAL sync interval (early=6h, startup/enterprise=1h) instead of a
        # hardcoded 1h/6h threshold that made every source look "stale". And a
        # red health_status (last sync errored — e.g. OAuth token expired) is
        # surfaced as "error" → the UI prompts a reconnect, not just "stale".
        from datetime import datetime, timezone

        from app.plan_enforcer import get_org_plan, sync_interval_hours

        plan_info = get_org_plan(db, org_id)
        interval_h = sync_interval_hours(plan_info["tier"])
        _now = datetime.now(timezone.utc)

        def _freshness(last_sync, health) -> str:
            if health == "red":
                return "error"
            if last_sync is None:
                return "pending"
            ls = last_sync if last_sync.tzinfo else last_sync.replace(tzinfo=timezone.utc)
            age_h = (_now - ls).total_seconds() / 3600.0
            window = interval_h if interval_h is not None else 24.0
            if age_h < window:
                return "healthy"
            if age_h < 2 * window:
                return "aging"
            return "stale"

        # Build the per-tool status payload
        status: dict[str, dict] = {}
        for tool in _TOOL_KEYS:
            v2_src = _TOOL_TO_V2_SOURCE[tool]
            conns = by_source.get(v2_src) or []
            if not conns:
                status[tool] = {"connected": False}
                continue
            primary = conns[0]
            last_sync = primary.last_sync_at
            if v2_src in active_now:
                sync_status = "syncing"
            elif primary.health_status == "red":
                sync_status = "error"
            elif primary.health_status == "yellow":
                sync_status = "syncing"
            else:
                sync_status = "idle"
            status[tool] = {
                "connected": primary.status == "active",
                "syncStatus": sync_status,
                "lastSyncAt": last_sync.isoformat() if last_sync else None,
                "freshness": _freshness(last_sync, primary.health_status),
                "syncIntervalHours": interval_h,
                "metadata": {
                    "accounts":          [c.source_id for c in conns],
                    "recordsPulled":     int(sum(getattr(c, "items_pulled", 0) or 0 for c in conns)),
                    "entitiesExtracted": nodes_by_source.get(v2_src, 0),
                    "factsExtracted":    facts_by_source.get(v2_src, fact_count if tool == "gmail" else 0),
                    "lastError":         primary.last_error,
                },
            }

        # Include plan's allowed integrations so frontend can gate UI
        # (plan_info already fetched above for the freshness window).
        status["_plan"] = {
            "tier": plan_info["tier"],
            "integrations_allowed": sorted(plan_info["config"]["integrations_allowed"]),
        }

        return status

    finally:
        db.close()


# ─── Disconnect ───────────────────────────────────────────────────────────────
# Two modes:
#   wipe_data=False  → remove only the OAuth connection / sync state (keep data)
#   wipe_data=True   → also delete all synced data tables (fresh-start next time)

# Connection-only deletes — v2 path: delete from connections (CASCADE removes
# cursors + secret_refs) plus the oauth_tokens audit row if it exists.
def _v2_disconnect_sql(source_type: str, oauth_token_pattern: str | None) -> list[str]:
    out = [
        "DELETE FROM cursors WHERE connection_id IN "
        "  (SELECT id FROM connections WHERE org_id = :oid AND source_type = '" + source_type + "')",
        "DELETE FROM secrets_ref WHERE connection_id IN "
        "  (SELECT id FROM connections WHERE org_id = :oid AND source_type = '" + source_type + "')",
        "DELETE FROM connections WHERE org_id = :oid AND source_type = '" + source_type + "'",
    ]
    if oauth_token_pattern is not None:
        # Some v1 OAuth callbacks still write oauth_tokens for legacy auth — best-effort delete.
        if oauth_token_pattern == "":
            out.append("DELETE FROM oauth_tokens WHERE org_id = :oid AND account_email NOT LIKE '%:%'")
        else:
            out.append(f"DELETE FROM oauth_tokens WHERE org_id = :oid AND account_email LIKE '{oauth_token_pattern}'")
    return out


TOOL_CONNECTION_SQL: dict[str, list[str]] = {
    "gmail":   _v2_disconnect_sql("gmail", ""),
    "gcal":    _v2_disconnect_sql("gcal", "gcal:%"),
    "slack":   _v2_disconnect_sql("slack", "slack:%"),
    "jira":    _v2_disconnect_sql("jira", "jira:%"),
    "notion":  _v2_disconnect_sql("notion", "notion:%"),
    "gsheets": _v2_disconnect_sql("gsheets", "gsheets:%"),
    "gdrive":  _v2_disconnect_sql("gdrive", "gdrive:%"),
    "gdocs":   _v2_disconnect_sql("gdocs", "gdocs:%"),
    "hubspot": _v2_disconnect_sql("hubspot", "hubspot:%"),
}

# Full wipe — v2 path. Per-source extracted nodes/facts/edges carry the
# source_type prefix in source_item_ids / source_item_id (e.g. "gmail:<id>").
# A wipe deletes everything tagged with this source_type so the next OAuth
# connect starts a truly fresh sync. Edges whose endpoints are deleted are
# cleaned up first to satisfy FK constraints.
def _v2_wipe_sql(source_type: str, oauth_token_pattern: str | None) -> list[str]:
    """Wipe a single source's data — preserving shared graph nodes.

    The OLD version deleted any node whose source_item_ids contained
    a {source}:% item, even if the node was ALSO sourced from manual
    entries or a different connector. That meant "Disconnect & delete
    Gmail data" silently nuked context the user had typed by hand into
    Resources or pulled from Slack/HubSpot, because resolve.py merges
    the same person across sources into one node.

    New flow (per-source, preserves shared context):
      1. Drop edges ASSERTED by this source. Edges from other sources
         (manual, slack, etc) survive even if the nodes they connect
         were also seen in this source.
      2. Drop facts with this source's prefix — facts are 1:1 with a
         source_item_id, so source-scoped deletion is exact.
      3. UPDATE every node that has this source's item in its
         source_item_ids → strip just that item. Multi-source nodes
         survive with their remaining provenance intact.
      4. DELETE nodes whose source_item_ids became empty after step 3
         (i.e. they were exclusive to this source). ON DELETE CASCADE
         on graph_edges automatically cleans dangling edges from those
         orphaned nodes.
    """
    src_pat = f"{source_type}:%"
    pre = [
        # 1. Edges asserted by THIS source (asserted_by_id carries the
        #    same `gmail:<msg>` prefix the ingest subscriber wrote).
        f"DELETE FROM graph_edges "
        f"WHERE org_id = :oid AND asserted_by_id LIKE '{src_pat}'",

        # 2. Facts produced by THIS source.
        f"DELETE FROM facts WHERE org_id = :oid AND source_item_id LIKE '{src_pat}'",

        # 3. Strip this source's items from every multi-source node.
        f"""UPDATE graph_nodes
            SET source_item_ids = (
                SELECT COALESCE(jsonb_agg(item), '[]'::jsonb)
                FROM jsonb_array_elements_text(
                    CASE jsonb_typeof(source_item_ids::jsonb)
                         WHEN 'array' THEN source_item_ids::jsonb
                         ELSE '[]'::jsonb END
                ) AS item
                WHERE item NOT LIKE '{src_pat}'
            )
            WHERE org_id = :oid
              AND EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(
                    CASE jsonb_typeof(source_item_ids::jsonb)
                         WHEN 'array' THEN source_item_ids::jsonb
                         ELSE '[]'::jsonb END
                ) AS item WHERE item LIKE '{src_pat}')""",

        # 4. Delete nodes that were sourced ONLY from this connector
        #    (their array is now empty). CASCADE on graph_edges drops
        #    any dangling cross-source edges that pointed at them.
        f"""DELETE FROM graph_nodes
            WHERE org_id = :oid
              AND (
                source_item_ids IS NULL
                OR source_item_ids::jsonb = '[]'::jsonb
              )""",
    ]
    return pre + _v2_disconnect_sql(source_type, oauth_token_pattern)


TOOL_CLEANUP_SQL: dict[str, list[str]] = {
    tool: _v2_wipe_sql(_TOOL_TO_V2_SOURCE[tool],
                       None if tool == "gmail" else f"{tool}:%" if tool != "gmail" else "")
    for tool in _TOOL_KEYS
}
# Gmail's oauth_token row has no prefix — patch:
TOOL_CLEANUP_SQL["gmail"] = _v2_wipe_sql("gmail", "")
TOOL_CLEANUP_SQL["gdrive"] = _v2_wipe_sql("gdrive", "gdrive:%")


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
        # g-i-8: every permission / data change must land in the
        # immutable audit trail. Distinguish the two flavours so a
        # support query "did the customer ask for a wipe or a soft
        # disconnect?" answers itself.
        try:
            from core.foundations import audit
            audit.record(
                org_id=org_id,
                actor_type="user",
                actor_id=org_id,
                action="data_subject_erasure" if wipe_data else "scope_revoked",
                target_type="integration",
                target_id=tool,
                metadata={
                    "tool": tool,
                    "wipe_data": wipe_data,
                    "scope": "source_only",  # shared nodes from other sources survive
                },
            )
        except Exception:
            # Audit failure must not break the disconnect — the SQL
            # already committed, the user's action is durable.
            pass
        return {"disconnected": True, "tool": tool, "data_wiped": wipe_data}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ─── Calendar Selector ────────────────────────────────────────────────────────


@router.get("/api/org/{org_id}/calendars")
def list_user_calendars(org_id: str):
    """
    List all Google Calendars available to the connected account.
    Returns each calendar with its sync_enabled status.
    """
    from app.ingestion.calendar_connector import build_calendar_service, list_calendars

    db = SessionLocal()
    try:
        token_row = db.execute(
            text("""
                SELECT access_token, refresh_token
                FROM oauth_tokens
                WHERE org_id = :oid AND account_email LIKE 'gcal:%'
                LIMIT 1
            """),
            {"oid": org_id},
        ).fetchone()

        if not token_row:
            raise HTTPException(status_code=404, detail="Google Calendar not connected")

        service = build_calendar_service(token_row.access_token, token_row.refresh_token)
        calendars = list_calendars(service)

        # Get current sync selections from DB
        enabled_rows = db.execute(
            text("SELECT calendar_id, sync_enabled FROM calendar_sync_state WHERE org_id = :oid"),
            {"oid": org_id},
        ).fetchall()
        enabled_map = {r.calendar_id: r.sync_enabled for r in enabled_rows}

        result = []
        for cal in calendars:
            if cal.get("accessRole") not in ("owner", "writer", "reader"):
                continue
            cal_id = cal["id"]
            result.append({
                "id": cal_id,
                "name": cal.get("summary", cal_id),
                "primary": cal.get("primary", False),
                "accessRole": cal.get("accessRole"),
                "sync_enabled": enabled_map.get(cal_id, cal_id == "primary"),
            })

        return {"calendars": result}
    finally:
        db.close()


@router.put("/api/org/{org_id}/calendars")
async def update_calendar_selection(org_id: str, request: Request):
    """
    Save which calendars the user wants to sync.
    Body: { "calendars": [{"id": "cal_id", "sync_enabled": true/false}] }
    """
    body = await request.json()
    selections = body.get("calendars", [])

    if not selections:
        raise HTTPException(status_code=400, detail="No calendars provided")

    db = SessionLocal()
    try:
        for sel in selections:
            cal_id = sel.get("id")
            enabled = sel.get("sync_enabled", False)
            cal_name = sel.get("name", "")
            if not cal_id:
                continue

            db.execute(
                text("""
                    INSERT INTO calendar_sync_state (org_id, calendar_id, sync_enabled, calendar_name)
                    VALUES (:oid, :cal_id, :enabled, :name)
                    ON CONFLICT (org_id, calendar_id) DO UPDATE SET
                        sync_enabled = EXCLUDED.sync_enabled,
                        calendar_name = COALESCE(EXCLUDED.calendar_name, calendar_sync_state.calendar_name),
                        updated_at = NOW()
                """),
                {"oid": org_id, "cal_id": cal_id, "enabled": enabled, "name": cal_name},
            )

        db.commit()
        return {"updated": True, "count": len(selections)}
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
    "hubspot": "app.tasks.hubspot_sync.run_hubspot_sync",
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


# ─── HubSpot OAuth ────────────────────────────────────────────────────────────

@router.get("/auth/hubspot/connect")
def hubspot_connect(org_id: str):
    from app.ingestion.hubspot_connector import get_hubspot_authorize_url

    state = secrets.token_urlsafe(32)
    _store_oauth_state(state, org_id)
    auth_url = get_hubspot_authorize_url(state)
    return RedirectResponse(auth_url)


@router.get("/auth/hubspot/callback")
async def hubspot_callback(state: str, code: str, background_tasks: BackgroundTasks):
    from app.ingestion.hubspot_connector import exchange_code_for_tokens

    state_data = _pop_oauth_state(state)
    if not state_data:
        return {"error": "Invalid OAuth state or session expired."}

    org_id = state_data["org_id"]
    token_data = exchange_code_for_tokens(code)

    hub_id = token_data.get("hub_id") or "unknown"
    account_key = f"hubspot:{hub_id}"

    from datetime import timedelta
    expires_in = token_data.get("expires_in", 1800)
    expiry = datetime.now() + timedelta(seconds=expires_in)

    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO oauth_tokens
                    (org_id, account_email, access_token, refresh_token, expires_at,
                     sync_status, created_at)
                VALUES
                    (:org_id, :account_email, :access_token, :refresh_token,
                     :expires_at, 'idle', NOW())
                ON CONFLICT (org_id, account_email) DO UPDATE SET
                    access_token  = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at    = EXCLUDED.expires_at,
                    sync_status   = 'idle',
                    updated_at    = NOW()
            """),
            {
                "org_id": org_id,
                "account_email": account_key,
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "expires_at": expiry,
            },
        )
        db.commit()
    finally:
        db.close()

    # Per g-i-1 plan: thin pipe via core.memory.adapters.known.hubspot.
    from core.memory.adapters.known.hubspot import register_v2_hubspot_connection
    v2_cid = register_v2_hubspot_connection(
        org_id=org_id, portal_id=str(hub_id),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        created_by=org_id,
    )
    from core.foundations.db import get_session as _v2s
    from core.memory.sync_runner import run_sync_for_connection

    def _sync_hs() -> None:
        import logging
        try:
            with _v2s() as s:
                r = run_sync_for_connection(s, connection_id=v2_cid, limit=50)
                logging.getLogger(__name__).info(f"hubspot sync done: emitted={r.items_emitted}")
        except Exception as e:
            logging.getLogger(__name__).exception(f"hubspot sync failed: {e}")

    background_tasks.add_task(_sync_hs)
    return RedirectResponse(f"{INTEGRATIONS_REDIRECT}?connected=hubspot")
