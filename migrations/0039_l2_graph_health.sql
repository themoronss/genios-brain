-- GeniOS Engine · L2 · Graph Maintenance — keeping the picture trustworthy over time.
--
-- Steps 1–3 BUILD the graph. Nothing until now KEPT it. A graph that is only written to
-- accumulates broken edges, orphan nodes, facts nobody can trace and duplicates nobody
-- resolved — and none of that announces itself. It surfaces as reasoning that is subtly
-- wrong for reasons no one can locate.

-- Per-entity lifecycle. A SEPARATE table rather than columns on graph_nodes, because
-- graph_nodes is versioned (node_id, version) and lifecycle is a derived, rewritable
-- projection — the same split context_attention already uses, for the same reason.
--
-- THIS IS A LABEL, NEVER A FILTER. A dormant entity is still evaluated, every sweep. If
-- dormancy narrowed evaluation, a quiet entity would produce no signals, so it would
-- stay quiet, so it would stay dormant — and the customer who went silent, exactly the
-- one worth noticing, is the one the system would go blind to. Enforced by
-- tests/test_graph_health.py.
create table if not exists context_node_lifecycle (
    org_id            text not null,
    node_id           text not null,
    lifecycle         text not null default 'active',   -- active | dormant | archived
    -- Null means we have no DATED evidence, which is not the same as old. Such an entity
    -- stays active: treating absence as age would retire everything the moment a source
    -- stopped sending timestamps.
    last_evidence_at  timestamptz,
    computed_at       timestamptz not null default now(),
    primary key (org_id, node_id)
);
create index if not exists context_node_lifecycle_state
    on context_node_lifecycle (org_id, lifecycle, last_evidence_at desc);

-- Health over TIME. One health number says little; the same number falling across three
-- weeks says a connector broke, a merge went wrong, or correlation stopped reaching
-- anything. Append-only, so the trend survives.
create table if not exists graph_health (
    org_id      text not null,
    computed_at timestamptz not null default now(),
    -- MINIMUM of the measured dimensions, not their average — these are failure modes,
    -- and averaging lets the parts that work conceal the part that does not.
    overall     int not null,
    dimensions  jsonb not null default '{}',   -- integrity, evidence, coherence, …
    -- Which dimensions had anything behind them. An empty graph scores 100/"not
    -- measured", never 0 — a new tenant has not failed anything, and a health page that
    -- calls fresh accounts broken is a health page nobody reads.
    measured    jsonb not null default '{}',
    metrics     jsonb not null default '{}',   -- the raw counts behind the scores
    issues      jsonb not null default '[]',   -- structural problems found, with detail
    primary key (org_id, computed_at)
);
create index if not exists graph_health_recent on graph_health (org_id, computed_at desc);

alter table context_node_lifecycle drop constraint if exists context_node_lifecycle_org_cascade_fk;
alter table context_node_lifecycle add constraint context_node_lifecycle_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table graph_health drop constraint if exists graph_health_org_cascade_fk;
alter table graph_health add constraint graph_health_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

comment on table context_node_lifecycle is
  'Derived per-entity state (active/dormant/archived). A LABEL for ordering and reporting — it must never narrow what gets evaluated.';
comment on table graph_health is
  'Append-only graph quality measurements. Nothing is ever repaired automatically: an auto-fix that runs unattended turns a small inconsistency into silent data loss.';
