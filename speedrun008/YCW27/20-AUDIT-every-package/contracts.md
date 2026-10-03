# L3 · `contracts/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py contracts > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-contracts-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       41
lines                       14,617
files that WRITE a table    0
distinct tables written     0
⛔ written, no receipt       0
declared silences           8
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|

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
| `reasoning.py` | 1990 | 8 | — | — | — |
| `situation.py` | 1308 | 1 | — | — | — |
| `signal.py` | 1112 | 2 | — | — | — |
| `domain_expertise.py` | 982 | 9 | — | — | — |
| `analytic.py` | 963 | 4 | — | — | — |
| `extraction.py` | 885 | 0 | — | — | — |
| `execution.py` | 678 | 1 | — | — | — |
| `delivery.py` | 512 | 2 | — | — | — |
| `publication.py` | 490 | 2 | — | — | — |
| `conflict.py` | 472 | 1 | — | — | — |
| `learning.py` | 380 | 1 | — | — | — |
| `outcomes.py` | 348 | 7 | 2 | — | — |
| `units.py` | 346 | 1 | — | — | — |
| `evidence.py` | 307 | 0 | — | — | — |
| `intent.py` | 302 | 0 | — | — | — |
| `authority.py` | 286 | 0 | — | — | — |
| `brain_address.py` | 285 | 7 | 1 | — | — |
| `plays.py` | 280 | 9 | — | — | — |
| `learning_attribution.py` | 250 | 2 | — | — | — |
| `dependency.py` | 233 | 0 | — | — | — |
| `situation_evidence.py` | 223 | 0 | — | — | — |
| `quality.py` | 212 | 0 | — | — | — |
| `claim_state.py` | 187 | 3 | 1 | — | — |
| `device/__init__.py` | 161 | 0 | — | — | — |
| `contract_health.py` | 138 | 4 | — | — | — |
| `learned_state.py` | 131 | 3 | 2 | — | `learned_brain_entries`, `temporary_memories` |
| `validators.py` | 131 | 13 | — | — | — |
| `moments.py` | 127 | 0 | — | — | — |
| `situation_stages.py` | 123 | 2 | 2 | — | — |
| `gated_event.py` | 116 | 0 | — | — | — |
| `visibility.py` | 102 | 1 | — | — | — |
| `source_event.py` | 94 | 1 | — | — | — |
| `events.py` | 76 | 0 | — | — | — |
| `availability.py` | 73 | 1 | — | — | — |
| `abstention.py` | 66 | 2 | — | — | — |
| `connection.py` | 55 | 1 | — | — | — |
| `prepared_content.py` | 53 | 0 | — | — | — |
| `trace.py` | 49 | 0 | — | — | — |
| `open_loop.py` | 48 | 2 | — | — | — |
| `__init__.py` | 24 | 0 | — | — | — |
| `parked.py` | 19 | 0 | — | — | — |
