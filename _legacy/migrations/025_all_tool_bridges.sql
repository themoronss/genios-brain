-- Migration 025: Idempotent indexes for all tool bridge interactions
-- Run: psql $DATABASE_URL -f migrations/025_all_tool_bridges.sql

-- Slack: one interaction per contact per message
CREATE UNIQUE INDEX IF NOT EXISTS idx_interactions_slack_contact
  ON interactions(slack_channel_id, slack_message_ts, contact_id)
  WHERE slack_channel_id IS NOT NULL AND slack_message_ts IS NOT NULL;

-- Drive: one interaction per contact per file share
CREATE UNIQUE INDEX IF NOT EXISTS idx_interactions_drive_contact
  ON interactions(gdrive_file_id, contact_id)
  WHERE gdrive_file_id IS NOT NULL;

-- Docs: one interaction per contact per document
CREATE UNIQUE INDEX IF NOT EXISTS idx_interactions_docs_contact
  ON interactions(gdocs_document_id, contact_id)
  WHERE gdocs_document_id IS NOT NULL;

-- Jira: add jira FK column to interactions if not exists
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS jira_issue_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_interactions_jira_contact
  ON interactions(jira_issue_id, contact_id)
  WHERE jira_issue_id IS NOT NULL;

-- Update interaction_type check to include new types
ALTER TABLE interactions DROP CONSTRAINT IF EXISTS interactions_interaction_type_check;
ALTER TABLE interactions ADD CONSTRAINT interactions_interaction_type_check
  CHECK (interaction_type IN (
    'email_reply', 'email_one_way', 'commitment', 'meeting', 'other',
    'cc', 'slack_dm', 'slack_mention', 'jira_issue', 'file_shared', 'doc_shared'
  ));
