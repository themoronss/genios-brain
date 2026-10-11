-- 0198 · expert_reviews.inputs — what the file WAS when it was judged (STEP-12, the expert pass).
--
-- WHY. The expert reviews a file once per fingerprint (0197), and a review must say what triggered it
-- (`speedrun008/YC-II W27/05` §5): new evidence in the file, a date closing in, an expected reply
-- overdue, a number past the file's normal, the founder asking — and a file none of them touched is
-- not reviewed (tree `yc2_w27_s12` M32.C3.L-logic.V1.U09). "New since the last review" needs what the
-- last review SAW, and 0197 keeps only the fingerprint's hash. A cut by time is not the same thing:
-- mail that arrives late (a resync, STEP-08) or joins the file after it was read would be missed.
--
-- So a review keeps its fingerprint's inputs (`reason/expert/fingerprint.fingerprint_inputs`): its
-- events and bookings, its open asks, whose move it is, its quiet days and its next meeting as rungs,
-- the brief's and the playbook's versions, the verdicts on its people, who decides. What moved since
-- is then a diff, never a guess — and "why was this file reviewed again?" is one read.
--
-- NULLABLE, AND AN OBJECT WHEN SET. The store writes it on every row from here on; a row written
-- before this migration has none (no such row exists in production: nothing writes `expert_reviews`
-- until the expert pass is built and switched on). The check holds its shape, never its presence, so
-- the previous image — which writes no inputs — still runs against this schema.

alter table expert_reviews add column if not exists inputs jsonb;

alter table expert_reviews drop constraint if exists expert_reviews_inputs_check;
alter table expert_reviews add constraint expert_reviews_inputs_check
    check (inputs is null or jsonb_typeof(inputs) = 'object');

comment on column expert_reviews.inputs is
  'STEP-12: the fingerprint''s inputs when the file was judged (reason/expert/fingerprint.fingerprint_inputs) — what a later review diffs to say what moved. Null only on a row written before 0198.';
