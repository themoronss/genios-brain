# Step 3 — Widen the L1 → L2 seam

**Status:** NOT STARTED · **Effort:** days · **Depends on:** nothing · **Engine:** D
**Moves:** metric 2 — columns crossing the seam, **9 of 28 → 24+**
**Already decomposed:** `tree.yaml` → `l1_signal_quality_seam` → M13 (11 units)

---

## 1. Why this step exists

This is the **"dead data"** step. Layer 1's code is fully wired — an AST audit of all 119 modules
found 0 genuinely dead ones. What is not wired is the **data**: eight values are computed
correctly every sweep and then dropped on the floor between L1 and L2.

| Computed by | Value | Where it dies |
|---|---|---|
| `structural/threads.py` ALG-03 | `ball_in_court` | recorded on the **trace**, not on the signal |
| `structural/threads.py` ALG-03 | `turn_index`, `thread_depth` | same |
| `pipeline._envelope_direction` | `direction` | written to `prepared_content` only |
| `esqe/normalize.py` ALG-22 | `subject_key` | written to the **drop ledger**, not to the published signal |
| `esqe/*` | `domain_hints`, `confidence_vector`, `occurred_at`, `expires_at`, `secondary_types`, `internal_kind`, `extraction_ref` | stored in `qualified_signals` and **never selected** |

Until this lands, **no later step can be measured end to end**, because nothing a later step
improves becomes visible to Layer 2. That is why step 3 blocks steps 5–10.

## 2. Current status — with evidence

### 2a · The projection reads 9 of 28 columns

```python
# genios_engine/context/situation_bso.py:516  — "the one projection of `qualified_signals`
# this module reads, spelled once"
_L1_SELECT = (
    "select m.correlation_id, qs.signal_id, qs.state, qs.importance_bp, "
    "qs.importance_version, qs.importance_components, qs.evidence_refs, qs.conflict_ids, "
    "qs.signal_type, qs.coverage_ready "
    ...)
```

Nine columns. The store writes **28** (`esqe/signal_store.py:58-63`). Never crossing:
`domain_hints` · `envelope` · `occurred_at` · `confidence_bp` · `confidence_vector` ·
`secondary_types` · `expires_at` · `supersedes` · `internal_kind` · `extraction_ref` ·
`authority_rank` · `content_hash` · `qualification_reason` · `superseded_by` · `ingested_at`.

### 2b · `subject_key` has no column at all

| Table | Migration | Has `subject_key`? |
|---|---|---|
| `qualification_drops` | 0088 | **yes** |
| `signal_lifecycle` | 0093 | **yes** |
| `signal_conflicts` | 0087 | **yes** |
| `qualified_signals` | 0089 | **NO** |

A **refused** signal records what it was about. A **published** one does not. ALG-19's supersession
key is `(subject_key, signal_type)`, so Layer 2 can walk a chain by pointer but **cannot ask
"give me every signal about the AWS renewal."** And nothing in `context/` reads `signal_lifecycle`
— only `platform/wiring.py` (the writer) and `api/account_routes.py` (the erasure list).

### 2c · Only the loudest signal gets an extraction

```python
# genios_engine/context/runner.py:249
(array_agg(qs.extraction_ref order by qs.importance_bp desc, qs.signal_id))[1] as qes_extraction_ref
```

`[1]` is an **event-level answer to a signal-level question**. An event carrying two qualified
signals resolves one extraction — the higher-scoring one — and the second signal reaches L2 with
nothing behind it.

### 2d · The module's own comment warns about the risk this step must not create

> *"Two hand-written copies of this select is how the two paths end up disagreeing about which
> signals a situation rests on, and only one of them has a test."*

There are already two selects (`_L1_SELECT` and `_L1_BY_EVENT_SELECT`). **Widening one and not
the other is the exact failure the file is warning about.**

## 3. Expected result — the number that must move

