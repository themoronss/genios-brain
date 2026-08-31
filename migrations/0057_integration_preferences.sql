-- Per-org, per-tool source preferences (the Sources modal: Gmail, Google Calendar, ... connector
-- settings + toggles). The `connections` table is Composio-backed and often empty, so preferences
-- live here, keyed by the canonical (org_id, tool) so connect/sync/disconnect and this config all
-- agree. Durable: a reconnect or a process restart keeps the user's choices. Org-cascade so an
-- account erasure removes them too.
create table if not exists integration_preferences (
    org_id        text not null,
    tool          text not null,
    sync_settings jsonb       not null default '{}'::jsonb,
    preferences   jsonb       not null default '{}'::jsonb,
    domains       jsonb       not null default '[]'::jsonb,
    updated_at    timestamptz not null default clock_timestamp(),
    primary key (org_id, tool),
    constraint integration_preferences_org_cascade_fk
        foreign key (org_id) references orgs (id) on delete cascade
);
