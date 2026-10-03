# L3 · `reason/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py reason > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-reason-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       121
lines                       41,363
files that WRITE a table    21
distinct tables written     35
⛔ written, no receipt       29
declared silences           14
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `signals` | 29 | `composer.py`, `domain_shadow.py`, `emit.py`, `publication.py`, `runner.py`, `situation_binding.py` |
| `discrepancies` | 6 | `passes.py`, `store.py` |
| `card_events` | 3 | `emit.py` |
| `moments` | 2 | `emit.py`, `store.py` |
| `reasoning_context_payloads` | 2 | `store.py` |
| `signal_suppression_log` | 2 | `runner.py` |
| `baselines` | 1 | `baselines.py` |
| `rate_counters` | 1 | `screen_insight.py` |
| `realtime_events` | 1 | `followups.py` |
| `reasoning_capability_snapshots` | 1 | `store.py` |
| `screen_memory_jobs` | 1 | `screen_memory_batch.py` |
| `screen_thread_summaries` | 1 | `screen_memory_batch.py` |
| `l4_brief_rankings` | 0 | `brief_ranking.py` |
| `l4_r_site_calls` | 0 | `store.py` |
| `l4_r_site_generations` | 0 | `llm_sites.py` |
| `l4_reasoning_bundles` | 0 | `store.py` |
| `moment_cache` | 0 | `prep.py`, `store.py` |
| `moment_feedback` | 0 | `store.py` |
| `post_pass_watermarks` | 0 | `passes.py` |
| `reasoning_candidate_checks` | 0 | `store.py` |
| `reasoning_context_snapshots` | 0 | `store.py` |
| `reasoning_evidence_digests` | 0 | `store.py` |
| `reasoning_evidence_id_map` | 0 | `store.py` |
| `reasoning_publication_watermarks` | 0 | `runner.py` |
| `screen_followups` | 0 | `followups.py`, `screen_memory.py` |
| `screen_thread_verdicts` | 0 | `followups.py` |
| `seat_profiles` | 0 | `seat_profile.py` |
| `seat_slice_versions` | 0 | `followups.py`, `slice.py` |
| `team_situations` | 0 | `emit.py` |

## ⛔ THE COLUMN THAT WAS HERE IS GONE, AND THAT IS A FINDING

This section used to list modules of 100+ lines that no test file names. ⛔⛔ **It was removed on 2026-10-03 after six repairs failed to make it honest**, and the removal is the most useful thing it produced.

Across three package audits it reported **33** entries. ⛔ Nineteen were false, and each false entry was a candidate finding that died on inspection:

```
a @router.get handler has no Python caller and no test imports its module   -> false
a table read through funnel.read_sweep: reached, path written nowhere       -> false
test_unit_roster.py parametrises ALL_UNITS: 23 units run, no class named    -> false x16
ConstraintReasoner = ConstraintUnit — an alias a ClassDef scan cannot see   -> false
```

⛔ And every repair over-corrected in the other direction, which is worse, because a false negative **hides** a live module:

```
counting a generic CAPABILITY constant rescued a module with NO test at all
counting __all__ as a definition made all 23 unit names look ambiguous, so the
    whole column collapsed to zero findings
⛔⛔ and the guard written FOR this column named two functions in its own docstring,
    which made the module it was asserting is untested read as named — the observer
    altering the thing it measured
```

> ⛔ **A column whose error rate is unknown in BOTH directions is a column nobody should act on.** Naming is not coverage, six attempts did not make it one, and the section produced **zero** surviving findings in three audits while costing nineteen false leads.

⛔ **What it did produce, kept as a real finding rather than a table row:** `api/identity_routes.py` has **five routes and 130 lines**, and no test file mentions it by any means — verified by hand, not by this column. That is on `21-PLAN-TO-PRODUCTION.md`.

⛔ **What replaced it: nothing.** The table above — *tables a package writes that no receipt covers* — held in all three audits and is what the audit is for.

