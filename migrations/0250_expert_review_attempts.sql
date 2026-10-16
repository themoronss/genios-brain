-- 0250 · expert_review_attempts — every rung's consult of a file, and the rung whose review stands (STEP-13b).
--
-- WHY. The expert's review of a file goes up a LADDER of models (`reason/expert/ladder`): the cheapest rung
-- first (Haiku-class); an answer that fails the check for the writer's own fault is asked ONCE more on its rung
-- with the check's verdicts; only a repaired answer that still fails climbs to the next (Sonnet-class, then
-- Opus-class when the tenant allows it — s13b-D1). `expert_reviews` (0197) keeps the one review that STANDS; this
-- table keeps every consult that led to it, so a scorecard can say which rung answered, what each cost and why the
-- others did not — "every attempt kept and counted" (`speedrun008/YC-II W27/` STEP-13b §8.4 item 5).
--
--   consult         first   the rung's first ask
--                   repair  the same rung asked again with the check's verdicts (crosscheck X32, s13b-D4)
--   status          as expert_reviews: valid · refused · truncated · over_budget · failed
--   fate            the check's fate of a valid answer: shown · held · suppressed · refused (null before a check)
--   climbed_because the writer's fault that sent the file up a rung (null: this consult did not climb) — closed;
--                   the ladder's rule (`contracts/model_ladder`) is the one that names them
--
-- ⛔ NO FOREIGN KEY ON `file_id`, as expert_reviews: a file is its anchor node, and a retired node's consults are
-- still the record of what was asked. `expert_reviews.rung` is the rung whose review stands; NULL on a row from
-- before 0250, which reads as rung one.
--
-- ⛔ `/reset` ERASES IT (`api/account_routes._ORG_SCOPED_TABLES`); the tenant's deletion cascades.
-- ADDITIVE: one new table and one nullable column; the previous image never names either.

create table if not exists expert_review_attempts (
    org_id           text        not null references orgs (id) on delete cascade,
    file_id          text        not null,
    fingerprint      text        not null,
    attempt_no       integer     not null,          -- 1, 2, 3 … in the order asked
    rung             integer     not null,          -- 1 = the cheapest
    model            text        not null,
    consult          text        not null,
    status           text        not null,
    fate             text,
    climbed_because  text,
    input_tokens     integer     not null default 0,
    output_tokens    integer     not null default 0,
    cost_micro_usd   bigint      not null default 0,
    attempted_at     timestamptz not null,

    primary key (org_id, file_id, fingerprint, attempt_no),

    constraint expert_review_attempts_no_check check (attempt_no >= 1),
    constraint expert_review_attempts_rung_check check (rung >= 1),
    constraint expert_review_attempts_model_check check (btrim(model) <> ''),
    constraint expert_review_attempts_consult_check check (consult in ('first', 'repair')),
    constraint expert_review_attempts_status_check
        check (status in ('valid', 'refused', 'truncated', 'over_budget', 'failed')),
    constraint expert_review_attempts_fate_check
        check (fate is null or fate in ('shown', 'held', 'suppressed', 'refused')),
    constraint expert_review_attempts_climbed_check
        check (climbed_because is null or climbed_because in (
               'malformed', 'truncated', 'nothing_stands', 'uncited', 'unknown_evidence', 'unquoted',
               'misquoted', 'unsupported', 'wrong_number', 'engine_is_no_fact', 'headline_failed',
               'recipient_is_us', 'recipient_is_connector')),
    constraint expert_review_attempts_cost_check
        check (input_tokens >= 0 and output_tokens >= 0 and cost_micro_usd >= 0)
);

-- "What was asked of this file, on this fingerprint" — the review that stands and the consults beside it.
create index if not exists expert_review_attempts_by_file
    on expert_review_attempts (org_id, file_id, fingerprint, attempt_no);

alter table expert_reviews add column if not exists rung integer;
alter table expert_reviews drop constraint if exists expert_reviews_rung_check;
alter table expert_reviews add constraint expert_reviews_rung_check check (rung is null or rung >= 1);

comment on table expert_review_attempts is
  'STEP-13b: every rung''s consult of a file on a fingerprint - its model, whether the first ask or the repair, its status, its check''s fate and the closed reason it climbed, tokens and cost. The review that stands is expert_reviews.';
comment on column expert_reviews.rung is
  'STEP-13b: the rung of the model ladder whose review stands (1 = the cheapest). Null on a row from before 0250: it reads as rung one.';
