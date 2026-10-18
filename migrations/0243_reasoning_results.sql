-- 0243 · reasoning_results — the Layer 2 judgment pass's output and receipt (GeniOS-008 L2 G1).
--
-- WHAT IT HOLDS. One row per (subject, fingerprint): what one run of the L2 judgment pass (R-9,
-- `reason/l2`) concluded about one subject — a file, or a bundle's own seed — and the receipt that lets
-- anyone replay it without a model: the request, the snapshot revision and expertise hash it read, the
-- depth and why, the groups run and skipped, the tool results, the model and prompt version, the
-- validation, the needs it raised, how it ended, the output hash, the cost.
--
-- ⛔ SHADOW. Nothing reads this table to make a card, a signal or a situation. It sits beside today's
-- path until the golden set says the new path is at least as good (speedrun008/GeniOS-008/01-RULES.md
-- Rule 2), and then one situation type switches at a time.
--
-- ⛔ THE FINGERPRINT IS THE CACHE. A subject whose inputs did not move since its last row is not
-- reasoned again — the row answers (`reason/l2/sweep`, the change gate). So the key is (org, subject,
-- fingerprint), and a replay of the same inputs is the same row.
--
-- `dossier` keeps the text and the ids the result was checked against, so a re-check under a newer check
-- version reads THAT dossier, never today's (the STEP-13 rule, `06` D48).
--
-- Idempotent: safe to run twice.

create table if not exists reasoning_results (
    org_id          text        not null,
    subject_ref     text        not null,
    fingerprint     text        not null,
    request_id      text        not null,
    trigger         text        not null,
    --: result | refused | failed | truncated | over_budget — `contracts/reasoning_result.ENDS` less
    --: `unchanged`, which writes no row.
    status          text        not null,
    reason          text,
    depth           text        not null,
    lane            text,
    lane_reason     text,
    result          jsonb,
    receipt         jsonb       not null default '{}'::jsonb,
    dossier         jsonb,
    model           text,
    prompt_version  text        not null,
    input_tokens    integer     not null default 0,
    output_tokens   integer     not null default 0,
    cost_micro_usd  bigint      not null default 0,
    bundle_ids      jsonb       not null default '[]'::jsonb,
    reasoned_at     timestamptz not null,
    created_at      timestamptz not null default now(),
    primary key (org_id, subject_ref, fingerprint),
    constraint reasoning_results_status_ck
        check (status in ('result', 'refused', 'failed', 'truncated', 'over_budget')),
    constraint reasoning_results_depth_ck
        check (depth in ('none', 'shallow', 'standard', 'deep')),
    constraint reasoning_results_lane_ck
        check (lane is null or lane in ('decision', 'investigation', 'conflict', 'monitor', 'suppress'))
);

-- The sweep's two reads: a subject's newest row, and a tenant's day of spend.
create index if not exists reasoning_results_subject_idx
    on reasoning_results (org_id, subject_ref, reasoned_at desc);
create index if not exists reasoning_results_org_day_idx
    on reasoning_results (org_id, reasoned_at desc);

-- A table that survives a tenant deletion is a compliance defect (0033's pattern).
alter table reasoning_results drop constraint if exists reasoning_results_org_cascade_fk;
alter table reasoning_results add constraint reasoning_results_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

comment on table reasoning_results is
  'GeniOS-008 L2: the judgment pass''s ReasoningResult and receipt per (subject, fingerprint). SHADOW: '
  'nothing reads it for a card, signal or situation until a situation type is switched.';
