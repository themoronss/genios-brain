-- 0199 · expert_reviews.triggers — what made the expert look at the file (STEP-12, the expert pass).
--
-- WHY. The expert reviews a file only when something in it changed, and a review says what
-- (`speedrun008/YC-II W27/05` §5; `reason/expert/triggers`, tree `yc2_w27_s12` M32.C3.L-logic.V1.U09):
-- a first look, new evidence, a date closing in, a reply overdue, a number past the file's normal, the
-- founder asking. Said only in the pass's memory, it would be gone by the time anyone asked "why was
-- this file looked at?" — the read model, the health check and the card's "why now" (STEP-14) all
-- read it from the row. So the row keeps it: a list, each trigger its kind and what moved.
--
-- NULLABLE, AND A LIST WHEN SET. The store writes it on every row from here on (an empty list is a
-- list); a row written before this migration has none — no such row exists in production. The check
-- holds its shape, never its presence, so the previous image still runs against this schema.

alter table expert_reviews add column if not exists triggers jsonb;

alter table expert_reviews drop constraint if exists expert_reviews_triggers_check;
alter table expert_reviews add constraint expert_reviews_triggers_check
    check (triggers is null or jsonb_typeof(triggers) = 'array');

comment on column expert_reviews.triggers is
  'STEP-12: what triggered the review (reason/expert/triggers) — a list of {kind, says}. Null only on a row written before 0199.';
