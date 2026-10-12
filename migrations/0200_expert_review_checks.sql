-- 0200 · expert_reviews.checked — what the check found in the review (STEP-13, check every claim).
--
-- WHY. Since STEP-13 a valid review is not shown as the model wrote it: `reason/expert/verify` checks it
-- line by line — each fact on the mail it quotes, each number against its calculator, whom its draft
-- goes to, whether its ask is already answered — and keeps a verdict per line, the move's fate (shown,
-- held for one question, suppressed, refused) and the card's words once checked
-- (`contracts/claim_check.CheckedReview`; `speedrun008/YC-II W27/` STEP-13 §8.4, tree `yc2_w27_s13`
-- M35.C1.L-contract.V1.U03). The decision reads the review THROUGH its check, and a replay must read the
-- same check back — never run it again over a dossier that is not stored. So the row keeps it.
--
-- NULLABLE, AND AN OBJECT WITH ITS FATE WHEN SET. The review run writes it on every valid row from here
-- on; a row written before this migration has none — no such row exists in production (STEP-12 is not
-- deployed). A valid row without a check, or with one of an older check version, is checked again by the
-- next pass before it decides anything. The check holds the shape, never the presence, so the previous
-- image still runs against this schema.

alter table expert_reviews add column if not exists checked jsonb;

alter table expert_reviews drop constraint if exists expert_reviews_checked_check;
alter table expert_reviews add constraint expert_reviews_checked_check
    check (checked is null
           or (jsonb_typeof(checked) = 'object'
               -- coalesce: a CHECK passes on NULL, and a check with no fate is no check.
               and coalesce(checked ->> 'fate', '') in ('shown', 'held', 'suppressed', 'refused')));

comment on column expert_reviews.checked is
  'STEP-13: the check of the review (contracts/claim_check.CheckedReview) — verdicts, fate, question, the card''s checked words, the ids its standing facts cite. Null on a row written before 0200, or not valid.';
