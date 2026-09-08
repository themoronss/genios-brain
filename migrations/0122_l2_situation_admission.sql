-- L2.5.8 · one durable decision for every candidate attempting to cross L2 -> L3.
create table if not exists situation_admission_decisions (
    decision_id       text primary key,
    org_id            text not null references orgs (id) on delete cascade,
    situation_id      text not null,
    candidate_hash    text not null,
    outcome           text not null check (outcome in ('admit', 'hold', 'reject')),
    reasons           jsonb not null default '[]'::jsonb,
    candidate         jsonb not null,
    schema_version    text not null,
    decided_at        timestamptz not null,
    reevaluate_after  timestamptz,
    constraint situation_admission_hold_retry check (
        (outcome = 'hold' and reevaluate_after is not null)
        or (outcome <> 'hold' and reevaluate_after is null))
);

create unique index if not exists situation_admission_candidate_decision
    on situation_admission_decisions (org_id, situation_id, candidate_hash);
create index if not exists situation_admission_held
    on situation_admission_decisions (org_id, reevaluate_after)
    where outcome = 'hold';

comment on table situation_admission_decisions is
  'L2.5.8 publication gate ledger. Every L2->L3 candidate is ADMIT, HOLD or REJECT; held candidates remain retryable and non-admitted decisions expose no BSO to the caller.';
