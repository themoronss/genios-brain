# Step 8 · Importance ceiling and the relevance allocator — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code
**Status:** 8-U1′ · U2 · U4 · U5 **DONE** · 8-U3 and 8-U6 **DEFERRED, with reasons** ·
the measured re-check is Harsh's

---

## 1. Premise check — 8-U1 was already built, and nothing had ever read it

| Written premise / unit | Verdict |
|---|---|
| 8-U1 · *"record when the money term was structurally unearnable"* | ❌ **ALREADY BUILT** — `ImportanceFlag` has **ten** members doing exactly this |
| *"`baseline_estimated` is set, never read"* | ✅ **confirmed, and worse** — a grep for `.flags` outside `importance.py` returned **zero**. Not one of the ten is read |
| 8-U2 · the achievable ceiling | ✅ confirmed missing |
| 8-U5 · `unjudged_for_budget` | ✅ confirmed missing |
| *"ceiling was 4,640 of 10,000 · 69 unjudged (31%)"* | ⚠️ **stale corpus** — the tenant was re-synced away on 19 Sept |

### 1.1 The one that reframes the step

`ImportanceFlag`'s own docstring makes the plan's argument for it, word for word:

> *"a zero term has several causes and they are not equivalent. A 0 monetary exposure because the
> signal named no amount is correct; a 0 because the amount's currency could not be compared is a
> gap in this module. **Reading them apart from the integer alone is impossible, which is how a
> missing-data bug hides inside a plausible score for a year.**"*

**It hid for a year.** The flags are computed on every score and had no consumer.

> So 8-U1 is not *"record it"* — it is **"make what is already recorded readable"**, and that is
> exactly what the ceiling is. The flags say which terms could not be earned; the ceiling is the
> scale minus their weights. One derivation, no new inputs, **no formula change**.

This is the seventh step running whose premises the code corrected, and the third where the thing
the plan asked for already existed and was simply unwired.

---

## 2. Cost check — clean, and checked first

```
grep vocabulary_fingerprint|_SETS  genios_engine/capture/esqe/*.py   → (no matches)
```

Everything in step 8 is **post-extraction**: importance, qualification and the relevance allocator
all run on values the model already produced. **No prompt change, no re-extraction.** Pinned by
`test_the_extraction_cache_fingerprint_is_untouched`.

**One real cost, and it is the point of the step.** 8-U4 makes LLM-5 run where it previously ran
not at all — but §9 says *"do not raise the budget to make the problem go away, ALLOCATE it"*, and
the budget is unchanged. Same spend, more information.

---

## 3. What was built

### 3.1 · 8-U1′ + 8-U2 — `achievable_ceiling_bp`

```
10000 − the weight of every term the TENANT'S OWN STATE closed off
```

**The distinction the whole unit rests on**, and getting it backwards makes the ceiling a lie:

| Flag | In the table? | Why |
|---|---|---|
| `NO_MONEY` | **no** | *this signal* named no amount. The scale was available; this one did not use it. `ImportanceFlag`: *"term 1 is 0 and that is the right answer."* |
| `NO_MONEY_BASELINE` | **yes** | the *org* has no priced history — no signal in this tenant could earn term 1 however much money it named |
| `BASELINE_ESTIMATED` | **yes** | same term, same cause. Deduplicated **by term**, or a cold-start score would subtract 6000 for one 3000-bp term |
| `NO_ENTITY` | **yes** | term 4 had nothing to rank |
| `CURRENCY_MISMATCH` · `UNKNOWN_CURRENCY` | **no** | those are gaps in **this module** (no FX table, an assumed exponent), not properties of the tenant. **Excusing our own gap by lowering the bar is how a missing-data bug stops being visible** |

**Why it matters:** 4,640 of 10,000 reads as mediocre. 4,640 against an achievable 7,000 is a high
score. Same integer, opposite conclusion, and Layer 4 ranks on it.

### 3.2 · 8-U4 + 8-U5 — the allocator

The over-budget branch used to `return self.stats` and judge **nothing**. On a young tenant almost
every sender is unknown, so the guard always tripped and LLM-5 never ran on a single event.

Now: same budget, same alert, but the head is judged and the tail is **named**. Measured on the
test page — 100 events, 40 ambiguous:

```
before:  llm calls 0  ·  40 × ambiguous_over_budget
after:   llm calls 1  ·  10 × llm5_business  +  30 × unjudged_for_budget
```

**The alert was always right** — a high ambiguous share *is* a graph-coverage problem. Only the
consequence was wrong.

`UNJUDGED_FOR_BUDGET` is its own value, not a reuse of `RULE_OVER_BUDGET`: *the page was over
budget* and *we judged the head and this one was in the tail* are different facts. It ranks **3000**
— the same as every other fail-open path, because the same thing happened: nobody decided. Not
lower (that would make "we ran out of budget" a statement about the message) and not higher (we did
not look at it).

**It never reorders.** E2: importance is computed *after* relevance, so the only proxy available is
the caller's arrival order — and the comment at the call site is where that proxy is **named**, as
E2 requires.

---

## 4. The totality guard caught me mid-build

Adding `UNJUDGED_FOR_BUDGET` without a row in `_RULE_RELEVANCE_BP` raised `KeyError` on the first
real page. **That is the table working exactly as designed** — a new rule cannot be half-added —
and it is the fourth time in this plan that a totality guard has caught an incomplete change before
a test could.

---

## 5. What was NOT built, and why

**8-U3 · a floor relative to the tenant's measured distribution.** Deferred, and the reason is in
the step's own E4: *"a relative floor on a tenant with 3 signals is meaningless."* Computing a
percentile needs the tenant's real distribution, and **the corpus we measured no longer exists**.
Building a relative floor against a vanished baseline is the exact mistake this plan is built to
avoid. It also interacts with step 4's finding — `relationship_change`'s ceiling sits *below* the
absolute floor — and that is now diagnosable with `achievable_ceiling_bp` for the first time.

**8-U6 · a per-tenant distribution report in CI.** The properties it would assert are already
enforced at gate time by `test_importance_gate_probe.py` (10 tests, including
`test_gate_the_distribution_is_wide_enough_for_layer_4_to_rank_on` and
`test_gate_no_single_score_swallows_the_corpus`). A CI report over a *real tenant* needs production
access; a report over a fixture adds ceremony and no information.

---

## 5b. Test result

```
FULL SUITE      12568 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 8:  12549 passed · 14 failed
```

**Zero regressions, +19 tests.** 12 of the 18 in this step's own file were RED first.

`test_importance_gate_probe.py` 10/10 — including `test_gate_the_whole_corpus_replays_byte_
identically`, which is the step's own stated success test: **if the distribution moved, the formula
was changed and the step failed.** It did not move.

### One test asserted the defect, and was rewritten

`test_an_over_budget_page_alerts_instead_of_spending` asserted `llm.calls == 0` — it pinned the
all-or-nothing behaviour as correct, because when it was written that WAS the design. Rewritten to
the new contract with the reasoning in the test, and a second row added proving an unjudged event
is distinguishable from a judged-relevant one.

---

## 6. What this step does NOT fix

* **It does not change any score.** ALG-17's formula, its five weights and the sum-to-10000 check
  are untouched and pinned.
* **It does not move the floor.** §5 — that is 8-U3, and it needs a live distribution.
* **It does not lift `relationship_change` over the floor.** Step 4 established that is a floor
  question; the ceiling now makes it *measurable*, which is the prerequisite, not the fix.
* **It does not re-measure the 31%.** That needs the live corpus — Harsh.
