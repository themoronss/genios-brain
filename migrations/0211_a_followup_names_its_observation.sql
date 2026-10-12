-- 0211 · a screen follow-up names the graph observation it was last written as (STEP-18 B13,
-- `yc2_w27_s18` M48.C2.L-contract.V0.U12).
--
-- THE DEFECT. A follow-up whose words, date or person change is written to memory again
-- (`reason/moments/followups.upsert` clears `graph_written_at`, 0162), and each write mints a fresh
-- observation id (`context/graph_store.write_observation`) — so every version of one follow-up stayed
-- an ACTIVE observation beside the next, and a reader counting a person's evidence counted one item as
-- many. Nothing on the row said which observation it had become, so the write could not retire the
-- one before.
--
-- `observation_id` is that name: written with `graph_written_at` and `subject_node_id`, read by the
-- next write of the same follow-up, which retires that observation (`status = 'superseded'`) before it
-- writes its own. NULL until the first write after this migration — a row written before it carries no
-- name, so its first rewrite leaves that one observation as it was.
--
-- Additive and idempotent: one nullable column. The tenant reset already deletes `screen_followups`.
alter table screen_followups add column if not exists observation_id text;

comment on column screen_followups.observation_id is
  'The graph observation this follow-up was last written as (reason/moments/screen_memory). The next write of a changed follow-up supersedes it, so one follow-up is one active observation. NULL until first written after 0211.';