## Every file

| file | lines | public | declared silences | writes | reads |
|---|---|---|---|---|---|
| `store.py` | 2423 | 0 | — | `reasoning_candidate_checks`, `reasoning_candidates`, `reasoning_capability_snapshots`, `reasoning_context_payloads`, `reasoning_context_snapshots`, `reasoning_evidence_digests`, `reasoning_evidence_id_map`, `reasoning_reasoner_results`, `reasoning_run_outputs`, `reasoning_runs` | `config_snapshots`, `reasoning_candidate_checks`, `reasoning_candidates`, `reasoning_capability_snapshots`, `reasoning_context_payloads`, `reasoning_context_snapshots` +5 |
| `adapters/expertise.py` | 1623 | 3 | — | — | — |
| `runner.py` | 1538 | 2 | — | `cards`, `reasoning_publication_watermarks`, `signal_suppression_log`, `signals` | `baselines`, `connections`, `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes` +9 |
| `domain_shadow.py` | 1326 | 3 | — | `cards`, `signals` | `context_situations`, `graph_facts`, `graph_nodes`, `graph_source_refs`, `signals`, `tenant_packs` |
| `decision_maker.py` | 1261 | 19 | — | — | — |
| `moments/screen_insight.py` | 1183 | 27 | — | `rate_counters` | `rate_counters` |
| `llm_decision_maker.py` | 866 | 8 | — | — | `graph_facts`, `graph_nodes`, `l1_extraction_results`, `source_events` |
| `moments/followups.py` | 858 | 45 | — | `realtime_events`, `screen_followups`, `screen_thread_verdicts`, `seat_slice_versions` | `capture_policies`, `delivery_preferences`, `graph_aliases`, `graph_nodes`, `moment_feedback`, `moments` +3 |
| `reasoners/timeline_unit.py` | 726 | 1 | — | — | — |
| `adapters/rule_compiler.py` | 711 | 7 | — | — | — |
| `adapters/situation_projection.py` | 710 | 2 | — | — | — |
| `meetings/prep.py` | 672 | 15 | — | `moment_cache` | `graph_aliases`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `open_loops` +4 |
| `critique.py` | 668 | 12 | — | — | `reasoning_run_outputs`, `reasoning_runs` |
| `adapters/play_priors.py` | 585 | 2 | — | — | — |
| `reasoners/recommendation_unit.py` | 582 | 0 | — | — | — |
| `interpretation.py` | 572 | 7 | — | — | — |
| `plan.py` | 571 | 2 | 2 | — | — |
| `reasoners/confidence.py` | 555 | 0 | — | — | — |
| `unit_health.py` | 555 | 11 | — | — | — |
| `narration.py` | 546 | 9 | 1 | — | — |
| `reasoners/policy_unit.py` | 531 | 0 | — | — | — |
| `bundle/gauntlet.py` | 512 | 1 | — | — | — |
| `reasoners/validation_unit.py` | 496 | 2 | — | — | — |
| `moments/slice.py` | 479 | 5 | — | `seat_slice_versions` | `connections`, `graph_aliases`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations` +4 |
| `reasoners/constraint.py` | 477 | 0 | — | — | — |
| `adapters/citations.py` | 444 | 6 | — | — | — |
| `brief_ranking.py` | 441 | 7 | — | `l4_brief_rankings` | `card_events`, `cards`, `graph_edges`, `l4_brief_rankings`, `signals` |
| `intelligence.py` | 439 | 3 | — | — | `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `graph_versions`, `reasoning_context_payloads` +1 |
| `moments/screen_memory_batch.py` | 436 | 12 | — | `screen_memory_jobs`, `screen_thread_summaries` | `org_seats`, `screen_memory_jobs`, `screen_thread_summaries` |
| `reasoners/dependency_unit.py` | 430 | 0 | — | — | — |
| `moments/draft_review.py` | 429 | 16 | — | — | `graph_edges`, `graph_facts`, `graph_nodes`, `screen_followups` |
| `reasoners/alternative_unit.py` | 416 | 0 | — | — | — |
| `llm_sites.py` | 414 | 6 | — | `l4_r_site_generations` | `l4_r_site_generations` |
| `reasoners/impact_unit.py` | 413 | 0 | — | — | — |
| `reasoners/tradeoff_unit.py` | 398 | 0 | — | — | — |
| `reasoners/cost_unit.py` | 393 | 0 | — | — | — |
| `reasoners/resource_unit.py` | 391 | 0 | — | — | — |
| `meetings/passes.py` | 381 | 7 | — | — | `devices`, `graph_aliases`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_source_refs` +4 |
| `bundle/gate.py` | 372 | 2 | — | — | — |
| `composer.py` | 366 | 3 | — | `cards`, `signals` | `graph_edges`, `graph_nodes`, `signals` |
| `authority.py` | 365 | 2 | — | — | — |
| `adapters/legacy_pack.py` | 364 | 1 | — | — | — |
| `bundle/template.py` | 363 | 2 | — | — | — |
| `evidence.py` | 363 | 13 | — | — | — |
| `orchestrator.py` | 362 | 0 | — | — | — |
| `reasoners/risk.py` | 362 | 0 | — | — | — |
| `bundle/store.py` | 360 | 1 | — | `l4_r_site_calls`, `l4_reasoning_bundles` | `cards`, `l4_r_site_calls`, `l4_reasoning_bundles`, `signals` |
| `moments/screen_rules.py` | 331 | 7 | — | — | — |
| `reasoners/priority.py` | 322 | 0 | — | — | — |
| `publication.py` | 318 | 4 | — | `cards`, `signals` | — |
| `reasoners/scheduling_unit.py` | 318 | 0 | — | — | — |
| `reasoners/context_unit.py` | 310 | 2 | — | — | — |
| `adapters/native.py` | 305 | 2 | — | — | — |
| `audit.py` | 300 | 1 | — | — | — |
| `moments/recall.py` | 290 | 4 | — | — | `graph_aliases`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `open_loops` +2 |
| `llm_interpretation.py` | 282 | 5 | — | — | — |
| `bundle/numbers.py` | 280 | 1 | — | — | — |
| `reasoners/opportunity.py` | 279 | 0 | — | — | — |
| `moments/seat_profile.py` | 273 | 9 | — | `seat_profiles` | `screen_followups`, `screen_thread_verdicts`, `seat_profiles` |
| `team/emit.py` | 271 | 4 | — | `card_events`, `cards`, `moments`, `signals`, `team_situations` | `cards`, `moments`, `team_situations` |
| `unit.py` | 266 | 0 | — | — | — |
| `situation_reasoner.py` | 262 | 9 | 1 | — | — |
| `baselines.py` | 260 | 3 | 2 | `baselines` | `baselines`, `graph_edges`, `graph_nodes`, `source_events` |
| `bundle/grounding.py` | 254 | 1 | — | — | — |
| `engine.py` | 244 | 2 | — | — | — |
| `bundle/budget.py` | 236 | 3 | — | — | `l4_r_site_calls` |
| `moments/store.py` | 234 | 9 | — | `learning_event_inbox`, `moment_cache`, `moment_feedback`, `moments` | `capture_policies`, `moment_cache`, `moment_feedback`, `moments` |
| `registry.py` | 227 | 3 | — | — | — |
| `verify/store.py` | 221 | 8 | — | `discrepancies` | `discrepancies`, `graph_facts`, `graph_nodes`, `graph_source_refs`, `source_events` |
| `cutover.py` | 218 | 2 | 2 | — | — |
| `bundle/narrator.py` | 216 | 1 | — | — | — |
| `team/readiness.py` | 213 | 8 | — | — | `graph_facts`, `graph_nodes`, `team_milestones` |
| `replay.py` | 206 | 7 | 1 | — | — |
| `bundle/prompt.py` | 199 | 1 | — | — | — |
| `moments/engagement.py` | 197 | 6 | — | — | `connections`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `graph_source_refs` +5 |
| `situation_binding.py` | 191 | 5 | — | `signals` | — |
| `bundle/sweep.py` | 187 | 2 | — | — | — |
| `team/away.py` | 187 | 2 | — | — | `graph_nodes`, `open_loops`, `org_seats`, `source_events` |
| `verify/passes.py` | 178 | 7 | — | `discrepancies`, `post_pass_watermarks` | `graph_facts`, `org_seats`, `orgs`, `post_pass_watermarks` |
| `moments/screen_triage.py` | 167 | 5 | — | — | — |
| `adapters/legacy_context.py` | 163 | 2 | — | — | — |
| `simulation.py` | 158 | 1 | 1 | — | — |
| `foresight.py` | 153 | 5 | — | — | `graph_facts` |
| `signals_derived.py` | 153 | 3 | — | — | — |
| `telemetry.py` | 146 | 3 | 2 | — | — |
| `output_lane.py` | 142 | 2 | 1 | — | — |
| `bundle/sites.py` | 136 | 4 | — | — | — |
| `moments/guards.py` | 134 | 4 | — | — | `capture_policies`, `delivery_preferences`, `moments`, `orgs`, `presence_leases` |
| `retention.py` | 132 | 1 | — | — | `reasoning_capability_snapshots`, `reasoning_context_snapshots`, `reasoning_runs`, `signals` |
| `reasoners/common.py` | 124 | 13 | — | — | — |
| `reasoning_health.py` | 121 | 4 | — | — | — |
| `scoring.py` | 120 | 6 | — | — | — |
| `actionability.py` | 117 | 2 | 1 | — | — |
| `reasoners/temporal.py` | 110 | 1 | — | — | — |
| `team/cover.py` | 106 | 1 | — | — | — |
| `moments/screen_memory.py` | 105 | 2 | — | `screen_followups` | `screen_followups` |
| `moments/common.py` | 102 | 7 | — | — | — |
| `reasoners/signal_composition.py` | 93 | 0 | — | — | — |
| `team/common.py` | 90 | 4 | — | — | — |
| `uncited_lanes.py` | 90 | 2 | — | — | — |
| `adapters/legacy.py` | 85 | 1 | — | — | — |
| `guards.py` | 84 | 3 | — | — | — |
| `reasoners/relationship.py` | 82 | 0 | — | — | — |
| `reasoners/__init__.py` | 77 | 1 | — | — | — |
| `unroutable.py` | 70 | 1 | — | — | — |
| `moments/reply_draft.py` | 66 | 3 | — | — | — |
| `reasoners/legacy_rule.py` | 59 | 0 | — | — | — |
| `reasoners/legacy_gate.py` | 57 | 0 | — | — | — |
| `team/postpass.py` | 56 | 1 | — | — | — |
| `bundle/__init__.py` | 54 | 0 | — | — | — |
| `team/passes.py` | 46 | 1 | — | — | — |
| `protocols.py` | 43 | 0 | — | — | — |
| `reasoners/planning.py` | 37 | 0 | — | — | — |
| `rules.py` | 33 | 2 | — | — | — |
| `adapters/__init__.py` | 11 | 0 | — | — | — |
| `canonical.py` | 11 | 0 | — | — | — |
| `team/__init__.py` | 9 | 0 | — | — | — |
| `moments/__init__.py` | 8 | 0 | — | — | — |
| `__init__.py` | 6 | 0 | — | — | — |
| `meetings/__init__.py` | 2 | 0 | — | — | — |
| `verify/__init__.py` | 2 | 0 | — | — | — |
