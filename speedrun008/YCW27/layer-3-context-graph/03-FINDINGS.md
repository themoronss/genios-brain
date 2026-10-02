# Layer 3 — every finding, in one place

`context/` — 118 files, 49,713 lines. Cross-checked and built 2026-09-30.

**Written for:** Harsh (CTO) and Rohit. Six sections: what was broken, what looked broken and wasn't,
what the Atlas calls missing but is built, what is genuinely missing, what nobody has decided, and the
numbers — each with where it came from.

---

## A · Defects found — and what happened to them

| # | Defect | Status |
|---|---|---|
| A1 | **No bounded read.** `read_graph` and `live_graph` return the whole tenant. A caller wanting 3 nodes gets everything and filters in Python — and `reason/` reads through it, so the cost lands on the layer with a budget and a model in the loop | ✅ **fixed** · `context/bounded_read.py` · 22 tests |
| A2 | **467 held situations were questions nobody asked.** The hold reason went to a ledger and stopped | ✅ **fixed** · `context/hold_needs.py` · 27 tests |
| A3 | **An answered question had nowhere to land.** Nothing read a need's outcome, so a met need could not free its hold and an unavailable one could not end the waiting | ✅ **fixed** · `context/hold_resolution.py` · 22 tests |
| A4 | ⛔ **Nothing wrote a need to the table.** `detect_residue` measured the gap, `needs_from_residue` turned it into a question, and no code persisted one — so the executor read an empty table. **The sixth "built, tested, green, called by nothing" in this programme, and the first one we created ourselves** | ✅ **fixed** · `context/evidence_need_store.py` + `context/runner.py` · 20 tests |
| A5 | **A truncated bounded view returned an edge pointing at a node it refused to contain.** Found by a test against code I had written minutes earlier. The caller would join on the edge, find nothing, and read that absence as a fact about the business | ✅ **fixed in the code, not the test** |
| A6 | `tree.yaml` named two test files that never existed — `tests/context/test_bounded_read.py` and `test_compare_and_set.py`. A verify command that cannot run is not a verify | ✅ **fixed** · all five M10 verify commands now exit 0 |

**Total: 91 new tests. Full suite 13,562 passed / 1 failed** — the one failure is Layer 1's known
`pytesseract`-missing test, unrelated. Before this work: 13,471 passed / 1 failed.

---

## B · Alarms that turned out not to be defects

| # | The alarm | What is actually true |
|---|---|---|
| B1 | ⛔ **"`graph_versions` increments and nothing guards it — two sweeps that read revision N can both write."** I wrote a full unit and scenario table for it | **WRONG.** `reason/runner.py:570` `_graph_version_guard` locks the row `for share`, compares against the expected revision, and yields a boolean the caller at line 1276 honours by refusing to publish. 12 more sites in `deliver/` and `api/` take the same lock. `tests/test_graph_version_consistency.py` — 6 tests, 6 passing, one named `test_runner_captures_graph_version_before_tenant_p90_and_retries_on_drift` |
| B2 | "Three hold reasons → three needs" | **Two questions, not three.** `qes_required` and `verified_evidence_required` are one question, and the codebase had already measured it: 480 of 504 holds carry both, and *"it is one: both are downstream of `l1` being `None`"* |

### ⛔ Why B1 happened, and the rule it adds

I grepped `context/` for the version reader and concluded from its absence there. But the
read-modify-write **spans packages by design** — `context/` writes the graph and bumps the counter,
`reason/` reads the counter and guards against it — so `context/` is the one place the guard could not
be.

> **A guard lives with the reader, not with the writer. Absence in the writer's package is not
> absence.**

**This is the second wrong finding in this programme from counting along the wrong dimension.** The
first was Layer 1's `no_model_wired`: 632 failures that looked like broken wiring and were one lane
that is model-free on purpose, which produced *"a count without its dimension is not a measurement."*
This adds the package dimension to the same rule.

**What I did not do:** refactor, move, share or rename `_graph_version_guard`. It works, it is tested,
and it is not what was asked for.

