"""
Google Drive Sync Task

Phase 1 MVP:
  - Two-phase change log processing (receive → log → process → advance token)
  - Folder structure top 3 levels
  - External permission detection
  - Shared Drive member sync → Authority Graph edges
  - Access expiry state tracking

CRITICAL:
  - NEVER advance changes_page_token until full batch is processed
  - Two-phase: write to gdrive_change_log as 'pending' FIRST, then process, then advance token
  - changes_page_token must not go 30 days without a call
"""

import logging
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.database import SessionLocal
from app.graph.relationship_calculator import recalculate_all_relationships
from app.ingestion.drive_connector import (
    build_drive_service,
    get_start_page_token,
    fetch_changes,
    classify_file_change,
    fetch_shared_drives,
    fetch_shared_drive_members,
    fetch_folder_structure,
)

logger = logging.getLogger(__name__)


def _get_drive_connection(db, org_id):
    return db.execute(
        text("""
            SELECT access_token, refresh_token, token_expires_at,
                   changes_page_token, drive_watch_expiry
            FROM gdrive_connections WHERE org_id = :oid LIMIT 1
        """),
        {"oid": org_id},
    ).fetchone()


def run_drive_sync(org_id: str):
    """
    Main Drive sync entry point.

    Signal taxonomy quality gates (in classify_file_change):
      - DROP trashed: true files
      - DROP shortcut files
      - DROP Google Forms files
      - DROP binary files for content extraction (metadata + permissions only)
      - DROP internal-only activity with no external signal
      - Route by mimeType: document → Docs pipeline, spreadsheet → Sheets pipeline

    Two-phase change log processing:
      Phase 1: Write all changes to gdrive_change_log as 'pending'
      Phase 2: Process each entry → advance page_token ONLY after full batch
    """
    db = SessionLocal()
    try:
        conn = _get_drive_connection(db, org_id)
        if not conn or not conn.access_token:
            logger.warning(f"Drive sync: no connection found for org {org_id}")
            return

        service = build_drive_service(conn.access_token, conn.refresh_token)

        page_token = conn.changes_page_token
        if not page_token:
            page_token = get_start_page_token(service)
            db.execute(
                text("UPDATE gdrive_connections SET changes_page_token = :token, updated_at = NOW() WHERE org_id = :oid"),
                {"token": page_token, "oid": org_id},
            )
            db.commit()

        # Sync Shared Drives + folder structure first
        _sync_shared_drives(db, service, org_id)
        _sync_folder_structure(db, service, org_id)

        # Process changes with two-phase log
        _process_changes(db, service, org_id, page_token)

        logger.info(f"Drive sync complete for org {org_id}")

        # ── Phase 2: Bridge Drive data into relationship graph ──
        try:
            from app.ingestion.drive_bridge import resolve_drive_people_to_contacts, create_drive_interactions
            resolve_drive_people_to_contacts(db, org_id)
            db.commit()
            created = create_drive_interactions(db, org_id)
            db.commit()
            if created > 0:
                recalculate_all_relationships(db, org_id)
        except Exception as bridge_err:
            logger.error(f"Drive bridge failed for org {org_id}: {bridge_err}")

    except Exception as e:
        logger.error(f"Drive sync failed for org {org_id}: {e}")
        raise
    finally:
        db.close()


