# Step 3 · The seam — findings

**Run:** 2026-09-23 · premise verified against code and PRODUCTION (read-only) before building
**Verdict:** hermetic work **COMPLETE** · the migration and the end-to-end replay are Harsh's

---

## 1. Premise check — two of three confirmed, one WITHDRAWN

| Claim | Verdict |
|---|---|
| `_L1_SELECT` reads 9 of 28 columns | **✅ confirmed** in code |
| `subject_key` has no column on `qualified_signals` | **✅ confirmed** — `grep -c` returns 0 on migration 0089 |
| `runner.py`'s `array_agg(...)[1]` loses every signal but the loudest | **❌ WITHDRAWN — the premise was wrong** |

### The withdrawn one, and how production said so

The plan called `(array_agg(qs.extraction_ref ...))[1]` *"an EVENT-level answer to a SIGNAL-level
question."* Measured on the pilot org, over every event carrying more than one qualified signal:

```
signals 107 · DISTINCT extraction_ref 32 · DISTINCT domain_hints 7

per event:   signals=5 → distinct_refs=1, distinct_domains=1     (every such event)
```

**LLM-2 runs once per event, not once per signal.** `domain_hints` are computed per event in
`capture/pipeline.py` too. So all five signals from one email share one extraction and one hint
set, `[1]` picks the only distinct value, and nothing is lost.

**Units M13.C3-U10 and -U11 are withdrawn.** In their place the test file now pins the
**invariant that makes `[1]` safe** — one `run_semantic_lane` call per event — because the day
that stops being true (an attachment extracted separately under its parent's event id would do
it) `[1]` becomes a silent loss with no error and no missing row.

> **Second step in a row whose written premise production corrected.** Step 2's was *"the gate
> deletes bounces"*; it did not. Both were caught by measuring, neither by reasoning.

---

## 2. What was built

| Unit | Artifact | What |
|---|---|---|
| U01 | `migrations/0177_qualified_signals_subject_key.sql` **(new)** | column + index `(org_id, subject_key, signal_type)` — ALG-19's key with the tenant in front. **Nullable on arrival** |
| U02 | `contracts/signal.py` | `subject_key` on C-12, **supplied never derived**, with the field note corrected |
| U03 | `esqe/publisher.py` | `build_signal` lifts it from `NormalizedSignal` — one kwarg |
| U04 | `esqe/signal_store.py` | `QualifiedSignalRow.subject_key` + `_COLUMNS` + the row construction |
| U06 | `context/situation_bso.py` | `L1Signals.subject_keys` — deduplicated, sorted, all-state |
| U07 | `context/situation_bso.py` | `_L1_SELECT` widened 9 → **17** |
| U08 | `context/situation_bso.py` | `_L1_BY_EVENT_SELECT` widened **identically**, and a test now asserts they agree |
| ~~U10/U11~~ | — | **withdrawn** — see §1 |

### The eight columns, and why each one

A column nothing reads is noise with a migration attached. Each of these has a consumer that
cannot get the value any other way:

| Column | Consumer |
|---|---|
| `subject_key` | grouping, and ALG-19's other half. **The headline** |
| `domain_hints` | which corpus Layer 3 selects — the 8% problem |
| `confidence_bp` | L2 could not tell a 9000 from a 1000 |
| `occurred_at` | the SIGNAL's world time; L2 had only the event's |
| `expires_at` | ALG-19 already decided it; L2 was re-guessing |
| `secondary_types` | a signal is often several kinds; only the primary crossed |
| `extraction_ref` | the claims behind the signal |
| `internal_kind` | company canon, which outranks observed traffic and was invisible |

**17, not the 24 the plan asked for.** The remaining eleven — `trace_id`, `authority_rank`,
`content_hash`, `ingested_at`, `qualification_reason`, `superseded_by`, `supersedes`, `envelope`,
`visibility`, `coverage_ready`, `importance_version` — either already cross, or have **no reader
in Layer 2 today**. Adding them would hit the number and change nothing. Recorded rather than
padded.

---

## 3. What the build found that the plan did not

### 3a · The drift the file warned about had no test

`situation_bso.py` already said:

> *"Two hand-written copies of this select is how the two paths end up disagreeing about which
> signals a situation rests on, and only one of them has a test."*

There were two copies. **Neither had that test.** There is one now —
`test_the_two_projections_select_exactly_the_same_columns` — and it passed *before* the widening,
which is what makes it a guard rather than a fix.

### 3b · The hermetic test schema is a hand-written subset, and it drifts the same way

Two files under `tests/context/` create their **own** `qualified_signals` table inline, with
exactly the columns the old projection read:

```
tests/context/test_l1_signals_reach_a_reading.py
tests/context/test_absence_receipt.py
```

Widening the projection broke nine tests with `no such column: qs.subject_key`. **Same class of
defect as 3a, one layer down:** a hand-written copy of a schema that nothing keeps in step with
the migration.

Both were widened, and both `insert into qualified_signals values (...)` statements were made
**column-explicit** — a positional insert breaks on every column added, and the failure it
produces is a column count rather than the thing the test is about.

### 3c · Five test fixtures construct C-12 directly

`subject_key` is required on the contract, so every fixture that builds a
`QualifiedEnterpriseSignal` or a `QualifiedSignalRow` had to name one. Five files. Each was given
a **real** subject rather than a placeholder — the lifecycle fixtures in particular, because
ALG-19 supersedes on `(subject_key, signal_type)` and rows with different subjects could not
replace one another at all.

---

## 4. Verification

| Suite | Result |
|---|---|
| `tests/test_the_seam_carries_what_layer_one_concluded.py` | **7 passed** |
| `tests/contracts` + `tests/capture` | **5,489 passed** · 3 failed |
| `tests/context` | **2,390 passed** · 11 failed |

**Zero regressions.** The 14 remaining failures are the same identified set: 11 `llm_costs`
fixture drift, 1 `h0_gate` baseline, 1 local tesseract, 1 Postgres.

**NOT verified:** the migration has not been applied anywhere, and the end-to-end read has not
run. `test_l2_reads_what_l1_publishes.py` and `test_l1_seam_activation.py` are Postgres-marked and
skip here — **and a skipped test is not a pass.**

---

## 5. Still open

| # | What | Owner |
|---|---|---|
| 1 | Apply `0177` | Harsh |
| 2 | Run the 618 Postgres tests, including both seam tests | Harsh (scratch DB) |
| 3 | Confirm a composed situation carries `subject_keys` on real data | after 1 and 2 |
