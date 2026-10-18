# S8 — DONE · the scorecard reaches the learning layer, and four reassuring badges hid a defect

**Unit:** `M14.C2.S8` · **Owner:** me · ✅ **2026-10-02** · **21 tests · 2/2 mutations caught**
**Output:** `08-ATLAS-SCORECARD-L1-to-L5.md` → **`-L1-to-L6.md`**, 45 → **56 claims**
**Source:** `Rohit_Updates/Secret War Updates/08-Cross-Layer-Synthesis/01-Master-Atlas-vs-Code-Coverage-Matrix.md`

---

## 1 · ⛔ The measure-first gate, and it caught my own numbering first

The gate I set was: *"the scorecard is named `L1-to-L5` — check whether it already carries L6 badges,
or I will write a section twice."* ⛔ It carries none: the cells are `L1-xx`, `L2-xx`, `L4-xx`,
`L5-xx` only.

⛔⛔ **But the same check caught a mistake of mine.** I had written the step as *"`L1-to-L7`"*. **This
scorecard numbers `deliver/` as L5**, so the learning layer is **L6** here — while the source matrix
labels the very same rows **`L7 Learning`**, because it uses `genios_engine/LAYERS.py`'s column
where `feedback` is 7.

> ⛔ **The programme has now paid for that collision three times**: `STEP-10`'s receipt count, the
> `L5`-labelled receipts I added to `deliver/`, and this step's own title. `LAYERS.py` says it in one
> line — *"always name the package, never the digit alone"* — and the file is still the only place
> that says it.

## 2 · The eleven claims, measured

```
EXPIRED           4    L6-02 explicit feedback · L6-06 Behavior evolution ·
                       L6-09 publisher/policy seams · L6-11 value analytics
PARTLY EXPIRED    4    L6-01 input health · L6-04 temporary memory ·
                       L6-05 outcome identity · L6-10 pivot/reset
STILL TRUE        3    L6-03 preference inbox · L6-07 Adaptive lifecycle · L6-08 review SLA
                 ──
                 11                                         total scorecard: 45 → 56
```

⛔⛔ **Four of eleven were out of date in the direction the Atlas is consistently wrong in: it calls
built things stubs.** `L6-06` is the clearest — *"Behavior cohort builder returns `[]`"* against a
**776-line component wired into the weekly run**, because the stub that preceded it by a month was
never removed.

## 3 · ⛔⛔ And four cells hid a defect the Atlas did not name

| Cell | The Atlas's badge | ⛔ What measuring it found |
|---|---|---|
| `L6-01` | *"live input health **Unknown**"* | the health gate **was broken** — `getattr(batch, "deliveries", ())` names a field that does not exist, so `degraded` was **always True** (`S7`) |
| `L6-09` | *"broken seams"* — both named ones now **fixed** | ⛔ `governed → published`, an edge the contract forbids, on **every brain publish** (`S6`) |
| `L6-10` | *"does not fully supersede Behavior"* | ⛔ **the module's stated REASON for that is now false** — see §4 |
| `L6-11` | *"hardcodes zero"* — **fixed** | ⛔ `macv_ledger`, *"the number the customer can verify"*, **has never had a writer** (`S2`) |

> ⛔ **A cell the Atlas marks *Present* is not a cell that needs no measurement.** Three of these
> four sit under badges that read as reassuring, and the fourth sits under one that had already been
> corrected.

## 4 · ⛔⛔ The new defect this step found: a stale sentence that justifies a gap

`feedback/reset.py`'s header explains why a pivot does not touch the Behavior brain:

> *"`unit_behavior_evolution` (feedback/units.py) is presently an **unwired stub that always returns
> `[]`** — **there is no live Behavior Brain content to decay**."*

⛔ **True when written, false now.** `S4` established that `packs/brains/behavior_distill.distill`
(776 lines) proposes `LearningTarget.BEHAVIOR` and is appended to the same weekly run by
`brain_pipeline_proposals`. ⛔ **So a pivot can leave live Behaviour content in place, and the
module's reason for leaving it no longer holds** — the Atlas's `L7-20` / `L7-40` concern exactly.

