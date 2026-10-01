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
