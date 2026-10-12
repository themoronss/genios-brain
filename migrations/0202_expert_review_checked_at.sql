-- 0202 · expert_reviews.checked_at and .dossier — when the check ran, and the dossier the review was written
-- against (STEP-13, check every claim; `06` D48 answered 12 Oct; tree `yc2_w27_s13` M35.C3.L-integration.V1.U06,
-- the crosscheck's X13 and X36).
--
-- WHY `checked_at` (X36). A check written with its review is dated by `reviewed_at` — one write — but a review
-- checked AGAIN (a newer check version, or a row from before 0200) had its check overwritten with no time: the
-- row could not say when what it now says was decided. `reason/expert/store` writes `checked_at` with every
-- check, the first and each re-check.
--
-- WHY `dossier` (X13, D48). D48: a version change re-checks each standing review against the dossier it was
-- reviewed on. That dossier was not kept — only its digest (0197) — and the re-check read TODAY's: a fact citing
-- a line no longer printed dropped as `unknown_evidence`, a number was corrected to today's value. Today's
-- dossier cannot be compared by digest either: the digest covers the text, whose head is "as of" the minute and
-- whose quiet days are today's, so it moves with the clock. So the row keeps the dossier's text and the ids it
-- printed (`{"text", "evidence_ids"}`) — what the check reads, nothing more. NULL on a row written before this
-- migration; such a row is checked against the file's current dossier, as before.
--
-- ⛔ AND A CORRECTION TO 0200's HEADER, which cannot be edited (migrations are immutable — `platform/migrate`
-- refuses checksum drift): it says a valid row "with one of an older check version, is checked again by the next
-- pass before it decides anything". For a file the pass found UNTOUCHED that was false — such a row was counted
-- `unchecked` and the file uncovered (X11). Since D48: re-checked on its own dossier when the file is the one it
-- saw, reviewed again when the file moved.
--
-- Additive and idempotent: two nullable columns. The tenant reset already deletes `expert_reviews`.
alter table expert_reviews add column if not exists checked_at timestamptz;
alter table expert_reviews add column if not exists dossier jsonb;

alter table expert_reviews drop constraint if exists expert_reviews_dossier_check;
alter table expert_reviews add constraint expert_reviews_dossier_check
    check (dossier is null
           -- coalesce: a CHECK passes on NULL, and a dossier missing its text or its ids is no dossier.
           or (jsonb_typeof(dossier) = 'object'
               and coalesce(jsonb_typeof(dossier -> 'text'), '') = 'string'
               and coalesce(jsonb_typeof(dossier -> 'evidence_ids'), '') = 'array'));

comment on column expert_reviews.checked_at is
  'STEP-13 (D48, X36): when the row''s check (expert_reviews.checked) was written — with the review, or by a re-check. Null on a row with no check, or written before 0202.';
comment on column expert_reviews.dossier is
  'STEP-13 (D48, X13): the dossier the review was written against — {"text", "evidence_ids"} — which a re-check under a newer check version reads. Null on a row written before 0202.';
