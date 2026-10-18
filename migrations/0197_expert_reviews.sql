-- 0197 · expert_reviews — the expert's one review of a file, per fingerprint (STEP-12, the expert pass).
--
-- WHY. STEP-12 asks a strong model to judge a FILE — the whole piece of work — once each time the
-- file's fingerprint moves, never once per situation per sweep (`speedrun008/YC-II W27/` STEP-12
-- §8.4). To know it already judged this file on these inputs, and to replay that judgment without
-- the model, the review is kept: one row per (org, file, fingerprint), what the model wrote, what it
-- was shown (the dossier's digest), who wrote it (the model and the prompt version — `06` D48), what
-- it cost, and what came of it.
--
-- A REFUSAL IS A ROW (STEP-12 §8.4 item 4). Every status but `valid` carries its reason, so "why has
-- this file no review?" is one read, and a fingerprint that was refused is not asked again until the
-- file moves:
--
--   valid         the answer parsed and validated against its dossier (`contracts/expert_review`)
--   refused       it parsed and did not validate — the reason names each refusal
--   truncated     the answer was cut at the token ceiling (`03` F140) — never parsed into a review
--   over_budget   the org's spend for the day was spent (`06` D7: $2 a day) — no call was made
--   failed        the call, or the parse after its one repair, failed — the reason says how
--
-- Only a `valid` row may be read for a decision, and it always carries its review; a `refused` row
-- may keep what the model wrote, for the audit.
--
-- ⛔ NO FOREIGN KEY ON `file_id`. A file is its anchor node (`context/workstreams.File.file_id`), and
-- the graph versions and retires nodes; a review of a file since merged or retired is still the
-- record of what was judged.
--
-- WHY cost IS MICRO-DOLLARS AND AN INTEGER: the R-site ledger's discipline (0120) — a review costs
-- a few cents, and a float re-rounds differently on every worker.

create table if not exists expert_reviews (
    org_id          text        not null references orgs (id) on delete cascade,
    file_id         text        not null,

    --: The file's fingerprint (`reason/expert/fingerprint.py`) — its events, asks, whose move, quiet
    --: days and next meeting as rungs, the brief's and the playbook's versions, the verdicts on its
    --: people, and who decides.
    fingerprint     text        not null,

    model           text        not null,
    prompt_version  text        not null,
    dossier_digest  text        not null,

    status          text        not null,
    reason          text,
    review          jsonb,

    input_tokens    integer     not null default 0,
    output_tokens   integer     not null default 0,
    cost_micro_usd  bigint      not null default 0,

    reviewed_at     timestamptz not null,

    primary key (org_id, file_id, fingerprint),

    constraint expert_reviews_status_check
        check (status in ('valid', 'refused', 'truncated', 'over_budget', 'failed')),
    constraint expert_reviews_reason_check
        check (status = 'valid' or coalesce(btrim(reason), '') <> ''),
    constraint expert_reviews_valid_review_check
        check (status <> 'valid' or review is not null),
    constraint expert_reviews_cost_check
        check (input_tokens >= 0 and output_tokens >= 0 and cost_micro_usd >= 0)
);

-- "The latest review of this file" — the read model and the dossier's "what was judged before".
create index if not exists expert_reviews_latest
    on expert_reviews (org_id, file_id, reviewed_at desc);

-- "What did the expert do today, and what did it cost" — the pass's daily cap and the health check.
create index if not exists expert_reviews_by_day
    on expert_reviews (org_id, reviewed_at desc);

comment on table expert_reviews is
  'STEP-12: the expert''s one review of a file per fingerprint — the review, the dossier digest, the model and prompt version, its cost, and its status. A status other than valid carries its reason; only a valid row may be read for a decision.';
