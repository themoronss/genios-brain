"""Drop v1 content tables — memory is now thin per g-i-1 plan.

After all OAuth callbacks, Celery beat refresh, manual sync, webhooks, and
dashboard read endpoints were migrated to the v2 thin pipe, the v1 content
storage layer has zero readers and zero writers. Drop the tables.

KEEP (v1 auth + billing per plan):
  orgs, org_members, api_keys, oauth_tokens, subscriptions,
  credit_ledger, action_ledger, ... (anything plan §1 + §8 referenced)

DROP (v1 content + auto-classification):
  Per-source content tables (gmail/slack/jira/notion/gdocs/gdrive/sheets/calendar)
  + derived/auto-classified tables (contacts, contact_facts, interactions, etc.)

If a customer has v1 data they want to preserve, this migration should NOT
be applied in production until they're notified. Local/dev: drop freely.

Revision ID: 0015_drop_v1_content_tables
Revises: 0014_rename_insights
Create Date: 2026-06-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015_drop_v1_content_tables"
down_revision: str | None = "0014_rename_insights"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# v1 content + auto-classification tables. The v2 thin pipe writes nothing here.
V1_TABLES_TO_DROP = [
    # Email / interactions (v1 auto-classified during ingest)
    "interactions",
    "contact_facts",
    "event_log",
    "ingest_events",
    # Per-source content tables (v2 stores nothing source-shaped)
    "slack_messages",
    "slack_user_cache",
    "slack_channel_config",
    "slack_workspaces",
    "calendar_events",
    "calendar_event_attendees",
    "calendar_sync_state",
    "upcoming_meetings",
    "jira_issues",
    "jira_sprints",
    "jira_user_cache",
    "jira_project_config",
    "jira_connections",
    "notion_pages",
    "notion_page_chunks",
    "notion_meeting_notes",
    "notion_policy_rules",
    "notion_connections",
    "gdocs_documents",
    "gdocs_chunks",
    "gdocs_comments",
    "gdocs_contracts",
    "gdocs_proposals",
    "gdocs_policy_rules",
    "gdocs_connections",
    "gdrive_files",
    "gdrive_activity",
    "gdrive_change_log",
    "gdrive_folder_structure",
    "gdrive_permissions",
    "gdrive_shared_drives",
    "gdrive_shared_drive_members",
    "gdrive_access_expiry_state",
    "gdrive_connections",
    "sheets_rows",
    "sheets_tab_config",
    "sheets_column_mappings",
    "sheets_spreadsheets",
    "sheets_policy_rules",
    "sheets_connections",
    "document_chunks",
    # Derived / auto-classified entities (replaced by v2 graph_nodes/facts/edges)
    "contacts",
    "contact_anomalies",
    "contact_baselines",
    "companies",
    "communities",
    "segments",
    "segment_members",
    "graph_segments",
    "engagement_health",
    "personal_baselines",
    "daily_snapshots",
    # v1 detector / proactive (replaced by g-i-4 proactive_insights + g-i-2 decisions)
    "recommendations",
    "precomputed_bundles",
    "pending_alerts",
    "outcome_events",
    "feedback_episodes",
    "context_requests",
    "context_calls",
    "context_outcomes",
    "state_events",
    "state_entities",
    "entity_aliases",
    "fact_type_mapping",
    "co_attendance",
    "merge_queue",
    "calibration_models",
    "graph_intelligence_dimensions",
    "graph_intelligence_reports",
    "precedent_graph",
    "precedent_situations",
    "webhook_config",
    "webhook_events",
    "refresh_jobs",
    "delivery_attempts",
    "approvals_queue",
    "policy_rules",
    "activity_log",
    "agent_activity_log",
    "agent_account_grants",
    "llm_usage",
    "feature_flags",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite tests don't have these tables; nothing to do.
        return

    # CASCADE — drops dependent indexes/foreign keys cleanly.
    for table in V1_TABLES_TO_DROP:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade() -> None:
    # Not reversible — v1 ingestion code is gone, recreating empty tables
    # serves no purpose. To restore, re-run v1 SQL files manually.
    raise NotImplementedError(
        "v1 content tables are not restorable via alembic — re-run the original "
        "v1 SQL files in migrations_v1/ to recreate the schema (will be empty)."
    )
