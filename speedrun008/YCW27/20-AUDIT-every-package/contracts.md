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
⛔ >=100 lines, no test names it  3
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

| file | lines | public fns | writes |
|---|---|---|---|
| `plays.py` | 280 | 9 | — |
| `device/__init__.py` | 161 | 0 | — |
| `validators.py` | 131 | 13 | — |

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `reasoning.py` | 1990 | 8 | 56 | — | — | — |
| `situation.py` | 1308 | 1 | 19 | — | — | — |
| `signal.py` | 1112 | 2 | 36 | — | — | — |
| `domain_expertise.py` | 982 | 9 | 22 | — | — | — |
| `analytic.py` | 963 | 4 | 18 | — | — | — |
| `extraction.py` | 885 | 0 | 50 | — | — | — |
| `execution.py` | 678 | 1 | 22 | — | — | — |
| `delivery.py` | 512 | 2 | 12 | — | — | — |
| `publication.py` | 490 | 2 | 7 | — | — | — |
| `conflict.py` | 472 | 1 | 21 | — | — | — |
| `learning.py` | 380 | 1 | 24 | — | — | — |
| `outcomes.py` | 348 | 7 | 4 | 2 | — | — |
| `units.py` | 346 | 1 | 27 | — | — | — |
| `evidence.py` | 307 | 0 | 51 | — | — | — |
| `intent.py` | 302 | 0 | 2 | — | — | — |
| `authority.py` | 286 | 0 | 7 | — | — | — |
| `brain_address.py` | 285 | 7 | 1 | 1 | — | — |
| `plays.py` | 280 | 9 | 0 | — | — | — |
| `learning_attribution.py` | 250 | 2 | 3 | — | — | — |
| `dependency.py` | 233 | 0 | 3 | — | — | — |
| `situation_evidence.py` | 223 | 0 | 4 | — | — | — |
| `quality.py` | 212 | 0 | 13 | — | — | — |
| `claim_state.py` | 187 | 3 | 8 | 1 | — | — |
| `device/__init__.py` | 161 | 0 | 0 | — | — | — |
| `contract_health.py` | 138 | 4 | 1 | — | — | — |
| `learned_state.py` | 131 | 3 | 3 | 2 | — | `learned_brain_entries`, `temporary_memories` |
| `validators.py` | 131 | 13 | 0 | — | — | — |
| `moments.py` | 127 | 0 | 3 | — | — | — |
| `situation_stages.py` | 123 | 2 | 2 | 2 | — | — |
| `gated_event.py` | 116 | 0 | 6 | — | — | — |
| `visibility.py` | 102 | 1 | 26 | — | — | — |
| `source_event.py` | 94 | 1 | 31 | — | — | — |
| `events.py` | 76 | 0 | 5 | — | — | — |
| `availability.py` | 73 | 1 | 1 | — | — | — |
| `abstention.py` | 66 | 2 | 9 | — | — | — |
| `connection.py` | 55 | 1 | 22 | — | — | — |
| `prepared_content.py` | 53 | 0 | 5 | — | — | — |
| `trace.py` | 49 | 0 | 4 | — | — | — |
| `open_loop.py` | 48 | 2 | 2 | — | — | — |
| `__init__.py` | 24 | 0 | 0 | — | — | — |
| `parked.py` | 19 | 0 | 1 | — | — | — |
