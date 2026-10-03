# L3 · `platform/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py platform > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-platform-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       49
lines                       12,651
files that WRITE a table    18
distinct tables written     29
⛔ written, no receipt       25
declared silences           26
⛔ >=100 lines, no test names it  0
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
| `l2_work_queue` | 1 | `warm_lane.py` |
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

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

None — every module of 100+ lines is named by at least one test file.

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `receipts.py` | 1161 | 2 | 19 | — | — | `authority_rules`, `calibration_runs`, `card_feedback_verdicts`, `cards`, `delivery_attempts`, `delivery_outbox` +22 |
| `screen_promoter.py` | 886 | 25 | 3 | — | `graph_source_refs`, `rate_counters`, `screen_session_deltas` | `graph_aliases`, `org_seats`, `orgs`, `rate_counters`, `screen_session_deltas` |
| `wiring.py` | 832 | 34 | 21 | — | — | `llm_costs`, `orgs` |
| `capture_policy.py` | 676 | 16 | 8 | — | `capture_policies`, `devices`, `presence_leases`, `screen_session_deltas`, `seat_capture_settings` | `capture_policies`, `device_auth_codes`, `prepared_content`, `presence_leases`, `raw_payloads`, `screen_memory_jobs` +4 |
| `warm_lane.py` | 630 | 15 | 3 | — | `l2_work_queue`, `org_run_leases`, `warm_lane_slots` | `l2_work_queue`, `org_run_leases`, `warm_lane_slots` |
| `l4_activation.py` | 525 | 10 | 15 | — | `l4_activation` | `l4_activation` |
| `auth.py` | 523 | 24 | 51 | — | `api_keys` | `api_keys`, `auth_sessions`, `feature_flags`, `org_seats`, `orgs` |
| `table_coverage.py` | 478 | 10 | 1 | 3 | — | — |
| `billing.py` | 465 | 22 | 8 | 1 | `credit_ledger`, `orgs` | `credit_ledger`, `orgs` |
| `l3_activation.py` | 460 | 10 | 9 | 3 | `l3_activation` | `l3_activation` |
| `devices.py` | 455 | 12 | 4 | — | `auth_sessions`, `device_auth_codes`, `devices` | `auth_sessions`, `device_auth_codes`, `devices`, `org_seats`, `orgs`, `presence_leases` |
| `reachability.py` | 453 | 13 | 2 | — | — | — |
| `realtime.py` | 349 | 8 | 6 | 2 | `realtime_events`, `seat_slice_versions` | `devices`, `realtime_events` |
| `l2_activation.py` | 340 | 7 | 4 | 1 | `l2_v2_activation` | `l2_v2_activation` |
| `config.py` | 276 | 2 | 54 | — | — | — |
| `intelligence_onboarding.py` | 260 | 2 | 5 | — | — | `tenant_packs` |
| `receipt_coverage.py` | 260 | 8 | 1 | 7 | — | — |
| `platform_health.py` | 259 | 4 | 1 | — | — | — |
| `sessions.py` | 234 | 6 | 2 | — | `auth_refresh_rotations`, `auth_sessions` | `auth_refresh_rotations`, `auth_sessions`, `org_seats`, `orgs` |
| `activation.py` | 227 | 6 | 6 | — | `l1_semantic_activation` | `l1_semantic_activation` |
| `analytics.py` | 202 | 5 | 1 | 2 | — | `orgs`, `subscriptions` |
| `migrate.py` | 184 | 1 | 13 | — | — | — |
| `progress.py` | 176 | 4 | 1 | — | `onboarding_progress` | `onboarding_progress` |
| `egress.py` | 174 | 4 | 2 | — | — | — |
| `funnel.py` | 163 | 5 | 3 | 3 | `pipeline_counters` | `pipeline_counters` |
| `provider_health.py` | 158 | 2 | 1 | — | — | — |
| `seats.py` | 157 | 7 | 1 | 1 | `org_channels`, `org_seats` | `org_invites`, `org_seats`, `orgs` |
| `corpus.py` | 150 | 6 | 8 | — | — | — |
| `scheduler.py` | 148 | 2 | 4 | — | — | — |
| `identity.py` | 143 | 7 | 6 | — | — | — |
| `memory.py` | 141 | 3 | 3 | — | — | — |
| `canonical.py` | 124 | 5 | 18 | — | — | — |
| `cache.py` | 122 | 3 | 1 | 2 | — | — |
| `metrics.py` | 100 | 5 | 3 | — | — | — |
| `quota.py` | 98 | 3 | 1 | — | — | `orgs`, `source_events` |
| `sync_jobs.py` | 90 | 5 | 1 | — | `sync_jobs` | `sync_jobs` |
| `secret_box.py` | 89 | 4 | 1 | — | `agent_registry` | `agent_registry` |
| `sync_worker.py` | 76 | 2 | 1 | — | — | — |
| `db.py` | 72 | 1 | 82 | — | — | — |
| `stage_timer.py` | 59 | 2 | 0 | — | — | — |
| `org_readiness_sql.py` | 58 | 0 | 1 | — | — | `org_channels`, `org_seats` |
| `quiet_hours.py` | 51 | 0 | 0 | — | — | — |
| `audit.py` | 45 | 1 | 7 | — | `audit_log` | — |
| `agent_plays.py` | 37 | 2 | 0 | — | — | `agent_registry` |
| `logging.py` | 27 | 1 | 1 | — | — | — |
| `ops_alert.py` | 26 | 1 | 3 | — | — | — |
| `crypto.py` | 24 | 3 | 8 | 1 | — | — |
| `ids.py` | 8 | 1 | 8 | — | — | — |
| `__init__.py` | 0 | 0 | 0 | — | — | — |
