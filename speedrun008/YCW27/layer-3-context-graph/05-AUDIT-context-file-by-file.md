# L3 · `context/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py context > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-context-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       124
lines                       50,885
files that WRITE a table    37
distinct tables written     44
⛔ written, no receipt       33
declared silences           23
⛔ >=100 lines, no test names it  2
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `graph_nodes` | 46 | `graph_store.py`, `merge.py` |
| `graph_versions` | 13 | `graph_store.py` |
| `l1_extraction_results` | 10 | `graph_store.py` |
| `graph_source_refs` | 9 | `derived_provenance.py`, `graph_store.py` |
| `l2_processing_runs` | 7 | `runner.py` |
| `context_correlation_members` | 4 | `correlation.py`, `correlation_membership.py`, `merge.py` |
| `discrepancies` | 4 | `graph_store.py` |
| `open_loops` | 4 | `open_loops.py` |
| `context_attention` | 3 | `attention.py` |
| `situation_admission_decisions` | 3 | `situation_publisher.py` |
| `cohort_definitions` | 2 | `cohort.py` |
| `merge_proposals` | 2 | `identity.py`, `merge.py` |
| `pattern_fires` | 2 | `store.py` |
| `pattern_runs` | 2 | `store.py` |
| `cohort_membership` | 1 | `cohort.py` |
| `context_read_models` | 1 | `read_models.py` |
| `graph_health` | 1 | `health.py` |
| `metric_history` | 1 | `history.py` |
| `pattern_activation` | 1 | `store.py` |
| `situation_resolution_claims` | 1 | `store.py` |
| `source_coverage` | 1 | `epoch.py` |
| `context_angle_verdicts` | 0 | `store.py` |
| `context_node_lifecycle` | 0 | `health.py` |
| `context_residue` | 0 | `residue.py` |
| `contract_spend_attributions` | 0 | `correlation_resource.py` |
| `coverage_epochs` | 0 | `epoch.py` |
| `edge_coverage_declarations` | 0 | `store.py` |
| `evidence_needs` | 0 | `evidence_need_store.py` |
| `graph_change_outbox` | 0 | `graph_store.py` |
| `l2_model_runs` | 0 | `model_audit.py` |
| `peer_baselines` | 0 | `peer_baseline.py` |
| `situation_absences` | 0 | `missing.py` |
| `situation_interpretations` | 0 | `interpretation_store.py` |

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

