-- Abstention as a first-class card state.
--
-- `cards.level` carried exactly two values, `prescriptive` and `predictive`, because those are
-- the only two a pack rule can author. With zero reviewed capabilities in the corpus, that means
-- one hundred percent of what reached a user was advice on domains the system holds no accepted
-- expertise for. It could BLOCK a candidate — a suppression row nobody sees — but it had no way
-- to SAY it did not know, and those are different products.
--
-- The constraint is deliberately a CHECK rather than a Postgres enum: a check can be widened in
-- one statement when a new level is authored, while an enum needs a type migration and locks the
-- table. The vocabulary lives in `genios_engine/contracts/abstention.py`; this mirrors it so a
-- typo cannot reach a user as a card whose authority nothing can interpret.

alter table cards add column if not exists abstained_because text;

comment on column cards.abstained_because is
  'Why this card declines to instruct: no accepted expertise, unresolved evidence, or a deliberate hold. NULL on an actionable card. An abstention with no stated cause is indistinguishable from a bug.';

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'cards_level_vocabulary') then
    alter table cards add constraint cards_level_vocabulary
      check (level in ('prescriptive', 'predictive', 'observation', 'review', 'wait', 'suppress'))
      not valid;   -- not valid: existing rows predate the vocabulary and must not block the deploy
  end if;
end $$;

-- "How much of what we ship is actually advice?" is the question this table should be able to
-- answer at a glance, and it could not: every row said `prescriptive`.
create index if not exists cards_level_authority on cards (org_id, level);
