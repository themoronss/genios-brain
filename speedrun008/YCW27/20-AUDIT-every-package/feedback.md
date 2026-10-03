# L3 · `feedback/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py feedback > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-feedback-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       15
lines                       4,461
files that WRITE a table    7
distinct tables written     19
⛔ written, no receipt       9
declared silences           17
⛔ >=100 lines, no test names it  0
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `signals` | 36 | `calibrate.py` |
| `learning_objects` | 3 | `org_rule_ingest.py`, `publisher.py` |
| `knowledge_suggestions` | 2 | `publisher.py` |
| `rule_mutes` | 2 | `calibrate.py` |
| `calibration_nudges` | 1 | `calibrate.py` |
| `learning_policies` | 1 | `orchestrator.py` |
| `organization_resets` | 1 | `reset.py` |
| `learning_metrics` | 0 | `publisher.py` |
| `org_rule_discovery_runs` | 0 | `org_rule_ingest.py` |

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

None — every module of 100+ lines is named by at least one test file.

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `target_policy.py` | 833 | 18 | 7 | 12 | — | — |
| `units.py` | 636 | 13 | 8 | — | — | — |
| `org_rule_ingest.py` | 518 | 10 | 2 | — | `authority_rules`, `learning_input_rejections`, `learning_objects`, `org_rule_discovery_runs` | `learned_brain_entries`, `learning_objects`, `org_rule_discovery_runs`, `orgs`, `prepared_content`, `source_events` |
| `calibrate.py` | 459 | 3 | 3 | 1 | `calibration_nudges`, `calibration_runs`, `cards`, `rule_mutes`, `signals`, `tenant_packs` | `calibration_runs`, `pack_registry`, `rule_mutes`, `signals`, `tenant_packs` |
| `orchestrator.py` | 399 | 5 | 10 | — | `learning_object_evaluations`, `learning_policies`, `learning_runs` | `learning_policies`, `tenant_packs` |
| `store.py` | 298 | 1 | 7 | — | `learning_input_rejections` | `card_feedback_verdicts`, `cards`, `execution_outcomes`, `graph_facts`, `graph_source_refs`, `learning_event_inbox` +1 |
| `publisher.py` | 284 | 8 | 9 | — | `knowledge_suggestions`, `learned_brain_entries`, `learning_metrics`, `learning_objects`, `learning_transitions`, `temporary_memories` | `learned_brain_entries`, `learning_objects` |
| `brain_pipeline.py` | 260 | 4 | 5 | — | `learning_input_rejections`, `temporary_memories` | — |
| `feedback_health.py` | 256 | 4 | 2 | — | — | — |
| `attribution.py` | 196 | 3 | 3 | 3 | — | — |
| `governance.py` | 128 | 2 | 4 | — | — | — |
| `reset.py` | 102 | 3 | 1 | 1 | `organization_resets`, `temporary_memories` | `organization_resets` |
| `delivery_facts.py` | 75 | 1 | 2 | — | — | `delivery_outbox` |
| `consumer.py` | 17 | 0 | 1 | — | — | — |
| `__init__.py` | 0 | 0 | 0 | — | — | — |
