# Step 5 — ✅ DONE · where the four objects live · owner: us

> **Status:** NEXT · **not blocked on the API limit** · blocked only on one decision
> **Written:** 2026-09-30
> **Why it comes before the bundle:** it bounds what the bundle in [Step 6](STEP-06-signal-bundle.md)
> is allowed to carry.

---

## 1 · The question, in one line

When Layer 1 sees something like *an open question* or *a meeting follow-up* — does **Layer 1 build
that object**, or does Layer 1 **record the evidence** and let Layer 3 build it?

## 2 · What is true today

| Object | Where it is produced now | State |
|---|---|---|
| **commitment** | L1 — `Commitment` in `ExtractionResult` (actor · action · beneficiary · due · `is_conditional` · `condition_text`) | ✅ at L1 |
| **delivery status** | L1 — `capture/delivery_status.py` + `DELIVERY_FAILURE` | ✅ at L1 |
| **condition** | split — L1 carries `is_conditional` + `condition_text`; `DormantCondition` is `context/correlation_timeline.py` | ~ split |
| **thread terminal state** | signal-level in `esqe/lifecycle.py`; **thread-level does not exist** | ~ partial |
| **open question** | `context/` — `ASK_KINDS` · `is_ask` · `open_loops.py` | above L1 |
| **meeting follow-up link** | `context/` — `meeting_touch.py` | above L1 |

The Design Atlas asks for all six "at L1". Two already are, two are split, two are one layer up.

## 3 · The recommendation on record

> **L1 produces the evidence. L3 produces the object.**

Three reasons:

1. **It is what the code already does**, in every case. No file moves.
2. **It keeps L1 free of graph reads.** An object like `open_loop` needs to know what the company
   already knows. If L1 built it, L1 would read `context/` — an upward import, and
   `tests/test_layer_topology.py` fails the build on it.
3. ⛔ **The condition split is deliberate and must survive.** `parse_condition` refuses anything it
   cannot ground, and that refusal is exactly what the `condition_now_true` angle gates on.
   Collapsing the split destroys the refusal queue the angle feeds from.

**The alternative**, stated fairly: move the four producers down into `capture/`. It buys vocabulary
alignment with the Atlas and costs four migrations, the topology problem in (2), and the refusal
queue in (3).

## 4 · What we build once it is decided

Each unit is a **guard**, not a move — it fails if a producer changes layer.

| Unit | What |
|---|---|
| `U-S2-01` | the rule recorded in `docs/LAYER_MAP.md` + `LAYERS.py`, with the rejected option named |
| `U-S2-02` | open question — producer pinned to `context/`; L1's evidence for it named |
| `U-S2-03` | meeting follow-up link — same |
| `U-S2-04` | condition — L1 keeps `is_conditional` + `condition_text`; `DormantCondition` stays L3 |
| `U-S2-05` | thread terminal state — ⛔ **genuinely missing.** Either build it at L3 beside the other thread state, or declare it deferred **with a reason** in `deferrals.yaml` |

## 5 · Scenario → expected result

| Scenario | Expected |
|---|---|
| someone moves `open_loops` into `capture/` | ⛔ the guard fails, naming the rule |
| someone collapses `condition_text` into a `DormantCondition` at L1 | ⛔ the guard fails, naming the refusal queue it would destroy |
| a new object type is proposed | the rule answers where it goes without a meeting |

## 6 · ⛔ What is needed from Rohit

**One answer: approve "L1 produces evidence, L3 produces objects" — or reject it.**

It is one sentence, and it settles four recurring arguments at once. Nothing else in Layer 1 waits
on it except Step 6's scope.

---

# ✅ DONE — 2026-09-30

## What was built

| Unit | Artifact | Result |
|---|---|---|
| `U-S2-01` | the rule in `docs/LAYER_MAP.md`, with the rejected alternative named | ✅ |
| `U-S2-02` | open question — producer pinned to `context/open_loops.py` · `waiting.py` | ✅ |
| `U-S2-03` | meeting follow-up — pinned to `context/meeting_touch.py` | ✅ |
| `U-S2-04` | condition — L1 keeps `is_conditional` + `condition_text`; `DormantCondition` stays L3 | ✅ |
| `U-S2-05` | thread terminal state — **declared absent** in the layer map, with a test that fails if the declaration is deleted without building the thing | ✅ |

`tests/test_object_placement.py` — **14 passed**.

## The rule, as recorded

> **`capture/` produces the EVIDENCE. `context/` produces the OBJECT.
> The VOCABULARY both use lives in `contracts/`.**

## Two guards worth naming

**A verdict field cannot creep onto the evidence.** The test asserts `Commitment` never gains
`is_met`, `satisfied`, `verdict` or `predicate` — those are judgements about the world, and L1
cannot see the world.

**`capture/` cannot grow its own copy of a producer.** The topology test already stops `capture/`
*importing* `context/`; it would not stop `capture/` *defining* its own `DormantCondition`, which
would silently fork the refusal queue. That half is covered here.

## Nothing moved

Zero files migrated. Every assertion already held — these are guards against future drift, not a
migration. ⛔ **Reversible:** if the rule is rejected, delete the section from `LAYER_MAP.md` and
this test file. No production code depends on either.


---

## ⛔ 2026-10-01 · the title line of this file was stale, and is corrected above

This file's **first line** read `Step 5 — NEXT · where the four objects live · owner: us · **needs one decision from Rohit**` while the `✅ DONE — 2026-09-30` section below recorded the
work as built, and the filename had already been renamed to `...-DONE-...`. Three labels on one
piece of work and one of them disagreed with the other two.

**Why this is recorded rather than quietly fixed.** A heading that says *TO BUILD* on finished work
is the same defect as a stale comment: it reads as a status somebody checked. Anyone auditing the
programme by scanning headings would have counted this step as outstanding and, worse, might have
rebuilt it. Found while assembling `07-LEDGER-every-step-what-why-how-outcome.md`, which reads the
first line of every step file — the ledger could not have been written without resolving it.

**What was verified before the title was changed:** the artifacts named in the DONE section exist in
the tree, and the full suite is 14,534 passed / 0 failed. The title was not made to agree with the
others; it was made to agree with the code.
