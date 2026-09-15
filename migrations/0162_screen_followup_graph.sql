-- 0162 · FOLLOW-UP → GRAPH MEMORY (SCREEN_INTEL_SYSTEM_DESIGN.html, phase 1 step S3).
--
-- `graph_written_at`  when the item became a graph observation (reason/moments/screen_memory.py
--                     `write_items`, run when its thread's screen content is promoted); NULL = not
--                     yet, so a later promotion writes each item exactly once.
-- `subject_node_id`   the person node the observation was written on (the manager's own node when
--                     the item names no one; NULL when neither resolves).
alter table screen_followups add column if not exists graph_written_at timestamptz;
alter table screen_followups add column if not exists subject_node_id text;
