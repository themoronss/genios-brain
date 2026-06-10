-- DROP every v1 table before applying v2 migrations 0001..0011.
-- Generated from _legacy/migrations/*.sql — 105 tables total.
--
-- v1/v2 collisions (table names that exist in BOTH): insights, agent_sessions,
-- registered_agents, policy_rules, llm_usage, activity_log. These get dropped
-- here and re-created by v2 migrations with the new (correct) schemas.
--
-- ASSUMPTION (per user): customer base is small + we are not preserving v1
-- data. If you need a backup, take it BEFORE running this script.
--
-- Usage (via wrapper):
--     venv/bin/python -m scripts.wipe_v1_and_migrate --confirm
--
-- Or directly:
--     psql "$DATABASE_URL" -f scripts/drop_v1_tables.sql

BEGIN;

DROP TABLE IF EXISTS action_ledger CASCADE;
DROP TABLE IF EXISTS activity_log CASCADE;
DROP TABLE IF EXISTS agent_account_grants CASCADE;
DROP TABLE IF EXISTS agent_activity_log CASCADE;
DROP TABLE IF EXISTS agent_scopes CASCADE;
DROP TABLE IF EXISTS agent_sessions CASCADE;
DROP TABLE IF EXISTS agent_trust CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS approvals_queue CASCADE;
DROP TABLE IF EXISTS authority_assignments CASCADE;
DROP TABLE IF EXISTS authority_permissions CASCADE;
DROP TABLE IF EXISTS authority_roles CASCADE;
DROP TABLE IF EXISTS budget_state CASCADE;
DROP TABLE IF EXISTS calendar_event_attendees CASCADE;
DROP TABLE IF EXISTS calendar_events CASCADE;
DROP TABLE IF EXISTS calendar_sync_state CASCADE;
DROP TABLE IF EXISTS calibration_models CASCADE;
DROP TABLE IF EXISTS co_attendance CASCADE;
DROP TABLE IF EXISTS commitments CASCADE;
DROP TABLE IF EXISTS communities CASCADE;
DROP TABLE IF EXISTS companies CASCADE;
DROP TABLE IF EXISTS connector_credentials CASCADE;
DROP TABLE IF EXISTS contact_anomalies CASCADE;
DROP TABLE IF EXISTS contact_baselines CASCADE;
DROP TABLE IF EXISTS contact_facts CASCADE;
DROP TABLE IF EXISTS contacts CASCADE;
DROP TABLE IF EXISTS context_calls CASCADE;
DROP TABLE IF EXISTS context_outcomes CASCADE;
DROP TABLE IF EXISTS context_requests CASCADE;
DROP TABLE IF EXISTS credit_ledger CASCADE;
DROP TABLE IF EXISTS daily_snapshots CASCADE;
DROP TABLE IF EXISTS delivery_attempts CASCADE;
DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS engagement_health CASCADE;
DROP TABLE IF EXISTS entity_aliases CASCADE;
DROP TABLE IF EXISTS event_log CASCADE;
DROP TABLE IF EXISTS fact_type_mapping CASCADE;
DROP TABLE IF EXISTS feature_flags CASCADE;
DROP TABLE IF EXISTS feedback_episodes CASCADE;
DROP TABLE IF EXISTS gdocs_chunks CASCADE;
DROP TABLE IF EXISTS gdocs_comments CASCADE;
DROP TABLE IF EXISTS gdocs_connections CASCADE;
DROP TABLE IF EXISTS gdocs_contracts CASCADE;
DROP TABLE IF EXISTS gdocs_documents CASCADE;
DROP TABLE IF EXISTS gdocs_policy_rules CASCADE;
DROP TABLE IF EXISTS gdocs_proposals CASCADE;
DROP TABLE IF EXISTS gdrive_access_expiry_state CASCADE;
DROP TABLE IF EXISTS gdrive_activity CASCADE;
DROP TABLE IF EXISTS gdrive_change_log CASCADE;
DROP TABLE IF EXISTS gdrive_connections CASCADE;
DROP TABLE IF EXISTS gdrive_files CASCADE;
DROP TABLE IF EXISTS gdrive_folder_structure CASCADE;
DROP TABLE IF EXISTS gdrive_permissions CASCADE;
DROP TABLE IF EXISTS gdrive_shared_drive_members CASCADE;
DROP TABLE IF EXISTS gdrive_shared_drives CASCADE;
DROP TABLE IF EXISTS graph_intelligence_dimensions CASCADE;
DROP TABLE IF EXISTS graph_intelligence_reports CASCADE;
DROP TABLE IF EXISTS graph_segments CASCADE;
DROP TABLE IF EXISTS ingest_events CASCADE;
DROP TABLE IF EXISTS insights CASCADE;
DROP TABLE IF EXISTS interactions CASCADE;
DROP TABLE IF EXISTS jira_connections CASCADE;
DROP TABLE IF EXISTS jira_issues CASCADE;
DROP TABLE IF EXISTS jira_project_config CASCADE;
DROP TABLE IF EXISTS jira_sprints CASCADE;
DROP TABLE IF EXISTS jira_user_cache CASCADE;
DROP TABLE IF EXISTS llm_usage CASCADE;
DROP TABLE IF EXISTS merge_queue CASCADE;
DROP TABLE IF EXISTS notion_connections CASCADE;
DROP TABLE IF EXISTS notion_meeting_notes CASCADE;
DROP TABLE IF EXISTS notion_page_chunks CASCADE;
DROP TABLE IF EXISTS notion_pages CASCADE;
DROP TABLE IF EXISTS notion_policy_rules CASCADE;
DROP TABLE IF EXISTS oauth_tokens CASCADE;
DROP TABLE IF EXISTS org_members CASCADE;
DROP TABLE IF EXISTS org_okr_state CASCADE;
DROP TABLE IF EXISTS orgs CASCADE;
DROP TABLE IF EXISTS outcome_events CASCADE;
DROP TABLE IF EXISTS pending_alerts CASCADE;
DROP TABLE IF EXISTS personal_baselines CASCADE;
DROP TABLE IF EXISTS policy_rules CASCADE;
DROP TABLE IF EXISTS precedent_graph CASCADE;
DROP TABLE IF EXISTS precedent_situations CASCADE;
DROP TABLE IF EXISTS precomputed_bundles CASCADE;
DROP TABLE IF EXISTS recommendations CASCADE;
DROP TABLE IF EXISTS refresh_jobs CASCADE;
DROP TABLE IF EXISTS registered_agents CASCADE;
DROP TABLE IF EXISTS seat_invites CASCADE;
DROP TABLE IF EXISTS segment_members CASCADE;
DROP TABLE IF EXISTS sheets_column_mappings CASCADE;
DROP TABLE IF EXISTS sheets_connections CASCADE;
DROP TABLE IF EXISTS sheets_policy_rules CASCADE;
DROP TABLE IF EXISTS sheets_rows CASCADE;
DROP TABLE IF EXISTS sheets_spreadsheets CASCADE;
DROP TABLE IF EXISTS sheets_tab_config CASCADE;
DROP TABLE IF EXISTS slack_channel_config CASCADE;
DROP TABLE IF EXISTS slack_messages CASCADE;
DROP TABLE IF EXISTS slack_user_cache CASCADE;
DROP TABLE IF EXISTS slack_workspaces CASCADE;
DROP TABLE IF EXISTS state_entities CASCADE;
DROP TABLE IF EXISTS state_events CASCADE;
DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS upcoming_meetings CASCADE;
DROP TABLE IF EXISTS webhook_config CASCADE;
DROP TABLE IF EXISTS webhook_events CASCADE;

-- Clear alembic state too so v2 migrations 0001..0011 run cleanly from scratch.
DROP TABLE IF EXISTS alembic_version CASCADE;

COMMIT;
