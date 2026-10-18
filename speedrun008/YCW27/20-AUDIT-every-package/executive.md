# L3 · `executive/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py executive > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-executive-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       27
lines                       6,230
files that WRITE a table    3
distinct tables written     9
⛔ written, no receipt       6
declared silences           14
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `card_events` | 4 | `delegation.py` |
| `execution_outcomes` | 4 | `execution_store.py` |
| `execution_escalations` | 2 | `execution_store.py` |
| `execution_events` | 2 | `execution_store.py` |
| `moment_feedback` | 2 | `delegation.py` |
| `agent_delegations` | 0 | `delegation.py` |

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
| `assignment.py` | 677 | 5 | 1 | — | `graph_nodes`, `org_seats`, `seat_responsibilities` |
| `delegation.py` | 587 | 19 | 1 | `agent_delegations`, `card_events`, `delivery_outbox`, `moment_feedback` | `agent_delegations`, `agent_registry`, `card_recipients`, `cards`, `moments`, `org_seats` +1 |
| `execution_store.py` | 530 | 17 | 1 | `execution_actions`, `execution_escalations`, `execution_events`, `execution_outcomes`, `executions` | `execution_actions`, `execution_escalations`, `execution_events`, `executions`, `graph_facts`, `graph_nodes` +4 |
| `sweep.py` | 496 | 3 | — | `executions` | `executions`, `graph_facts`, `graph_nodes`, `signals` |
| `interpret.py` | 363 | 4 | — | — | — |
| `planning.py` | 354 | 4 | — | — | — |
| `unreached.py` | 293 | 2 | — | — | — |
| `communication.py` | 277 | 6 | — | — | — |
| `collect.py` | 270 | 4 | — | — | — |
| `reminder.py` | 251 | 4 | — | — | — |
| `execution_guard.py` | 232 | 3 | 1 | — | — |
| `brief.py` | 225 | 2 | 1 | — | `discrepancies`, `graph_facts`, `graph_nodes`, `graph_versions`, `reasoning_context_payloads`, `signals` |
| `execution.py` | 189 | 3 | 1 | — | — |
| `modes.py` | 182 | 3 | 1 | — | `graph_facts`, `graph_nodes`, `graph_observations`, `graph_versions`, `signals` |
| `readiness.py` | 177 | 2 | 1 | — | — |
| `escalation.py` | 176 | 3 | — | — | — |
| `lifecycle.py` | 161 | 4 | 2 | — | — |
| `monitor.py` | 154 | 2 | — | — | — |
| `coordination.py` | 92 | 3 | 2 | — | — |
| `summary.py` | 85 | 1 | — | — | `context_attention`, `discrepancies`, `graph_facts`, `graph_nodes`, `graph_versions`, `signals` |
| `memory.py` | 83 | 1 | 1 | — | `context_attention`, `decisions`, `graph_facts`, `graph_nodes`, `graph_versions`, `signals` |
| `validate.py` | 83 | 3 | — | — | — |
| `authority.py` | 79 | 1 | — | — | — |
| `verbs.py` | 75 | 2 | — | — | — |
| `explain.py` | 52 | 1 | 1 | — | `graph_nodes`, `signal_suppression_log` |
| `plays.py` | 45 | 1 | — | — | — |
| `__init__.py` | 42 | 0 | — | — | — |
