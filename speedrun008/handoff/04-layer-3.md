# Layer 3 — handoff for Harsh

**Written:** 2026-09-25 · branch `speedrun008` · **steps L3-0A through L3-07 complete**
**Suite at handoff:** 13,216 passed · 1,061 skipped · 152 xfailed · **14 failed, all pre-existing**

---

## 0. Read this first — what changed, in one paragraph

Eight steps landed. **Two need something from you, and one needs a decision** (one migration, one operator call). **Five need
nothing** — they are code and tests already on the branch. Nothing in here changes a computed score,
a prompt, or `vocabulary_fingerprint`; there is **no model call in any of the seven**, and **one
migration**.

⛔ **The thing worth your attention is not the code. It is that four of the seven steps discovered
their own premise was wrong, and two of those premises were things this plan had told Rohit were
the highest-value work in the layer.** §6 is the honest list, because you will otherwise read the
earlier planning documents and act on claims that are now corrected in place.

---

## 1. ⛔ What needs YOU — two items, in this order

### 1.1 · Apply migration `0184_graph_recorded_at.sql` (HARSH-ORDER item 22)

**What it does.** Adds a nullable `recorded_at timestamptz` to `graph_nodes`, `graph_facts` and
`graph_edges`, plus three partial indexes. Idempotent, add-if-not-exists throughout.

**Why it exists.** `GET /graph/as-of` answers *"what did GeniOS know when it made that decision?"* —
the question every enterprise security review asks — with **one predicate over three tables**:

```sql
valid_from <= :t and (valid_to is null or valid_to > :t)
```

**The three tables did not agree about what `valid_from` means.**

| table | `valid_from` was | meaning |
|---|---|---|
| `graph_nodes` | the column default | **when we learned it** |
| `graph_facts` | the column default | **when we learned it** |
| `graph_edges` | `coalesce(occurred_at, now())` | ⛔ **when it happened** |

`write_edge` binds `:vf` to `occurred_at`, which on the live capture path is the **message's own
timestamp** (`context/pipeline.py:1040`, `context/structured.py:95`, `context/documents.py:267`).

**The consequence:** backfill a six-month-old email today and the edge it creates is stamped six
months ago. **An as-of read of five months ago then sees a relationship we learned about this
morning.** `write_fact`'s empty-window trick protects facts from exactly this; nothing protected
edges.

**⛔ Why it is urgent rather than tidy:** item 21 below widens the backfill window from 60 days
toward 365. That is **a year of edges backdated into the as-of history**. Apply 0184 before or with
item 21.

**Why the column was not simply redefined** — the decision you would otherwise re-litigate:
`reason/moments/recall.py:113` reads `max(valid_from)` as *"when did we last relate to this node"*
and `reason/moments/slice.py:100` orders by it. **Both are right to.** Changing the write would have
moved every one of those answers to a different question **with nothing failing**. So a second,
unambiguous column was added and the predicate became `coalesce(recorded_at, valid_from)` — uniform
across all three, which preserves `_view`'s property that the three selects differ only in their
window.

**⛔ Existing rows are NOT backfilled, deliberately.** `default now()` would assert we learned a
tenant's entire history at the instant the migration ran; `default valid_from` would assert the very
thing the step exists to stop believing. **We do not know when we learned them.** They carry NULL
and fall through the coalesce to exactly today's behaviour — so an as-of read over pre-0184 edges is
**still wrong, and now visibly rather than silently.**

**After applying:** nothing to verify by hand.

---

### 1.2 · Set the backfill window on the pilot connection (HARSH-ORDER item 21)

**This is an operator call, not a deploy.** The code is built, wired and tested.

```
PATCH /connections/{connection_id}/backfill-window     { "days": 365 }
POST  /connections/{connection_id}/backfill
```

**Why.** Tested against the 23 September benchmark mailbox:

```
⛔ INVISIBLE   Keshav 77d · Aditya 79d · Radhesh 69d · John 63d · Vatsa 61d
✅ visible     Manik 46d · Pankaj 16d · Onur 7d
```

**Five of eight waiting relationships, and three of four broken-promise source messages, sit outside
the current 60-day window.** They are not badly answered — they are **invisible**. Not one of those
misses is a reasoning failure.

| days | buys |
|---|---|
| 180 | all 8 waiting rows · all 4 broken promises · benchmark **P3** (6 months) |
| **365** ✅ | **＋ P4** (12-month calendar × email) |

