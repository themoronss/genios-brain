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
| `outbox.py` | 1470 | 19 | — | `card_events`, `delivery_outbox`, `org_channels` | `agent_registry`, `card_recipients`, `cards`, `delivery_outbox`, `executions`, `graph_versions` +4 |
| `card_builder.py` | 1111 | 7 | — | — | `graph_edges`, `graph_facts`, `graph_nodes`, `graph_observations`, `graph_source_refs`, `org_seats` +2 |
| `render.py` | 904 | 4 | — | — | — |
| `store.py` | 712 | 0 | — | `agent_claims`, `card_build_claims`, `card_events`, `card_recipients`, `cards`, `signals` | `agent_claims`, `card_build_claims`, `card_events`, `card_recipients`, `cards`, `graph_versions` +3 |
| `pipeline.py` | 627 | 1 | — | — | `cards`, `graph_facts`, `org_seats`, `orgs`, `reasoning_context_payloads`, `signals` |
| `gate.py` | 525 | 8 | — | — | `delivery_outbox`, `delivery_preferences`, `org_channels`, `org_seats`, `orgs` |
| `delivery_health.py` | 457 | 5 | — | — | — |
| `executive_bridge.py` | 322 | 9 | — | `delivery_outbox`, `executions` | `cards`, `delivery_outbox`, `execution_escalations`, `execution_events`, `executions` |
| `slots.py` | 270 | 3 | — | — | — |
| `agent_api.py` | 264 | 4 | 1 | `agent_claims`, `agent_metering`, `card_events`, `cards`, `signals` | `agent_claims`, `agent_registry`, `cards`, `graph_versions`, `signals` |
| `timing.py` | 255 | 3 | — | — | — |
| `channels/agent.py` | 237 | 4 | — | — | — |
| `claims.py` | 204 | 4 | 1 | — | — |
| `timezone_infer.py` | 202 | 5 | — | `orgs` | `org_seats`, `orgs`, `source_events` |
| `actions.py` | 182 | 2 | — | `card_events`, `cards`, `human_events`, `signals` | `cards`, `executions`, `graph_versions`, `signals` |
| `lane_display.py` | 159 | 2 | — | — | — |
| `claim_validator.py` | 158 | 2 | 1 | — | — |
| `spine.py` | 157 | 6 | 5 | `delivery_events`, `delivery_materialization_failures`, `delivery_outbox` | `delivery_outbox` |
| `push.py` | 156 | 3 | 2 | `card_events` | `agent_registry`, `cards`, `signals` |
| `channels/slack.py` | 154 | 5 | — | — | — |
| `units.py` | 142 | 2 | 1 | — | — |
| `routing.py` | 140 | 3 | 1 | — | — |
| `policy.py` | 135 | 2 | — | — | — |
| `lane_recall.py` | 125 | 3 | 2 | — | — |
| `card_source.py` | 94 | 3 | — | — | — |
| `tracker.py` | 93 | 2 | — | `delivery_outbox` | `delivery_events`, `delivery_outbox` |
| `orchestrator.py` | 84 | 2 | — | — | — |
| `router.py` | 81 | 3 | — | — | `cards` |
| `act_pump.py` | 74 | 3 | 1 | — | — |
| `analytics.py` | 71 | 2 | — | — | `delivery_outbox` |
| `presence.py` | 70 | 1 | 1 | — | — |
| `retry.py` | 65 | 4 | 3 | — | — |
| `audience.py` | 64 | 1 | — | — | — |
| `rate_limiter.py` | 64 | 3 | 3 | `delivery_rate_windows` | — |
| `scheduler.py` | 64 | 3 | 1 | — | — |
| `seat_access.py` | 47 | 2 | — | — | `cards` |
| `channels/base.py` | 32 | 1 | — | — | — |
| `digest.py` | 24 | 1 | — | — | — |
| `bands.py` | 14 | 1 | — | — | — |
| `channels/__init__.py` | 11 | 0 | — | — | — |
| `__init__.py` | 0 | 0 | — | — | — |
