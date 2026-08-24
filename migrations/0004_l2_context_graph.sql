-- GeniOS Engine · L2 · Context Graph (Supabase/Postgres)
-- Laws: org_id on every table · every fact has provenance · versioned + reversible ·
-- identity deterministic-or-proposed · graph = projection of the L1 event stream.

-- Entities, time-versioned. Identity + stable display only; reason-worthy attributes
-- live in graph_facts, trivial display props in attributes jsonb (facts-vs-props).
create table if not exists graph_nodes (
    node_id                text not null,
    version                int  not null default 1,
    org_id                 text not null,
    node_type              text not null,               -- person | company | deal | meeting | ...
    canonical_key          text,                        -- deterministic identity key (email/domain/source-id)
    display_name           text,
    identity_strength      text not null default 'weak',-- strong | weak | proposed
    attributes             jsonb not null default '{}', -- flat display props (not versioned facts)
    valid_from             timestamptz not null default now(),
    valid_to               timestamptz,
    created_by_event_id    text,
    registry_snapshot_hash text,
    primary key (node_id, version)
);
create index if not exists graph_nodes_by_org  on graph_nodes (org_id, node_type);
create index if not exists graph_nodes_by_key  on graph_nodes (org_id, canonical_key);
create index if not exists graph_nodes_current  on graph_nodes (org_id, node_id) where valid_to is null;

-- provider/source object id → node_id (deterministic identity anchor)
create table if not exists source_identity_map (
    org_id           text not null,
    source           text not null,
    source_object_id text not null,
    node_id          text not null,
    created_at       timestamptz not null default now(),
    primary key (org_id, source, source_object_id)
);

-- Versioned attributes — only reason-worthy / authority-conflict / freshness fields.
create table if not exists graph_facts (
    fact_version_id   text primary key,
    fact_id           text not null,               -- stable across versions
    org_id            text not null,
    subject_node_id   text not null,
    field             text not null,
    value             jsonb not null,
    value_type        text not null default 'string',
    status            text not null default 'active',  -- active | candidate | superseded
    authority_rank    int  not null default 1,          -- R1..R4
    confidence        numeric(4,3) not null default 0.5,
    occurred_at       timestamptz,
    valid_from        timestamptz not null default now(),
    valid_to          timestamptz,
    freshness_policy_id text,
    visibility_scope  text not null default 'org',
    created_by_event_id text,
    created_at        timestamptz not null default now()
);
create index if not exists graph_facts_current on graph_facts (org_id, subject_node_id, field)
    where valid_to is null and status = 'active';
create index if not exists graph_facts_by_fact on graph_facts (org_id, fact_id);

-- Versioned relationships.
create table if not exists graph_edges (
    edge_version_id text primary key,
    edge_id         text not null,
    org_id          text not null,
    edge_type       text not null,
    from_node_id    text not null,
    to_node_id      text not null,
    authority_rank  int  not null default 1,
    confidence      numeric(4,3) not null default 0.5,
    valid_from      timestamptz not null default now(),
    valid_to        timestamptz,
    created_by_event_id text,
    created_at      timestamptz not null default now()
);
create index if not exists graph_edges_current on graph_edges (org_id, from_node_id, edge_type)
    where valid_to is null;

-- Evidence: every fact/edge/observation ties back to an exact L1 event + span.
create table if not exists graph_source_refs (
    source_ref_id     text primary key,
    org_id            text not null,
    fact_version_id   text,
    edge_version_id   text,
    observation_id    text,
    event_id          text not null,               -- → source_events
    source            text,
    source_object_id  text,
    source_field_path text,
    evidence          jsonb not null default '{}', -- {span:[s,e], text, page, bbox}
    independence_group text,
    extractor_version text,
    mapping_version   text,
    created_at        timestamptz not null default now()
);
create index if not exists source_refs_by_fact on graph_source_refs (org_id, fact_version_id);
create index if not exists source_refs_by_event on graph_source_refs (org_id, event_id);

-- Evidence-backed statements → L3 inputs (not alerts).
create table if not exists graph_observations (
    observation_id  text primary key,
    org_id          text not null,
    subject_node_id text,
    kind            text not null,
    occurred_at     timestamptz,
    confidence      numeric(4,3) not null default 0.5,
    status          text not null default 'active',
    created_by_event_id text,
    pack_id         text,
    pack_version    text,
    created_at      timestamptz not null default now()
);
create index if not exists observations_by_subject on graph_observations (org_id, subject_node_id);

-- Fuzzy identity candidates (human decides) + reversible merges.
create table if not exists merge_proposals (
    id             text primary key,
    org_id         text not null,
    left_node_id   text not null,
    right_node_id  text not null,
    evidence       jsonb not null default '{}',
    status         text not null default 'open',    -- open | merged | rejected
    created_at     timestamptz not null default now()
);
create index if not exists merge_proposals_open on merge_proposals (org_id, status);

create table if not exists merge_history (
    id              text primary key,
    org_id          text not null,
    survivor_node_id text not null,
    merged_node_id  text not null,
    snapshots       jsonb not null default '{}',
    reason          text,
    reversed        boolean not null default false,
    created_at      timestamptz not null default now()
);

-- Source disagreement (a product signal, not a silent overwrite).
create table if not exists discrepancies (
    id              text primary key,
    org_id          text not null,
    subject_node_id text not null,
    field           text not null,
    held            jsonb not null,
    challenger      jsonb not null,
    status          text not null default 'open',
    created_at      timestamptz not null default now()
);
create index if not exists discrepancies_open on discrepancies (org_id, status);

-- Monotonic version per tenant + transactional change publish (outbox).
create table if not exists graph_versions (
    org_id        text primary key,
    graph_version bigint not null default 0,
    updated_at    timestamptz not null default now()
);

create table if not exists graph_change_outbox (
    change_id     text primary key,
    org_id        text not null,
    graph_version bigint not null,
    cause_event_id text,
    payload       jsonb not null,
    published_at  timestamptz,
    created_at    timestamptz not null default now()
);
create index if not exists change_outbox_unpublished on graph_change_outbox (org_id)
    where published_at is null;

-- Projection read models (compact stable contract for L3/dashboard/cards).
create table if not exists context_read_models (
    org_id        text not null,
    model_type    text not null,               -- company_360 | person_360 | deal_360 | ...
    entity_id     text not null,
    payload       jsonb not null default '{}',
    graph_version bigint,
    built_at      timestamptz not null default now(),
    primary key (org_id, model_type, entity_id)
);

-- Immutable extraction cache (replay) — same input+model → reuse, no re-call.
create table if not exists l2_extraction_results (
    processing_key text primary key,           -- hash(content + model + prompt version)
    org_id         text not null,
    event_id       text not null,
    output         jsonb not null,
    input_tokens   int not null default 0,
    output_tokens  int not null default 0,
    model_snapshot text,
    created_at     timestamptz not null default now()
);
create index if not exists extraction_by_event on l2_extraction_results (org_id, event_id);

-- LLM cost attribution (per org) — feeds budgets/visibility (fixes the V2 cost gap).
create table if not exists llm_costs (
    id            bigserial primary key,
    org_id        text not null,
    model         text not null,
    purpose       text not null default 'extract',
    input_tokens  int not null default 0,
    output_tokens int not null default 0,
    success       boolean not null default true,
    error         text,
    event_id      text,
    created_at    timestamptz not null default now()
);
create index if not exists llm_costs_by_org on llm_costs (org_id, created_at);
