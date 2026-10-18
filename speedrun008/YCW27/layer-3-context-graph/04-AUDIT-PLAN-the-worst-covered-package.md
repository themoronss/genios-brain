# L3 · AUDIT PLAN — `context/`, the worst-covered package in the product

**Why this step exists.** `S7` turned "guards per package" into DATA and the number pointed here,
not at `deliver/` where `STEP-10` had been looking:

```
context/    50,877 lines · 124 files · 2 receipts · 25,438 lines per receipt   ← the WORST
feedback/    3,111 lines ·  14 files · 10 receipts
```

⛔ **And the first measurement refutes the headline.** `context/` is **not** under-tested: **306 test
files** import it, `tests/context/` is one of the largest suites in the repo, and
`context_health.UNREACHED` already declares **22** silences. ⛔ **Both of its two receipts are
CORRECTNESS receipts** — the best ratio in the product by quality.

> ⛔ **So the gap is not "nobody looked at this package". It is: `context/` writes 36 tables and
> almost nothing checks any of them against PRODUCTION data.** That is a different audit, and it is
> the one `S6` proved pays — *asking the unread ledgers a question found two LIVE defects.*

---

## 0 · The measurement that shapes the audit

Every `text(...)` SQL literal in `genios_engine/`, classified by verb, cross-referenced against
every reader in the engine **and** in `scripts/`, and against all 41 receipts.

```
44 tables written by context/        (36 before the resolver learned to read name constants)
⛔ 3 of context/'s are WRITTEN AND READ BY NOTHING — and 6 more elsewhere in the engine
⛔ graph_nodes  46 external readers · NO receipt   ← the most-read table context writes
✅ graph_edges  now covered by receipt 42
```

> ⛔⛔ **THIS BLOCK WAS WRONG TWICE AND IS CORRECTED IN PLACE.** It first read *"36 tables … 3 are
> written and read by nothing — referenced only by the tenant DELETE LIST"*, naming
> `contract_spend_attributions`, `edge_coverage_declarations` and `l2_model_runs`. ⛔ **Two of those
> three were RETRACTED** once the extractor learned to read SQL held in a module constant:
> `edge_coverage_declarations` is read by its own writer and `l2_model_runs` by
> `context/lifecycle/resolution.py`. The surviving `context/` three are
> `contract_spend_attributions`, `source_identity_map` and `situation_interpretations`. *A plan that
> contradicts its own findings is the accumulation defect that has already cost this programme two
> documents.*

### ⛔⛔ Four resolver traps hit in ONE measurement pass, all four caught

| | What it cost, and the rule |
|---|---|
| **`[a-z_]+` cannot match a digit** | `l2_convergence` resolved as table **`l`**, and `l2_model_runs` did not appear at all — ⛔ **one of the three orphans was invisible** until the pattern became `[a-z_][a-z_0-9]*`. Second time this exact regex has lied in this programme |
| **the extractor only read `genios_engine/`** | `situation_admission_decisions` looked orphaned and is read by **five scripts** (`activate_tenant`, `l2_refusal_report`, `pipeline_funnel_report`, `speedrun008_layer2_measurements`). ⛔ **An operator-read table is a read table** |
| **a bare-name grep answers without its subject** | `context_node_lifecycle` looked orphaned; `context/runner.py:369` reads it. Classifying each mention as READ / WRITE / DELETE / prose is what separated them |
| ⛔⛔ **a WRITE through a name constant** | `context/merge.py:45` holds `_NODE_REFERENCES = (("graph_facts","subject_node_id"), …, ("source_identity_map","node_id"), …)` and repoints them in a **generic loop**. ⛔ **So every writer count for a table in that tuple was undercounted** — the `authority_rules`/`AUTHORITY_TABLE` trap, in the write direction |

⛔ *A resolver must report its COVERAGE beside its verdict* — and here the first verdict named **six**
orphans, of which **three survived** classification.

---

## 1 · `C1` · the inventory as data, with the resolver's limits declared

A `context/` declaration module that MEASURES — never restates — table → `(writers, readers,
receipt)`, reading `text()` literals **and** name-constant table tuples, and reporting what it could
not resolve. Guarded in both directions like every declaration module in this engine.

