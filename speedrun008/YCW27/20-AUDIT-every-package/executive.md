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
⛔ >=100 lines, no test names it  1
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

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

| file | lines | public fns | writes |
|---|---|---|---|
| `planning.py` | 354 | 4 | — |

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `assignment.py` | 677 | 5 | 11 | 1 | — | `graph_nodes`, `org_seats`, `seat_responsibilities` |
| `delegation.py` | 587 | 19 | 3 | 1 | `agent_delegations`, `card_events`, `delivery_outbox`, `moment_feedback` | `agent_delegations`, `agent_registry`, `card_recipients`, `cards`, `moments`, `org_seats` +1 |
| `execution_store.py` | 530 | 17 | 5 | 1 | `execution_actions`, `execution_escalations`, `execution_events`, `execution_outcomes`, `executions` | `execution_actions`, `execution_escalations`, `execution_events`, `executions`, `graph_facts`, `graph_nodes` +4 |
| `sweep.py` | 496 | 3 | 4 | — | `executions` | `executions`, `graph_facts`, `graph_nodes`, `signals` |
| `interpret.py` | 363 | 4 | 1 | — | — | — |
| `planning.py` | 354 | 4 | 0 | — | — | — |
| `unreached.py` | 293 | 2 | 9 | — | — | — |
| `communication.py` | 277 | 6 | 2 | — | — | — |
| `collect.py` | 270 | 4 | 4 | — | — | — |
| `reminder.py` | 251 | 4 | 2 | — | — | — |
| `execution_guard.py` | 232 | 3 | 3 | 1 | — | — |
| `brief.py` | 225 | 2 | 2 | 1 | — | `discrepancies`, `graph_facts`, `graph_nodes`, `graph_versions`, `reasoning_context_payloads`, `signals` |
| `execution.py` | 189 | 3 | 10 | 1 | — | — |
| `modes.py` | 182 | 3 | 1 | 1 | — | `graph_facts`, `graph_nodes`, `graph_observations`, `graph_versions`, `signals` |
| `readiness.py` | 177 | 2 | 1 | 1 | — | — |
| `escalation.py` | 176 | 3 | 2 | — | — | — |
| `lifecycle.py` | 161 | 4 | 4 | 2 | — | — |
| `monitor.py` | 154 | 2 | 3 | — | — | — |
| `coordination.py` | 92 | 3 | 1 | 2 | — | — |
| `summary.py` | 85 | 1 | 1 | — | — | `context_attention`, `discrepancies`, `graph_facts`, `graph_nodes`, `graph_versions`, `signals` |
| `memory.py` | 83 | 1 | 0 | 1 | — | `context_attention`, `decisions`, `graph_facts`, `graph_nodes`, `graph_versions`, `signals` |
| `validate.py` | 83 | 3 | 1 | — | — | — |
| `authority.py` | 79 | 1 | 1 | — | — | — |
| `verbs.py` | 75 | 2 | 1 | — | — | — |
| `explain.py` | 52 | 1 | 0 | 1 | — | `graph_nodes`, `signal_suppression_log` |
| `plays.py` | 45 | 1 | 1 | — | — | — |
| `__init__.py` | 42 | 0 | 0 | — | — | — |