---

## C · Things the Design Atlas calls missing or a target that are already built

| | Where |
|---|---|
| the situation publisher's ADMIT / HOLD / REJECT | sound, and HOLD already distinguishes **recoverable** incompleteness from the rest |
| the coverage read — *"read 37 of about 465"* | `context/quality/window.py`, built and correct |
| absence machinery | `situation_absences`, `context/quality/missing.py` |
| the graph-revision compare-and-set | `reason/runner.py:570` — see **B1** |
| correlation | ten modules, 5,234 lines, joins only. The group law holds |
| the two graphs | the Intelligence Graph is a foreign-key chain with **no tables of its own**, and 0 hard deletes |
| the sweep's cycle | state → residue → angles → readings → re-rank, with a second pass. The ordering comments explain why reordering would break the coverage measurement |

---

## D · What was genuinely missing

Four things, all now built:

1. **A bounded question.** No seeds, no hops, no cap.
2. **Truncation that reports itself.** The difference between *"there is nothing more"* and *"we
   stopped looking"* — and a caller that cannot tell them apart will eventually claim the first.
3. **A hold that asks.** 467 waits, 0 questions.
4. **Somewhere to put a question.** The single largest gap, because it made three already-built pieces
   worthless.

---

## E · Open questions nobody has resolved

| # | Question | Whose |
|---|---|---|
| E1 | ⛔ **The ConfidenceVector axes.** Code has evidence/freshness/consistency/identity/coverage/analytic with `overall_bp` bounded by the weakest axis; the Atlas wants evidence/frame/temporal/causal/authority/coverage. **Only 2 of 6 overlap.** L2 is the layer that computes it, so M11's cross-check hits this first | Rohit — a naming/semantics decision, not a code one |
| E2 | **Where `hold_needs` gets called from.** Inside the publication transaction, or a later pass reading the ledger? The second is safer — publication must not wait on anything — but it is not my call | Rohit / Harsh |
| E3 | **`tests/platform/test_migrations_apply.py` does not exist** and is named by 3 units in `03-PROGRAM.md`. So migration `0187` has no automated proof it applies | Harsh |
| E4 | Two of the four blocking decisions in `02-DECISIONS.md` are still open (correlation placement, layer-vs-package). Only object placement and now the naming of the revision guard are settled | Rohit |

---

## F · Measured, for the record

Every number below carries its source, and none are blended.

| Number | What | Source |
|---|---|---|
| 467 held / 223 admitted | situations at the publication gate | this cross-check pass, 2026-09-30 |
| 398 / 398 / 69 | `verified_evidence_required` / `qes_required` / `source_coverage_insufficient` | same pass |
| 504 held / 28 admitted · 480 carrying both | an earlier, differently-scoped population | `situation_bso.py` comments, measured 2026-09-16 |
| 349 held candidates, **all** carrying both hold reasons | the pair-collapse evidence | `situation_bso._preflight` docstring |
| 2 of 2 | graph reads that return the whole tenant, before this work | `graph_store.py` |
| 12 | sites in `deliver/` and `api/` already locking `graph_versions` | grep, verified |
| 5,234 | lines of correlator, all reading the graph | cross-check |
| 91 | new tests written here | measured |
| 13,562 passed / 1 failed | full suite after | measured, 421s |

⛔ **Read F with this caveat:** every production number in this table was taken while the API spend
limit was refusing all model calls (since 2026-09-25 11:09 UTC — Layer 1 STEP-04). The hold counts are
model-independent and stand. Anything that depends on a model having answered does not.

---
---

# ⛔⛔ 2026-10-02 · THE COVERAGE AUDIT — `C-F1`…`C-F10`

`S7` turned "receipts per package" into data and the number pointed here. The audit that followed
retracted **six** of its own findings, which is the result worth reading.

## `C-F1` · ⛔ The headline was wrong: `context/` is not under-tested

