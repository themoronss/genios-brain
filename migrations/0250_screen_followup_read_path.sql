-- 0250 · screen_followups.read_by + due_phrase — how a screen item was read, and the words its due came from
-- (GeniOS-010 B8, `speedrun008/GeniOS-010/05-SCREEN/README.md` §5).
--
-- `read_by` is the path that FIRST wrote the item: `rule` (a screen rule read it outright, no model), `quick_read`
-- (the instant screen-insight call) or `hourly_batch` (the hourly memory batch). A later sighting by another path
-- keeps the first — the Screen page says how the item was caught, not who touched it last.
-- `due_phrase` is the text the due was parsed from ("kal tak", "by Friday"), so the page can mark those words in
-- the rebuilt screen. NULL for a row written before this migration, or an item with no due: both read "not served".
--
-- Two nullable columns on a table that is purged on its retention; no backfill. Idempotent: safe to run twice.

alter table screen_followups add column if not exists read_by text;
alter table screen_followups add column if not exists due_phrase text;

alter table screen_followups drop constraint if exists screen_followups_read_by_ck;
alter table screen_followups add constraint screen_followups_read_by_ck
    check (read_by is null or read_by in ('rule', 'quick_read', 'hourly_batch'));
