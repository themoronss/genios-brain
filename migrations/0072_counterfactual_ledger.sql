-- L7-12 (RC-7 / B-10): the joined recommendation → exposure → action → delivery → outcome view.
--
-- Every stage already had a ledger; no query joined them, so "did this recommendation lead to
-- anything?" required a hand-written five-table join nobody had written. The chain now has
-- every key it needs: signals carry the decision (0070), cards the exposure, card_events the
-- human action, delivery_outbox the send (delivery_id since L6-05), executions/execution_
-- outcomes the commitment result, card_feedback_verdicts the judgment, and llm_costs the spend
-- (subject_ref since 0069).
--
-- A VIEW, not a table: every source is already append-only/versioned, so materialising a copy
-- would be a second thing to keep honest. One row per signal — the recommendation is the unit
-- the counterfactual question is asked about.
create or replace view counterfactual_ledger as
select
    s.org_id,
    s.signal_id,
    s.rule_id,
    s.reason_code,
    s.level,
    s.eval_time                       as recommended_at,
    s.do_nothing_consequence,
    s.rejected_candidates,
    -- exposure
    k.card_id,
    k.state                           as card_state,
    k.created_at                      as exposed_at,
    -- human action (the first claiming/judging act on the card)
    act.first_action_at,
    act.first_action,
    -- judgment
    v.cause                           as verdict,
    v.reason                          as verdict_reason,
    v.occurred_at                     as judged_at,
    -- delivery
    d.deliveries,
    d.first_delivered_at,
    -- commitment + outcome
    x.execution_id,
    x.state                           as execution_state,
    o.label                           as outcome_label,
    o.closed_at                       as outcome_at,
    o.seconds_to_close,
    -- spend attributed to this recommendation
    coalesce(cost.usd_calls, 0)       as llm_calls,
    cost.input_tokens,
    cost.output_tokens
from signals s
left join cards k
       on k.org_id = s.org_id and k.signal_id = s.signal_id
left join lateral (
    select min(ce.occurred_at) as first_action_at,
           (array_agg(ce.cause order by ce.occurred_at))[1] as first_action
    from card_events ce
    where ce.org_id = k.org_id and ce.card_id = k.card_id
      and ce.kind = 'human.card_action'
) act on true
left join card_feedback_verdicts v
       on v.org_id = k.org_id and v.card_id = k.card_id
left join lateral (
    select count(*) as deliveries, min(ob.delivered_at) as first_delivered_at
    from delivery_outbox ob
    where ob.org_id = k.org_id and ob.card_id = k.card_id and ob.status = 'delivered'
) d on true
left join executions x
       on x.org_id = s.org_id and x.signal_id = s.signal_id
left join execution_outcomes o
       on o.org_id = x.org_id and o.execution_id = x.execution_id
left join lateral (
    select count(*) as usd_calls, sum(lc.input_tokens) as input_tokens,
           sum(lc.output_tokens) as output_tokens
    from llm_costs lc
    where lc.org_id = s.org_id and lc.subject_ref = 'signal:' || s.signal_id
) cost on true;

comment on view counterfactual_ledger is
  'One row per recommendation: what it cost, whether it was seen, what a human did, what it became. The denominator for every ROI claim.';
