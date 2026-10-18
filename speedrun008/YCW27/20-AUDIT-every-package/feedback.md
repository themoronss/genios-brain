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
| `target_policy.py` | 833 | 18 | 12 | — | — |
| `units.py` | 636 | 13 | — | — | — |
| `org_rule_ingest.py` | 518 | 10 | — | `authority_rules`, `learning_input_rejections`, `learning_objects`, `org_rule_discovery_runs` | `learned_brain_entries`, `learning_objects`, `org_rule_discovery_runs`, `orgs`, `prepared_content`, `source_events` |
| `calibrate.py` | 459 | 3 | 1 | `calibration_nudges`, `calibration_runs`, `cards`, `rule_mutes`, `signals`, `tenant_packs` | `calibration_runs`, `pack_registry`, `rule_mutes`, `signals`, `tenant_packs` |
| `orchestrator.py` | 399 | 5 | — | `learning_object_evaluations`, `learning_policies`, `learning_runs` | `learning_policies`, `tenant_packs` |
| `store.py` | 298 | 1 | — | `learning_input_rejections` | `card_feedback_verdicts`, `cards`, `execution_outcomes`, `graph_facts`, `graph_source_refs`, `learning_event_inbox` +1 |
| `publisher.py` | 284 | 8 | — | `knowledge_suggestions`, `learned_brain_entries`, `learning_metrics`, `learning_objects`, `learning_transitions`, `temporary_memories` | `learned_brain_entries`, `learning_objects` |
| `brain_pipeline.py` | 260 | 4 | — | `learning_input_rejections`, `temporary_memories` | — |
| `feedback_health.py` | 256 | 4 | — | — | — |
| `attribution.py` | 196 | 3 | 3 | — | — |
| `governance.py` | 128 | 2 | — | — | — |
| `reset.py` | 102 | 3 | 1 | `organization_resets`, `temporary_memories` | `organization_resets` |
| `delivery_facts.py` | 75 | 1 | — | — | `delivery_outbox` |
| `consumer.py` | 17 | 0 | — | — | — |
| `__init__.py` | 0 | 0 | — | — | — |
