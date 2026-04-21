"""
Slack Sync Task

Two-phase architecture:
  Phase 1 (webhook handler): validate → enqueue → return 200 in <200ms
  Phase 2 (async processing): classify → quality gate → NLP extract → graph write

Backfill: low-priority background job, spread over hours.
"""

import logging
import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal
from app.graph.relationship_calculator import recalculate_all_relationships
from app.ingestion.slack_connector import (
    fetch_channels,
    fetch_channel_history,
    fetch_user_info,
    classify_message,
)

logger = logging.getLogger(__name__)


def run_slack_backfill(org_id: str):
    """
    Backfill Slack message history for all configured channels.
    Low-priority: processes in batches, respects Tier 3 rate limits.
    """
    db = SessionLocal()
    try:
        workspace = db.execute(
            text("SELECT workspace_id, bot_token, backfill_status FROM slack_workspaces WHERE org_id = :oid LIMIT 1"),
            {"oid": org_id},
        ).fetchone()

        if not workspace or workspace.backfill_status == "complete":
            return

        if not workspace.bot_token:
            logger.warning(f"Slack backfill: no bot_token for org {org_id}")
            return

        # Mark as running
        db.execute(
            text("UPDATE slack_workspaces SET backfill_status = 'running', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()

        # Sync channel list first
        channels = fetch_channels(workspace.bot_token)
        _upsert_channels(db, org_id, workspace.workspace_id, channels)
        db.commit()

        # Process each sync-enabled channel
        channel_configs = db.execute(
            text("""
                SELECT channel_id, channel_name, priority_tier, last_cursor
                FROM slack_channel_config
                WHERE org_id = :oid AND sync_enabled = TRUE
            """),
            {"oid": org_id},
        ).fetchall()

        for channel in channel_configs:
            _backfill_channel(db, workspace.bot_token, org_id, workspace.workspace_id, channel)

        # Mark complete
        db.execute(
            text("UPDATE slack_workspaces SET backfill_status = 'complete', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()
        logger.info(f"Slack backfill complete for org {org_id}")

        # ── Phase 2: Bridge Slack data into relationship graph ──
        try:
            from app.ingestion.slack_bridge import resolve_slack_users_to_contacts, create_slack_interactions
            resolve_slack_users_to_contacts(db, org_id)
            db.commit()
            created = create_slack_interactions(db, org_id)
            db.commit()
            if created > 0:
                recalculate_all_relationships(db, org_id)
        except Exception as bridge_err:
            logger.error(f"Slack bridge failed for org {org_id}: {bridge_err}")

    except Exception as e:
        db.execute(
            text("UPDATE slack_workspaces SET backfill_status = 'error', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()
        logger.error(f"Slack backfill failed for org {org_id}: {e}")
        raise
    finally:
        db.close()


def _upsert_channels(db, org_id, workspace_id, channels):
    """Insert/update channel configs from workspace channel list."""
    for ch in channels:
        # Apply drop rules for water cooler channels
        channel_name = ch.get("name", "")
        drop_names = {"random", "general", "watercooler", "fun", "memes", "off-topic"}
        sync_enabled = not any(channel_name.lower() == d or channel_name.lower().startswith(d + "-") for d in drop_names)

        db.execute(
            text("""
                INSERT INTO slack_channel_config
                    (org_id, workspace_id, channel_id, channel_name, channel_type,
                     is_external, sync_enabled, priority_tier)
                VALUES (:org_id, :workspace_id, :channel_id, :channel_name, :channel_type,
                        :is_external, :sync_enabled, :tier)
                ON CONFLICT (org_id, channel_id) DO UPDATE SET
                    channel_name = EXCLUDED.channel_name,
                    is_external = EXCLUDED.is_external
            """),
            {
                "org_id": org_id,
                "workspace_id": workspace_id,
                "channel_id": ch.get("id"),
                "channel_name": channel_name,
                "channel_type": "public" if not ch.get("is_private") else "private",
                "is_external": ch.get("is_ext_shared", False),
                "sync_enabled": sync_enabled,
                "tier": 1 if ch.get("is_ext_shared") else 2,
            },
        )


def _backfill_channel(db, bot_token, org_id, workspace_id, channel):
    """Fetch and process historical messages for a single channel."""
    cursor = channel.last_cursor
    messages_processed = 0

    while True:
        try:
            messages, next_cursor = fetch_channel_history(
                bot_token, channel.channel_id, cursor=cursor, limit=200
            )
        except Exception as e:
            logger.error(f"Failed to fetch history for channel {channel.channel_id}: {e}")
            break

        for message in messages:
            tier, reason = classify_message(message, channel_name=channel.channel_name)
            if tier == 3:
                continue  # Drop

            _upsert_message(db, org_id, workspace_id, channel.channel_id, message, tier)
            messages_processed += 1

        # Save cursor progress
        if next_cursor:
            db.execute(
                text("UPDATE slack_channel_config SET last_cursor = :cursor WHERE org_id = :oid AND channel_id = :cid"),
                {"cursor": next_cursor, "oid": org_id, "cid": channel.channel_id},
            )
            db.commit()
            cursor = next_cursor
        else:
            break

    db.execute(
        text("UPDATE slack_channel_config SET last_synced_at = NOW() WHERE org_id = :oid AND channel_id = :cid"),
        {"oid": org_id, "cid": channel.channel_id},
    )
    db.commit()
    logger.info(f"Slack backfill: org={org_id} channel={channel.channel_name} processed {messages_processed} messages")


def _upsert_message(db, org_id, workspace_id, channel_id, message, tier):
    """Upsert a slack message after passing quality gates."""
    db.execute(
        text("""
            INSERT INTO slack_messages (
                org_id, workspace_id, channel_id, message_ts,
                thread_ts, is_thread_root, sender_slack_id,
                text_content, text_cleaned, is_bot, raw_event
            )
            VALUES (
                :org_id, :workspace_id, :channel_id, :message_ts,
                :thread_ts, :is_root, :sender_id,
                :text_content, :text_cleaned, :is_bot, CAST(:raw AS jsonb)
            )
            ON CONFLICT (workspace_id, channel_id, message_ts) DO NOTHING
        """),
        {
            "org_id": org_id,
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "message_ts": message.get("ts"),
            "thread_ts": message.get("thread_ts"),
            "is_root": message.get("ts") == message.get("thread_ts"),
            "sender_id": message.get("user"),
            "text_content": message.get("text", ""),
            "text_cleaned": message.get("text", "").strip(),
            "is_bot": bool(message.get("bot_id")),
            "raw": json.dumps(message),
        },
    )


async def process_slack_event_async(payload: dict):
    """
    Phase 2 async event processor — called from the webhook background task.
    Applies quality gates before any DB writes.
    """
    event = payload.get("event", {})
    if not event:
        return

    event_type = event.get("type")
    if event_type not in ("message", "app_mention"):
        return

    # Route to correct org via team_id
    team_id = payload.get("team_id")
    if not team_id:
        return

    db = SessionLocal()
    try:
        workspace = db.execute(
            text("SELECT org_id, workspace_id FROM slack_workspaces WHERE workspace_id = :tid LIMIT 1"),
            {"tid": team_id},
        ).fetchone()

        if not workspace:
            return

        org_id = str(workspace.org_id)
        channel_id = event.get("channel", "")

        channel_config = db.execute(
            text("SELECT channel_name, priority_tier, sync_enabled FROM slack_channel_config WHERE org_id = :oid AND channel_id = :cid"),
            {"oid": org_id, "cid": channel_id},
        ).fetchone()

        if channel_config and not channel_config.sync_enabled:
            return

        channel_name = channel_config.channel_name if channel_config else ""
        tier, reason = classify_message(event, channel_name=channel_name)

        if tier == 3:
            return  # Quality gate drop

        _upsert_message(db, org_id, workspace.workspace_id, channel_id, event, tier)
        db.commit()

        # Update last_event_at on workspace
        db.execute(
            text("UPDATE slack_workspaces SET last_event_at = NOW() WHERE workspace_id = :tid"),
            {"tid": team_id},
        )
        db.commit()

    except Exception as e:
        logger.error(f"Slack event processing failed: {e}")
    finally:
        db.close()
