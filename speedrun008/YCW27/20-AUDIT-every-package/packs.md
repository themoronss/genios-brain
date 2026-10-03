# L3 · `packs/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py packs > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-packs-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       35
lines                       8,188
files that WRITE a table    2
distinct tables written     4
⛔ written, no receipt       2
declared silences           3
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `config_snapshots` | 1 | `registry.py` |
| `pack_registry` | 1 | `registry.py` |

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
| `compiler/capability_resolver.py` | 861 | 8 | — | — | — |
| `compiler/context_adapter.py` | 850 | 0 | — | — | — |
| `brains/behavior_distill.py` | 776 | 11 | — | — | `graph_facts`, `learned_brain_entries` |
| `sales_v1.py` | 712 | 0 | — | — | — |
| `brains/org_discovery.py` | 655 | 5 | — | — | `connections`, `graph_nodes`, `org_seats`, `orgs` |
| `compiler/runtime_brains.py` | 542 | 0 | — | — | `learned_brain_entries`, `temporary_memories` |
| `capabilities/deal_cooling.py` | 433 | 1 | — | — | — |
| `brains/adaptive_lease.py` | 301 | 7 | — | — | `card_feedback_verdicts`, `temporary_memories` |
| `general_v1.py` | 259 | 0 | — | — | — |
| `compiler/authoring.py` | 235 | 1 | — | — | — |
| `compiler/models.py` | 228 | 1 | — | — | — |
| `capabilities/deal_cooling_v2.py` | 209 | 1 | — | — | — |
| `compiler/expertise_builder.py` | 208 | 0 | — | — | — |
| `brains/org_rule_extract.py` | 180 | 2 | — | — | — |
| `wiring.py` | 176 | 4 | — | — | `tenant_packs` |
| `registry.py` | 154 | 0 | — | `config_snapshots`, `pack_registry`, `tenant_packs` | `config_snapshots`, `pack_registry`, `tenant_packs` |
| `compiler/knowledge_retriever.py` | 144 | 0 | — | — | — |
| `compiler/errors.py` | 136 | 0 | — | — | — |
| `admin_v1.py` | 128 | 0 | — | — | — |
| `substrate_demand.py` | 125 | 3 | 3 | — | — |
| `compiler/expertise_publisher.py` | 120 | 1 | — | `expertise_packages` | `expertise_packages` |
| `capabilities/deal_health.py` | 112 | 1 | — | — | — |
| `support_v1.py` | 104 | 0 | — | — | — |
| `compiler/brain_resolver.py` | 91 | 0 | — | — | — |
| `pack_health.py` | 77 | 4 | — | — | — |
| `compiler/domain_compiler.py` | 75 | 0 | — | — | — |
| `compiler/object_resolver.py` | 65 | 0 | — | — | — |
| `merge.py` | 64 | 3 | — | — | — |
| `domain_wiring.py` | 42 | 1 | — | — | — |
| `compiler/evidence_aggregator.py` | 40 | 0 | — | — | — |
| `capabilities/__init__.py` | 33 | 0 | — | — | — |
| `brains/__init__.py` | 21 | 0 | — | — | — |
| `compiler/__init__.py` | 16 | 0 | — | — | — |
| `snapshot.py` | 16 | 2 | — | — | — |
| `__init__.py` | 0 | 0 | — | — | — |
