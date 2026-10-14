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

-- @cards_expired_while_deferred
-- STEP-02's second target: 0. A card expired in the last 14 days whose subject's latest decision, as
-- the change gate holds it, is a DEFER (or an unavailable decider) - a DEFER must keep the card.
select count(*) as expired_cards,
       count(*) filter (where f.outcome in ('deferred', 'indeterminate')) as expired_while_deferred,
       max(c.resolved_at) filter (where f.outcome in ('deferred', 'indeterminate')) as last_one
from cards c
join signals s on s.org_id = c.org_id and s.signal_id = c.signal_id
left join reasoning_fingerprints f on f.org_id = c.org_id
     and f.subject_key in (s.situation_id, s.rule_id || ':' || s.subject_node_id)
where c.org_id = 'org_e97e86f858ad48b2bbf64b8a' and c.state = 'expired'
  and c.resolved_at > now() - interval '14 days';

-- @gate_redecided_unchanged
-- STEP-02's first target, as far as the store can say it: the gate keeps ONE row per subject, so a
-- flip (decision <-> DEFER on one fingerprint) shows as a subject decided again inside a day with no
-- skip between. Per lane and outcome; the health check reads the same table.
select lane, outcome, count(*) as subjects, sum(skips) as skips,
       count(*) filter (where skips = 0 and decided_at > now() - interval '1 day') as decided_today_never_skipped,
       max(decided_at) as last_decided
from reasoning_fingerprints
where org_id = 'org_e97e86f858ad48b2bbf64b8a'
group by lane, outcome
order by subjects desc;

-- @dates_framed_late
-- 03 F148: a stored date resolved against a read more than a day after its mail (the first connect,
-- a sync after downtime, a re-sync) - scripts/reframe_stored_dates.py re-frames them. By month of mail.
select to_char(date_trunc('month', se.occurred_at), 'YYYY-MM') as month, count(*) as dates,
       count(*) filter (where (d ->> 'resolved_against')::timestamptz - se.occurred_at
                              > interval '1 day') as framed_late
from l1_extraction_results x
join source_events se on se.org_id = x.org_id and se.event_id = x.event_id
cross join lateral jsonb_array_elements(coalesce(x.output -> 'dates_mentioned', '[]'::jsonb)) as d
where x.org_id = 'org_e97e86f858ad48b2bbf64b8a' and x.profile_id is not null
  and d ? 'resolved_against'
group by 1
order by 1;

-- @promises_framed_late
-- 03 F148, the promises: a commitment's due date framed more than a day after its mail.
select to_char(date_trunc('month', se.occurred_at), 'YYYY-MM') as month, count(*) as promises_dated,
       count(*) filter (where (c -> 'due' ->> 'resolved_against')::timestamptz - se.occurred_at
                              > interval '1 day') as framed_late
from l1_extraction_results x
join source_events se on se.org_id = x.org_id and se.event_id = x.event_id
cross join lateral jsonb_array_elements(coalesce(x.output -> 'commitments', '[]'::jsonb)) as c
where x.org_id = 'org_e97e86f858ad48b2bbf64b8a' and x.profile_id is not null
  and jsonb_typeof(c -> 'due') = 'object'
group by 1
order by 1;

-- @thinking_lanes
-- STEP-18 §9 (13 Oct), Claude 5 thinks by default: per lane and model over 30 days, every call that
-- stopped at its lane's ceiling — failed (`failures_at_ceiling`) OR closed by the lenient parser and
-- recorded a success (`parsed_but_cut`), which a `not success` filter cannot see. The ceilings, per
-- lane: l4_bundle 2400 (1400 before 4 Oct), l4_r1 400, l4_r3 600, l4_r4 400, l4_r7 4000 (6000 after
-- the speedrun008 deploy), intelligence_analyze and _query 700, intelligence_draft 500,
-- company_brief_draft 2400 (4000 after), l4_llm_decision 900, l4_llm_r1 700, l5_render 600,
-- moment.screen_insight 400. On harsh/mvp R-2 is l4_bundle on claude-sonnet-5: at least 10% of its
-- calls at 2400 confirms the defect (s5t-F3).
with ceiling(purpose, model_like, max_tokens) as (values
    ('l4_bundle', 'claude-sonnet-5%', 2400), ('l4_bundle', 'claude-sonnet-5%', 1400),
    ('l4_r1', '%', 400), ('l4_r3', '%', 600), ('l4_r4', '%', 400),
    ('l4_r7', '%', 4000), ('l4_r7', '%', 6000),
    ('intelligence_analyze', '%', 700), ('intelligence_query', '%', 700),
    ('intelligence_draft', '%', 500),
    ('company_brief_draft', '%', 2400), ('company_brief_draft', '%', 4000),
    ('l4_llm_decision', '%', 900), ('l4_llm_r1', '%', 700), ('l5_render', '%', 600),
    ('moment.screen_insight', '%', 400)),
calls as (
    select c.purpose, c.model, c.success, c.error, c.output_tokens, c.input_tokens,
           exists (select 1 from ceiling k
                    where k.purpose = c.purpose and c.model like k.model_like
                      and c.output_tokens = k.max_tokens) as at_ceiling
      from llm_costs c
     where c.org_id = 'org_e97e86f858ad48b2bbf64b8a'
       and c.created_at > now() - interval '30 days')
