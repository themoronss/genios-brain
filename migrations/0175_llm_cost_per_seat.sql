-- 0175 · WHO SPENT IT — per-seat attribution and the cache split on `llm_costs`.
--
-- `llm_costs` answered "what did this ACCOUNT cost this month". It could not answer "which
-- PERSON in the account cost that", because org_id was the only identity on the row. That gap
-- is not cosmetic: screen intelligence is per-seat by construction (a device belongs to one
-- seat, 0140), mailboxes are per-seat since 0138, and the intelligence API already knows the
-- caller's seat (`AuthCtx.seat_id`). Every lane KNEW whose spend it was and threw the fact away
-- at the ledger boundary, so a runaway or abusive seat was invisible until the org-wide daily
-- cap tripped — by which point the whole tenant is blocked, not the one seat responsible.
--
--   seat_id — the person the call was made for. NULL is a real and common value: background
--             sweeps, drains and org-wide work genuinely serve no single seat, and inventing an
--             owner for them would make per-user bills wrong in the direction that looks precise.
--             `purpose` already names which lane an unattributed row came from.
--
-- THE CACHE SPLIT. `LLMClient` computes a COST-EQUIVALENT input token count (uncached +
-- 1.25x/2x writes + 0.1x reads) so pricing stays correct without the pricer knowing about
-- caching — and then discards the raw counts. Money was right; "is the prompt cache actually
-- working on this build" was unanswerable from the ledger, which is exactly the question a
-- caching change has to be judged on. Stored alongside, never priced: `input_tokens` remains
-- THE billable number, and `metrics.cost_usd` is untouched.
--
-- Additive and nullable/defaulted: every existing writer keeps working unchanged.
alter table llm_costs add column if not exists seat_id            text;
alter table llm_costs add column if not exists cache_read_tokens  int not null default 0;
alter table llm_costs add column if not exists cache_write_tokens int not null default 0;

-- NO NEW INDEX, deliberately. The obvious one is (org_id, seat_id, created_at), and it would
-- earn nothing: the per-account rollup filters org + time and GROUPS BY seat, which
-- `llm_costs_by_org (org_id, created_at)` already serves, and the cross-org runaway view filters
-- time and rechecks `seat_id is not null`, which `llm_costs_by_time (created_at desc)` serves.
-- Against that, `apply_migrations` runs each file inside ONE transaction, so CREATE INDEX
-- CONCURRENTLY is not available here and a plain build would hold a write lock on `llm_costs`
-- at boot — blocking every lane's cost write while it scans. An index that serves no query is
-- not worth a second of that. Add one when a real query plan asks for it.

comment on column llm_costs.seat_id is
  'The seat (person) the call served. NULL = background/org-wide work with no single owner.';
comment on column llm_costs.cache_read_tokens is
  'Raw prompt-cache READ tokens, for measurement. Already priced inside input_tokens at 0.1x.';
comment on column llm_costs.cache_write_tokens is
  'Raw prompt-cache WRITE tokens, for measurement. Already priced inside input_tokens at 1.25x/2x.';
