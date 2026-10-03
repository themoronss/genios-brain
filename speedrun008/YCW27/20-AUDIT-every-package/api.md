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
⛔ >=100 lines, no test names it  11
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

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

| file | lines | public fns | writes |
|---|---|---|---|
| `workspace_routes.py` | 595 | 13 | `graph_facts`, `user_tasks`, `workspace_accounts` |
| `device_routes.py` | 406 | 9 | — |
| `brain_routes.py` | 269 | 1 | — |
| `situation_routes.py` | 243 | 9 | — |
| `policy_routes.py` | 200 | 6 | `policy_rules` |
| `usermodel_routes.py` | 187 | 6 | `user_model_proposals`, `user_models` |
| `delegation_routes.py` | 185 | 6 | — |
| `expertise_routes.py` | 177 | 3 | `domain_requests` |
| `identity_routes.py` | 130 | 5 | — |
| `team_routes.py` | 130 | 3 | `team_milestones` |
| `approval_routes.py` | 100 | 4 | `approvals_queue` |

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `routes.py` | 5372 | 95 | 72 | — | `feature_flags`, `l1_sync_runs`, `org_mission_critical_entities`, `org_seats`, `seat_objectives`, `source_events` | `cards`, `context_attention`, `context_read_models`, `context_situations`, `discrepancies`, `feature_flags` +21 |
| `intelligence_routes.py` | 1631 | 15 | 10 | — | `card_events`, `card_feedback_revisions`, `card_feedback_verdicts`, `cards`, `decisions`, `orgs` | `card_events`, `card_feedback_verdicts`, `cards`, `credit_ledger`, `decisions`, `execution_outcomes` +9 |
| `admin_routes.py` | 1489 | 25 | 7 | — | `orgs` | `audit_log`, `card_events`, `cards`, `connections`, `credit_ledger`, `decisions` +12 |
| `account_routes.py` | 957 | 20 | 41 | — | `api_keys`, `integration_preferences`, `org_invites`, `org_members`, `org_seats`, `orgs`, `orgs_archive`, `tenant_packs` | `api_keys`, `credit_ledger`, `graph_versions`, `integration_preferences`, `org_invites`, `org_members` +4 |
| `moment_routes.py` | 779 | 11 | 2 | — | — | `moments`, `org_seats` |
| `upload_routes.py` | 753 | 4 | 5 | — | `graph_edges`, `resource_uploads` | `graph_facts`, `graph_nodes`, `graph_observations`, `orgs`, `prepared_content`, `raw_payloads` +3 |
| `agent_mgmt_routes.py` | 632 | 15 | 3 | — | `agent_grants`, `agent_registry`, `api_keys` | `agent_events`, `agent_grants`, `agent_registry`, `api_keys`, `connections`, `org_seats` |
| `workspace_routes.py` | 595 | 13 | 0 | — | `graph_facts`, `user_tasks`, `workspace_accounts` | `cards`, `graph_edges`, `graph_facts`, `graph_nodes`, `signals`, `user_tasks` +1 |
| `delivery_routes.py` | 561 | 13 | 4 | — | `delivery_preferences` | `delivery_attempts`, `delivery_events`, `delivery_materialization_failures`, `delivery_outbox`, `delivery_preferences`, `org_channels` |
| `billing_routes.py` | 446 | 9 | 1 | — | `subscriptions` | `credit_ledger`, `orgs`, `subscriptions` |
| `device_routes.py` | 406 | 9 | 0 | — | — | — |
| `auth_routes.py` | 362 | 9 | 3 | — | `api_keys`, `credit_ledger`, `orgs` | `api_keys`, `org_members`, `org_seats`, `orgs` |
| `learning_routes.py` | 321 | 8 | 5 | — | `knowledge_suggestions`, `learning_objects`, `learning_transitions` | `knowledge_suggestions`, `learned_brain_entries`, `learning_objects`, `learning_policies`, `temporary_memories` |
| `home_routes.py` | 294 | 4 | 1 | — | — | `connections`, `context_situations`, `decisions`, `execution_outcomes`, `graph_edges`, `graph_facts` +4 |
| `cohort_routes.py` | 288 | 5 | 2 | — | — | `cohort_definitions` |
| `executive_routes.py` | 270 | 11 | 2 | — | `executions` | `execution_actions`, `execution_escalations`, `execution_events`, `executions` |
| `brain_routes.py` | 269 | 1 | 0 | — | — | `knowledge_suggestions`, `learned_brain_entries`, `learning_objects`, `source_events`, `temporary_memories` |
| `segments_routes.py` | 256 | 9 | 1 | — | `graph_segments`, `segment_members` | `graph_nodes`, `graph_segments`, `orgs`, `segment_members` |
| `situation_routes.py` | 243 | 9 | 0 | — | — | `context_correlation_members`, `context_correlations`, `context_situations`, `graph_health`, `graph_nodes`, `source_events` |
| `mapping_routes.py` | 235 | 6 | 1 | — | `source_mappings` | `connections`, `source_mappings` |
| `l4_seam_routes.py` | 234 | 3 | 1 | — | — | — |
| `correlation_routes.py` | 226 | 5 | 2 | — | — | — |
| `pattern_routes.py` | 214 | 5 | 1 | — | — | — |
| `policy_routes.py` | 200 | 6 | 0 | 1 | `policy_rules` | `policy_rules` |
| `usermodel_routes.py` | 187 | 6 | 0 | — | `user_model_proposals`, `user_models` | `user_model_proposals`, `user_models` |
| `delegation_routes.py` | 185 | 6 | 0 | — | — | — |
| `expertise_routes.py` | 177 | 3 | 0 | — | `domain_requests` | `calibration_nudges`, `rule_mutes` |
| `authority_routes.py` | 174 | 5 | 1 | — | — | — |
| `knowledge_routes.py` | 157 | 4 | 2 | — | — | `graph_facts`, `graph_observations`, `orgs`, `prepared_content`, `raw_payloads`, `source_events` |
| `quality_routes.py` | 148 | 3 | 1 | — | — | — |
| `benchmarks_routes.py` | 147 | 2 | 1 | — | — | `cards`, `decisions`, `graph_edges`, `graph_facts`, `graph_nodes`, `orgs` |
| `merge_routes.py` | 136 | 4 | 1 | — | — | `graph_edges`, `merge_proposals` |
| `identity_routes.py` | 130 | 5 | 0 | — | — | `merge_history`, `merge_proposals` |
| `team_routes.py` | 130 | 3 | 0 | — | `team_milestones` | `org_seats` |
| `transcript_routes.py` | 129 | 4 | 1 | — | — | — |
| `capture_routes.py` | 127 | 4 | 1 | — | — | — |
| `channel_routes.py` | 125 | 4 | 1 | — | `org_channels` | `org_channels` |
| `stream_routes.py` | 107 | 2 | 2 | — | — | — |
| `approval_routes.py` | 100 | 4 | 0 | 1 | `approvals_queue` | `approvals_queue`, `orgs` |
| `lifecycle_routes.py` | 100 | 2 | 1 | — | — | `situation_resolution_claims` |
| `api_health.py` | 85 | 4 | 1 | — | — | — |
| `discrepancy_routes.py` | 63 | 2 | 0 | — | — | — |
| `audit_routes.py` | 58 | 2 | 0 | — | — | `audit_log` |
| `__init__.py` | 0 | 0 | 0 | — | — | — |
