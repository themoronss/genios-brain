-- GeniOS Engine · L3 · Reasoning (signals). No LLM here — deterministic rules + integer
-- basis-point scoring over the L2 graph. Every emitted signal carries score.inputs (so the
-- Evidence Explorer shows arithmetic, not vibes); every suppression is logged with a reason
-- code (Law 5 — silence has receipts). eval_time recorded for byte-identical replay.

create table if not exists signals (
    signal_id       text primary key,
    org_id          text not null,
    rule_id         text not null,
    rule_version    int  not null default 1,
    level           text not null default 'prescriptive',   -- descriptive|diagnostic|predictive|prescriptive
    subject_node_id text not null,
    score           int  not null,                           -- S, integer points (0..100)
    score_inputs    jsonb not null default '{}',             -- {U,I,R,C, terms}
    reason_code     text not null,
    evidence        jsonb not null default '[]',             -- the facts that justify it
    play            text,
    status          text not null default 'open',            -- open|acted|snoozed|expired
    eval_time       timestamptz not null,
    created_at      timestamptz not null default now()
);
create index if not exists signals_open on signals (org_id, status, score desc);
create index if not exists signals_dedup on signals (org_id, rule_id, subject_node_id);

-- Suppression log — why a detected signal did NOT become a card (below_gate|budget|cooldown|muted|shadow).
create table if not exists signal_suppression_log (
    id              bigserial primary key,
    org_id          text not null,
    rule_id         text not null,
    subject_node_id text not null,
    reason_code     text not null,                           -- below_gate|budget|cooldown|muted|shadow
    detail          jsonb not null default '{}',
    eval_time       timestamptz not null,
    created_at      timestamptz not null default now()
);
create index if not exists suppression_by_rule on signal_suppression_log (org_id, rule_id, created_at);
