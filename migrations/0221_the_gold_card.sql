-- 0221 · the gold card — the move whole, its alternative, when to stop; and the lines code wrote for the card
-- (STEP-14, the card; §3.3, §8.4 item 5; tree `yc2_w27_s14` M43.C1.L-contract.V0.U01; s14-F6, s14-F7).
--
-- WHY. The gold card (the Atlas's, and the Secret War audit's actionable contract) says: who and what the file is,
-- what remains, why now, the move WHOLE (who, what, for whom, by when, to whom), its alternative, when to wait or
-- stop, what done looks like, its window, its receipts. Measured on 31 golden cases (STEP-14 §8.1): the move was
-- the headline cut at 60 characters — 38 of 39 longer, 10 cut mid-phrase and their date then on no field — and its
-- recipient, alternative and stop rule sat in the audited play's metadata only (`reason/expert/decide._play`).
-- The existing columns (0065) carry the rest: subject, role, what remains, why now, done when, window,
-- do-nothing, receipts, confidence.
--
--   cards.recommended   the move whole — an object `{who, what, for_whom, by_when, to}`, its `what` said
--   cards.alternative   the move the review would make instead
--   cards.wait_or_stop  when to wait, and when to stop advising
--
-- AND THE LINES CODE WROTE FOR THE CARD (`reason/expert/card_lines`): `expert_reviews.card_lines` — why now, what
-- remains, subject, role, the window — written at review time from the dossier the review was written against, so a
-- decision and a replay read them without the dossier. NULL on a review stored before this migration: its card
-- shows the review's own words without them.
--
-- Additive and idempotent: four nullable columns, two shape checks. The tenant reset already deletes `cards` and
-- `expert_reviews`.
alter table cards add column if not exists recommended jsonb;
alter table cards add column if not exists alternative text;
alter table cards add column if not exists wait_or_stop text;
alter table expert_reviews add column if not exists card_lines jsonb;

alter table cards drop constraint if exists cards_recommended_check;
alter table cards add constraint cards_recommended_check
    check (recommended is null
           -- An object that says its `what`: `->>` gives NULL on anything but an object holding the key, and
           -- coalesce makes that a refusal (a CHECK passes on NULL) — a move that says no `what` is no move.
           or btrim(coalesce(recommended ->> 'what', '')) <> '');

alter table expert_reviews drop constraint if exists expert_reviews_card_lines_check;
alter table expert_reviews add constraint expert_reviews_card_lines_check
    check (card_lines is null or jsonb_typeof(card_lines) = 'object');

comment on column cards.recommended is
  'STEP-14 (0221): the move whole — {who, what, for_whom, by_when, to} — the headline cut at a clause, never the move; NULL on a card no review wrote.';
comment on column cards.alternative is
  'STEP-14 (0221): the move the review would make instead, as its check let it stand.';
comment on column cards.wait_or_stop is
  'STEP-14 (0221): when to wait, and when to stop advising, as the review''s check let it stand.';
comment on column expert_reviews.card_lines is
  'STEP-14 (0221): the lines code wrote for the card at review time (reason/expert/card_lines) — why now, what remains, subject, role, window — from the dossier the review was written against. NULL before 0221.';