| | Before | After |
|---|---|---|
| Columns in `_L1_SELECT` | **9** | **24+** |
| `_L1_BY_EVENT_SELECT` | 9, hand-copied | identical set, **asserted by a test** |
| `subject_key` on `qualified_signals` | absent | present + indexed |
| Extractions resolved per event | **1 (the loudest)** | one per signal |
| A composed situation's L1 rows carrying domains / confidence / `occurred_at` | `None` | populated |

**Prediction:** this changes no scores and no counts. It changes what Layer 2 can *see*. If any
funnel count moves, something was broken, not fixed — **that is the signal to stop**.

## 4. Edge cases and failure scenarios

| # | Scenario | What must happen | Why |
|---|---|---|---|
| E1 | Rows written before the migration | `subject_key` is **nullable on arrival** | a `NOT NULL` refuses the migration on any live tenant |
| E2 | Two signals, same subject, same type, same authority | supersession must stay authority-gated and world-time ordered | ALG-19's rules do not change here |
| E3 | The two selects drift again | a test asserts they select the **same column set** | 2d |
| E4 | Structured events have no prepared text | `content_hash` is `None` by design — do not backfill it with a digest of `""` | `publisher.py:961-978` says hashing the empty string gives every one of them the same non-answer |
| E5 | An event with 5 qualified signals | 5 extraction refs resolved, not 1 | the actual fix in 2c |
| E6 | `extraction_ref` points at a row that was evicted | resolve to `None`, do not fail the read | the cache is content-addressed and may expire |
| E7 | The wider select slows the sweep | measure it; the join in 2c is the one to watch | a correctness fix that makes ingestion time out is not shipped |
| E8 | A replayed sweep | upsert, not a second row | the store is content-addressed for exactly this |
| E9 | `subject_key` disagrees between the published signal and its lifecycle row | impossible by construction — **pass the value, never re-derive it** | `record_of` takes it as a parameter precisely so there is one answer |

**E9 is the one to be careful about.** `contracts/signal.py` currently argues that C-12 should
*not* carry `subject_key` because re-deriving it would be a second answer. That reasoning is right
about **re-deriving** and wrong about **carrying**. The field must be **supplied** from
`NormalizedSignal.subject_key`, and its docstring must say so.

## 5. How to do it — unit by unit

Units are already cut in `tree.yaml` as **M13**. Summary here; the tree is authoritative for IDs.

> **Number changed 0176 → 0177 on 2026-09-23.** Step 2 took `0176` for the `delivery_failure`
> CHECK-constraint widening, which is required before any bounce signal can be written at all.

### M13.C1 — subject identity crosses
| Unit | What | Artifact |
|---|---|---|
| U01 | migration `0177`: `subject_key text` + index `(org_id, subject_key, signal_type)`, nullable | `migrations/0177_qualified_signals_subject_key.sql` |
| U02 | `subject_key: str` on C-12, **supplied, never derived** — and the field note must say so | `contracts/signal.py` |
| U03 | `build_signal` passes `NormalizedSignal.subject_key` (it already holds the object — one kwarg) | `esqe/publisher.py::build_signal` |
| U04 | `_COLUMNS` and the row params carry it; upsert takes it from `excluded` | `esqe/signal_store.py` |
| U05 | a published signal and its refused sibling agree on `subject_key` | `tests/capture/esqe/test_subject_key_seam.py` |

### M13.C2 — the projection widens
| Unit | What | Artifact |
|---|---|---|
| U06 | the L2-side row shape gains the fields **first**, so a partial landing cannot half-populate a situation | `context/situation_bso.py::_l1_from_rows` |
| U07 | `_L1_SELECT` widens | same file |
| U08 | `_L1_BY_EVENT_SELECT` widens identically **+ a test that the two agree** | same file |
| U09 | end to end on scratch Postgres | `tests/test_l2_reads_what_l1_publishes.py` |