**Verify:** `pytest tests/context/test_the_context_layer_declares_what_nothing_reads.py`

## 2 · `C2` · the three orphans, declared with their evidence

| table | writer | verdict |
|---|---|---|
| `contract_spend_attributions` | `context/correlation_resource.py` | ⛔ **SURVIVED** — read by nothing; every other mention is prose |
| `source_identity_map` | `context/graph_store.py` **+** `context/merge.py` | ⛔ **SURVIVED** — and the second writer is only visible because `merge.py`'s name-constant loop is declared |
| `situation_interpretations` | `context/interpretation_store.py` | ⛔ **SURVIVED** — `record_interpretation` inserts; nothing selects |
| `edge_coverage_declarations` | `context/patterns/store.py` | ⛔ **RETRACTED** — read by its own writer |
| `l2_model_runs` | `context/model_audit.py` | ⛔ **RETRACTED** — read by `context/lifecycle/resolution.py` |

⛔ **The `macv_ledger` pattern held for the three that survived** (*"referenced only by the delete
list"*), and the delete list's own comment states the stake: *"the loop below runs with no
try/except by design, so a name missing here leaks silently."*

⛔ Both retractions are recorded in `table_coverage.RETRACTED_UNREAD_WRITES` rather than deleted,
because the next reader will re-derive the list with a simpler scan and get them back.

**Verify:** the same guard, plus a correctness receipt where the data can answer.

## 3 · `C3` · a receipt derived from the module's own stated failure mode

⛔ **NOT a receipt per unreceipted table.** `graph_nodes` (46 external readers) and `graph_edges`
(17) were the ranked top, and a claim about `graph_nodes` would have had to be **invented**. What
was derivable is `merge.py`'s own sentence — *"Missing one leaves rows pointing at a closed node"* —
so receipt **42** is *"no live row points at a node a merge absorbed"*, built from
`_NODE_REFERENCES`, `_CORRELATION_HANDLED_SEPARATELY` and `_EDGE_NODE_COLUMNS`. It covers
`graph_edges` as a side effect. ⛔ **`graph_nodes` is left as a measurement**, at the top of
`written_without_a_receipt("context")`, because *a gate derived from an invented claim is a gate
nobody reads.*

**Verify:** `pytest tests/platform/test_a_receipt_names_the_package_it_guards.py` + the new receipts
render and are correctness-shaped.

## 4 · `C4` · the file-by-file audit document — ⛔ generated, not written

124 files. ⛔ **A hand-written paragraph per file is wrong the next day** (`S9`'s rule), so the audit
document is **generated from the measurement** and regenerable: per file — lines, public functions,
declared silences, tables written, tables read, receipts, and the tests that import it.

## 5 · `C5` · `HANDOFF-HARSH.md`

Everything this audit turns up that needs a database, a migration or a product decision, written for
somebody who has not read this folder.

---

## Build order — bottom-up

| | unit | artifact |
|---|---|---|
| 1 | `C1` | `genios_engine/context/table_coverage.py` + its both-ways guard |
| 2 | `C2` | the orphan declarations inside it |
| 3 | `C3` | `genios_engine/platform/receipts.py` + `receipt_coverage.py` |
| 4 | `C4` | `05-AUDIT-context-file-by-file.md`, generated |
| 5 | `C5` | `../HANDOFF-HARSH.md` |

Each unit mutation-tested, baseline asserted **before and after**, `PYTHONDONTWRITEBYTECODE=1` with
`__pycache__` cleared per invocation. Then the full suite.

---

## ⛔⛔ 6 · And the audit's last finding is about the measurement that sent it here

Re-ranking with the **tables-written** column beside the receipt count puts ⛔ **`api/` last: 19,498
lines, 42 tables written, ZERO receipts** — and it never appeared in `S7`'s ranking at all, because
*lines per receipt* with a zero denominator is not sortable. ⛔ **The worst-covered package was
invisible to the measurement built to find it.** `contracts/` is the control: 14,617 lines, zero
receipts, and **zero tables written**, so its zero is correct rather than a gap.

> ⛔ **Print the raw terms beside the ratio.** `03-FINDINGS.md` §`C-F11` has the full table, and the
> next package to audit is **`api/`**, not another slice of `context/`.
