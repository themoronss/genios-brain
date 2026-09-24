# Step 11 — The P1–P5 replay harness

**Status:** NOT STARTED · **Effort:** weeks · **Depends on:** all · **Engine:** D
**Moves:** metric 6 — benchmark objects present, **16 of 38 → 30+**

## 1. Why this step exists

Every step in this plan is a hypothesis until something replays it. This is the step that makes the
architecture **empirical** rather than argued — and it is the one that fills the third column of
the benchmark page, which is currently empty.

The benchmark is not five random questions. It is an **acceptance suite**, because each prompt
requires a specific set of Layer 1 semantic objects:

| Prompt | Tests |
|---|---|
| P1 | people · direction · reciprocity · reply latency · waiting state · coverage |
| P2 | commitments · promisor · object · deadline · fulfilment evidence |
| P3 | historical completeness · terminal thread state · silence |
| P4 | calendar↔email identity · cross-source temporal joins |
| P5 | conditional promises · whether fulfilment is actually **evidenced** |

## 2. Current status
`L1_P1_P5_AUDIT.md` holds the object-by-object scoreboard: **38 objects — 16 built · 8 stranded ·
14 missing.** The golden corpus is **8 messages against the 30 the spec asks for**. There is no
harness; the audit was done by hand.

## 3. Expected result

| | Before | After |
|---|---|---|
| Golden corpus | **8 messages** | 425 items (300 email · 50 calendar · 50 documents · 25 transcripts) |
| Benchmark objects present | **16 of 38** | **30+** |
| The benchmark's third column | empty | filled |
| Running the suite | by hand | one command, on every change |

**Honest ceiling:** objects 3 and 9 (6-month scope, reply-latency judgement) are partly Layer 2's.
**30 of 38 is the real target for a Layer 1 sprint**, not 38.

## 4. Edge cases
E1 the corpus contains real customer data → tenant isolation and erasure apply; the harness must
use the same guards as every gate script (`scripts/_db.py`) · E2 annotation is subjective → two
annotators on a sample, and disagreement is recorded as a finding about the *taxonomy* · E3 a
passing harness on 8 messages means nothing — **grow the corpus before trusting the number** ·
E4 N=1 mailbox with unusually low outbound flatters sent-side prompts; **a second, high-volume
mailbox is required before any number is quoted externally** · E5 the harness must not become a
test that is weakened to pass.

## 5. How to do it
| Unit | What |
|---|---|
| 11-U1 | grow the golden corpus 8 → 425, annotated |
| 11-U2 | per prompt, the list of required objects — already written in `L1_P1_P5_AUDIT.md` |
| 11-U3 | the harness: corpus → L1 → assert each object present, with its evidence |
| 11-U4 | the failure taxonomy — every miss gets a class (ingestion · pagination · scope · extraction · entity · intent · temporal · evidence · qualification false-negative · coverage misreport · unknown→false) |
| 11-U5 | a before/after report per run |
| 11-U6 | run it on a second, high-volume mailbox |

## 6. Test cases
T1 the harness reproduces today's 16 of 38 on today's code — **the calibration check; if it does
not, the harness is wrong, not the layer** · T2 every miss carries a failure class · T3 the corpus
is reproducible and frozen · T4 no live database, no network.

## 7. Verify
```bash
uv run --no-sync pytest tests/golden -q -p no:randomly
python -m scripts.l1_benchmark_replay --corpus golden/l1 --report
```

## 8. Done criteria
**Ticked 2026-09-24.** Two closed, three need real data and are Harsh's.

- [ ] **the corpus is 425 items, annotated** — **NOT DONE.** It is 8 files. Needs real customer
      data with tenant-isolation guards (E1) and **two annotators** (E2: *"disagreement is recorded
      as a finding about the taxonomy"*). Not something to fabricate.
- [x] **T1 passes: the harness reproduces the hand-audited baseline before any improvement** —
      **and it found two errors in the audit doing it.** (a) the audit's summary says *"16 built"*
      while its own tables show **15** — miscounted in the flattering direction, quoted into the
      plan, used as metric 6's baseline, and invisible because nothing re-derived it. (b) it was
      already stale: **five objects have moved** since, each attributed to the step that moved it.
      `calibrate` separates *improved* (a step claims it) from *unexplained* (**a harness bug**)
      from *regressed*, so the harness cannot read its own bugs as progress — and it caught 8 of
      mine within a minute of being written.
- [ ] **30+ objects present after steps 1–10** — **measured: 20 of 38**, up from 15. Short of the
      target, and the harness says exactly where: **11 of the 18 misses are `not_carried`** —
      computed in L1 and dropped at the seam. That is carriable work and mostly **step 14's**.
- [x] **every miss carries a failure class** — 13-class taxonomy, asserted on every miss.
      `not_carried` was ADDED to the step's list because the audit's ⚠️ category had no class and
      it turns out to be the largest one.
- [ ] **a second mailbox has been run** — **Harsh's.** E4: *"N=1 mailbox with unusually low
      outbound flatters sent-side prompts."* Until then `behavioural_score_is_quotable` returns
      False with the reason attached, and no behavioural number exists to quote.

### 8.1 · The harness caught its own author first

The first version checked *"does the type exist"*, so `reconstruct_thread` existing made
`ball_in_court` read PRESENT while the value it produces reaches nothing. `calibrate` reported
**8 unexplained** — the population that exists to catch exactly that — and every stranded object is
now checked against `QualifiedEnterpriseSignal`, the actual L1→L2 boundary.

> The audit's ⚠️ never meant *"the type is missing"*. It meant **"computed in L1, not carried to
> the seam"**, and a check that could not tell those apart would have reported 28 of 38 and called
> it progress.

## 9. Must NOT do
**Do not weaken an assertion to make the harness pass.** Do not quote a number from one mailbox
externally. Do not report the 8-message corpus as complete — the build record already flags that as
a known overstatement.
