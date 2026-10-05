-- The production-state part of the YC-II W27 baseline: the statements behind
-- `<date>/production_state.txt`, verbatim. Rohit's org, plus two global facts (the latest
-- migration, the server version). Metadata only — no mail content.
--
-- Read-only. Each of these runs must refuse a write on the server:
--   * Claude's runner opens one connection with `scripts/_gate.read_only_connection`;
--   * with psql:
--       PGOPTIONS='-c default_transaction_read_only=on' psql "$URL" -f production_state.sql
--
-- Each block starts with a `-- @<name>` line. The runner prints the blocks in this order, and
-- prints every timestamp in UTC.

-- @sweeps_recorded
select count(distinct sweep_id) as sweeps, min(sweep_at) as first_sweep, max(sweep_at) as last_sweep
from pipeline_counters
where org_id = 'org_e97e86f858ad48b2bbf64b8a';

-- @funnel_last_8_sweeps
-- A stage with no row in a sweep: its count never reached the chain. By design that means
-- "nobody looked" — but `decision_emitted` also loses every zero this way (03-FINDINGS F27).
select sweep_at, string_agg(stage || '=' || n, ' · ' order by stage) as stages
from pipeline_counters
where org_id = 'org_e97e86f858ad48b2bbf64b8a'
group by sweep_id, sweep_at
order by sweep_at desc
limit 8;

-- @funnel_per_stage
-- Some stages are a level (situations ranked this pass), one is a per-sweep count (cards built),
-- so only the range is printed, never a sum.
select stage, count(distinct sweep_id) as sweeps_that_wrote_it, min(n) as min_n, max(n) as max_n,
       min(sweep_at) as first_written, max(sweep_at) as last_written
from pipeline_counters
where org_id = 'org_e97e86f858ad48b2bbf64b8a'
group by stage
order by stage;

-- @l2_processing_runs
-- STEP-18 B2's probe. An event whose writer emits an edge type outside the closed vocabulary
-- would carry `unknown edge_type ...` here.
select status, count(*) as runs,
       count(*) filter (where last_error like 'unknown edge_type%') as edge_type_errors,
       min(updated_at) as first_run, max(updated_at) as last_run
from l2_processing_runs
where org_id = 'org_e97e86f858ad48b2bbf64b8a'
group by status
order by runs desc;

-- @park_queue
-- What waits, what was given up on, and what came back. `source_outcome` is the event's own
-- outcome: an event can be `emitted` and still have a pending park row.
select p.source, se.object_type, se.outcome as source_outcome, p.stage, p.reason_code, p.status,
       count(*) as n, max(p.refetch_attempts) as max_attempts,
       min(p.created_at) as first_parked, max(p.created_at) as last_parked,
       max(p.refetch_next_attempt_at) as latest_next_attempt
from parked_events p
join source_events se on se.org_id = p.org_id and se.event_id = p.event_id
where p.org_id = 'org_e97e86f858ad48b2bbf64b8a'
group by p.source, se.object_type, se.outcome, p.stage, p.reason_code, p.status
order by n desc;

-- @attachment_refetch_errors
-- Why the parked attachments do not come back: the stored provider error, with the message and
-- attachment ids replaced, and cut at 160 characters.
select left(regexp_replace(coalesce(refetch_last_error, '(no error stored)'),
                           ' for [^ :]+::[^ ]+', ' for <message>::<attachment>'), 160) as error_shape,
       refetch_failure_kind, status, count(*) as n, max(refetch_last_attempt_at) as last_attempt
from parked_events
where org_id = 'org_e97e86f858ad48b2bbf64b8a' and source = 'gmail' and reason_code like 'DOC-%'
group by 1, 2, 3
order by n desc;

-- @model_calls_by_day
-- STEP-02's number — the per-sweep decider and its r1 pass — and the relevance gate, per UTC day.
select (created_at at time zone 'utc')::date as day, purpose, count(*) as calls,
       count(*) filter (where not success) as failed
from llm_costs
where org_id = 'org_e97e86f858ad48b2bbf64b8a'
  and created_at > now() - interval '4 days'
  and purpose in ('l4_llm_decision', 'l4_llm_r1', 'relevance_gate')
group by 1, 2
order by 1, 2;

-- @narrator_ceiling
-- 03-FINDINGS F24: did the narrator (`l4_bundle`) stop failing at its old 1,400-token ceiling?
select (created_at at time zone 'utc')::date as day, count(*) as calls,
       count(*) filter (where not success) as failed,
       count(*) filter (where not success and output_tokens = 1400) as failed_at_1400,
       max(created_at) filter (where not success) as last_failure
from llm_costs
where org_id = 'org_e97e86f858ad48b2bbf64b8a' and purpose = 'l4_bundle'
  and created_at > now() - interval '4 days'
group by 1
order by 1;

-- @l3_domains
select domain, enabled_at, disabled_at, enabled_by
from l3_activation
where org_id = 'org_e97e86f858ad48b2bbf64b8a'
order by domain;

-- @l4_features
select feature, enabled_at, disabled_at, enabled_by
from l4_activation
where org_id = 'org_e97e86f858ad48b2bbf64b8a'
order by feature;

-- @latest_migration
select filename, applied_at
from schema_migrations
order by applied_at desc
limit 1;

-- @connections
select provider, source_type, status, created_at
from connections
where org_id = 'org_e97e86f858ad48b2bbf64b8a'
order by created_at;

-- @database
select version();
