-- 0015 — intelligence decisions ledger. Every /v1/intelligence/query result (an Envelope) is
-- persisted here for explain (derivation trace), feedback (L6 calibration), and the decision cache
-- (repeat question on an unchanged graph → serve the stored Envelope, zero LLM).
create table if not exists decisions (
    decision_id    text primary key,
    org_id         text not null,
    module_id      text not null default 'sales',
    question       text,
    envelope       jsonb not null,          -- the full Envelope returned to the caller
    confidence     numeric,
    route          text,
    graph_version  integer,
    cache_key      text,                    -- sha256(org | module | normalized_question | graph_version)
    triggered_by   text not null default 'query',
    created_at     timestamptz not null default now()
);

create index if not exists ix_decisions_org   on decisions (org_id, created_at desc);
create index if not exists ix_decisions_cache on decisions (cache_key);
