-- 0189 · `output_lane` — which KIND of output a reader gets, carried to the two rows that render.
--
-- WHAT WAS MISSING. Grepped 2026-09-30: `"investigation"` had **zero hits** in `genios_engine/`, as did
-- `OUTPUT_LANE` and `LANES =`. So the product had one shape of output — a card — and no way to say
-- whether a given card was a thing to DO, a thing to FIND OUT, a disagreement to RULE ON, a thing to
-- WATCH, or something deliberately withheld.
--
-- ⛔ THIS IS NOT `outcome_kind`, AND THE TWO MUST NOT BE MERGED.
--
--     outcome_kind  ->  did we reach a decision, and if not, why not
--     output_lane   ->  what kind of output should the human see
--
-- `contracts/reasoning.ReasoningDecision` defends the first in its own docstring: *"`outcome` may be
-- `no_action`, `defer`, `insufficient_context`, `blocked` or `failed`, and each of those is a real
-- decision that must survive to the surface. A projection that only carries `decision` loses five
-- sixths of the vocabulary."* And a `decision` outcome routes to the DECISION lane or the MONITOR lane
-- depending on confidence, so one column cannot carry both.
--
-- ⛔ AND `lane_reason` IS NOT OPTIONAL DECORATION. A card in the wrong lane with no recorded reason is
-- undiagnosable, and the router is the single most consequential new branch in the reasoning layer. The
-- check below makes the pair atomic: a lane without its reason cannot be written at all.
--
-- NULLABLE, and the NULL is an answer: every row written before this migration was never routed, and a
-- default lane would claim a routing decision nobody made. `deliver/` reads NULL as "unrouted" exactly
-- as it already reads a NULL `situation_id` as UNINTERPRETED — migration 0182 set that precedent and
-- its comment states the rule: *"fewer cards must come from merging, never from dropping."*

-- ⛔ WHAT THIS MIGRATION DELIBERATELY DOES NOT ADD: columns on `reasoning_run_outputs`.
--
-- The audited decision row already carries the lane, in two ways. `ReasoningDecision.to_semantic_dict`
-- includes `output_lane` and `lane_reason`, so the lane is inside `decision_hash` — a decision routed
-- differently is a different decision, by identity. And `decision_core` is the caller's own mapping of
-- that dict.
--
-- So a pair of columns there would duplicate a value already in the same row, and a duplicated value
-- can disagree with its original. Adding them and wiring no writer would be worse still: this
-- programme has found "built, tested, green, and called by nothing" seven times, and an unused nullable
-- column is the cheapest possible way to produce the eighth.
--
-- A queryable column on the audited row is a real thing somebody may want. It is a separate unit, with
-- a writer, when somebody wants it.

-- ── the shredded projection the card actually reads ────────────────────────────────────────────
alter table signals add column if not exists output_lane text;
alter table signals add column if not exists lane_reason text;

alter table signals drop constraint if exists signals_output_lane_check;
alter table signals add constraint signals_output_lane_check
    check (output_lane is null
           or output_lane in ('decision', 'investigation', 'conflict', 'monitor', 'suppress'))
    not valid;

alter table signals drop constraint if exists signals_lane_has_a_reason;
alter table signals add constraint signals_lane_has_a_reason
    check ((output_lane is null and lane_reason is null)
           or (output_lane is not null and lane_reason is not null
               and length(trim(lane_reason)) > 0))
    not valid;

-- "How many of each kind did this tenant receive, and when?" — the read that makes a lane mix
-- observable instead of anecdotal. Partial, because an unrouted row is not part of the mix.
create index if not exists signals_by_output_lane
    on signals (org_id, output_lane, eval_time desc)
    where output_lane is not null;

comment on column signals.output_lane is
  'decision | investigation | conflict | monitor | suppress — what KIND of output the reader gets. '
  'NOT outcome_kind, which says whether a decision was reached. NULL means this row was never routed.';
