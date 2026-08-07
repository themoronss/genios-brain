-- GeniOS Engine · L2 · Correlation Engine — signals that describe ONE situation.
--
-- Four systems report one reality: Slack "need pricing approval", email "customer is
-- waiting", calendar "Pricing Review tomorrow", CRM "Enterprise deal". Until now those
-- were four unrelated events. These tables record that they are one thing.
--
-- A correlation is a GROUP, not a pairwise link. Pairwise would be O(n²) rows and O(n²)
-- comparisons; grouping by a deterministic key is one lookup per event and stays cheap
-- at enterprise volume.

create table if not exists context_correlations (
    correlation_id text primary key,
    org_id         text not null,
    -- What the situation is ABOUT. A node, so an entity merge repoints it (the merge
    -- engine lists this column) and a situation survives learning that two customers
    -- were one customer.
    anchor_node_id text not null,
    anchor_type    text not null default 'company',   -- deal | company | person
    domain         text not null default 'general',   -- from L1's deterministic hints
    -- A conversation that went silent past the window and restarted is a NEW situation,
    -- not a continuation. Generations keep the old one findable instead of overwritten.
    generation     int  not null default 1,
    first_event_at timestamptz,
    last_event_at  timestamptz,
    event_count    int  not null default 0,
    status         text not null default 'open',      -- open | dormant
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),
    -- One live group per (anchor, domain, generation). This is also the concurrency
    -- guard: L2 drains with several workers, and without it two workers processing two
    -- events for the same customer at the same moment would each open generation 2.
    unique (org_id, anchor_node_id, domain, generation)
);
create index if not exists context_correlations_by_anchor
    on context_correlations (org_id, anchor_node_id, domain, generation desc);
create index if not exists context_correlations_open
    on context_correlations (org_id, status, last_event_at desc);

-- Many-to-many ON PURPOSE. An introduction email naming two companies belongs to two
-- situations; forcing one row per event would silently drop one of them.
create table if not exists context_correlation_members (
    org_id         text not null,
    correlation_id text not null,
    event_id       text not null,
    -- WHY this event was grouped: 'thread' (it continued a conversation) or 'anchor'
    -- (it named a known entity). Without this a wrong grouping is unexplainable after
    -- the fact — you can see two events were joined but not what joined them.
    joined_via     text not null default 'anchor',
    joined_at      timestamptz not null default now(),
    -- Idempotent membership: replaying an event must not double a situation's evidence.
    primary key (org_id, correlation_id, event_id)
);
create index if not exists correlation_members_by_event
    on context_correlation_members (org_id, event_id);

-- Tenant erasure complete by schema, not by an application list (tests enforce this).
alter table context_correlations drop constraint if exists context_correlations_org_cascade_fk;
alter table context_correlations add constraint context_correlations_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table context_correlation_members
    drop constraint if exists context_correlation_members_org_cascade_fk;
alter table context_correlation_members add constraint context_correlation_members_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

comment on table context_correlations is
  'Groups of events that describe one business situation. Anchored on (entity, domain); a thread joins events across anchors. Merges reality only — never priority, risk or recommendation.';
