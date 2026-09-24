# Step 7 — PENDING · owner: Harsh

> **Status:** code COMPLETE and green · **NO migration · NO new model call · NO re-extraction**
> **What it does:** four signal types never fired and nothing could say why; intent was unreadable-
> ness you could not measure.
> **Written:** 2026-09-24 · **Evidence:** [`findings/step-07-intent-predicates.md`](findings/step-07-intent-predicates.md)

---

## 1. TL;DR — what you have to do

| # | Action | Blocking? | Time |
|---|---|---|---|
| **1** | **DECIDE: split intent into its own model call, or keep the derived version I built?** | no — I built the free version | 10 min |
| **2** | Nothing else. **No migration, no env var, no table, no new model call.** | — | — |

**This is the cheapest step in the plan so far.** It adds no cost of any kind and it did not touch
`vocabulary_fingerprint`, so nothing re-extracts.

> **Why it is so small:** the premise check found that **one unit was already done**, **one unit
> had nothing to retire**, and **one done criterion asked for something the codebase already argues
> against in writing.** Details in §4.

---

## 2. DECISION — the intent split, priced

The step planned to pull intent out of LLM-2 into its own model call, so that *"intent was wrong"*
could be told from *"the whole extraction was wrong"*.

### 2.1 What it would cost

```python
# capture/semantic/vocabulary.py
_SETS = {"intent": INTENT, ...}      # ← feeds vocabulary_fingerprint(), which is a cache key part
```

| | |
|---|---|
| **One-off** | taking intent out of LLM-2's prompt moves the fingerprint → **the whole corpus re-extracts.** A THIRD full bill, after step 4's (still unpriced) |
| **Ongoing** | a second model call on **every message, forever.** Step 6's proposer at least skips anything under 80 characters; an intent call cannot |

### 2.2 What I built instead, for nothing

`MessageIntent.confidence_bp` — **derived** from the seven observed axes the model already answers.
No prompt change, no new call, no re-extraction.

It is also *more* correct: doctrine 1 says a model may **describe, never score**, so a
self-reported certainty must never become a stored confidence. Deriving it from what was actually
answered is the only version of this that obeys the rule.

Plus two things the split would not have given on its own:

- **`intent_disagreements`** — when the gate says AUTOMATED and the extractor says WORKING,
  `merged_with` silently keeps WORKING and the disagreement vanished. It is now recorded. That is
  the difference between *"the prompt is wrong"* and *"this message is genuinely ambiguous"*.
- **`intent_unknown_rate_bp` per sweep** — a source returning `unknown` for 80% of its mail is a
  prompt defect that does not raise, does not log and does not fail a test. It just produces
  slightly emptier readings until somebody notices, and "slightly emptier" looks like a quiet week.

### 2.3 Your options

| Option | What it means |
|---|---|
| **A — keep the derived version** *(built, recommended)* | attribution for zero cost. Revisit only if the rate report shows intent is the actual problem |
| **B — split it anyway** | a third re-extraction plus a permanent per-message call, for an attribution we now already have |

**Reply "A" or "B".** If A, this step needs nothing from you at all.

---

## 3. What changed

| Unit | What |
|---|---|
| **7-U1′** | `MessageIntent.confidence_bp` — derived, integer basis points, never asked for |
| **7-U2** | `disagreements_with` + `EsqeOutcome.intent_disagreements`, computed **before** the fold destroys the evidence |
| **7-U3** | `capture/intent_rate.py` + three counters on `SyncSummary`, incremented on the capture loop |
| **7-U4′** | every one of the 16 taxonomy members has a test that fires it — so *"it never fired"* is now a corpus fact rather than an open question |
| **7-U6** | five stale prose sites fixed by **removing the counts**, not updating them |
| ~~7-U5~~ | **nothing to retire** — all 16 members have fixtures |
| ~~7-U1~~ | the split — §2, declined |

---

## 4. Three things the premise check found — worth reading before anyone quotes the plan

**a · The plan said four types "have never fired" and nothing says whether the predicate can.**
Something does: `ESCALATION` has 3 detector tests, `INFORMATION_CONFLICT` 3, `ANOMALY` 2,
`AVAILABILITY_CHANGE` 1. **All four can fire.** Their production silence is a corpus question.

**b · `DELIVERY_FAILURE` is the real version of that bug, and you can fix it.** It has 19 tests, it
fires in every one, and it has produced **zero** production signals — because **migration 0176 is
not applied**, so the INSERT is refused by a CHECK constraint. The detector reports success and the
table refuses the row. That is item 2 of [`HARSH-ORDER.md`](../../HARSH-ORDER.md).

**c · One done criterion asked for something the codebase argues against.** *"intent has its own
contract, confidence and **evidence**"* — `contracts/intent.py` refuses the third in writing:

> *"'the tone is warm' or 'a person composed this' have no quotable span to point at. A field for
> them would invite a model to manufacture a citation for something that is not a quotation, which
> is worse than having none."*

That is the fabricated-receipt failure this architecture exists to prevent, and §9 of the same step
says the design is correct and must not be rebuilt. **The criterion was amended, not met**, and a
regression guard now asserts intent has no evidence field.

---

## 5. How to cross-check me

```bash
.venv/bin/python -m pytest tests -q -p no:randomly          # ~7 min
```
**Expect:** `12549 passed · 14 failed`. All 14 pre-existing. Before step 7: `12530 passed · 14 failed` — **zero regressions, +19 tests.**

```bash
.venv/bin/python -m pytest tests/capture/test_a_silent_predicate_explains_itself.py -q
```
**Expect:** `18 passed`. 10 were RED first.

### The cost guard — the one command that matters most

```bash
.venv/bin/python -c "from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint as f; print(f())"
```

**Must still print `a3d5496aa0d3`.** Unchanged since step 4. If it moved during an INTENT step, the
split happened by accident and the corpus is about to re-extract.

### See the new signals yourself

```bash
.venv/bin/python -c "
from genios_engine.contracts.intent import IntentCategory, MessageIntent, Tone
blank, read = MessageIntent(), MessageIntent(category=IntentCategory.WORKING, tone=Tone.WARM)
print('unread :', blank.confidence_bp)      # 0
print('partial:', read.confidence_bp)       # > 0
gate = MessageIntent(category=IntentCategory.AUTOMATED)
print('disagreement:', gate.disagreements_with(MessageIntent(category=IntentCategory.WORKING)))
"
```

---

## 6. Known failures — unchanged, 14, all pre-existing

Same list as steps 4–6. The `comm -13` procedure to verify that without trusting me is in
[step 6 §7](STEP-06-PENDING-HARSH.md).

---

## 7. What this step does NOT do

* **It does not make the four silent types fire in production.** They can fire; whether they should
  have is a corpus question, and `DELIVERY_FAILURE`'s case is a migration you have not applied.
* **It does not split the model call.** §2.
* **It does not give intent an evidence span.** §4c — deliberately.
* **It does not surface the rate anywhere a human reads.** The counters are on the sweep and in the
  ledger's shape; a weekly report over them is a reporting task, not an L1 one.

---

## 8. Send back to me

| # | Item | Your answer |
|---|---|---|
| 1 | §2.3 — intent split: **A** (keep derived) or **B** (split)? | |
| 2 | §5 — did the fingerprint still print `a3d5496aa0d3`? | |
| 3 | §5 — full suite passed / failed counts | |