def _process_changes(db, service, org_id, page_token):
    """
    Two-phase change log processing.
    Phase 1: Receive all changes + write to gdrive_change_log as 'pending'.
    Phase 2: Process each pending entry → advance page_token ONLY after full batch succeeds.
    """
    current_token = page_token
    has_more = True

    while has_more:
        changes, new_token, has_more = fetch_changes(service, current_token)

        # Phase 1: Write all changes to change log as 'pending' (DO NOT advance token yet)
        change_log_ids = []
        for change in changes:
            action, route = classify_file_change(change)
            if action is None:
                continue  # Quality gate: drop

            row = db.execute(
                text("""
                    INSERT INTO gdrive_change_log
                        (org_id, change_type, file_id, page_token_at_receipt, raw_change, status, received_at)
                    VALUES (:org_id, :type, :file_id, :token, :raw::jsonb, 'pending', NOW())
                    RETURNING id
                """),
                {
                    "org_id": org_id,
                    "type": action,
                    "file_id": change.get("fileId"),
                    "token": current_token,
                    "raw": json.dumps(change),
                },
            ).fetchone()
            if row:
                change_log_ids.append((row.id, change, action, route))

        db.commit()

        # Phase 2: Process each change log entry
        all_processed = True
        for log_id, change, action, route in change_log_ids:
            try:
                _process_single_change(db, org_id, change, action, route)
                db.execute(
                    text("UPDATE gdrive_change_log SET status = 'processed', processed_at = NOW() WHERE id = :id"),
                    {"id": log_id},
                )
            except Exception as e:
                logger.error(f"Failed to process drive change {log_id}: {e}")
                db.execute(
                    text("UPDATE gdrive_change_log SET status = 'failed' WHERE id = :id"),
                    {"id": log_id},
                )
                all_processed = False

        db.commit()

        # ONLY advance page_token after full batch successfully processed
        if all_processed or len(change_log_ids) == 0:
            db.execute(
                text("UPDATE gdrive_connections SET changes_page_token = :token, last_changes_sync_at = NOW(), updated_at = NOW() WHERE org_id = :oid"),
                {"token": new_token, "oid": org_id},
            )
            db.commit()
            current_token = new_token


def _process_single_change(db, org_id, change, action, route):
    """Process a single Drive change event."""
    file = change.get("file", {})
    file_id = change.get("fileId")

    if action == "removed":
        # Mark file as trashed
        db.execute(
            text("UPDATE gdrive_files SET trashed = TRUE WHERE org_id = :oid AND file_id = :fid"),
            {"oid": org_id, "fid": file_id},
        )
        return

    if not file:
        return

    # Upsert file metadata
    mime_type = file.get("mimeType", "")
    content_type = _classify_content_type(mime_type)

    owners = file.get("owners", [{}])
    owner_email = owners[0].get("emailAddress") if owners else None

    db.execute(
        text("""
            INSERT INTO gdrive_files (
                org_id, file_id, file_name, mime_type, content_type,
                owner_email, drive_id, trashed, modified_time, created_time,
                is_shared_externally, synced_at
            )
            VALUES (
                :org_id, :file_id, :file_name, :mime_type, :content_type,
                :owner_email, :drive_id, :trashed, :modified_time, :created_time,
                :is_external, NOW()
            )
            ON CONFLICT (org_id, file_id) DO UPDATE SET
                file_name = EXCLUDED.file_name,
                owner_email = EXCLUDED.owner_email,
                trashed = EXCLUDED.trashed,
                modified_time = EXCLUDED.modified_time,
                is_shared_externally = EXCLUDED.is_shared_externally,
                synced_at = NOW()
        """),
        {
            "org_id": org_id,
            "file_id": file_id,
            "file_name": file.get("name"),
            "mime_type": mime_type,
            "content_type": content_type,
            "owner_email": owner_email,
            "drive_id": file.get("driveId"),
            "trashed": file.get("trashed", False),
            "modified_time": file.get("modifiedTime"),
            "created_time": file.get("createdTime"),
            "is_external": file.get("shared", False),
        },
    )