⛔ **Corrected, not repaired.** Superseding a durable brain entry is a governed decision, not a
narrowing of this function — it is part of Rohit's Adaptive/durable-lifecycle call. What changed is
that the justification no longer asserts something false.

> ⛔ *A stale comment reads as a measurement* — and **the most expensive place for one is the
> sentence that explains why something was left undone.**

### ⛔ And a cross-package guard, because the claim and the fact live in different packages

`test_reset_does_not_claim_behaviour_has_no_live_content` ties `feedback/reset.py`'s prose to
`feedback/target_policy.DELEGATED`'s fact. Nothing connected them before, which is why the sentence
could rot for a month.

⛔ **Checked by ATTRIBUTION, not presence** — `S2`'s lesson: the corrected docstring **quotes** the
stale sentence in order to say it is false, so a presence check would fail on the correction. The
guard allows the phrase and requires a marker near it; a **relapse** adds an unmarked occurrence and
fails.

## 5 · What the Atlas is RIGHT about in L6, and it is the part that matters

⛔ **`L6-07`.** *"Contradictory/partial… does not currently fail closed"* — six weeks on, every word
still true, verified line by line in `S1`. ⛔ And the Atlas names the required disposition,
`adaptive_ttl_unresolved` — **which `feedback/reset.py` already returns.** The codebase agrees with
the Atlas about the shape of the unanswered question and is waiting on the answer.

⛔ **`L6-03` and `L6-08`.** The preference inbox and the review SLA are genuinely absent. `S5`
narrowed the first from *"no inbox"* to *"no `kind`"* — which moves it from engineering to a
**surface decision**, and that is Rohit's.

## 6 · The mutation run — baseline first, 2/2

```
✅ baseline: 21 passed
  M1 · the stale claim is ASSERTED again, far from any marker   ✅ CAUGHT
  M2 · the delegation stops naming behavior_distill             ✅ CAUGHT
✅ baseline again: 21 passed                        2 caught · 0 survived
```

⛔ **`M1` SURVIVED on its first attempt**, because I removed one marker phrase while two others sat
in the same window. The faithful failure mode is a **relapse** — the stale sentence written again,
far from any marker. ⛔ *An invalid mutation is not a surviving mutation*, and this harness has now
refused to round one up four times in one session.

## 7 · The rename, and the citations

`08-ATLAS-SCORECARD-L1-to-L5.md` → **`-L1-to-L6.md`** — the file's third rename
(`L1-L2-L3` → `L1-to-L4` → `L1-to-L5` → `L1-to-L6`). ⛔ **Two LIVE citations fixed**
(`17-THE-THREE-LAYERS-end-to-end.md`, `08-PLAN-v2`'s `S8` row, which carried my `L1-to-L7` error);
the dated rows in `STATUS.md`, `07-LEDGER` and the `layer-5-delivery/` step files are **left
untouched** — they are the record of what was true on the day they were written.

## 8 · Verify

```bash
.venv/bin/pytest tests/feedback/test_a_quarantined_seam_is_not_an_empty_one.py -q   # 21 passed
.venv/bin/pytest -q                                                          # the FULL suite
grep -c '^| \*\*L6-' ../08-ATLAS-SCORECARD-L1-to-L6.md                        # 11 cells
```

## 9 · Doctrine

| Rule |
|---|
| ⛔ **a cell the Atlas marks *Present* is not a cell that needs no measurement** — three of four new defects sat under reassuring badges |
| ⛔ **the most expensive stale comment is the one that explains why something was left undone** |
| ⛔ **tie a claim to its fact across packages, or it rots** — nothing connected `reset.py`'s prose to `behavior_distill`'s existence |
| ⛔ **always name the package, never the digit alone** — paid for a third time, in this step's own title |
| ⛔ **an invalid mutation is not a surviving mutation** — fourth refusal to round one up |
| **a correction is not a repair, and saying which is which is the honest part** |
