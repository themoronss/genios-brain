# Step 11 · The P1–P5 replay harness — findings

**Run:** 2026-09-24 · premise checked BEFORE any code
**Status:** 11-U2 · U3 · U4 · U5 **DONE (structural)** · 11-U1 and U6 **need real data — Harsh**

---

## 1. The headline: the harness's first act was to find two errors in our own scoreboard

`L1_P1_P5_AUDIT.md` was produced by a person reading code. The step says so: *"There is no harness;
the audit was done by hand."* Within a minute of existing, the machine-checked version found:

### 1.1 · The audit miscounted itself, in the flattering direction

| | |
|---|---|
| Its **summary line** | *"38 objects — **16 built** · 8 stranded · 14 missing"* |
| Counting the ✅ in its **own tables** | **15 built · 9 stranded · 14 missing** |

One object. Trivial on its own — **and it survived being written down, quoted into the plan, and
used as metric 6's baseline**, because nothing ever re-derived it. That is this plan's own recurring
defect committed in this plan's own documents.

The table is the evidence and the summary was a summary, so **the baseline is 15**, and
`test_the_baseline_matches_the_registry_it_describes` stops the constant and the 38 rows drifting
apart again.

### 1.2 · It was already stale — five objects have moved since

```
CALIBRATION   baseline 15  →  measured 20
  improved    relationship_state_change (step 8) · coverage_denominator (step 5)
              delivery_failure (step 2) · six_month_corpus (step 5)
              final_unresolved_question (step 4)
  unexplained (none — the harness agrees with the audit everywhere else)
  regressed   (none)
```

**20 of 38, up from 15.** Nobody edited the audit because nothing re-runs it.

---

## 2. ⭐ The harness caught MY bug before it caught anything else

The first version checked *"does the type exist"*. So `reconstruct_thread` existing made
`ball_in_court` read **present** — while the value it produces reaches nothing.

`calibrate` reported **8 unexplained** objects: *present now, absent in the audit, and no step
claims them*. That population exists precisely to catch a harness bug, and it caught mine within a
minute of being written.

> **The audit's ⚠️ never meant "the type is missing". It meant *"computed in L1, not carried to the
> seam"*** — and a check that cannot tell those apart would have reported 28 of 38 and called it
> progress.

Every stranded object is now checked against `QualifiedEnterpriseSignal` — the actual L1→L2
boundary — and nowhere else. **A value Layer 2 cannot read is a value the benchmark cannot use,
whatever exists upstream of it.**

---

## 3. What the scoreboard says now

```
SCOREBOARD   20 of 38 present
  P1 2/8   P2 7/9   P3 2/6   P4 3/7   P5 6/8

MISSES BY CLASS
  not_carried 11 · entity 2 · layer_two 1 · temporal 1
  intent 1 · extraction 1 · evidence 1
```

### 3.1 · `not_carried` is 11 of 18 misses, and that is this plan's whole thesis, measured

Not *"we cannot extract this"* — **the work is done and the answer is thrown away.** Direction,
who spoke last, whose turn it is, turn index, thread depth, the fulfilment link, the commitment
state, the meeting→follow-up edge.

Step 3 widened the seam 9 → 17 columns on exactly this finding, and the columns it added were
**signal-level** (`subject_key`, `domain_hints`, `confidence_bp`, `occurred_at`, `expires_at`,
`secondary_types`, `extraction_ref`, `internal_kind`). The **thread-level** values — everything
`reconstruct_thread` computes — still do not cross. `QualifiedEnterpriseSignal` has 30 fields and
not one of them is `direction`, `ball_in_court` or `turn_index`.

> **That is the single largest, cheapest block of benchmark objects left in Layer 1, and it is now
> a number rather than an impression.** It is also step 14's subject (temporal field set + reply
> pairing), which the harness has just made measurable in advance.

---

## 4. What was NOT built, and why

**11-U1 · grow the corpus 8 → 425, annotated.** Needs real customer data, tenant-isolation guards
(E1) and **two annotators** (E2, *"disagreement is recorded as a finding about the taxonomy"*). Not
something to fabricate.

**11-U6 · a second, high-volume mailbox.** Harsh's, and E4 is explicit about why it is not optional:
*"N=1 mailbox with unusually low outbound flatters sent-side prompts."*

**Therefore no BEHAVIOURAL score exists**, and the harness refuses to produce one:

```
behavioural quotable?  (False, 'corpus is 8 items, below the 425 the spec asks for —
                               a passing harness on a small corpus means nothing')
```

E3 says *"grow the corpus before trusting the number"* and §9 says *"do not report the 8-message
corpus as complete"*. A harness that printed a behavioural number on eight files would be the most
convincing wrong number in the repo — so the refusal is a feature, with the reason attached rather
than a bare `False` somebody deletes.

**The STRUCTURAL score is honest, reproducible and runs in CI on every commit**, which is the only
thing that stops a scoreboard going stale again.

---

## 5. Guards

| | |
|---|---|
| No database, no network, no clock, no model | pinned by `test_the_harness_needs_no_database_and_no_network` |
| `vocabulary_fingerprint` | `a3d5496aa0d3` — the harness reads code, it does not run the pipeline |
| E5 · *"must not become a test that is weakened to pass"* | the registry's `audit_present` flags are **frozen history**; a maintainer who "corrects" them to match the code deletes the only baseline the step has, and the docstring says so |

---

## 5b. Test result

```
FULL SUITE      12626 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 11: 12611 passed · 14 failed
```

**Zero regressions, +15 tests.** No migration, no model call, no re-extraction.

---

## 6. What this step does NOT do

* **It does not replay messages.** §4 — the corpus does not exist yet.
* **It does not fill the benchmark's third column.** 20 of 38 structurally present is not the same
  as 20 of 38 *demonstrated on real mail*, and conflating them is the error the whole benchmark was
  built to expose in somebody else's product.
* **It does not reach 30+.** That is the step's target and 11 of the 18 misses are `not_carried` —
  carriable, and mostly step 14's work.
