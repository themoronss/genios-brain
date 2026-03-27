"""
Jira Sync Task

Phase 1 MVP:
  - Fetch all projects → build per-project terminal_statuses map
  - Register webhook (valid 30 days — renewal cron at 25 days)
  - JQL backfill in 3-month windows
  - Changelog field filter — first pass before any DB write

CRITICAL: Never hardcode "Done" as terminal — fetch per-project status maps.
"""

import logging
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.database import SessionLocal
from app.ingestion.jira_connector import (
    fetch_projects,
    fetch_project_statuses,
    search_issues_jql,
    register_webhook,
    filter_changelog_items,
    is_bot_transition,
    refresh_access_token,
)

logger = logging.getLogger(__name__)


def _get_jira_connection(db, org_id):
    return db.execute(
        text("""
            SELECT atlassian_cloud_id, site_url, access_token, refresh_token,
                   token_expires_at, webhook_id, webhook_registered_at
            FROM jira_connections WHERE org_id = :oid LIMIT 1
        """),
        {"oid": org_id},
    ).fetchone()


def _refresh_token_if_needed(db, org_id, conn):
    """Refresh access token if expired or expiring in next 5 minutes."""
    from app.config import JIRA_CLIENT_ID, JIRA_CLIENT_SECRET

    if not conn.token_expires_at:
        return conn.access_token

    expires_at = conn.token_expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) < expires_at - timedelta(minutes=5):
        return conn.access_token

    token_data = refresh_access_token(conn.refresh_token, JIRA_CLIENT_ID, JIRA_CLIENT_SECRET)
    new_token = token_data["access_token"]
    new_expiry = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))

    db.execute(
        text("UPDATE jira_connections SET access_token = :token, token_expires_at = :expiry, updated_at = NOW() WHERE org_id = :oid"),
        {"token": new_token, "expiry": new_expiry, "oid": org_id},
    )
    db.commit()
    return new_token


