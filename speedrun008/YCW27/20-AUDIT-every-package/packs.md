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
⛔ >=100 lines, no test names it  1
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `config_snapshots` | 1 | `registry.py` |
| `pack_registry` | 1 | `registry.py` |

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

| file | lines | public fns | writes |
|---|---|---|---|
| `compiler/knowledge_retriever.py` | 144 | 0 | — |

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `compiler/capability_resolver.py` | 861 | 8 | 19 | — | — | — |
| `compiler/context_adapter.py` | 850 | 0 | 11 | — | — | — |
| `brains/behavior_distill.py` | 776 | 11 | 3 | — | — | `graph_facts`, `learned_brain_entries` |
| `sales_v1.py` | 712 | 0 | 9 | — | — | — |
| `brains/org_discovery.py` | 655 | 5 | 4 | — | — | `connections`, `graph_nodes`, `org_seats`, `orgs` |
| `compiler/runtime_brains.py` | 542 | 0 | 1 | — | — | `learned_brain_entries`, `temporary_memories` |
| `capabilities/deal_cooling.py` | 433 | 1 | 7 | — | — | — |
| `brains/adaptive_lease.py` | 301 | 7 | 3 | — | — | `card_feedback_verdicts`, `temporary_memories` |
| `general_v1.py` | 259 | 0 | 7 | — | — | — |
| `compiler/authoring.py` | 235 | 1 | 22 | — | — | — |
| `compiler/models.py` | 228 | 1 | 3 | — | — | — |
| `capabilities/deal_cooling_v2.py` | 209 | 1 | 5 | — | — | — |
| `compiler/expertise_builder.py` | 208 | 0 | 2 | — | — | — |
| `brains/org_rule_extract.py` | 180 | 2 | 3 | — | — | — |
| `wiring.py` | 176 | 4 | 14 | — | — | `tenant_packs` |
| `registry.py` | 154 | 0 | 1 | — | `config_snapshots`, `pack_registry`, `tenant_packs` | `config_snapshots`, `pack_registry`, `tenant_packs` |
| `compiler/knowledge_retriever.py` | 144 | 0 | 0 | — | — | — |
| `compiler/errors.py` | 136 | 0 | 9 | — | — | — |
| `admin_v1.py` | 128 | 0 | 2 | — | — | — |
| `substrate_demand.py` | 125 | 3 | 1 | 3 | — | — |
| `compiler/expertise_publisher.py` | 120 | 1 | 4 | — | `expertise_packages` | `expertise_packages` |
| `capabilities/deal_health.py` | 112 | 1 | 1 | — | — | — |
| `support_v1.py` | 104 | 0 | 1 | — | — | — |
| `compiler/brain_resolver.py` | 91 | 0 | 0 | — | — | — |
| `pack_health.py` | 77 | 4 | 1 | — | — | — |
| `compiler/domain_compiler.py` | 75 | 0 | 3 | — | — | — |
| `compiler/object_resolver.py` | 65 | 0 | 0 | — | — | — |
| `merge.py` | 64 | 3 | 1 | — | — | — |
| `domain_wiring.py` | 42 | 1 | 2 | — | — | — |
| `compiler/evidence_aggregator.py` | 40 | 0 | 0 | — | — | — |
| `capabilities/__init__.py` | 33 | 0 | 0 | — | — | — |
| `brains/__init__.py` | 21 | 0 | 0 | — | — | — |
| `compiler/__init__.py` | 16 | 0 | 0 | — | — | — |
| `snapshot.py` | 16 | 2 | 3 | — | — | — |
| `__init__.py` | 0 | 0 | 0 | — | — | — |
