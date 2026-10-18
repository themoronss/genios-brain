# Step 4 — PENDING · the API spend limit · owner: Rohit (account) / Harsh (ops)

> **Status:** PENDING · ⛔ **and it is now DECISION #5 — the single thing blocking every card**
> **Why it is not ours:** it is a setting on the Anthropic account. No change in `genios-brain`
> can move it.
> **Written:** 2026-09-30 · ⛔ **corrected 2026-10-01**

---

## ⛔ 0 · CORRECTION, 2026-10-01 — "no build waits on it" was wrong

This step shipped saying *"not blocked on any code in this repo · **no build waits on it**"*. The
L4 re-crosscheck measured otherwise. **Everything downstream of L2 waits on it.**

    GENIOS_L4_LLM_DECISION_MAKER = true     no org allowlist -> ON for every org
    reason/llm_decision_maker.py:20         "Failure is DEFER, never the formula."   ← BY DESIGN

    the 8,044 candidates on the 2,681 runs since 2026-09-29:
      formula_utility  5,469   ✅ the deterministic scorer is HEALTHY
      llm_utility          0   ⛔ zero on every single one
      final_utility_bp     0   ⛔ zero on every single one
      outcome_kind     defer 2,669 · blocked 12 · decision ZERO  ->  0 signals emitted

    L1 / L2 / L3 wrote rows 2026-09-30.   L4 stopped 09-25.   L5 stopped 09-25.
    0 cards and 0 commitments since 2026-09-25. The 150 existing cards aged out.

⛔ **So the spend limit did not merely switch off LLM features — it stopped the card pipeline**, in
a way that reads from outside as a delivery defect while six layers report healthy. The module's
refusal to fall back is sound and stated; **what nobody declared is that the measurement mode is
the production mode.**

> ⛔ **A deliberate refusal to degrade is still a stop.**

**Three options, and they are now DECISION #5 in `../02-DECISIONS.md`:**

| | Option | Effect |
|---|---|---|
| **A** | raise the limit | the switch stays on; the product resumes exactly as designed |
| **B** | `GENIOS_L4_LLM_DECISION_MAKER = false` | the formula decides — `formula_utility` is already **5,469** on live candidates, so cards resume immediately |
| **C** | a third path: `llm_decision_unavailable` falls back, `llm_declined` still defers | ⛔ one unit, **and a declared doctrine changes** |

**Recommendation: B now, C as a unit, A when the budget allows.** ⛔ And **receipt #31**
*"the current reasoning era selects, not only defers"* is **RED at 3,582** until this is answered —
which is correct, and is the first time this state has been visible from inside the product.

**Full trace:** `../layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md`.

---

## 1 · The finding, in one line

Since **2026-09-25 11:09 UTC**, every model call in the product has been refused with:

```
Error code: 400 — invalid_request_error
"You have reached your specified API usage limits."
```

## 2 · What it is — and what it is not

| | |
|---|---|
| **Is** | the spend ceiling configured on the Anthropic account/workspace, outside this system |
| **Is not** | GeniOS's own cost governor — that is working correctly and was never the blocker |
| **Is not** | a rate limit, a deprecated model, or a code fault |

## 3 · What to do

1. **console.anthropic.com**
2. **Settings → Billing** (or **Limits / Usage limits**)
3. Raise or remove the **monthly spend limit**
4. While there, confirm the **credit balance** is not empty — the error names a *configured limit*
   rather than no funds, but one glance settles it

No deploy. No code change.

## 4 · ⛔ Does this block the build?

**No.** Every other step in Layer 1 proceeds without it. What it blocks is **measurement**:

> Every number taken from production since 25 September was taken with the model switched off —
> including Harsh's 29 Sep shadow-pass tallies (39 compiled / 39 reasoned of 66).

So: **build now, re-measure after.** Nothing in Steps 5–7 needs the model to be answering.

## 5 · Scenario → expected result, once it is raised

| Scenario | Expected |
|---|---|
| one clean sweep runs | `l1_relevance` shows `llm5_business` / `llm5_not_business`, not `llm5_unavailable` |
| `scripts/l1_relevance_state.py --assert-judged` | **PASS** for `gmail` |
| `l4_bundle` | produces its first bundle ever — **only because Step 2 also landed** |
| it happens again | ⛔ **Step 3's alert fires within minutes**, not after five days |

## 6 · Related, and also not ours

Two more operational items sit behind the same wall — [Step 8](STEP-08-PENDING-HARSH-ocr.md) (OCR
has never run) and [Step 9](STEP-09-PENDING-HARSH-backfill.md) (the 60-day window).
