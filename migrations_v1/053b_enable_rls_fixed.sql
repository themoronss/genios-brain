-- Phase 2.1 (retry): Enable RLS per-table with error isolation.
-- Each table is handled in its own subtransaction so one failure
-- doesn't roll back the rest.

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
        'oauth_tokens', 'org_members', 'org_okr_state',
        'outcome_events',
        'precedent_graph', 'precomputed_bundles',
        'refresh_jobs', 'registered_agents',
        'sheets_column_mappings', 'sheets_connections', 'sheets_policy_rules',
        'sheets_rows', 'sheets_spreadsheets', 'sheets_tab_config',
        'slack_channel_config', 'slack_messages', 'slack_tokens',
        'slack_user_cache', 'slack_workspaces',
        'state_entities', 'state_events',
        'upcoming_meetings', 'webhook_events'
    ];
    success_count INT := 0;
    skip_count INT := 0;
BEGIN
    FOREACH t IN ARRAY tables_with_org LOOP
        BEGIN
            -- Check if org_id column actually exists on this table
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = t AND column_name = 'org_id'
            ) THEN
                RAISE NOTICE 'SKIP %: no org_id column', t;
                skip_count := skip_count + 1;
                CONTINUE;
            END IF;

            EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
            EXECUTE format('DROP POLICY IF EXISTS org_isolation ON %I', t);
            EXECUTE format(
                'CREATE POLICY org_isolation ON %I FOR ALL TO authenticated USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid)',
                t
            );
            success_count := success_count + 1;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'FAIL %: %', t, SQLERRM;
        END;
    END LOOP;
    RAISE NOTICE 'RLS enabled on % tables, % skipped', success_count, skip_count;
END
$$;

-- orgs table: scope to own org
ALTER TABLE IF EXISTS orgs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_self ON orgs;
CREATE POLICY org_self ON orgs FOR ALL TO authenticated
    USING (id = auth.uid()::uuid) WITH CHECK (id = auth.uid()::uuid);