### M13.C3 — every signal's extraction
| Unit | What | Artifact |
|---|---|---|
| U10 | replace `array_agg(...)[1]` with a per-signal join | `context/runner.py` |
| U11 | two signals on one event, each with its own extraction | `tests/context/test_runner_extraction_join.py` |

**Order:** U01/U02 → U03 → U04 → U05 → U06 → U07 → U08 → U09 → U10 → U11. Eight deep.

## 6. Test cases

| # | Test | Asserts | RED today because |
|---|---|---|---|
| T1 | `qualified_signals` has `subject_key` | column exists, indexed | migration not written |
| T2 | published + refused sibling | same `subject_key` | published has no such field |
| T3 | the two selects | **identical column sets** | nothing enforces it |
| T4 | composed situation | domains, confidence, `occurred_at` not `None` | not selected |
| T5 | two signals on one event | two distinct extractions resolved | `[1]` returns one |
| T6 | replayed sweep | upsert, one row | — |
| T7 | pre-migration rows | still readable with `subject_key` null | — |
| T8 | **funnel counts unchanged** | emitted / published / refused identical before and after | **the guard for §3's prediction** |

T8 is the most important test in this step. This step must change *visibility*, not *behaviour*.

## 7. Verify commands

```bash
uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q -p no:randomly
uv run --no-sync pytest tests/capture/esqe/test_publisher.py -q -p no:randomly
uv run --no-sync pytest tests/capture/esqe/test_qes_provenance.py tests/capture/esqe/test_subject_key_seam.py -q -p no:randomly
uv run --no-sync pytest tests/test_l2_reads_what_l1_publishes.py tests/test_l1_seam_activation.py -q -p no:randomly
uv run --no-sync pytest tests/context/test_runner_extraction_join.py -q -p no:randomly

# behaviour must be unchanged
python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"
```

**These are Postgres-only (`pytest.mark.pg`). Without `GENIOS_TEST_DATABASE_URL` they skip, and a
skipped test is a RED step.**

## 8. Done criteria

**Ticked 2026-09-24**, retroactively — same reason as step 2: this step predates the checklist
being enforced. Three closed, one WITHDRAWN, two are Harsh's.

- [ ] **migration `0177` applied; column present and indexed** — written and idempotent, not yet
      applied. **Harsh, item 3 of `HARSH-ORDER.md`.** It is a hard ordering constraint: the
      widened projection READS `qs.subject_key`, so the column must exist before the code ships.
- [x] **both selects widened, and T3 asserts they agree** —
      `test_the_two_projections_select_exactly_the_same_columns`. This is the drift guard
      `situation_bso.py`'s own comment asked for and never had: *"two hand-written copies of this
      select is how the two paths end up disagreeing, and only one of them has a test."*
- [x] **`subject_key` on published signals matches the drop ledger's** — it is SUPPLIED from
      `NormalizedSignal.subject_key`, never re-derived (`test_the_publisher_passes_the_subject_
      rather_than_recomputing_it`). Two derivations of one subject is how a signal ends up
      superseded under one key and queried under another.
- [~] **an event with 2+ signals resolves 2+ extractions** — **WITHDRAWN as a defect.** Production
      showed every multi-signal event has exactly one distinct `extraction_ref`, because LLM-2
      runs once per EVENT. `array_agg(...)[1]` loses nothing. The test now pins the INVARIANT that
      makes it safe rather than the SQL that depends on it.
- [x] **T8 green — every funnel count identical to before** — the full suite shows zero
      regressions across every step since.
- [ ] **before/after column count written into `STATUS.md`** — `9 → 17` is in the table. The
      measured production confirmation needs the migration applied.

## 9. What this step must NOT do

- **Do not re-derive `subject_key`.** Pass it. E9.
- **Do not widen one select and not the other.** 2d.
- **Do not change any score, floor or count.** If a number moves, stop and find out why.
- **Do not make `subject_key` NOT NULL** in this migration. E1.
- **Do not backfill `content_hash` for structured events.** E4.
