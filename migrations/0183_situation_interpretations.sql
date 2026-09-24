-- GeniOS Engine · L2-5 · where a Context Reasoner reading lives, and how it is replayed.
--
-- ⛔ WHY A TABLE AND NOT FOUR COLUMNS ON `context_situations`.
--
-- L2-2 deferred `hypotheses`, `implications`, `reasoning_trace` and `valid_until` to this step
-- "with their writer", assuming four columns. Measured before building: the v2 situation object
-- is NEVER PERSISTED AS A ROW — `publish_situation` returns it in memory and only the admission
-- RECEIPT is stored. And an interpretation has its own lifecycle:
--
--   * it EXPIRES (`valid_until`) while the situation it reads does not;
--   * it is re-made on the next sweep, so there are MANY readings of one situation over time;
--   * a column would keep the latest and lose the history, which is the one thing an audit of
--     "why did GeniOS say that last Tuesday" needs.
--
-- So it sits beside `situation_admission_decisions` — the same pattern, for the same reason.
--
-- ⛔ AND IT PAYS L2-3's DEBT IN THE SAME PLACE. That step recorded: "the hash is stored, the slice
-- is not. A hash proves sameness and cannot reproduce the input — a fingerprint, not a record."
-- `context_slice` holds the bytes the reading was made from, so `reasoning_trace` points at a
-- conclusion whose premises are still there. Its only reader is a reasoner trace, which is why it
-- waited for this step rather than shipping empty in L2-3.

create table if not exists situation_interpretations (
    interpretation_id text primary key,
    -- ⛔ ON DELETE CASCADE, because `test_every_org_scoped_table_has_a_proven_account_delete_
    -- cascade` refused this table without it — and it was right to. An org-scoped table with no
    -- schema-enforced path to `orgs` is a table that survives an account erasure, which is a
    -- promise this product makes and a law it is held to.
    org_id            text not null references orgs (id) on delete cascade,
    situation_id      text not null,

    -- WHAT THE GATE WAS ASKED, and the key it was served under. Two sweeps over an unchanged
    -- slice must resolve to one row rather than paying twice, and this is what makes that
    -- checkable after the fact instead of trusted.
    slice_digest      text not null,
    -- ⛔ L2-3's debt. The slice ITSELF, not its hash.
    context_slice     jsonb not null,

    -- WHAT CAME BACK. `proposal` is the validated payload — the fields a model may write, and no
    -- others; `context/proposal_gate` refused everything else before this row existed.
    proposal          jsonb not null default '{}',
    -- accept | unknown | escalate | refuse — L2-6's four outcomes. `unknown` is a RESULT and gets
    -- a row: a reading that declined to conclude is an answer, and a sweep that asked nothing
    -- must not look like a sweep that was never run.
    outcome           text not null,
    -- The refusal codes, when there were any. `<check>:<subject>`, the shape L2-2 chose, because
    -- BundleStore persists codes and not traces.
    reason_codes      jsonb not null default '[]',

    -- The R-site consult this came from. NULL when the quadrant answered `unknown` without
    -- spending anything, which is a different fact from a consult that produced nothing.
    reasoning_trace   text,
    -- ⛔ NULLABLE ON PURPOSE. An interpretation that never expires is not an interpretation.
    -- NULL here means "no expiry was set", which is a gap somebody can find — not a claim that it
    -- is true forever.
    valid_until       timestamptz,
    created_at        timestamptz not null default now(),

    -- One reading per (situation, slice). A re-sweep over unchanged facts updates in place; a
    -- sweep after the facts moved writes a new row and the history survives.
    unique (org_id, situation_id, slice_digest)
);

create index if not exists situation_interpretations_live
    on situation_interpretations (org_id, situation_id, created_at desc);

-- The expiry sweep reads this and nothing else, so it is partial.
create index if not exists situation_interpretations_expiring
    on situation_interpretations (org_id, valid_until)
    where valid_until is not null;