def _sync_shared_drives(db, service, org_id):
    """Sync Shared Drive list and member roles."""
    try:
        drives = fetch_shared_drives(service)
    except Exception as e:
        logger.warning(f"Drive: could not fetch Shared Drives for org {org_id}: {e}")
        return

    for drive in drives:
        db.execute(
            text("""
                INSERT INTO gdrive_shared_drives (org_id, drive_id, drive_name, created_time)
                VALUES (:org_id, :drive_id, :name, :created)
                ON CONFLICT (org_id, drive_id) DO UPDATE SET
                    drive_name = EXCLUDED.drive_name
            """),
            {
                "org_id": org_id,
                "drive_id": drive.get("id"),
                "name": drive.get("name"),
                "created": drive.get("createdTime"),
            },
        )

        # Sync members
        try:
            members = fetch_shared_drive_members(service, drive["id"])
            for member in members:
                db.execute(
                    text("""
                        INSERT INTO gdrive_shared_drive_members
                            (org_id, drive_id, email, drive_role, is_external)
                        VALUES (:org_id, :drive_id, :email, :role, :is_external)
                        ON CONFLICT (org_id, drive_id, email) DO UPDATE SET
                            drive_role = EXCLUDED.drive_role
                    """),
                    {
                        "org_id": org_id,
                        "drive_id": drive["id"],
                        "email": member.get("emailAddress", ""),
                        "role": member.get("role"),
                        "is_external": member.get("type") == "user" and "externalUser" in str(member),
                    },
                )
        except Exception as e:
            logger.warning(f"Drive: could not fetch members for drive {drive['id']}: {e}")

    db.execute(
        text("UPDATE gdrive_connections SET last_shared_drive_sync_at = NOW(), updated_at = NOW() WHERE org_id = :oid"),
        {"oid": org_id},
    )
    db.commit()


def _sync_folder_structure(db, service, org_id):
    """Sync top 3 levels of folder structure."""
    try:
        folders = fetch_folder_structure(service, max_depth=3)
    except Exception as e:
        logger.warning(f"Drive: could not fetch folder structure for org {org_id}: {e}")
        return

    for folder in folders:
        db.execute(
            text("""
                INSERT INTO gdrive_folder_structure
                    (org_id, folder_id, folder_name, parent_folder_id, folder_level, owner_email)
                VALUES (:org_id, :folder_id, :name, :parent_id, :level, :owner_email)
                ON CONFLICT (org_id, folder_id) DO UPDATE SET
                    folder_name = EXCLUDED.folder_name,
                    folder_level = EXCLUDED.folder_level,
                    owner_email = EXCLUDED.owner_email
            """),
            {
                "org_id": org_id,
                "folder_id": folder["folder_id"],
                "name": folder["folder_name"],
                "parent_id": folder["parent_folder_id"],
                "level": folder["folder_level"],
                "owner_email": folder["owner_email"],
            },
        )

    db.execute(
        text("UPDATE gdrive_connections SET last_full_metadata_sync_at = NOW(), updated_at = NOW() WHERE org_id = :oid"),
        {"oid": org_id},
    )
    db.commit()


def _classify_content_type(mime_type):
    mapping = {
        "application/vnd.google-apps.document": "document",
        "application/vnd.google-apps.spreadsheet": "spreadsheet",
        "application/vnd.google-apps.presentation": "presentation",
        "application/pdf": "pdf",
    }
    if any(t in mime_type for t in ["image/", "video/", "audio/"]):
        return "binary"
    return mapping.get(mime_type, "other")


async def process_drive_webhook_async(headers: dict):
    """Handle incoming Drive push notification — triggers a sync for the affected org."""
    # Drive push notifications contain channel ID in X-Goog-Channel-ID header
    channel_id = headers.get("x-goog-channel-id") or headers.get("X-Goog-Channel-ID")
    if not channel_id:
        return

    db = SessionLocal()
    try:
        conn = db.execute(
            text("SELECT org_id FROM gdrive_connections WHERE drive_watch_channel_id = :cid LIMIT 1"),
            {"cid": channel_id},
        ).fetchone()

        if not conn:
            return

        # Trigger a sync (non-blocking — already in background task)
        await run_drive_sync_async(str(conn.org_id))

    except Exception as e:
        logger.error(f"Drive webhook processing failed: {e}")
    finally:
        db.close()


async def run_drive_sync_async(org_id: str):
    """Async wrapper for run_drive_sync."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_drive_sync, org_id)