select purpose, model,
       count(*) as calls,
       count(*) filter (where not success) as failures,
       count(*) filter (where not success and at_ceiling) as failures_at_ceiling,
       count(*) filter (where success and at_ceiling) as parsed_but_cut,
       count(*) filter (where error like 'truncated:%') as error_says_truncated,
       round(100.0 * count(*) filter (where at_ceiling) / count(*), 1) as pct_at_ceiling,
       percentile_disc(0.5) within group (order by output_tokens) as out_p50,
       percentile_disc(0.9) within group (order by output_tokens) as out_p90,
       max(output_tokens) as out_max,
       round(avg(input_tokens)) as in_avg
  from calls
 group by purpose, model
 order by count(*) filter (where at_ceiling) desc, count(*) desc;

-- @thinking_r_sites
-- The R-site receipts (l4_r_site_calls). Tokens and cost are SUMMED over a consult's attempts, so a
-- consult cut on every attempt shows output = attempts x the site's ceiling. On harsh/mvp the gate has
-- no `truncated` outcome: an R-2 cut is `failed_generation`, retried once at the same ceiling
-- (attempts 2, output 4800) — two charged calls, then the template.
select site, model, outcome,
       count(*) as consults,
       sum(attempts) as model_calls,
       count(*) filter (where attempts > 0 and output_tokens = attempts * case site
                 when 'R-1' then 400 when 'R-2' then 2400 when 'R-3' then 600
                 when 'R-4' then 400 when 'R-7' then 4000 end) as every_attempt_at_ceiling,
       round(avg(output_tokens)) as out_avg,
       round(sum(cost_micro_usd) / 1e6, 2) as usd,
       jsonb_agg(distinct reason_codes) as reason_codes
  from l4_r_site_calls
 where org_id = 'org_e97e86f858ad48b2bbf64b8a'
   and created_at > now() - interval '30 days'
 group by site, model, outcome
 order by site, count(*) desc;

-- @thinking_sonnet_by_day
-- The Sonnet 5 lanes per UTC day, to see whether R-2's raise of 4 Oct (1400 to 2400) changed anything.
select (created_at at time zone 'utc')::date as day, purpose, model,
       count(*) as calls,
       count(*) filter (where not success) as failures,
       count(*) filter (where output_tokens in (700, 1400, 2400, 4000)) as at_a_ceiling,
       max(output_tokens) as out_max
  from llm_costs
 where org_id = 'org_e97e86f858ad48b2bbf64b8a'
   and created_at > now() - interval '30 days'
   and model like 'claude-sonnet-5%'
 group by 1, 2, 3
 order by 1, 2;

-- @thinking_models_in_use
-- Which models production called in 30 days, and for what: is GENIOS_ANTHROPIC_MODEL still Haiku,
-- read without reading the environment. A T1 lane on any model but Haiku is the override hazard.
select model, count(*) as calls, count(distinct purpose) as purposes,
       string_agg(distinct purpose, ', ' order by purpose) as which
  from llm_costs
 where org_id = 'org_e97e86f858ad48b2bbf64b8a'
   and created_at > now() - interval '30 days'
 group by model
 order by count(*) desc;

-- @thinking_expert_after_deploy
-- AFTER the speedrun008 deploy only (expert_reviews is 0197; production is at 0190 — this errors
-- before it). R-7 by status: whether the cut reviews still sit at a ceiling (4000 before M50, 6000 after).
select model, status, reason, count(*) as reviews,
       count(*) filter (where output_tokens in (4000, 6000)) as at_a_ceiling,
       round(sum(cost_micro_usd) / 1e6, 2) as usd
  from expert_reviews
 where org_id = 'org_e97e86f858ad48b2bbf64b8a'
   and reviewed_at > now() - interval '30 days'
 group by 1, 2, 3
 order by count(*) desc;

-- @thinking_brief_after_deploy
-- AFTER the speedrun008 deploy only (company_brief_reviews is 0195). The weekly brief review's
-- outcomes: a model failure is outcome text (`model:truncated…` for a cut draft).
select outcome like 'model:truncated%' as truncated, outcome, count(*) as weeks, sum(proposed) as proposed
  from company_brief_reviews
 where org_id = 'org_e97e86f858ad48b2bbf64b8a'
   and started_at > now() - interval '30 days'
 group by 1, 2
 order by count(*) desc;

-- @b13_duplicate_screen_observations
-- G-2 (yc2_w27_s1718 M48.C2.L-data.V2.U21, second crosscheck). Pre-0211 writes minted one active
-- observation per version with no retiring id; a follow-up with more than one still-active
-- observation is one `scripts/retire_duplicate_screen_observations.py`'s dry run (08 §4.11) should
-- name, then move past zero with --apply.
select count(*) as followups_with_more_than_one_active_observation from (
  select r.evidence->>'followup_id' as followup_id
    from graph_observations o
    join graph_source_refs r on r.observation_id = o.observation_id and r.org_id = o.org_id
   where o.org_id = 'org_e97e86f858ad48b2bbf64b8a' and r.source = 'screen_insight'
     and o.status = 'active'
   group by 1
  having count(*) > 1
) d;

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