def run_jira_sync(org_id: str):
    """
    Main Jira sync entry point.
    1. Fetch all projects + build terminal_statuses per project
    2. Register/renew webhook
    3. JQL backfill (3-month windows)
    """
    db = SessionLocal()
    try:
        conn = _get_jira_connection(db, org_id)
        if not conn:
            logger.warning(f"Jira sync: no connection found for org {org_id}")
            return

        access_token = _refresh_token_if_needed(db, org_id, conn)
        cloud_id = conn.atlassian_cloud_id

        # Mark backfill as running
        db.execute(
            text("UPDATE jira_connections SET backfill_status = 'running', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()

        # Register webhook if not already registered or if expired
        _ensure_webhook(db, org_id, cloud_id, access_token, conn)

        # Fetch and cache all projects + their status maps
        projects = fetch_projects(cloud_id, access_token)
        logger.info(f"Jira sync: org={org_id} found {len(projects)} projects")

        for project in projects:
            _sync_project(db, org_id, cloud_id, access_token, project)

        # Backfill issues via JQL (3-month windows)
        _backfill_issues(db, org_id, cloud_id, access_token)

        db.execute(
            text("UPDATE jira_connections SET backfill_status = 'complete', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()
        logger.info(f"Jira sync complete for org {org_id}")

        # ── Phase 2: Bridge Jira data into relationship graph ──
        try:
            from app.ingestion.jira_bridge import resolve_jira_users_to_contacts, create_jira_interactions
            from app.graph.relationship_calculator import recalculate_all_relationships
            resolve_jira_users_to_contacts(db, org_id)
            db.commit()
            created = create_jira_interactions(db, org_id)
            db.commit()
            if created > 0:
                recalculate_all_relationships(db, org_id)
        except Exception as bridge_err:
            logger.error(f"Jira bridge failed for org {org_id}: {bridge_err}")

    except Exception as e:
        db.execute(
            text("UPDATE jira_connections SET backfill_status = 'error', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()
        logger.error(f"Jira sync failed for org {org_id}: {e}")
        raise
    finally:
        db.close()


def _ensure_webhook(db, org_id, cloud_id, access_token, conn):
    """Register webhook if needed, or renew if within 25 days of registration (30-day expiry)."""
    import os

    webhook_url = os.getenv("JIRA_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("JIRA_WEBHOOK_URL not set — skipping webhook registration")
        return

    needs_registration = not conn.webhook_id

    if conn.webhook_registered_at:
        days_since = (datetime.now(timezone.utc) - conn.webhook_registered_at.replace(tzinfo=timezone.utc)).days
        if days_since >= 25:
            needs_registration = True

    if not needs_registration:
        return

    try:
        result = register_webhook(cloud_id, access_token, webhook_url)
        webhook_id = str(result.get("webhookRegistrationResult", [{}])[0].get("createdWebhookId", ""))
        db.execute(
            text("UPDATE jira_connections SET webhook_id = :wid, webhook_registered_at = NOW(), updated_at = NOW() WHERE org_id = :oid"),
            {"wid": webhook_id, "oid": org_id},
        )
        db.commit()
        logger.info(f"Jira webhook registered: {webhook_id}")
    except Exception as e:
        logger.error(f"Jira webhook registration failed: {e}")


def _sync_project(db, org_id, cloud_id, access_token, project):
    """Sync project config including terminal status map."""
    project_key = project.get("key")
    project_name = project.get("name")

    try:
        statuses = fetch_project_statuses(cloud_id, project_key, access_token)
    except Exception as e:
        logger.warning(f"Could not fetch statuses for project {project_key}: {e}")
        statuses = {"terminal_statuses": [], "active_statuses": []}

    db.execute(
        text("""
            INSERT INTO jira_project_config
                (org_id, project_key, project_name, terminal_statuses, active_statuses,
                 extract_enabled, last_config_refresh)
            VALUES (:org_id, :key, :name, :terminal::jsonb, :active::jsonb, TRUE, NOW())
            ON CONFLICT (org_id, project_key) DO UPDATE SET
                project_name = EXCLUDED.project_name,
                terminal_statuses = EXCLUDED.terminal_statuses,
                active_statuses = EXCLUDED.active_statuses,
                last_config_refresh = NOW()
        """),
        {
            "org_id": org_id,
            "key": project_key,
            "name": project_name,
            "terminal": json.dumps(statuses["terminal_statuses"]),
            "active": json.dumps(statuses["active_statuses"]),
        },
    )
    db.commit()


def _backfill_issues(db, org_id, cloud_id, access_token):
    """Backfill Jira issues using JQL in 3-month windows."""
    # Get existing cursor
    conn = db.execute(
        text("SELECT backfill_jql_cursor FROM jira_connections WHERE org_id = :oid LIMIT 1"),
        {"oid": org_id},
    ).fetchone()

    # Start from 12 months ago if no cursor
    if conn and conn.backfill_jql_cursor:
        cursor_date = conn.backfill_jql_cursor
    else:
        cursor_date = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Process in 3-month windows
    window_start = datetime.strptime(cursor_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    window_end_limit = datetime.now(timezone.utc)

    while window_start < window_end_limit:
        window_end = min(window_start + timedelta(days=90), window_end_limit)
        jql = (
            f'updated >= "{window_start.strftime("%Y-%m-%d")}" '
            f'AND updated <= "{window_end.strftime("%Y-%m-%d")}" '
            f'ORDER BY updated ASC'
        )

        start_at = 0
        while True:
            issues, total, is_last = search_issues_jql(cloud_id, access_token, jql, start_at=start_at)
            for issue in issues:
                _upsert_jira_issue(db, org_id, issue)

            db.commit()
            if is_last:
                break
            start_at += len(issues)

        # Update cursor
        db.execute(
            text("UPDATE jira_connections SET backfill_jql_cursor = :cursor, updated_at = NOW() WHERE org_id = :oid"),
            {"cursor": window_end.strftime("%Y-%m-%d"), "oid": org_id},
        )
        db.commit()
        window_start = window_end

    logger.info(f"Jira backfill complete for org {org_id}")


def _upsert_jira_issue(db, org_id, issue):
    """Upsert a single Jira issue."""
    fields = issue.get("fields", {})
    issue_id = issue.get("id")
    issue_key = issue.get("key")
    project_key = issue_key.split("-")[0] if issue_key else ""

    status_name = fields.get("status", {}).get("name", "")
    status_category = fields.get("status", {}).get("statusCategory", {}).get("key", "")

    # Look up terminal status from project config
    project_config = db.execute(
        text("SELECT terminal_statuses FROM jira_project_config WHERE org_id = :oid AND project_key = :key"),
        {"oid": org_id, "key": project_key},
    ).fetchone()

    terminal_statuses = []
    if project_config and project_config.terminal_statuses:
        terminal_statuses = project_config.terminal_statuses

    is_terminal = status_name in terminal_statuses or status_category == "done"

    assignee = fields.get("assignee") or {}
    reporter = fields.get("reporter") or {}

    # Sprint field (common Jira field)
    sprint_data = fields.get("customfield_10020") or []
    sprint_id = None
    if sprint_data and isinstance(sprint_data, list):
        active_sprint = next((s for s in sprint_data if s.get("state") == "active"), None)
        if active_sprint:
            sprint_id = str(active_sprint.get("id", ""))

    db.execute(
        text("""
            INSERT INTO jira_issues (
                org_id, issue_id, issue_key, project_key, summary,
                issue_type, status, status_category, is_terminal,
                priority, assignee_account_id, sprint_id,
                due_date, story_points, labels, created_at, updated_at
            )
            VALUES (
                :org_id, :issue_id, :issue_key, :project_key, :summary,
                :issue_type, :status, :status_category, :is_terminal,
                :priority, :assignee_id, :sprint_id,
                :due_date, :story_points, :labels::jsonb, :created_at, :updated_at
            )
            ON CONFLICT (org_id, issue_id) DO UPDATE SET
                summary = EXCLUDED.summary,
                status = EXCLUDED.status,
                status_category = EXCLUDED.status_category,
                is_terminal = EXCLUDED.is_terminal,
                priority = EXCLUDED.priority,
                assignee_account_id = EXCLUDED.assignee_account_id,
                sprint_id = EXCLUDED.sprint_id,
                due_date = EXCLUDED.due_date,
                story_points = EXCLUDED.story_points,
                labels = EXCLUDED.labels,
                updated_at = EXCLUDED.updated_at,
                synced_at = NOW()
        """),
        {
            "org_id": org_id,
            "issue_id": issue_id,
            "issue_key": issue_key,
            "project_key": project_key,
            "summary": fields.get("summary", ""),
            "issue_type": fields.get("issuetype", {}).get("name", ""),
            "status": status_name,
            "status_category": status_category,
            "is_terminal": is_terminal,
            "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
            "assignee_id": assignee.get("accountId"),
            "sprint_id": sprint_id,
            "due_date": fields.get("duedate"),
            "story_points": fields.get("customfield_10016"),
            "labels": json.dumps(fields.get("labels", [])),
            "created_at": fields.get("created"),
            "updated_at": fields.get("updated"),
        },
    )


async def process_jira_event_async(payload: dict):
    """
    Phase 2: Process incoming Jira webhook event.
    CRITICAL: Apply changelog field filter FIRST.
    If filtered changelog is empty — drop entire event immediately.
    """
    event_type = payload.get("webhookEvent", "")
    if not event_type.startswith("jira:issue"):
        return

    issue = payload.get("issue", {})
    if not issue:
        return

    # Get changelog
    changelog = payload.get("changelog", {})
    raw_items = changelog.get("items", [])

    if event_type == "jira:issue_updated":
        # CRITICAL: Filter changelog items first
        filtered_items = filter_changelog_items(raw_items)
        if not filtered_items:
            return  # Drop: no meaningful field changes

        # DROP: bot transitions
        author = changelog.get("author", {})
        if is_bot_transition(author):
            return

    # Find org from issue project key
    project_key = issue.get("fields", {}).get("project", {}).get("key", "")
    if not project_key:
        return

    db = SessionLocal()
    try:
        config = db.execute(
            text("SELECT org_id FROM jira_project_config WHERE project_key = :key LIMIT 1"),
            {"key": project_key},
        ).fetchone()

        if not config:
            return

        org_id = str(config.org_id)
        _upsert_jira_issue(db, org_id, issue)
        db.commit()

    except Exception as e:
        logger.error(f"Jira event processing failed: {e}")
    finally:
        db.close()