Cost is **one-time and bounded** — the extraction cache means a document is extracted **once, ever**.
Range enforced at 1–3650; an out-of-range value is refused at the edit, not at the next sync.

**Then check the log for both lines, in this order:**

```
backfill drain done|TRUNCATED org=… scanned=… emitted=…
l2 history replay org=… moved=True {…}
```

⛔ **`moved=False` on a first widened drain is the signal to investigate** — it means the rebuild ran
and found nothing to do, which on freshly landed history should not happen.

**`TRUNCATED` is not a failure.** The older tail remains; re-run `POST /backfill` to resume. The
rebuild runs either way, deliberately.

**⛔ Known consequence, recorded not fixed:** widening history improves coverage for facts that were
**held** for lack of it, and **nothing re-examines them yet**. That is Wave 4's held-candidate
recovery step. Do not read a quiet result as "nothing was there".

---

## 1.3 · ⛔ A DECISION, not a task — `freshness_half_life_days` is misnamed

**Nothing is broken and nothing was changed. This needs a call from you and Rohit.**

`reason/engine._freshness` feeds the 30%-freshness slot of every decision's confidence term:

```python
def _freshness(occurred_at, eval_time, *, half_life_days: float = 30.0) -> float:
    return math.exp(-age_days / max(1.0, half_life))
```

`exp(-age / T)` is an **e-folding time constant, not a half-life.** Measured:

```
  0d -> 1.0000
 15d -> 0.6065
 30d -> 0.3679      ⛔ the value a pack configures as its "half life" — 36.8%, not 50%
 60d -> 0.1353
120d -> 0.0183
```

**The curve's true half-life is `half_life_days × ln2` ≈ 20.8 days when a pack sets 30.**

**Why it matters operationally:** a pack author reading `freshness_half_life_days: 30` reasonably
expects half the weight after a month. They get 37%. **Every value anyone has tuned is roughly 30%
out from the intent behind it** — and the tuning looks like it worked, because the number moved.

### The three options, with their blast radius

| | change | blast radius |
|---|---|---|
| **A** | **Do nothing.** Behaviour is pinned; the misnomer is documented at the function and here | zero. The next author still has to read the docstring to avoid the trap |
| **B** | **Rename the key** to `freshness_efold_days` (or similar), keeping the formula | ⛔ breaks every authored pack config that sets it. Needs a compatibility read of the old key for at least one release |
| **C** | **Fix the formula** to a true half-life (`0.5 ** (age/hl)`) | ⛔⛔ **moves the confidence term of every decision this product has ever made.** Every stored `decision_hash` stays valid but every NEW score shifts, and replay comparisons across the change will differ. Needs a measured before/after on real data, not a deploy |

**My recommendation: A now, B when packs are next versioned.** C is only worth it if someone shows
the current curve is measurably too aggressive — and nobody has measured it. ⛔ **Do not take C as
"a small maths fix"; it is a silent global re-scoring.**

**Pinned by** `tests/test_one_answer_per_decay_question.py`, which fails if the curve moves in
either direction — so whichever option is chosen, it cannot happen by accident.

---

## 2. What landed, step by step

| step | what | needs you |
|---|---|---|
| **L3-0A** | capture backfill now chains into the Layer 2 history rebuild | item 21 |
| **L3-00** | the product layer vocabulary in `LAYERS.py`; `mcp` declared; reverse totality guard | — |
| **L3-01** | `ReasoningDecision` named as the Decision Object; outcome vocabulary pinned to the DB | — |
| **L3-02** | `capture/coverage/window.py` — the coverage read that had no reader | — |
| **L3-02b** | a situation now says how much of its own window it read | — |
| **L3-03** | an absence claim now requires the window to have been **read**, not just the source **connected** | — |
| **L3-04** | knowledge time | ⛔ **item 22** |
| **L3-05** | the corroboration `distinct` given one home and a pin | — |
| **L3-06** | four guards on the heartbeat that notices what did not happen | — |
| **L3-07** | the two staleness curves given one owner each; the dead column pinned dead | ⛔ **decision §1.3** |

---

## 3. ⛔ Three behaviour changes to be aware of

**1 · Fewer `GENUINELY_ABSENT` verdicts, on purpose (L3-03).** An absence now needs the sweep over
the situation's own evidence span to have **exhausted its cursor and known its denominator**. A
tenant whose sync is partial, failed, or gave no total will see absences downgrade to `UNKNOWABLE`.
**That is the fix, not a regression** — `licenses_negative_inference` is what stops *"no follow-up
found"* being published off an 8%-read mailbox.

