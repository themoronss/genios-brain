# L3-0A · The window — see the five relationships that are invisible

**Needs Harsh:** ⛔ **an operator action** (set the window on the pilot connection) · **Model:** none
· **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · ⛔ PENDING HARSH (item 21, the window) · the step shrank three times · [findings](findings/step-0A-the-window.md)
>
> All three things this step planned to build **already exist**: the window setting is wired with
> an admin endpoint and five test files; `backfill_drain` is the background progressive sync,
> tuned 1 → 8 pages against a live run; `backfill_layer2` is the oldest-first L2 replay.
>
> ⛔ **What is missing is the chain between them** — and the order is load-bearing, because capture
> drains **newest-first** and correlation must replay **oldest-first** or it *"shatters one history
> into dozens of situations."*

---

## 1. Why this step is first

Tested against `DEFAULT_BACKFILL_DAYS = 60`, on the benchmark's own mailbox:

```
⛔ INVISIBLE   Keshav 77d · Aditya 79d · Radhesh 69d · John 63d · Vatsa 61d
✅ visible     Manik 46d · Pankaj 16d · Onur 7d
```

**5 of 8 waiting relationships, and 3 of 4 broken-promise source messages, sit outside the window.**
Every later step in Layer 3 would operate on 3 of 8 facts.

## 2. The units

| | |
|---|---|
| **0A-U1** | chain `backfill_layer2` after `backfill_drain`, same background task |
| **0A-U2** | run it on `TRUNCATED` as well as `done` |
| **0A-U3** | ⛔ the chain can never abort the drain |
| **0A-U4** | a test driving the real endpoint, asserting both halves ran in order |
| **0A-U5** | the operator runbook → HARSH-ORDER |

## 3. Done criteria

- [x] the chain exists and runs in one background task
- [x] it runs on `TRUNCATED` as well as `done`
- [x] an L2 replay failure is logged and cannot fail the drain
- [x] a test proves both halves ran, in order — `drain → run_l2 → replay → run_l2`
- [x] technique 3: **three** mutations, all red, restore green
- [x] runbook: HARSH-ORDER **item 21**
- [x] full suite: **13,132 passed · 14 pre-existing · 0 regressions · +10 tests**

## 4. The decision this step needs

| window | buys |
|---|---|
| 180 days | all 8 waiting rows · all 4 broken promises · **P3** |
| **365 days** ✅ | **＋ P4** (12-month calendar × email) |

**Cost is one-time and bounded** — the extraction cache means a document is extracted once, ever.