```
124 files · 50,885 lines · 306 test files import it · 23 declared silences
⛔ 2 modules of 100+ lines are named by no test — and BOTH are live and reached
⛔ 2 receipts guarded it at audit time, 3 now — and ALL are CORRECTNESS receipts
```

⛔ **So the gap was never "nobody looked at this package".** It is that `context/` writes **44
tables** and almost nothing checks any of them against production data. That is the audit `S6`
proved pays: *asking the unread ledgers a question found two LIVE defects.*

⛔ And the "2 modules no test names" column is **narrower than it reads**: `lifecycle/resolution.py`
is driven by `context/runner.py`, and `correlation_membership.finding_events` is called directly by
`tests/test_nothing_reads_a_name_that_cannot_exist.py` under an import form the matcher does not
count. *A guard that measures naming cannot answer coverage.*

## `C-F2` · ⛔ Nine tables are written by the product and read by nothing

Declared in `platform/table_coverage.UNREAD_WRITES`, with the writer and the mover for each.
Three are `context/`'s (`contract_spend_attributions`, `source_identity_map`,
`situation_interpretations`); the other six belong to `capture/`, `deliver/`, `feedback/` and
`api/`, found by the same pass because the measurement is engine-wide.

## `C-F3` · ✅ `learning_metrics` — `F11`'s last unread ledger, rediscovered from the other side

L6 counted four ledgers nothing read; `S5` and `S6` closed three. ⛔ **This audit found the fourth
without looking for it.** Two independent measurements reaching the same table is the cross-check
that makes both worth trusting.

## `C-F4` · ⛔⛔ SEVEN resolver traps, and SIX findings died to them

| trap | what it cost |
|---|---|
| `[a-z_]+` cannot match a digit | `l2_convergence` resolved as table **`l`**; `l2_model_runs` was **invisible** |
| the engine is not the whole reader set | `situation_admission_decisions` looked orphaned; **five scripts** read it |
| a bare-name grep has no subject | `context_node_lifecycle` looked orphaned; `runner.py` reads it |
| a tuple of PAIRS contributes its column | `node_id` and `anchor_node_id` became **tables** |
| SQL held in a module constant | retracted `edge_coverage_declarations` **and** `l2_model_runs` |
| a name constant passed as an ARGUMENT | `learning_event_inbox` read as write-only — a table `S5` had **proven** is read |
| printing a query is not running one | `activate_tenant.py` prints SQL for a human to paste |

> ⛔⛔ **Nine findings survived three broadenings of the measurement. That is the only reason to
> believe them** — and `resolution()` now reports **639 unresolved of 2,867 statements** beside
> every verdict, because *a resolver that answers for 1 of 104 answers nothing*.

## `C-F5` · ⛔⛔ The audit's largest finding was FALSE, and the gate was reading the contract

**183** org-scoped tables; **102** named in `/reset`'s erasure loop; **4** declared
`RETAINED_AFTER_ERASURE`; ⛔ **77 in neither** — which reads as a 77-table retention hole, including
`transcripts` and `screen_thread_summaries`, which hold verbatim customer content.

⛔ **It is not one.** `_ORG_SCOPED_TABLES` governs **`/reset`**, whose own docstring says it *"keeps
the account, connections, tasks"*; ACCOUNT erasure is done by migration `0033`'s foreign keys, and
`RETAINED_AFTER_ERASURE`'s docstring says a **receipt** is what asks the deployed schema whether
anything else survives — *"a comment cannot be asked"*.

> ⛔ **Read the endpoint's contract before calling a list incomplete.** Had this shipped, Rohit
> would have been told the product leaks 77 tables of deleted-customer data.

## `C-F6` · ✅ And the one apparent hole in that story is documented AND true

Four `reasoning_*` children have no direct FK to `orgs`. `RETAINED_AFTER_ERASURE` says they cascade
*"through a parent that does"*. ⛔ **Verified, not trusted:** `reasoning_candidates → reasoning_runs
→ reasoning_context_snapshots → reasoning_capability_snapshots → orgs`. Pinned by a test, because
*a stale comment reads as a measurement* and this one happens to be right.

