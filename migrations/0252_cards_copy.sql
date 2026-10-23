-- 0252 · cards.copy — the card writer's words for the card's current version (GeniOS-011 S34.U3, C1;
-- `speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md` §5 C1, `02-CARD-DEFINITION.md` §2–§3).
--
-- `deliver/card_copy` words each NEW card version once (model site R-10, its own budget, feature `card_copy`,
-- off by default): subject, summary (the two lines), how, steps, result, avoid, done_when, if_not, alternative and
-- goal, each sentence with the ids of the card's own facts it rests on (`rests_on`), the sentences code dropped and
-- why (`dropped`), and `card_version` — the version of the card it was written for.
--
-- WRITTEN FOR ONE VERSION, CLEARED BY THE NEXT. A version or a refresh rewrites the card's words in place
-- (`deliver/store._VERSION_WORDS`, `insert_card`'s upsert) and sets this back to NULL in the same statement, so a
-- copy written for old words never shows over new ones; the writer's own update lands only on the version and the
-- headline it was written for. NULL — off, not yet written, or nothing stood — means the card shows today's
-- fields (headline, situation, recommended, success_signal …): the copy fails closed.
--
-- One nullable column; no backfill (a card built before reads as "not written"). Idempotent: safe to run twice.

alter table cards add column if not exists copy jsonb;

alter table cards drop constraint if exists cards_copy_is_an_object;
alter table cards add constraint cards_copy_is_an_object
    check (copy is null or jsonb_typeof(copy) = 'object');

comment on column cards.copy is
  'GeniOS-011 S34.U3 (C1) · the card writer''s words for this card''s current version (deliver/card_copy, R-10): subject, summary, how, steps, result, avoid, done_when, if_not, alternative, goal — each with rests_on (the card''s own fact ids), dropped (what code refused and why), card_version. NULL = not written; the card shows today''s fields.';
