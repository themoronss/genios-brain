-- 0187 · `evidence_needs` — the one fact that would change the conclusion, asked for by name.
--
-- WHAT WAS WRONG. Layer 2 could only HOLD and wait. A situation missing its signed contract stayed
-- incomplete until some later sweep happened to bring the document in by luck. Meanwhile
-- `context/residue.py` was already computing the demand — `signal_unreached` measures "the Layer 1
-- verdicts no Layer 2 reading consumes" — and that number reached the model angles and stopped.
-- The measurement half existed; only the wire did not.
--
-- ⛔ `need_id` IS DETERMINISTIC OVER THE QUESTION AND ITS SUBJECT, and the primary key is what
-- makes that matter: the same need raised on two sweeps collapses to one row. Without it an unmet
-- need is re-raised every sweep and the queue grows forever — a table that measures how long the
-- system has been waiting rather than what it is waiting FOR.
--
-- ⛔ THREE STATES, AND `unavailable` IS THE ONE THAT MATTERS. A need that can never be met must
-- CLOSE, with a reason. One left open forever is a hold that can never clear — exactly the state
-- this table exists to end, re-created one layer down. The check constraint makes the reason
-- mandatory in that state, so a closure with no explanation cannot be written at all.
--
-- ⛔ AND `unacceptable_sources` IS A COLUMN, NOT A COMMENT. A vendor's quote email may not stand in
-- for a signed contract. Without the negative list persisted beside the positive one, an executor
-- that found something mentioning the right words would close the need, and Layer 2 would proceed
-- on evidence that cannot carry the claim — worse than the hold it replaced, because the hold at
-- least knew it was missing something.
--
-- Soft close, never delete: a met need is the record of a question that was answered, and it is
-- what makes "why did this situation finally resolve?" answerable months later.

create table if not exists evidence_needs (
    --: Deterministic over (org, question, subject). Re-raising is idempotent.
    need_id              text primary key,
    org_id               text        not null,
    --: Minted in L1 and unchanged to L6, so a need is joinable to the run that raised it.
    trace_id             text        not null,
    --: In words a person could act on. Not a code.
    question             text        not null,
    --: ⛔ Why it changes the decision. A need that cannot say this is not decision-relevant, and
    --: fetching for it spends a tenant's budget on curiosity.
    why_it_matters       text        not null,
    subject_ref          text,
    acceptable_sources   jsonb       not null default '[]'::jsonb,
    --: What would NOT settle it, however well it matches.
    unacceptable_sources jsonb       not null default '[]'::jsonb,
    window_from          timestamptz,
    window_to            timestamptz,
    --: An unbounded fetch is a backfill wearing a question's clothes.
    max_cost_usd         numeric(10, 4),
    --: After this the answer arrives too late to change anything, so it is not worth buying.
    expires_at           timestamptz,
    state                text        not null default 'open',
    --: The sentence a card shows instead of waiting.
    unavailable_reason   text,
    created_at           timestamptz not null default now(),
    closed_at            timestamptz,

    constraint evidence_needs_state_check
        check (state in ('open', 'met', 'unavailable')),
    -- A closure with no explanation cannot be written.
    constraint evidence_needs_unavailable_has_a_reason
        check (state <> 'unavailable'
               or (unavailable_reason is not null and length(trim(unavailable_reason)) > 0))
);

-- The executor's own read: this tenant's open needs, oldest first, so the longest-waiting
-- question is worked before the newest one.
create index if not exists evidence_needs_open_idx
    on evidence_needs (org_id, created_at)
    where state = 'open';

-- "Which needs is this situation waiting on?" — the card's read.
create index if not exists evidence_needs_subject_idx
    on evidence_needs (org_id, subject_ref);

-- Doc 07: a table that survives a tenant deletion is a compliance defect, and it is the kind that
-- is only discovered during an audit. `tests/test_account_erasure.py` enforces it.
alter table evidence_needs drop constraint if exists evidence_needs_org_cascade_fk;
alter table evidence_needs add constraint evidence_needs_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

comment on table evidence_needs is
  'L2 -> L1: one named fact, for one decision, with a cost limit and an expiry. Not a backfill: it '
  'records what would AND would not settle the question, and it closes as unavailable with a '
  'reason rather than waiting forever.';
