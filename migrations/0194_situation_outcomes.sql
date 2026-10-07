-- 0194 · situation_outcomes — what came of each ADMITTED situation candidate (STEP-06, nothing is
-- lost silently).
--
-- WHY. The admission gate records admit, hold and reject for every live situation (0122), and the
-- change gate records every DECIDED subject (0191). Between the two, a situation that was admitted
-- and then stopped — no expertise route, an incomplete or conflicting slice, a required field
-- missing, an unsupported shape, no tenant pack, today's budget, an error — left a counter in one
-- log line and nothing else (`reason/domain_shadow.py`; `speedrun008/YC-II W27/` STEP-06 §8). This
-- table holds that end, so "why did this situation never become a card?" is one read.
--
-- ONE ROW PER ADMITTED CANDIDATE, keyed on its admission `decision_id`: a changed candidate is a new
-- admission decision, so this is one row per material change, never one per sweep (the
-- 9-row-receipt lesson, `7e19a1c9`). The row holds the candidate's CURRENT end: a pass that ends it
-- the same way moves `last_seen_at` and `sweeps`; a pass that ends it differently — today's budget,
-- then a decision tomorrow — replaces the outcome and starts the count again.
--
-- LIVE ROWS ONLY. A measurement pass writes nothing, the rule the admission ledger already keeps
-- (`record=live_row`): a read-only gate command must be able to run the compiled pass.

create table if not exists situation_outcomes (
    org_id        text        not null references orgs (id) on delete cascade,
    decision_id   text        not null
                  references situation_admission_decisions (decision_id) on delete cascade,
    situation_id  text        not null,

    --: What came of the candidate after it was admitted:
    --:   decided            it reached a decision — the change gate's row says which
    --:   no_route           no expertise claims it (`NoExpertiseRoute`; the reason says why)
    --:   incomplete         the slice was incomplete
    --:   conflict           the slice carried a conflict
    --:   required_missing   a field the capability requires was missing
    --:   unsupported        the shape is not supported (the reason says which)
    --:   no_tenant_pack     the tenant holds no pack for its domain
    --:   budget_exhausted   today's allowance was spent
    --:   error              the pass failed on it
    outcome       text        not null,
    reason        text,

    recorded_at   timestamptz not null,
    last_seen_at  timestamptz not null,
    sweeps        integer     not null default 1,

    primary key (org_id, decision_id),

    constraint situation_outcomes_outcome_check
        check (outcome in ('decided', 'no_route', 'incomplete', 'conflict', 'required_missing',
                           'unsupported', 'no_tenant_pack', 'budget_exhausted', 'error')),
    constraint situation_outcomes_sweeps_check
        check (sweeps >= 1)
);

create index if not exists situation_outcomes_by_situation
    on situation_outcomes (org_id, situation_id);

comment on table situation_outcomes is
  'STEP-06: what came of each admitted live situation candidate after admission — decided, or the stop and its reason. One row per admission decision, written once; last_seen_at and sweeps move.';
