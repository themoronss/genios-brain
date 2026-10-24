-- 0255 · a card carries the goals it moves (GeniOS-012 S31.U1; `speedrun008/GeniOS-012/07-GOALS.md`).
--
-- `goal_refs`: the LIVE goals (`company_goals`, approved or active — a human made them real) the card's work moves,
-- each `{"ref": "goal:<id>", "statement": …}`: a goal proposed for the card's file (its `subject_ref`), and a goal
-- a judgment's `GoalImpact` linked to one of the file's admitted situations (`goal_situation_links`). Refreshed at
-- the end of every card build (`deliver/goal_line.refresh_card_goals`), so a goal approved after its work was judged
-- reaches the card on the next build, with no new judgment. Empty = no live goal. Idempotent: safe to run twice.

alter table cards add column if not exists goal_refs jsonb not null default '[]'::jsonb;

comment on column cards.goal_refs is
  'GeniOS-012 S31.U1 · the live goals this card''s work moves — [{ref, statement}]: a goal proposed for its file, or linked to its file''s admitted situations. Refreshed every card build.';
