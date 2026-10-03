# L3 · `deliver/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py deliver > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-deliver-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       41
lines                       10,020
files that WRITE a table    10
distinct tables written     15
⛔ written, no receipt       10
declared silences           23
⛔ >=100 lines, no test names it  0
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `signals` | 31 | `actions.py`, `agent_api.py`, `store.py` |
| `card_events` | 3 | `actions.py`, `agent_api.py`, `outbox.py`, `push.py`, `store.py` |
| `card_recipients` | 1 | `store.py` |
| `delivery_events` | 1 | `spine.py` |
| `delivery_materialization_failures` | 1 | `spine.py` |
| `agent_claims` | 0 | `agent_api.py`, `store.py` |
| `agent_metering` | 0 | `agent_api.py` |
| `card_build_claims` | 0 | `store.py` |
| `delivery_rate_windows` | 0 | `rate_limiter.py` |
| `human_events` | 0 | `actions.py` |

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

None — every module of 100+ lines is named by at least one test file.

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `outbox.py` | 1470 | 19 | 13 | — | `card_events`, `delivery_outbox`, `org_channels` | `agent_registry`, `card_recipients`, `cards`, `delivery_outbox`, `executions`, `graph_versions` +4 |
| `card_builder.py` | 1111 | 7 | 16 | — | — | `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `graph_source_refs`, `org_seats` +2 |
| `render.py` | 904 | 4 | 17 | — | — | — |
| `store.py` | 712 | 0 | 15 | — | `agent_claims`, `card_build_claims`, `card_events`, `card_recipients`, `cards`, `signals` | `agent_claims`, `card_build_claims`, `card_events`, `card_recipients`, `cards`, `graph_versions` +3 |
| `pipeline.py` | 627 | 1 | 11 | — | — | `cards`, `graph_facts`, `org_seats`, `orgs`, `reasoning_context_payloads`, `signals` |
| `gate.py` | 525 | 8 | 4 | — | — | `delivery_outbox`, `delivery_preferences`, `org_channels`, `org_seats`, `orgs` |
| `delivery_health.py` | 457 | 5 | 10 | — | — | — |
| `executive_bridge.py` | 322 | 9 | 4 | — | `delivery_outbox`, `executions` | `cards`, `delivery_outbox`, `execution_escalations`, `execution_events`, `executions` |
| `slots.py` | 270 | 3 | 7 | — | — | — |
| `agent_api.py` | 264 | 4 | 2 | 1 | `agent_claims`, `agent_metering`, `card_events`, `cards`, `signals` | `agent_claims`, `agent_registry`, `cards`, `graph_versions`, `signals` |
| `timing.py` | 255 | 3 | 3 | — | — | — |
| `channels/agent.py` | 237 | 4 | 1 | — | — | — |
| `claims.py` | 204 | 4 | 2 | 1 | — | — |
| `timezone_infer.py` | 202 | 5 | 1 | — | `orgs` | `org_seats`, `orgs`, `source_events` |
| `actions.py` | 182 | 2 | 6 | — | `card_events`, `cards`, `human_events`, `signals` | `cards`, `executions`, `graph_versions`, `signals` |
| `lane_display.py` | 159 | 2 | 3 | — | — | — |
| `claim_validator.py` | 158 | 2 | 2 | 1 | — | — |
| `spine.py` | 157 | 6 | 6 | 5 | `delivery_events`, `delivery_materialization_failures`, `delivery_outbox` | `delivery_outbox` |
| `push.py` | 156 | 3 | 2 | 2 | `card_events` | `agent_registry`, `cards`, `signals` |
| `channels/slack.py` | 154 | 5 | 6 | — | — | — |
| `units.py` | 142 | 2 | 6 | 1 | — | — |
| `routing.py` | 140 | 3 | 4 | 1 | — | — |
| `policy.py` | 135 | 2 | 2 | — | — | — |
| `lane_recall.py` | 125 | 3 | 2 | 2 | — | — |
| `card_source.py` | 94 | 3 | 4 | — | — | — |
| `tracker.py` | 93 | 2 | 3 | — | `delivery_outbox` | `delivery_events`, `delivery_outbox` |
| `orchestrator.py` | 84 | 2 | 1 | — | — | — |
| `router.py` | 81 | 3 | 2 | — | — | `cards` |
| `act_pump.py` | 74 | 3 | 1 | 1 | — | — |
| `analytics.py` | 71 | 2 | 1 | — | — | `delivery_outbox` |
| `presence.py` | 70 | 1 | 1 | 1 | — | — |
| `retry.py` | 65 | 4 | 1 | 3 | — | — |
| `audience.py` | 64 | 1 | 1 | — | — | — |
| `rate_limiter.py` | 64 | 3 | 1 | 3 | `delivery_rate_windows` | — |
| `scheduler.py` | 64 | 3 | 1 | 1 | — | — |
| `seat_access.py` | 47 | 2 | 0 | — | — | `cards` |
| `channels/base.py` | 32 | 1 | 5 | — | — | — |
| `digest.py` | 24 | 1 | 0 | — | — | — |
| `bands.py` | 14 | 1 | 1 | — | — | — |
| `channels/__init__.py` | 11 | 0 | 0 | — | — | — |
| `__init__.py` | 0 | 0 | 0 | — | — | — |
