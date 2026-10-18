# L3 · `api/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py api > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-api-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       44
lines                       19,498
files that WRITE a table    20
distinct tables written     42
⛔ written, no receipt       28
declared silences           2
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `agent_registry` | 8 | `agent_mgmt_routes.py` |
| `delivery_preferences` | 3 | `delivery_routes.py` |
| `learning_objects` | 3 | `learning_routes.py` |
| `card_events` | 2 | `intelligence_routes.py` |
| `l1_sync_runs` | 2 | `routes.py` |
| `org_members` | 2 | `account_routes.py` |
| `api_keys` | 1 | `account_routes.py`, `agent_mgmt_routes.py`, `auth_routes.py` |
| `decisions` | 1 | `intelligence_routes.py` |
| `feature_flags` | 1 | `routes.py` |
| `org_invites` | 1 | `account_routes.py` |
| `org_mission_critical_entities` | 1 | `routes.py` |
| `seat_objectives` | 1 | `routes.py` |
| `team_milestones` | 1 | `team_routes.py` |
| `agent_grants` | 0 | `agent_mgmt_routes.py` |
| `approvals_queue` | 0 | `approval_routes.py` |
| `card_feedback_revisions` | 0 | `intelligence_routes.py` |
| `domain_requests` | 0 | `expertise_routes.py` |
| `graph_segments` | 0 | `segments_routes.py` |
| `integration_preferences` | 0 | `account_routes.py` |
| `knowledge_suggestions` | 0 | `learning_routes.py` |
| `policy_rules` | 0 | `policy_routes.py` |
| `resource_uploads` | 0 | `upload_routes.py` |
| `segment_members` | 0 | `segments_routes.py` |
| `source_mappings` | 0 | `mapping_routes.py` |
| `user_model_proposals` | 0 | `usermodel_routes.py` |
| `user_models` | 0 | `usermodel_routes.py` |
| `user_tasks` | 0 | `workspace_routes.py` |
| `workspace_accounts` | 0 | `workspace_routes.py` |

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
| `routes.py` | 5372 | 95 | — | `feature_flags`, `l1_sync_runs`, `org_mission_critical_entities`, `org_seats`, `seat_objectives`, `source_events` | `cards`, `context_attention`, `context_read_models`, `context_situations`, `discrepancies`, `feature_flags` +21 |
| `intelligence_routes.py` | 1631 | 15 | — | `card_events`, `card_feedback_revisions`, `card_feedback_verdicts`, `cards`, `decisions`, `orgs` | `card_events`, `card_feedback_verdicts`, `cards`, `credit_ledger`, `decisions`, `execution_outcomes` +9 |
| `admin_routes.py` | 1489 | 25 | — | `orgs` | `audit_log`, `card_events`, `cards`, `connections`, `credit_ledger`, `decisions` +12 |
| `account_routes.py` | 957 | 20 | — | `api_keys`, `integration_preferences`, `org_invites`, `org_members`, `org_seats`, `orgs`, `orgs_archive`, `tenant_packs` | `api_keys`, `credit_ledger`, `graph_versions`, `integration_preferences`, `org_invites`, `org_members` +4 |
| `moment_routes.py` | 779 | 11 | — | — | `moments`, `org_seats` |
| `upload_routes.py` | 753 | 4 | — | `graph_edges`, `resource_uploads` | `graph_facts`, `graph_nodes`, `graph_observations`, `orgs`, `prepared_content`, `raw_payloads` +3 |
| `agent_mgmt_routes.py` | 632 | 15 | — | `agent_grants`, `agent_registry`, `api_keys` | `agent_events`, `agent_grants`, `agent_registry`, `api_keys`, `connections`, `org_seats` |
| `workspace_routes.py` | 595 | 13 | — | `graph_facts`, `user_tasks`, `workspace_accounts` | `cards`, `graph_edges`, `graph_facts`, `graph_nodes`, `signals`, `user_tasks` +1 |
| `delivery_routes.py` | 561 | 13 | — | `delivery_preferences` | `delivery_attempts`, `delivery_events`, `delivery_materialization_failures`, `delivery_outbox`, `delivery_preferences`, `org_channels` |
| `billing_routes.py` | 446 | 9 | — | `subscriptions` | `credit_ledger`, `orgs`, `subscriptions` |
| `device_routes.py` | 406 | 9 | — | — | — |
| `auth_routes.py` | 362 | 9 | — | `api_keys`, `credit_ledger`, `orgs` | `api_keys`, `org_members`, `org_seats`, `orgs` |
| `learning_routes.py` | 321 | 8 | — | `knowledge_suggestions`, `learning_objects`, `learning_transitions` | `knowledge_suggestions`, `learned_brain_entries`, `learning_objects`, `learning_policies`, `temporary_memories` |
| `home_routes.py` | 294 | 4 | — | — | `connections`, `context_situations`, `decisions`, `execution_outcomes`, `graph_edges`, `graph_facts` +4 |
| `cohort_routes.py` | 288 | 5 | — | — | `cohort_definitions` |
| `executive_routes.py` | 270 | 11 | — | `executions` | `execution_actions`, `execution_escalations`, `execution_events`, `executions` |
| `brain_routes.py` | 269 | 1 | — | — | `knowledge_suggestions`, `learned_brain_entries`, `learning_objects`, `source_events`, `temporary_memories` |
| `segments_routes.py` | 256 | 9 | — | `graph_segments`, `segment_members` | `graph_nodes`, `graph_segments`, `orgs`, `segment_members` |
| `situation_routes.py` | 243 | 9 | — | — | `context_correlation_members`, `context_correlations`, `context_situations`, `graph_health`, `graph_nodes`, `source_events` |
| `mapping_routes.py` | 235 | 6 | — | `source_mappings` | `connections`, `source_mappings` |
| `l4_seam_routes.py` | 234 | 3 | — | — | — |
| `correlation_routes.py` | 226 | 5 | — | — | — |
| `pattern_routes.py` | 214 | 5 | — | — | — |
| `policy_routes.py` | 200 | 6 | 1 | `policy_rules` | `policy_rules` |
| `usermodel_routes.py` | 187 | 6 | — | `user_model_proposals`, `user_models` | `user_model_proposals`, `user_models` |
| `delegation_routes.py` | 185 | 6 | — | — | — |
| `expertise_routes.py` | 177 | 3 | — | `domain_requests` | `calibration_nudges`, `rule_mutes` |
| `authority_routes.py` | 174 | 5 | — | — | — |
| `knowledge_routes.py` | 157 | 4 | — | — | `graph_facts`, `graph_observations`, `orgs`, `prepared_content`, `raw_payloads`, `source_events` |
| `quality_routes.py` | 148 | 3 | — | — | — |
| `benchmarks_routes.py` | 147 | 2 | — | — | `cards`, `decisions`, `graph_edges`, `graph_facts`, `graph_nodes`, `orgs` |
| `merge_routes.py` | 136 | 4 | — | — | `graph_edges`, `merge_proposals` |
| `identity_routes.py` | 130 | 5 | — | — | `merge_history`, `merge_proposals` |
| `team_routes.py` | 130 | 3 | — | `team_milestones` | `org_seats` |
| `transcript_routes.py` | 129 | 4 | — | — | — |
| `capture_routes.py` | 127 | 4 | — | — | — |
| `channel_routes.py` | 125 | 4 | — | `org_channels` | `org_channels` |
| `stream_routes.py` | 107 | 2 | — | — | — |
| `approval_routes.py` | 100 | 4 | 1 | `approvals_queue` | `approvals_queue`, `orgs` |
| `lifecycle_routes.py` | 100 | 2 | — | — | `situation_resolution_claims` |
| `api_health.py` | 85 | 4 | — | — | — |
| `discrepancy_routes.py` | 63 | 2 | — | — | — |
| `audit_routes.py` | 58 | 2 | — | — | `audit_log` |
| `__init__.py` | 0 | 0 | — | — | — |
