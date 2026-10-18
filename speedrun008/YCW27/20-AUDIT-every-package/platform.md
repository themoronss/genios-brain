# L3 · `platform/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py platform > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-platform-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       49
lines                       12,817
files that WRITE a table    18
distinct tables written     29
⛔ written, no receipt       24
declared silences           27
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `graph_source_refs` | 22 | `screen_promoter.py` |
| `agent_registry` | 7 | `secret_box.py` |
| `capture_policies` | 4 | `capture_policy.py` |
| `l1_semantic_activation` | 4 | `activation.py` |
| `api_keys` | 3 | `auth.py` |
| `audit_log` | 2 | `audit.py` |
| `l2_v2_activation` | 2 | `l2_activation.py` |
| `l3_activation` | 2 | `l3_activation.py` |
| `devices` | 1 | `capture_policy.py`, `devices.py` |
| `l4_activation` | 1 | `l4_activation.py` |
| `org_run_leases` | 1 | `warm_lane.py` |
| `presence_leases` | 1 | `capture_policy.py` |
| `rate_counters` | 1 | `screen_promoter.py` |
| `seat_slice_versions` | 1 | `realtime.py` |
| `sync_jobs` | 1 | `sync_jobs.py` |
| `auth_refresh_rotations` | 0 | `sessions.py` |
| `auth_sessions` | 0 | `devices.py`, `sessions.py` |
| `device_auth_codes` | 0 | `devices.py` |
| `onboarding_progress` | 0 | `progress.py` |
| `pipeline_counters` | 0 | `funnel.py` |
| `realtime_events` | 0 | `realtime.py` |
| `screen_session_deltas` | 0 | `capture_policy.py`, `screen_promoter.py` |
| `seat_capture_settings` | 0 | `capture_policy.py` |
| `warm_lane_slots` | 0 | `warm_lane.py` |

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
| `receipts.py` | 1215 | 2 | — | — | `authority_rules`, `calibration_runs`, `card_feedback_verdicts`, `cards`, `delivery_attempts`, `delivery_outbox` +23 |
| `screen_promoter.py` | 886 | 25 | — | `graph_source_refs`, `rate_counters`, `screen_session_deltas` | `graph_aliases`, `org_seats`, `orgs`, `rate_counters`, `screen_session_deltas` |
| `wiring.py` | 832 | 34 | — | — | `llm_costs`, `orgs` |
| `capture_policy.py` | 676 | 16 | — | `capture_policies`, `devices`, `presence_leases`, `screen_session_deltas`, `seat_capture_settings` | `capture_policies`, `device_auth_codes`, `prepared_content`, `presence_leases`, `raw_payloads`, `screen_memory_jobs` +4 |
| `warm_lane.py` | 630 | 15 | — | `l2_work_queue`, `org_run_leases`, `warm_lane_slots` | `l2_work_queue`, `org_run_leases`, `warm_lane_slots` |
| `table_coverage.py` | 571 | 13 | 4 | — | — |
| `l4_activation.py` | 525 | 10 | — | `l4_activation` | `l4_activation` |
| `auth.py` | 523 | 24 | — | `api_keys` | `api_keys`, `auth_sessions`, `feature_flags`, `org_seats`, `orgs` |
| `billing.py` | 465 | 22 | 1 | `credit_ledger`, `orgs` | `credit_ledger`, `orgs` |
| `l3_activation.py` | 460 | 10 | 3 | `l3_activation` | `l3_activation` |
| `devices.py` | 455 | 12 | — | `auth_sessions`, `device_auth_codes`, `devices` | `auth_sessions`, `device_auth_codes`, `devices`, `org_seats`, `orgs`, `presence_leases` |
| `reachability.py` | 453 | 13 | — | — | — |
| `realtime.py` | 349 | 8 | 2 | `realtime_events`, `seat_slice_versions` | `devices`, `realtime_events` |
| `l2_activation.py` | 340 | 7 | 1 | `l2_v2_activation` | `l2_v2_activation` |
| `config.py` | 276 | 2 | — | — | — |
| `platform_health.py` | 269 | 4 | — | — | — |
| `receipt_coverage.py` | 269 | 8 | 7 | — | — |
| `intelligence_onboarding.py` | 260 | 2 | — | — | `tenant_packs` |
| `sessions.py` | 234 | 6 | — | `auth_refresh_rotations`, `auth_sessions` | `auth_refresh_rotations`, `auth_sessions`, `org_seats`, `orgs` |
| `activation.py` | 227 | 6 | — | `l1_semantic_activation` | `l1_semantic_activation` |
| `analytics.py` | 202 | 5 | 2 | — | `orgs`, `subscriptions` |
| `migrate.py` | 184 | 1 | — | — | — |
| `progress.py` | 176 | 4 | — | `onboarding_progress` | `onboarding_progress` |
| `egress.py` | 174 | 4 | — | — | — |
| `funnel.py` | 163 | 5 | 3 | `pipeline_counters` | `pipeline_counters` |
| `provider_health.py` | 158 | 2 | — | — | — |
| `seats.py` | 157 | 7 | 1 | `org_channels`, `org_seats` | `org_invites`, `org_seats`, `orgs` |
| `corpus.py` | 150 | 6 | — | — | — |
| `scheduler.py` | 148 | 2 | — | — | — |
| `identity.py` | 143 | 7 | — | — | — |
| `memory.py` | 141 | 3 | — | — | — |
| `canonical.py` | 124 | 5 | — | — | — |
| `cache.py` | 122 | 3 | 2 | — | — |
| `metrics.py` | 100 | 5 | — | — | — |
| `quota.py` | 98 | 3 | — | — | `orgs`, `source_events` |
| `sync_jobs.py` | 90 | 5 | — | `sync_jobs` | `sync_jobs` |
| `secret_box.py` | 89 | 4 | — | `agent_registry` | `agent_registry` |
| `sync_worker.py` | 76 | 2 | — | — | — |
| `db.py` | 72 | 1 | — | — | — |
| `stage_timer.py` | 59 | 2 | — | — | — |
| `org_readiness_sql.py` | 58 | 0 | — | — | `org_channels`, `org_seats` |
| `quiet_hours.py` | 51 | 0 | — | — | — |
| `audit.py` | 45 | 1 | — | `audit_log` | — |
| `agent_plays.py` | 37 | 2 | — | — | `agent_registry` |
| `logging.py` | 27 | 1 | — | — | — |
| `ops_alert.py` | 26 | 1 | — | — | — |
| `crypto.py` | 24 | 3 | 1 | — | — |
| `ids.py` | 8 | 1 | — | — | — |
| `__init__.py` | 0 | 0 | — | — | — |
