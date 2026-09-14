-- 0160 · SCREEN VERDICT MEMORY + MUTE (SCREEN_INTEL_COST_RELEVANCE_BUILD.md K2, K4).
--
-- `memory`      the screen-insight model's "is there anything here worth keeping in long-term
--               memory?" (K1) for (seat, thread). The screen promoter routes the thread's held
--               content by it with no AI gate call (K3): true → memory, false → parked (kept,
--               `insight_no_memory`). NULL = the model gave no memory answer (rows from P8).
-- `muted_until` "Not useful" on an insight → now + 7 days; "Mute chat" → far future (K4). While
--               it is in the future the thread gets no insight popups (and no model call).
alter table screen_thread_verdicts add column if not exists memory boolean;
alter table screen_thread_verdicts add column if not exists muted_until timestamptz;
