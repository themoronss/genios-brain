"""
Slack Bridge — Phase 2

Bridges Slack data into the relationship graph:
1. Resolve slack_user_cache emails → contacts table
2. Create SLACK_DM interaction edges for external messages

Per PDF spec signal weights:
  - DM (external) = 2.5x
  - Shared channel msg = 1.8x
  - @mention = 0.8x
"""

import logging
from uuid import uuid4
from sqlalchemy import text

from app.ingestion.graph_builder import upsert_contact
from app.ingestion.bridge_utils import get_org_domain, is_internal_email

logger = logging.getLogger(__name__)


def resolve_slack_users_to_contacts(db, org_id: str):
    """
    For every slack_user_cache entry with person_id IS NULL and a valid email,
    upsert into contacts table.
    """
    org_domain = get_org_domain(db, org_id)

    unresolved = db.execute(
        text("""
            SELECT id, email, display_name, is_bot, is_external
            FROM slack_user_cache
            WHERE org_id = :oid AND person_id IS NULL
              AND email IS NOT NULL AND email != ''
              AND is_bot = FALSE
        """),
        {"oid": org_id},
    ).fetchall()

    resolved = 0
    for row in unresolved:
        email = row.email.lower().strip()
        if not email or "@" not in email:
            continue
        # Skip internal users — only external people become relationship contacts
        if is_internal_email(email, org_domain):
            continue

        name = row.display_name or email.split("@")[0].replace(".", " ").title()
        contact_id = upsert_contact(db, org_id, email, name)
        if contact_id:
            db.execute(
                text("UPDATE slack_user_cache SET person_id = :cid WHERE id = :sid"),
                {"cid": contact_id, "sid": row.id},
            )
            # Also link slack_messages from this user
            db.execute(
                text("""
                    UPDATE slack_messages SET sender_person_id = :cid
                    WHERE org_id = :oid AND sender_slack_id IN (
                        SELECT slack_user_id FROM slack_user_cache WHERE id = :sid
                    ) AND sender_person_id IS NULL
                """),
                {"cid": contact_id, "oid": org_id, "sid": row.id},
            )
            resolved += 1

    logger.info(f"Slack bridge: resolved {resolved}/{len(unresolved)} users for org={org_id}")
    return resolved


def create_slack_interactions(db, org_id: str):
    """
    For each Slack message with a resolved external sender,
    create a SLACK_DM/SLACK_MENTION interaction edge.

    Only processes messages from external senders that don't already have interactions.
    """
    # Get user's primary email so graph edges connect to the user node
    user_row = db.execute(text("SELECT email FROM orgs WHERE id = :oid"), {"oid": org_id}).fetchone()
    account_email = user_row.email if user_row else None

    # Find messages from external resolved users without existing interactions
    messages = db.execute(
        text("""
            SELECT sm.id, sm.channel_id, sm.message_ts, sm.thread_ts,
                   sm.sender_person_id, sm.text_content, sm.sentiment_score,
                   sm.has_commitment, sm.mentions_external,
                   scc.is_external AS channel_is_external,
                   scc.channel_type
            FROM slack_messages sm
            JOIN slack_user_cache suc ON suc.org_id = sm.org_id
                AND suc.slack_user_id = sm.sender_slack_id
            LEFT JOIN slack_channel_config scc ON scc.org_id = sm.org_id
                AND scc.channel_id = sm.channel_id
            WHERE sm.org_id = :oid
              AND sm.sender_person_id IS NOT NULL
              AND sm.is_bot = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM interactions i
                  WHERE i.slack_channel_id = sm.channel_id
                    AND i.slack_message_ts = sm.message_ts
                    AND i.contact_id = sm.sender_person_id
              )
            ORDER BY sm.created_at DESC
            LIMIT 500
        """),
        {"oid": org_id},
    ).fetchall()

    created = 0
    for msg in messages:
        # Determine interaction type and weight per PDF spec
        is_dm = msg.channel_type in ("dm", "im", "mpim")
        is_shared = msg.channel_is_external or False

        if is_dm:
            edge_weight = 2.5
            interaction_type = "slack_dm"
        elif is_shared:
            edge_weight = 1.8
            interaction_type = "slack_mention"
        else:
            edge_weight = 0.8
            interaction_type = "slack_mention"

        sentiment = msg.sentiment_score if msg.sentiment_score is not None else 0.1
        synthetic_msg_id = f"slack:{msg.channel_id}:{msg.message_ts}:{msg.sender_person_id}"

        db.execute(
            text("""
                INSERT INTO interactions (
                    id, org_id, contact_id, gmail_message_id,
                    account_email,
                    direction, subject, summary, sentiment,
                    interaction_at, source, interaction_type,
                    weight_score, signal_score,
                    edge_weight_multiplier,
                    slack_channel_id, slack_message_ts,
                    slack_thread_depth, is_external_slack
                )
                VALUES (
                    :id, :org_id, :contact_id, :gmail_message_id,
                    :account_email,
                    'inbound', :subject, :summary, :sentiment,
                    NOW(), 'slack', :interaction_type,
                    :weight_score, :signal_score,
                    :edge_weight_multiplier,
                    :channel_id, :message_ts,
                    :thread_depth, :is_external
                )
                ON CONFLICT (slack_channel_id, slack_message_ts, contact_id)
                    WHERE slack_channel_id IS NOT NULL AND slack_message_ts IS NOT NULL
                DO NOTHING
            """),
            {
                "id": str(uuid4()),
                "org_id": org_id,
                "contact_id": str(msg.sender_person_id),
                "gmail_message_id": synthetic_msg_id,
                "account_email": account_email,
                "subject": f"Slack {'DM' if is_dm else 'message'}",
                "summary": (msg.text_content or "")[:200],
                "sentiment": sentiment,
                "interaction_type": interaction_type,
                "weight_score": 0.7 if is_dm else 0.5,
                "signal_score": 0.7 if is_dm else 0.4,
                "edge_weight_multiplier": edge_weight,
                "channel_id": msg.channel_id,
                "message_ts": msg.message_ts,
                "thread_depth": 1 if msg.thread_ts else 0,
                "is_external": is_shared or is_dm,
            },
        )
        created += 1

    logger.info(f"Slack bridge: created {created} interactions for org={org_id}")
    return created
