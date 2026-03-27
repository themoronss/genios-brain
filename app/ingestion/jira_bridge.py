"""
Jira Bridge — Phase 2

Bridges Jira data into the relationship graph:
1. Resolve jira_user_cache emails → contacts
2. Create lightweight JIRA_ISSUE interactions (5% relationship graph per PDF)
3. Cross-match issues → commitments table for State Graph

Per PDF spec: Jira primarily feeds State Graph (60%), not Relationship Graph.
Its killer value is commitment cross-validation.
"""

import logging
from uuid import uuid4
from sqlalchemy import text

from app.ingestion.graph_builder import upsert_contact
from app.ingestion.bridge_utils import get_org_domain, is_internal_email

logger = logging.getLogger(__name__)


def resolve_jira_users_to_contacts(db, org_id: str):
    """
    For every jira_user_cache entry with person_id IS NULL and a valid email,
    upsert into contacts table. Also link back to jira_issues.
    """
    org_domain = get_org_domain(db, org_id)

    unresolved = db.execute(
        text("""
            SELECT id, atlassian_account_id, email, display_name, is_bot
            FROM jira_user_cache
            WHERE org_id = :oid AND person_id IS NULL
              AND email IS NOT NULL AND email != ''
        """),
        {"oid": org_id},
    ).fetchall()

    resolved = 0
    for row in unresolved:
        email = row.email.lower().strip()
        if not email or "@" not in email:
            continue
        # For Jira, resolve both internal and external — assignees matter
        name = row.display_name or email.split("@")[0].replace(".", " ").title()
        contact_id = upsert_contact(db, org_id, email, name)

        if contact_id:
            db.execute(
                text("UPDATE jira_user_cache SET person_id = :cid WHERE id = :jid"),
                {"cid": contact_id, "jid": row.id},
            )
            # Link assignee on jira_issues
            db.execute(
                text("""
                    UPDATE jira_issues SET assignee_person_id = :cid
                    WHERE org_id = :oid AND assignee_account_id = :aid AND assignee_person_id IS NULL
                """),
                {"cid": contact_id, "oid": org_id, "aid": row.atlassian_account_id},
            )
            # Link reporter on jira_issues
            db.execute(
                text("""
                    UPDATE jira_issues SET reporter_person_id = :cid
                    WHERE org_id = :oid
                      AND reporter_person_id IS NULL
                      AND issue_id IN (
                          SELECT issue_id FROM jira_issues
                          WHERE org_id = :oid
                      )
                """),
                {"cid": contact_id, "oid": org_id},
            )
            resolved += 1

    logger.info(f"Jira bridge: resolved {resolved}/{len(unresolved)} users for org={org_id}")
    return resolved


def create_jira_interactions(db, org_id: str):
    """
    Create lightweight JIRA_ISSUE interactions.
    Only for issues with resolved assignees — Jira is 5% relationship graph.
    """
    # Get user's primary email so graph edges connect to the user node
    user_row = db.execute(text("SELECT email FROM orgs WHERE id = :oid"), {"oid": org_id}).fetchone()
    account_email = user_row.email if user_row else None

    issues = db.execute(
        text("""
            SELECT ji.id, ji.issue_id, ji.issue_key, ji.summary,
                   ji.assignee_person_id, ji.status, ji.priority,
                   ji.updated_at, ji.is_terminal
            FROM jira_issues ji
            WHERE ji.org_id = :oid
              AND ji.assignee_person_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM interactions i
                  WHERE i.jira_issue_id = ji.issue_key
                    AND i.contact_id = ji.assignee_person_id
              )
            LIMIT 200
        """),
        {"oid": org_id},
    ).fetchall()

    created = 0
    for issue in issues:
        synthetic_msg_id = f"jira:{issue.issue_key}:{issue.assignee_person_id}"

        # Low weight — Jira is State Graph primary, not Relationship Graph
        db.execute(
            text("""
                INSERT INTO interactions (
                    id, org_id, contact_id, gmail_message_id,
                    account_email,
                    direction, subject, summary, sentiment,
                    interaction_at, source, interaction_type,
                    weight_score, signal_score, edge_weight_multiplier,
                    jira_issue_id
                )
                VALUES (
                    :id, :org_id, :contact_id, :gmail_message_id,
                    :account_email,
                    'bidirectional', :subject, :summary, 0.1,
                    COALESCE(:interaction_at, NOW()), 'jira', 'jira_issue',
                    0.3, 0.3, 1.0,
                    :issue_key
                )
                ON CONFLICT (jira_issue_id, contact_id)
                    WHERE jira_issue_id IS NOT NULL
                DO UPDATE SET
                    summary = EXCLUDED.summary,
                    interaction_at = EXCLUDED.interaction_at
            """),
            {
                "id": str(uuid4()),
                "org_id": org_id,
                "contact_id": str(issue.assignee_person_id),
                "gmail_message_id": synthetic_msg_id,
                "account_email": account_email,
                "subject": f"{issue.issue_key}: {issue.summary or ''}",
                "summary": f"Jira {issue.status}: {issue.issue_key} — {issue.summary or ''}",
                "interaction_at": issue.updated_at,
                "issue_key": issue.issue_key,
            },
        )
        created += 1

    logger.info(f"Jira bridge: created {created} issue interactions for org={org_id}")
    return created
