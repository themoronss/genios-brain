# Step 18 · The conversation crosses the seam — findings

**Run:** 2026-09-24 · premise checked BEFORE any code · migration **0181**
**Trigger:** closing `S01b`, the one OPEN row step 17's failure log left behind.

---

## 1. ⛔ Premise check — S01b was real and the diagnosis was wrong

The failure log said:

> *"`pipeline.py` hands `reconstruct_thread` a list of ONE message, so ALG-03's full RFC 5322 parent
> resolution has never run on real data."*

**Both halves true. The conclusion was not.** One sentence in `reconstruct_thread` settles it:

> *"`ball_in_court` is derived from the most recent message BY TIME, not from the last link of the
> walk."*

At capture the event **is** the newest message of its thread. And `_thread_context` reads **only**
`.ball_in_court` from that call — `turn_index` and `thread_depth` come from step 16's header
derivation, not from the chain.

**Verified by execution rather than by reading:**

| input | `ball_in_court` |
|---|---|
| a 4-message thread | `us` |
| its newest message **alone** | `us` |
| a 3-message thread | `them` |
| its newest message **alone** | `them` |

**So the one-message call is correct for the value its caller reads.** Feeding it the whole thread —
an API call or a store read per event — would have bought nothing.

### 1.1 · What the check found instead, and it is bigger

Chasing S01b led to the real question: *where does the correct value go?*

**Nowhere.** `QualifiedEnterpriseSignal` carried **none** of the five conversation facts, and
`NormalizedSignal.thread` sits in `build_signal` **unread**.

`ThreadContext`'s own docstring already said half of it — *"NONE of it reached S4"* — and that was
fixed. The value then stopped **one seam later**, which nothing was watching.

**It is the same leak step 14 found in `domain_hints`**, where this very builder rebuilt a value by
hand and dropped `confidence_bp`. And it is the plan's whole diagnosis said out loud:

> *"Every measured loss is a value that is computed correctly and then not carried: `ball_in_court`
> and `turn_index` reach only the trace."*

---

## 2. Why this unit, out of eleven candidates

**11 of the benchmark's 18 misses are classed `not_carried`.** One `ThreadContext` closes four of
them at once — the largest single-change block on the board:

| benchmark object | reads | was |
|---|---|---|
| `message_direction` | `direction` | not carried |
| `ball_in_court` | `ball_in_court` | not carried |
| `turn_index` | `turn_index` | not carried |
| `activity_count` | `thread_depth` | not carried |

**And Layer 2 already wants it.** `context/attention.py:66` scores `ball_in_court == "us"` at +15 —
today from its own weaker recomputation off Gmail labels (`runner.py:159`), because L1's ALG-03
answer never arrives.

### 2.1 · What was deliberately NOT carried

`last_inbound_at` — read by `who_sent_last` and `p3_who_sent_last`. **You cannot know the previous
inbound time from a single message.** That genuinely needs siblings, so it stays open rather than
being guessed. `S01b` is re-scoped to exactly that and nothing more.

---

## 3. Cost check

| | |
|---|---|
| prompt | unchanged |
| `vocabulary_fingerprint` | **`a3d5496aa0d3`** — unchanged |
| model calls | none — every value was already computed |
| re-extraction | **none** |
| migration | **0181**, five nullable columns + two partial indexes |

The values existed and were being thrown away. This step adds no computation at all.

---

## 4. What was built

| | |
|---|---|
| contract | five fields on `QualifiedEnterpriseSignal`, with the **refusing defaults preserved** |
| publisher | `_conversation(signal.thread)`, spread into the C-12 kwargs |
| store | `_COLUMNS`, the row dataclass, the INSERT, the parameter map **and the upsert** |
| migration | `0181_signal_conversation.sql` |

### 4.1 · `direction=None` is a refusal and had to survive as one

*"With no identity for 'us' every message looks inbound, which is how a product's own onboarding
mail got modelled as a prospect asking for a demo."*

So the migration's columns are **nullable with no default**, and `_conversation` returns an **empty
dict** when there is no thread rather than a dict of Nones — the contract's defaults are then the
single place those refusals are written, instead of a second copy that drifts.

### 4.2 · The upsert carries the conversation, deliberately

Whose turn it is **changes** — that is the entire point of the field. A re-published signal whose
`ball_in_court` stayed at its first value would keep reporting a conversation as owed after it was
answered.

---

## 5. Two mistakes made and caught

**⛔ I repeated step 14's blunt-grep mistake.** `assert " not null" not in sql` failed — on this
migration's **own comment** explaining why `direction` must stay nullable. Step 14 recorded the
identical mistake against 0179's partial index. The test now parses column **declarations**, and
says in the docstring that it was made twice.

**⛔ `calibrate` refused the gain until a step claimed it.** The four newly-crossing objects came
back as `unexplained` — *"present now, absent in the audit, and NO step claims it"*, the signature
of a harness bug. Declaring `moved_by` on each is what turned four unexplained into four improved.
The harness did its job on the person who wrote it, for the second time.

---

## 6. Result

```
BENCHMARK       20 → 24 of 38        0 unexplained · 0 regressed
FULL SUITE      12885 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 18: 12875 passed · 14 failed
```

**Zero regressions, +10 tests.** `vocabulary_fingerprint` unchanged.

### 6.1 · A gap this step closed in the tests themselves

**No test in this repository called `build_signal`.** Step 14's `due_at` check and step 6's
`domain_hints` check both assert by reading the function's **source** — which passes on a builder
nobody calls, the exact defect this project keeps finding. `_build()` in the new test drives the
real function and asserts on what comes out; the scaffolding it needs (V-4's evidence, the four
vector components, `versions`) is the price of that, and worth paying once.

---

## 7. What this step does NOT do

* **It does not close S01b.** It re-scopes it to `last_inbound_at` and carries everything that did
  not depend on it.
* **It does not make Layer 2 read the values.** `attention.py` still recomputes its own; pointing it
  at L1's answer is a Layer 2 change, and Layer 2 is next.
* **It does not backfill.** Signals written before 0181 carry nulls, which read as *"we do not
  know"* — true. `turn_index` on rows written before step 16's deploy carries the old *turn 0 of 1*
  reading and cannot be repaired without a re-sync.
* **It does not apply the migration.** 0181 joins 0176–0180 waiting on Harsh.
