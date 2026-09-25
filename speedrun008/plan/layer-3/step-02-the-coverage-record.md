# L3-02 · The coverage record

**Needs Harsh:** none · **Model:** none · ⛔ **Migration: none — 0178 already did it**

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-02-coverage-record.md)
>
> +21 tests · 13,164 passed · 0 regressions.
>
> ⛔ **The premise check corrected this step three times, and all three shrank it.** The absence
> contract is not 3 of 8 ingredients — `capture/coverage/` is a seven-module subsystem. `context/`
> does not read coverage zero times — it reads `source_coverage` in five places. And no migration
> was needed: **0178 added every column already.**
>
> ⛔ **The real defect was one writer and zero readers.** `l1_sync_runs` carries the numerator, the
> denominator, the estimate flag and the exhaustion flag; `api/routes.py` writes them on every
> sync; **no `select` in the engine reads them back.** `not_carried`, one seam further along than
> usual — the value reaches storage and stops there, which is harder to see because the write looks
> like success.

## Done criteria

- [x] `SyncHealth` closed and guarded both ways
- [x] ⛔ `SUCCESS_EMPTY ≠ FAILED` — FX-08's case, and `l1_sync_runs.error` already separated them
- [x] `completeness_bp → None`, never 10000
- [x] the denominator is a MAX, not a SUM
- [x] a null `cursor_exhausted` counts as not finished
- [x] health alone does not license an absence claim
- [x] the sentence: *"read 37 of about 465 from gmail"*
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,164 passed · 14 pre-existing · 0 regressions**

## What is next, and why it is separate

**L3-02b** carries `describe()` onto the QES, the situation and the card — three seams, and the
step that makes the benchmark's sentence visible to a founder. **L3-03** is the gate that refuses an
absence claim without it.
