-- GeniOS Engine · L2 Context Intelligence upgrade.
--   1. graph_facts.relevance — the LLM's interest score, stored SEPARATELY from
--      confidence. Confidence becomes deterministic (authority-rank derived) and is the
--      only thing the L3 gate reads; relevance ranks, it never gates. Before this, the
--      model's relevance float WAS fact confidence → fed engine ext_conf → C → c_min:
--      an LLM mood decided whether signals fired.
--   2. graph_edges interaction state — count + last_seen turn the boolean adjacency
--      list into a relationship graph ("how deep, how recent"), the substrate for
--      relationship_stage and attention.
--   3. context_attention — the Attention component: per-node "look here first" ranking
--      written by L2. It ORDERS retrieval; it never gates evaluation (enforced by test).
-- All statements idempotent.

alter table graph_facts add column if not exists relevance real;

alter table graph_edges add column if not exists interaction_count int not null default 1;
alter table graph_edges add column if not exists last_seen_at timestamptz;
-- initialize last_seen_at for existing edges from their valid_from
update graph_edges set last_seen_at = valid_from where last_seen_at is null;

create table if not exists context_attention (
    org_id       text not null,
    node_id      text not null,
    score        int  not null default 0,          -- integer 0..100, deterministic
    band         text not null default 'low',      -- critical | high | medium | low
    inputs       jsonb,                            -- the arithmetic behind the score
    computed_at  timestamptz not null default now(),
    primary key (org_id, node_id)
);
create index if not exists context_attention_rank on context_attention (org_id, score desc);
