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
⛔ >=100 lines, no test names it  0
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `agent_events` | 1 | `server.py` |

## ⛔ Files of 100+ lines that no test file names

⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its dotted path. It does **not** say the code is untested — a module reached only through a caller that is itself heavily tested appears here, and so does one whose functions a test calls under a different import form. ⛔ *A guard that measures naming cannot answer coverage*; what this column finds is a module with no test of its OWN, which is a different and smaller thing. ⛔ Each row needs its callers checked before it is called a gap — when this ran for `context/`, BOTH rows turned out to be live and reached.

None — every module of 100+ lines is named by at least one test file.

## Every file

| file | lines | public | tests | declared silences | writes | reads |
|---|---|---|---|---|---|---|
| `server.py` | 593 | 7 | 2 | — | `agent_events` | `agent_registry`, `cards`, `graph_aliases`, `graph_facts`, `graph_nodes`, `graph_observations` +3 |
| `__init__.py` | 1 | 0 | 0 | — | — | — |