| file | lines | public fns | writes |
|---|---|---|---|
| `lifecycle/resolution.py` | 320 | 1 | — |
| `correlation_membership.py` | 140 | 2 | `context_correlation_members` |

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `situation_bso.py` | 2133 | 23 | 27 | 1 | `context_situations` | `context_correlation_members`, `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_source_refs` +6 |
| `pipeline.py` | 2049 | 5 | 39 | — | — | `graph_edges`, `graph_facts`, `graph_nodes`, `source_events` |
| `outreach_situations.py` | 1916 | 17 | 35 | — | — | `context_correlation_members`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `graph_source_refs` +1 |
| `analytic/cohort.py` | 1814 | 25 | 12 | — | `cohort_definitions`, `cohort_membership` | `cohort_definitions`, `cohort_membership`, `graph_facts`, `graph_nodes` |
| `support_situations.py` | 1764 | 22 | 9 | — | `context_situations`, `graph_facts` | `baselines`, `connections`, `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes` +4 |
| `runner.py` | 1622 | 2 | 42 | — | `l2_convergence`, `l2_processing_runs` | `connections`, `context_correlation_members`, `context_node_lifecycle`, `context_situations`, `l1_extraction_results`, `l2_processing_runs` +7 |
| `analytic/sampler.py` | 1465 | 10 | 10 | — | — | `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `graph_source_refs` +2 |
| `importance.py` | 1387 | 9 | 8 | — | — | `context_correlation_members`, `graph_facts`, `qualified_signals`, `signal_conflicts`, `source_coverage`, `source_events` |
| `graph_store.py` | 1330 | 3 | 56 | — | `discrepancies`, `graph_change_outbox`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `graph_source_refs`, `graph_versions`, `l1_extraction_results`, `llm_costs`, `source_identity_map` | `discrepancies`, `graph_change_outbox`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_source_refs` +3 |
| `situations.py` | 1325 | 20 | 40 | — | `context_situations` | `context_correlation_members`, `context_correlations`, `context_situations`, `discrepancies`, `graph_facts`, `graph_nodes` +4 |
| `correlation_dependency.py` | 1154 | 10 | 9 | — | — | `graph_facts`, `graph_nodes`, `graph_source_refs`, `l1_extraction_results`, `source_events` |
| `analytic/comparator.py` | 1139 | 16 | 5 | — | — | `graph_facts` |
| `correlation_timeline.py` | 1126 | 13 | 6 | 1 | — | `l1_extraction_results`, `source_events` |
| `backfill.py` | 832 | 10 | 6 | 1 | `graph_facts` | `context_correlation_members`, `context_correlations`, `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes` +6 |
| `analytic/history.py` | 773 | 8 | 13 | — | `metric_history` | `metric_history` |
| `analytic/peer_baseline.py` | 763 | 13 | 5 | — | `peer_baselines` | `peer_baselines` |
| `document_register.py` | 708 | 8 | 4 | — | `context_situations`, `graph_facts` | `context_situations`, `graph_edges`, `prepared_content`, `source_events` |
| `domain_spec.py` | 692 | 9 | 31 | 1 | — | — |
| `authority_view.py` | 676 | 6 | 5 | — | `authority_rules` | `authority_rules` |
| `analytic/correlator.py` | 674 | 14 | 3 | — | — | — |
| `derived.py` | 653 | 4 | 11 | — | `graph_facts` | `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations` |
| `patterns/store.py` | 643 | 12 | 2 | — | `edge_coverage_declarations`, `pattern_activation`, `pattern_fires`, `pattern_runs` | `edge_coverage_declarations`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `pattern_activation` +2 |
| `patterns/matcher.py` | 628 | 2 | 5 | — | — | — |
| `analytic/trend.py` | 610 | 5 | 8 | — | `graph_facts` | — |
| `analytic/gap_reason.py` | 587 | 7 | 1 | — | — | `source_events` |
| `correlation.py` | 579 | 11 | 38 | 1 | `context_correlation_members`, `context_correlations` | `context_correlation_members`, `context_correlations`, `graph_edges`, `graph_nodes`, `source_events` |
| `situation_publisher.py` | 573 | 4 | 14 | — | `situation_admission_decisions` | — |
| `analytic/anomaly.py` | 568 | 4 | 5 | — | — | `graph_facts` |
| `correlation_resource.py` | 566 | 4 | 2 | — | `contract_spend_attributions` | `graph_facts`, `graph_nodes`, `source_coverage` |
| `patterns/contract.py` | 548 | 3 | 5 | — | — | — |
| `merge.py` | 544 | 5 | 8 | — | `context_correlation_members`, `context_correlations`, `context_situations`, `graph_aliases`, `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `merge_history`, `merge_proposals`, `source_identity_map` | `context_attention`, `context_correlation_members`, `context_correlations`, `context_situations`, `graph_edges`, `graph_facts` +3 |
| `identity.py` | 535 | 14 | 15 | 1 | `graph_aliases`, `merge_proposals` | `graph_aliases`, `graph_nodes`, `merge_proposals` |
| `condition_situations.py` | 515 | 5 | 3 | — | — | `context_angle_verdicts`, `graph_facts` |
| `quality/missing.py` | 497 | 11 | 5 | — | `situation_absences` | `situation_absences` |
| `campaign_candidates.py` | 431 | 6 | 2 | — | — | `graph_facts` |
| `angles/contract.py` | 427 | 5 | 6 | — | — | — |
| `framing/headline.py` | 422 | 5 | 2 | — | — | — |
| `health.py` | 405 | 6 | 3 | — | `context_node_lifecycle`, `graph_health` | `context_correlation_members`, `context_correlations`, `context_node_lifecycle`, `context_situations`, `discrepancies`, `graph_aliases` +8 |
| `quality/epoch.py` | 396 | 8 | 1 | — | `coverage_epochs`, `source_coverage` | `coverage_epochs` |
| `patterns/registry.py` | 395 | 10 | 4 | — | — | — |
| `correlation_people.py` | 388 | 7 | 1 | — | — | `graph_aliases`, `graph_edges`, `graph_facts`, `graph_nodes`, `org_members`, `org_seats` +2 |
| `availability.py` | 386 | 7 | 3 | 1 | `graph_facts` | `graph_facts`, `graph_nodes`, `graph_source_refs` |
| `extract/availability.py` | 385 | 2 | 1 | 1 | — | — |
| `lifecycle/store.py` | 381 | 10 | 2 | — | `context_situations`, `situation_resolution_claims` | `context_correlation_members`, `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes`, `l1_extraction_results` +3 |
| `angles/store.py` | 369 | 3 | 6 | — | `context_angle_verdicts` | `context_angle_verdicts`, `context_residue`, `graph_facts` |
| `correlation_domain.py` | 368 | 6 | 1 | — | — | `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes` |
| `analytic/publish.py` | 364 | 3 | 5 | — | `graph_facts` | `graph_facts` |
| `tenant_profile.py` | 360 | 12 | 2 | 5 | — | `graph_facts`, `graph_nodes` |
| `waiting.py` | 360 | 3 | 7 | — | — | `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `graph_source_refs`, `source_events` |
| `angles/library.py` | 325 | 0 | 4 | — | — | — |
| `correlation_organization.py` | 324 | 3 | 3 | — | — | `graph_edges`, `graph_facts`, `graph_nodes` |
| `lifecycle/resolution.py` | 320 | 1 | 0 | — | — | `l2_model_runs` |
| `documents.py` | 319 | 7 | 2 | — | — | `graph_facts`, `graph_nodes` |
| `correlation_history.py` | 299 | 2 | 1 | — | — | `card_feedback_verdicts`, `cards`, `context_correlations`, `execution_outcomes`, `signals` |
| `quality/refusals.py` | 299 | 2 | 2 | — | — | — |
| `periodic.py` | 297 | 5 | 5 | — | `context_situations`, `graph_facts` | `context_situations`, `graph_facts`, `graph_nodes`, `source_events` |
| `correlation_conversation.py` | 293 | 6 | 3 | — | — | `graph_edges`, `graph_facts`, `graph_nodes`, `graph_source_refs`, `qualified_signals`, `source_events` |
| `meeting_touch.py` | 289 | 1 | 5 | — | `context_situations` | `connections`, `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes`, `org_seats` +1 |
| `vocabulary.py` | 286 | 4 | 5 | — | — | — |
| `analytic_situations.py` | 263 | 2 | 1 | — | — | `graph_facts` |
| `residue.py` | 262 | 2 | 5 | — | `context_residue` | `context_correlation_members`, `context_residue`, `context_situations`, `graph_facts`, `graph_observations`, `graph_source_refs` +2 |
| `lifecycle/judge.py` | 259 | 1 | 4 | — | — | — |
| `blocker_situations.py` | 254 | 3 | 2 | — | — | `graph_facts` |
| `proposal_gate.py` | 248 | 2 | 3 | — | — | — |
| `lifecycle/contract.py` | 235 | 0 | 4 | — | — | — |
| `projections.py` | 235 | 5 | 1 | 1 | — | `context_correlation_members`, `context_situations`, `graph_edges`, `graph_facts`, `graph_nodes` |
| `fact_visibility.py` | 228 | 11 | 2 | 2 | — | `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `source_events` |
| `lifecycle/prompt.py` | 211 | 5 | 4 | — | — | — |
| `hold_needs.py` | 206 | 3 | 1 | 1 | — | — |
| `bounded_read.py` | 195 | 3 | 1 | 1 | — | `graph_versions` |
| `framing/timeline.py` | 195 | 4 | 1 | — | — | — |
| `patterns/slice.py` | 190 | 0 | 3 | — | — | — |
| `qes_adapter.py` | 187 | 1 | 5 | — | — | — |
| `angles/queues.py` | 182 | 3 | 3 | — | — | `context_angle_verdicts` |
| `structured.py` | 177 | 1 | 6 | — | — | — |
| `lifecycle/gate.py` | 174 | 3 | 5 | — | — | — |
| `extract/prompt.py` | 170 | 0 | 2 | — | — | — |
| `attention.py` | 166 | 2 | 3 | — | `context_attention` | `graph_facts`, `graph_nodes`, `graph_observations`, `signals` |
| `attention_situations.py` | 166 | 3 | 1 | — | — | `graph_nodes` |
| `hold_resolution.py` | 163 | 1 | 1 | 1 | — | — |
| `angles/asker.py` | 162 | 2 | 2 | — | — | — |
| `extract/vocab.py` | 161 | 5 | 3 | — | — | — |
| `meeting_situations.py` | 159 | 1 | 1 | — | — | — |
| `context_health.py` | 152 | 4 | 1 | — | — | — |
| `reworded_outreach.py` | 152 | 1 | 1 | — | — | — |
| `llm/client.py` | 146 | 1 | 14 | — | — | — |
| `slice_weight.py` | 141 | 4 | 1 | — | — | — |
| `correlation_membership.py` | 140 | 2 | 0 | — | `context_correlation_members` | `context_correlations`, `graph_facts`, `graph_source_refs` |
| `derived_provenance.py` | 140 | 2 | 4 | — | `graph_source_refs` | `graph_source_refs`, `source_events` |
| `evidence_need_store.py` | 140 | 4 | 1 | 2 | `evidence_needs` | `evidence_needs` |
| `canon.py` | 135 | 6 | 2 | 2 | — | `graph_nodes` |
| `stated_dependency.py` | 135 | 3 | 1 | — | — | `graph_facts` |
| `open_loops.py` | 134 | 4 | 3 | — | `open_loops` | `open_loops` |
| `quality/lens.py` | 134 | 2 | 2 | — | — | `source_coverage` |
| `conversion.py` | 128 | 4 | 1 | — | — | `graph_facts` |
| `evidence_needs.py` | 123 | 3 | 1 | — | — | — |
| `lifecycle/authority.py` | 118 | 5 | 3 | — | — | — |
| `extract/extractor.py` | 117 | 2 | 9 | — | — | — |
| `lifecycle/ledger.py` | 116 | 1 | 2 | — | — | — |
| `patterns/candidate.py` | 116 | 1 | 2 | — | — | — |
| `quality/inference.py` | 116 | 4 | 6 | — | — | — |
| `lifecycle/textguard.py` | 114 | 1 | 1 | — | — | — |
| `lane_health.py` | 112 | 2 | 1 | — | — | — |
| `patterns/scorer.py` | 108 | 2 | 1 | — | — | — |
| `extract/envelope.py` | 102 | 1 | 1 | — | — | — |
| `meeting_lifecycle.py` | 95 | 1 | 3 | — | — | — |
| `model_audit.py` | 93 | 2 | 1 | — | `l2_model_runs`, `llm_costs` | — |
| `read_models.py` | 92 | 2 | 2 | — | `context_read_models` | `graph_facts`, `graph_nodes`, `graph_observations`, `graph_versions` |
| `domain_silence.py` | 91 | 2 | 4 | — | — | — |
| `slice_silence.py` | 86 | 3 | 2 | — | — | — |
| `llm/parse.py` | 79 | 2 | 0 | — | — | — |
| `interpretation_store.py` | 77 | 1 | 1 | — | `situation_interpretations` | — |
| `patterns/routing.py` | 73 | 0 | 2 | — | — | — |
| `guard.py` | 44 | 3 | 0 | — | — | — |
| `expected_facts.py` | 42 | 1 | 1 | — | — | — |
| `quality/__init__.py` | 40 | 0 | 0 | — | — | — |
| `lifecycle/__init__.py` | 35 | 0 | 0 | — | — | — |
| `patterns/__init__.py` | 35 | 0 | 0 | — | — | — |
| `angles/__init__.py` | 30 | 0 | 0 | — | — | — |
| `framing/__init__.py` | 19 | 0 | 0 | — | — | — |
| `analytic/__init__.py` | 11 | 0 | 0 | — | — | — |
| `__init__.py` | 0 | 0 | 0 | — | — | — |
| `extract/__init__.py` | 0 | 0 | 0 | — | — | — |
| `llm/__init__.py` | 0 | 0 | 0 | — | — | — |
