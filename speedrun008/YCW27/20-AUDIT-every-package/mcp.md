# L3 · `mcp/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py mcp > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-mcp-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       2
lines                       594
files that WRITE a table    1
distinct tables written     1
⛔ written, no receipt       1
declared silences           0
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `agent_events` | 1 | `server.py` |

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
| `server.py` | 593 | 7 | — | `agent_events` | `agent_registry`, `cards`, `graph_aliases`, `graph_facts`, `graph_nodes`, `graph_observations` +3 |
| `__init__.py` | 1 | 0 | — | — | — |
