-- Phase 2.1: Enable Row-Level Security on all tenant tables.
--
-- The backend connects as `postgres` (superuser) which BYPASSES RLS.
-- This protects against:
--   1. Direct Supabase REST API access with anon/authenticated keys
--   2. Supabase Dashboard "SQL Editor" access by non-admin team members
--   3. Any future API that uses the authenticated role
--
-- Policy: authenticated users can only see rows where org_id matches
-- their JWT claim `auth.uid()`. Service role bypasses everything.
--
-- Safe to run multiple times (IF NOT EXISTS / OR REPLACE).

-- Helper: enable RLS + create policy for a table with org_id
DO $$
DECLARE
    t TEXT;
    tables_with_org TEXT[] := ARRAY[
        'activity_log', 'agent_sessions', 'api_keys',
        'authority_assignments', 'authority_permissions', 'authority_roles',
        'budget_state',
        'calendar_event_attendees', 'calendar_events', 'calendar_sync_state',
        'co_attendance', 'commitments', 'communities', 'companies',
        'contact_facts', 'contacts', 'context_calls', 'context_outcomes',
        'context_requests',
        'daily_snapshots', 'document_chunks',
        'gdocs_chunks', 'gdocs_comments', 'gdocs_connections',
        'gdocs_contracts', 'gdocs_documents', 'gdocs_policy_rules', 'gdocs_proposals',
        'gdrive_access_expiry_state', 'gdrive_activity', 'gdrive_change_log',
        'gdrive_connections', 'gdrive_files', 'gdrive_folder_structure',
        'gdrive_permissions', 'gdrive_shared_drive_members', 'gdrive_shared_drives',
        'graph_intelligence_dimensions', 'graph_intelligence_reports', 'graph_segments',
        'hubspot_tokens',
        'insights', 'interactions',
        'jira_connections', 'jira_issues', 'jira_project_config', 'jira_sprints', 'jira_user_cache',
        'merge_queue',
        'notion_connections', 'notion_meeting_notes', 'notion_page_chunks',
        'notion_pages', 'notion_policy_rules',
        'oauth_tokens', 'org_members',
        'outcome_events',
        'precedent_graph', 'precomputed_bundles',
        'refresh_jobs', 'registered_agents',
        'seat_invites', 'segment_members',
        'sheets_column_mappings', 'sheets_connections', 'sheets_policy_rules',
        'sheets_rows', 'sheets_spreadsheets', 'sheets_tab_config',
        'slack_channel_config', 'slack_messages', 'slack_tokens',
        'slack_user_cache', 'slack_workspaces',
        'state_entities', 'state_events',
        'upcoming_meetings', 'webhook_events'
    ];
BEGIN
    FOREACH t IN ARRAY tables_with_org LOOP
        -- Enable RLS (idempotent)
        EXECUTE format('ALTER TABLE IF EXISTS %I ENABLE ROW LEVEL SECURITY', t);

        -- Drop existing policy if any (for idempotency)
        EXECUTE format('DROP POLICY IF EXISTS org_isolation ON %I', t);

        -- Create policy: authenticated role scoped to org_id
        EXECUTE format(
            'CREATE POLICY org_isolation ON %I FOR ALL TO authenticated USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid)',
            t
        );
    END LOOP;
END
$$;

-- Special case: orgs table — users can only see their own org
ALTER TABLE IF EXISTS orgs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_self ON orgs;
CREATE POLICY org_self ON orgs FOR ALL TO authenticated
    USING (id = auth.uid()::uuid) WITH CHECK (id = auth.uid()::uuid);

-- Special case: subscriptions — scope to org_id if column exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscriptions' AND column_name = 'org_id') THEN
        ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS org_isolation ON subscriptions;
        CREATE POLICY org_isolation ON subscriptions FOR ALL TO authenticated
            USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);
    END IF;
END $$;
