# Step 4 — PENDING · the API spend limit · owner: Rohit (account) / Harsh (ops)

> **Status:** PENDING · **not blocked on any code in this repo** · no build waits on it
> **Why it is not ours:** it is a setting on the Anthropic account. No change in `genios-brain`
> can move it.
> **Written:** 2026-09-30

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