## `C-F7` · ⛔ `merge.py` states a failure mode nothing checked — now receipt **42**

> *"Every table that names a node. **Missing one leaves rows pointing at a closed node — invisible
> in the UI, still returned by any query that joins on node_id.**"*

Entity merge is the one operation that rewrites identity across the graph, and `context/` had two
receipts, neither about it. The new claim — *"no live row points at a node a merge absorbed"* — is
**derived** from `_NODE_REFERENCES`, `_CORRELATION_HANDLED_SEPARATELY` and `_EDGE_NODE_COLUMNS`, so
a sixth table entering the merge loop enters the receipt without an edit.

⛔ `graph_edges` was briefly a candidate defect — it names a node twice and is **not** in
`_NODE_REFERENCES`. It is handled by its own loop, deliberately, because the two columns need the
self-edge close and the interaction-count dedup. **Seventh candidate killed before it was written.**

## `C-F8` · ⛔ Three tables survive a `/reset` and nothing says whether they should

`agent_metering`, `delivery_rate_windows`, `domain_requests` are in neither declared list. ⛔ Fine
for account deletion (the FKs take them); an **open question** for `/reset`. → `HANDOFF-HARSH.md`
§H8.4, with our read and why the decision is not ours.

## `C-F9` · ⛔ `graph_nodes` — 46 external readers, no receipt

The most-read table `context/` writes, and the top of the ranked gap list
(`written_without_a_receipt`). Left as the measurement rather than closed with an invented claim:
the merge receipt was derivable from the module's own constants, and a `graph_nodes` claim is not
yet.

## `C-F10` · ⛔ And my own guard conflated two questions

`written_and_unread()` excluded tables that had a receipt — so **writing the merge receipt made a
declared write-only table look like it had gained a reader**, and the both-ways guard went red.
⛔ *"Does any code consult this table"* and *"does anything check its contents"* are different
questions, and conflating them meant a new receipt could silently retire a finding about
readership.

## `C-F11` · ⛔⛔ And `S7`'s metric was hiding the real worst case — a zero denominator drops out

Extending the same axis with the **tables-written** column, engine-wide:

```
package       files    lines  receipts  corr  tables written  no receipt   worst uncovered
api              44   19,498      ⛔ 0     0              42          28   agent_registry (8 readers)
context         124   50,885         3     3              44          33   graph_nodes (46 readers)
contracts        41   14,617        0      0           ✅ 0            0   — (holds no state)
platform         49   12,649      ⛔ 1     1              29          25   graph_source_refs (22)
capture         158   47,184         5     5              25          19   graph_source_refs (22)
reason          121   41,363         8     5              35          29   signals (29 readers)
deliver          41   10,020         7     5              15          10   signals (31 readers)
executive        27    6,230         2     1               9            6  card_events (4 readers)
feedback         15    4,461        10     6              19            9  signals (36 readers)
```

⛔⛔ **`api/` has 19,498 lines, writes 42 tables and has ZERO receipts.** It is the worst-covered
package in the product by a wide margin — and it never appeared in `S7`'s ranking, because
*lines per receipt* with a **zero denominator** is not a number you can sort. The package that had
never been measured was invisible to the measurement built to find it.

> ⛔ **A ratio hides the cases its denominator cannot express.** Third artifact of this kind in two
> steps, after `[a-z_]+` swallowing `l2_convergence` and a pair-tuple turning `node_id` into a
> table. ⛔ *Print the raw terms beside the ratio* — `receipts`, `tables written` and `no receipt`
> are all above, and the ratio is now the least informative column.

⛔ **`contracts/` is the control that proves the column means something**: 14,617 lines, zero
receipts, and **zero tables written** — it holds no state, so zero is the correct number rather
than a gap. A package's receipt count is only readable next to what it writes.

**→ The next package to audit is `api/`, not another slice of `context/`.** `platform/` is second
(1 receipt, 29 tables written, 25 uncovered).
