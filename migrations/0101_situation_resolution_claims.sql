-- GeniOS Engine · L2.7.7-U1 (M-4) — RESOLUTION CLAIMS: the third way a situation can end.
--
-- Until this table existed a situation could end exactly two ways: a CRM stage moving to
-- closed-won (`RESOLVED_BY_FACT`) or a person clicking "handled" (`RESOLVED_BY_HUMAN`). One
-- field, one source, two values. So "all sorted, we signed yesterday" landed as fresh activity,
-- bumped `last_seen_at`, and made the situation look MORE alive than it had before anyone said
-- it was over — which is how a product becomes a nagging machine and how a founder ends up being
-- told about a contract they cancelled last week.
--
-- WHY A LEDGER AND NOT A COLUMN ON `context_situations`. Three reasons, and each of them is a
-- behaviour the plan requires rather than a preference:
--
--   1. RE-DERIVATION. `RESOLVED_BY_STATEMENT` is reversible BY DESIGN — recomputed on every
--      drain, exactly like the fact path, so a contradiction un-resolves it with no human in the
--      loop. Recomputing needs the claims to still be there; a status column remembers the
--      answer and forgets the evidence.
--   2. LATEST STATEMENT WINS. "done" … "actually not yet" is only decidable if BOTH statements
--      are stored with the time each was WRITTEN (`stated_at`, not `created_at` — a backfill
--      that reads a thread out of order must reach the same answer as a live drain).
--   3. NO CLAIM WITHOUT A RECEIPT. Every row carries the verbatim quote, its offsets and the
--      ALG-08 grade that verified it against the source. "Why did this close?" is answerable
--      from the row, and "why did this one only reach the queue?" is answerable from the same
--      row, which is what makes the confidence floor auditable rather than decorative.
--
-- THIS TABLE IS ALSO THE COST CONTROL. One row per (situation, event) is what stops the next
-- drain from paying to re-read a message we have already read — including the messages that said
-- nothing, which is why a `reject` is stored rather than dropped. The two daily ceilings doc 11
-- names (3 calls per situation, 200 per org) are counted off `created_at` here.
--
-- WHAT IS DELIBERATELY *NOT* STORED: a model-authored score. `certainty` is one of four
-- documented bands the model chose, and every `_bp` column below was computed by
-- `context/lifecycle/judge.py` from that band and the speaker-authority table.
-- `raw_confidence_bp` is the exception that proves it: it is whatever number a model volunteered,
-- kept only so the ledger can be cut by it later, and read by nothing that decides.

create table if not exists situation_resolution_claims (
    claim_id        text primary key,
    org_id          text not null references orgs (id) on delete cascade,
    situation_id    text not null,
    -- The message that carried the statement. The pair below is the idempotence key AND the
    -- cache: a message is judged once per situation, ever.
    event_id        text not null,

    -- WHEN THE SENTENCE WAS WRITTEN, not when we read it. `ledger.derive_statement_state` orders
    -- on this, so "latest wins" means latest in the world rather than latest in our queue.
    stated_at       timestamptz not null,

    -- What the model DESCRIBED (verdict, certainty band) and what deterministic code CONCLUDED
    -- (everything below `scope`). The applied verdict is stored: a RESOLVED that covered 3 of 5
    -- obligations is written here as PARTIALLY_RESOLVED, with the downgrade named in `reason`.
    verdict         text not null,        -- RESOLVED | PARTIALLY_RESOLVED | NOT_RESOLVED | CONTRADICTED
    certainty       text not null,        -- EXPLICIT_COMPLETION | IMPLIED_COMPLETION | INTENT_ONLY | AMBIGUOUS
    scope           jsonb not null default '[]'::jsonb,   -- obligation ids, or ['situation']

    -- WHO SAID IT. The role is derived from the sender's identity — never from the model's
    -- reading of the prose — and it is stored beside the weight because 6000 bp from "external
    -- counterparty" and 6000 bp from anything else would otherwise be the same integer with two
    -- meanings.
    speaker_email   text,
    speaker_role    text not null,        -- owner | internal | external | machine
    authority_bp    integer not null,     -- 10000 | 8000 | 6000  (doc 07's 1.0 / 0.8 / 0.6)
    certainty_bp    integer not null,     -- the band, after ALG-08's span-grade penalty
    effective_bp    integer not null,     -- certainty_bp * authority_bp / 10000, integer division

    -- THE RECEIPT.
    quote           text,
    source_ref      text,
    start_offset    integer,
    end_offset      integer,
    span_verdict    text,                 -- ALG-08's grade: verified | ..._relocated | ..._fuzzy

    -- THE DECISION, and why. `reason` is prose on purpose: it is read by a human in the review
    -- queue and by whoever asks, six weeks later, why a live thread went quiet.
    decision        text not null,        -- apply | review | reject
    reason          text not null,

    -- THE HUMAN REVIEW QUEUE (doc 12, cross-cutting rule 7: below the floor is a queue, never a
    -- card). NULL for anything that never entered it.
    review_state    text,                 -- pending | accepted | dismissed
    reviewed_at     timestamptz,
    reviewed_by     text,

    -- Reproducibility. A claim whose prompt version is unknown cannot be re-derived, only
    -- re-guessed — the same reason `importance_version` sits on `context_situations`.
    prompt_version  text not null,
    schema_version  text not null,
    model           text,
    raw_confidence_bp integer,            -- volunteered by the model; never compared to anything

    created_at      timestamptz not null default now(),

    -- One judgement per message per situation. This is the idempotence rule and the cache key.
    unique (org_id, situation_id, event_id),
    constraint situation_resolution_claims_bp check (
        authority_bp between 0 and 10000 and certainty_bp between 0 and 10000
        and effective_bp between 0 and 10000)
);

-- The ledger read: every claim on one situation, oldest first. `derive_statement_state` runs on
-- every drain for every situation that has claims, so this is the hot path.
create index if not exists situation_resolution_claims_by_situation
    on situation_resolution_claims (org_id, situation_id, stated_at);
-- The two daily budget counts (doc 11: 3 per situation, 200 per org).
create index if not exists situation_resolution_claims_by_day
    on situation_resolution_claims (org_id, created_at);
-- The queue's own read, and only the rows that are in it.
create index if not exists situation_resolution_claims_pending
    on situation_resolution_claims (org_id, review_state)
    where review_state = 'pending';

comment on table situation_resolution_claims is
  'M-4 resolution claims — one judgement per (situation, message): what the model described, what the speaker-authority table and the confidence floor concluded, and the verbatim quote that verified against source. Re-read every drain, which is what makes a stated resolution reversible.';
