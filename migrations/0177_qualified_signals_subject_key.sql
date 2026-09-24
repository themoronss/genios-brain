-- 0177 · `qualified_signals.subject_key` — the half of ALG-19's key the seam never carried.
--
-- THE DEFECT. ALG-19 supersedes on `(subject_key, signal_type)`. `subject_key` has a column on
-- `qualification_drops` (0088), on `signal_lifecycle` (0093) and on `signal_conflicts` (0087) —
-- and **not on `qualified_signals` (0089)**. So a signal the floor REFUSED recorded what it was
-- about, and a signal Layer 1 PUBLISHED did not. Layer 2 could walk a supersession chain by
-- pointer and could never ask *"give me every signal about the AWS renewal."*
--
-- It is derived by ALG-22 at L1.6.2 from the anchor claim and lifted unchanged through
-- `NormalizedSignal.subject_key` -> C-12 -> this column. It is never re-derived: `record_of`
-- already takes it as a parameter for exactly that reason, and two derivations of one subject is
-- how a signal ends up superseded under one key and queried under another.
--
-- NULLABLE ON ARRIVAL, DELIBERATELY. Every row written before this migration has no subject, and
-- a NOT NULL would refuse the migration on any live tenant. New rows always carry one —
-- `NormalizedSignal.subject_key` can never be None, its last rung being ALG-22's event fallback —
-- so the null set is closed and shrinks to nothing as the corpus turns over. Tightening it later
-- is a separate, deliberate migration once a tenant reports zero nulls.
--
-- THE INDEX IS THE POINT, not the column. `(org_id, subject_key, signal_type)` is exactly
-- ALG-19's supersession key with the tenant in front, so "every signal about this subject, of
-- this kind" is one index scan rather than a table scan per lookup.
--
-- Idempotent: add-if-not-exists on both, safe to re-run.
alter table qualified_signals
    add column if not exists subject_key text;

create index if not exists qualified_signals_subject_idx
    on qualified_signals (org_id, subject_key, signal_type);