**2 · Situations may carry new `gaps` sentences (L3-02b).** e.g. *"the gmail sweep did not finish,
so a tail of this window was never read"*. They land where `unmet_source_families` lands. ⛔ **Whether
the renderer surfaces them is a `deliver/` question and is not claimed.**

**3 · The capture backfill now costs more per run (L3-0A).** It chains a Layer 2 rebuild and, when
that moves anything, a second L4/cards pass. That is the point — before it, a widened window landed
a year of mail and derived no situations from it.

---

## 4. Things you will trip over if nobody tells you

**4.1 · The graph schema is duplicated across the test suite.** Adding `recorded_at` broke **8 test
files**, each carrying its own hand-written `graph_facts` DDL. There is **no guard that the test
DDLs match the migrations**, so every graph column addition is an N-file change discovered by
breakage. A first over-broad fix touched 38 files and produced **210 failures** before being
reverted. ⛔ **Not fixed — it is a real cost and it was not this layer's to pay.**

**4.2 · Two predicates live in two places each.** `graph_store._WINDOW_AT` is mirrored by
`importance.FACT_WINDOW_AT` and **is pinned by a test** — that pin is the only reason the second copy
moved with the first in L3-04. The corroboration subquery was in two copies with **no** pin until
L3-05 gave it one home. **If you duplicate SQL in this codebase, pin it the same day.**

**4.3 · `context/importance.py` bans clock tokens in its own source, comments included.** A comment
explaining a change tripped it. The guard is right; write around it.

**4.4 · The 14 pre-existing failures are genuinely pre-existing.** Verified by stashing the branch's
production changes and re-running: they fail either way. They are not this layer's.

---

## 5. ⛔ What is still open, and where it is routed

| | |
|---|---|
| `situation_interpretations.valid_until` **has no reader** | written by L2-5's store; an expired interpretation stays live for ever. Same *one writer, zero readers* shape as the coverage columns. → **L3-16** (`expired` is one of its five words) |
| held candidates are not re-examined when coverage improves | → **Wave 4**, and item 21 makes it matter |
| cross-channel evidence lineage | one assertion quoted across channels counts as several sources. **Declared** in `reason/runner.LINEAGE_UNPROTECTED` with a mover: **the third connector** |
| `independence_group` populated only for screen/email | same declaration |

---

## 6. ⛔ Four premises this plan got wrong, corrected in place

**Read this before acting on anything in `speedrun008/plan/layer-3/12`–`16`.** Those documents now
carry the corrections inline, but they were written before the code was measured.

| the plan said | measured |
|---|---|
| *"the Decision Object is five shapes; one must become it"* | **one object, five projections.** `ReasoningDecision` already was it — which **removed a Wave 6 blocker** |
| *"the absence contract is 3 of 8 ingredients"* | `capture/coverage/` is a **seven-module subsystem**; `context/` reads `source_coverage` in five places |
| *"ten copies of one claim read as ten independent sources"* | `src_count` is `count(distinct sr.source)`. **Ten forwards are one system.** The real defect was that the word was untested |
| ⛔ *"nothing evaluates when nothing arrives — the biggest functional gap"* | **four live mechanisms**, three already pinned. The heavy tick reasons for **every org every 6 hours** regardless of new mail |

**The pattern in all four: a grep for a word I expected, rather than a measurement of the
mechanism.** `due_evaluation` and `next_evaluation` really do return zero — they are not the names
this system uses. It calls them a scheduler thread, a cadence in hours, a cooldown, and
`next_check_at`.

⛔ **Treat any remaining unmeasured claim in the Layer 3 planning documents as unverified.** The
steps' own `findings/` files are measured; the plan files are the hypothesis.

---

## 7. How to verify the branch yourself

```
.venv/bin/pytest -q                    # expect 13,208 passed · 14 failed (pre-existing)
.venv/bin/pytest tests/capture/coverage/ tests/context/test_connected_is_not_read.py -q
.venv/bin/pytest tests/test_layer_topology.py -q
```

⛔ **Never run the suite against production.** It drops and recreates schema. `scripts/_db.py`
requires `GENIOS_TARGET_DATABASE_URL` **plus** `GENIOS_ALLOW_PROD_WRITE=1` for any Supabase host,
and that guard is deliberate.
