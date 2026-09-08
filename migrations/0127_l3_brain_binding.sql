-- 0127 · Layer 3 binding: the brain address index, the lease read, and the ratio threshold.
--
-- WHAT THIS MIGRATION IS FOR. Layer 3 held knowledge in four brains and could not decide which of
-- it applied to a live situation, so it applied none of it. `scripts/l3_pilot_report.py` measured
-- the end state on a tenant holding 6 behaviour entries, 5 organization entries and a live adaptive
-- lease: `packages_with_a_brain_slice = 0` across four compiled packages. Not an empty brain — an
-- unaddressable one.
--
-- The fix is `contracts/brain_address.py`: one token vocabulary a situation and a brain entry both
-- speak, written by the producers onto `value->'address'->'tokens'` and selected on by
-- `packs/compiler/runtime_brains`. That is all code. THREE things about it are schema:
--
--   1. the compiler's prefilter now asks "does this entry's address name anything this situation
--      is about" on every compile, per situation, and a jsonb containment question over a text
--      array wants a GIN index or it is a sequential scan of the tenant's whole brain;
--   2. the Adaptive lease reader is NEW — `temporary_memories` was never read by Layer 3 at all —
--      and it filters on `(org_id, active, expires_at)` plus the same address question;
--   3. a percentage threshold now survives CLG-09 (`contracts/units.Ratio`), and the Authority
--      view it projects into has nowhere to put one.
--
-- IDEMPOTENT AND ADDITIVE. No column is dropped, no value is rewritten, and nothing here changes
-- what an existing row means. Layer 6 owns publication and Layer 3 never edits what it is handed,
-- so pre-address entries are NOT backfilled — `brain_address.legacy_tokens` derives their tokens at
-- read time instead, which keeps the ownership line where it belongs and needs no migration at all.

-- ── 1 · the address index ──────────────────────────────────────────────────────────────────────
-- `jsonb_path_ops` rather than the default operator class: it is roughly half the size and faster
-- for exactly the one question asked here (does this array contain any of these values). The
-- expression is indexed rather than the whole `value` column because `value` also holds statements,
-- cohorts and evidence — indexing all of it would be a large index answering one small question.
create index if not exists learned_brain_entries_address
    on learned_brain_entries using gin ((value -> 'address' -> 'tokens') jsonb_path_ops)
    where active;

create index if not exists temporary_memories_address
    on temporary_memories using gin ((value -> 'address' -> 'tokens') jsonb_path_ops)
    where active;

-- ── 2 · the lease read ─────────────────────────────────────────────────────────────────────────
-- `temporary_memories_active` already covers `(org_id, expires_at) where active`, which is exactly
-- this query's leading predicate, so no second btree is added. Stated here rather than left silent
-- so the next reader does not add a duplicate.

-- ── 3 · the ratio threshold ────────────────────────────────────────────────────────────────────
-- "A discount greater than 15% requires approval from the founder." was refused in whole — not
-- just its threshold — because `threshold_as_written` was validated by ALG-10, a MONEY parser,
-- which answers UNPARSEABLE_TOKEN for `15%`. Discount authority is the most common approval rule a
-- sales-led startup writes down and the Organization brain could not hold one.
--
-- BASIS POINTS IN THEIR OWN COLUMN, not folded into `threshold_minor_units`. 1500 minor units and
-- 1500 basis points are the same integer and mean nothing alike, and a reader that had to consult
-- `currency` to discover which it was holding would get it wrong exactly once, on the rule that
-- decides who signs.
alter table authority_rules
    add column if not exists threshold_basis_points int;

-- A rule has AT MOST ONE threshold, and it is money or a ratio. Both set is not a stricter rule,
-- it is an unreadable one: nothing downstream could say which bound bit.
--
-- NOT VALID, then validated separately, so the ALTER takes no long table lock on a live database.
-- `authority_rules` is small everywhere today; the discipline is kept anyway because the next
-- constraint added to a big table will be copied from this one.
do $$
begin
    if not exists (select 1 from pg_constraint
                   where conname = 'authority_rules_one_threshold_dimension') then
        alter table authority_rules
            add constraint authority_rules_one_threshold_dimension check (
                threshold_basis_points is null or threshold_minor_units is null) not valid;
    end if;
    if not exists (select 1 from pg_constraint
                   where conname = 'authority_rules_basis_points_range') then
        -- 0..10000. A threshold above 100% is a parse that went wrong, and admitting it would turn
        -- a bug into a rule that always fires.
        alter table authority_rules
            add constraint authority_rules_basis_points_range check (
                threshold_basis_points is null
                or (threshold_basis_points >= 0 and threshold_basis_points <= 10000)) not valid;
    end if;
end $$;

alter table authority_rules validate constraint authority_rules_one_threshold_dimension;
alter table authority_rules validate constraint authority_rules_basis_points_range;

-- The Authority view's own read is `(org_id, subject_type, valid_from desc)`, already indexed by
-- 0097. The new column is projected, never filtered on, so it gets no index of its own.
