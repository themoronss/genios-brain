-- Graph segments: named, typed groups of contacts (person/company graph nodes).
-- Ported from the v1 backend (graph_segments + segment_members) and adapted to the v2 model:
-- text org_id/node_id (not uuid), membership keyed on graph_nodes, no legacy `contacts` FK.

create table if not exists graph_segments (
    id                 text primary key,
    org_id             text not null references orgs(id) on delete cascade,
    name               text not null,
    cluster_type       text not null
        check (cluster_type in ('Investor','Customer','Team','Vendor','Admin','Other')),
    config             jsonb not null default '{}',
    sync_interval_hours int,
    last_synced_at     timestamptz,
    created_at         timestamptz not null default now()
);
create index if not exists graph_segments_org on graph_segments (org_id);

-- Membership join. node_id references the subject graph node (person/company); not FK-constrained
-- to graph_nodes because that table is version-composite (node_id, version) — ownership is checked
-- in the route against the current (valid_to is null) node instead.
create table if not exists segment_members (
    org_id     text not null references orgs(id) on delete cascade,
    segment_id text not null references graph_segments(id) on delete cascade,
    node_id    text not null,
    source     text not null default 'manual' check (source in ('auto','manual')),
    added_at   timestamptz not null default now(),
    added_by   text,
    primary key (segment_id, node_id)
);
create index if not exists segment_members_org_node on segment_members (org_id, node_id);
