# Layer 1 — start here

`capture/` — 154 files, 46,377 lines. It reads Gmail, Calendar, Slack, Drive and Screen and turns
each message into a **qualified signal**: typed, dated, scored, deduplicated, and honest about how
much of the mailbox was actually searched.

It decides what a message **says**. Never what it means for the company, never what to do.

---

## The steps

| # | Step | Status | Owner | Blocks the build? |
|---|---|---|---|---|
| 1 | [Relevance judgment](STEP-01-DONE-relevance-judgment.md) | ✅ **DONE** — no defect; probe built | us | — |
| 2 | [`temperature` on refusing models](STEP-02-DONE-temperature.md) | ✅ **DONE** — 600 calls that never worked | us | — |
| 3 | [Provider-refusal alert](STEP-03-DONE-provider-alert.md) | ✅ **DONE** — 5-day outage was invisible, twice | us | — |
| 4 | [API spend limit](STEP-04-PENDING-api-limit.md) | ⏳ **PENDING** | Rohit | ❌ **no** — blocks measurement only |
| 5 | [Where the four objects live](STEP-05-DONE-object-placement.md) | ✅ **DONE** — rule recorded + 4 guards | us | — |
| 6 | [The signal bundle](STEP-06-DONE-signal-bundle.md) | ✅ **DONE** — 5 units | us | — |
| 7 | [The evidence-need door](STEP-07-DONE-evidence-need.md) | ✅ **DONE** — 4 units | us | — |
| 8 | [OCR has never run](STEP-08-PENDING-HARSH-ocr.md) | ⏳ **PENDING** | Harsh | ❌ no |
| 9 | [The 60-day window](STEP-09-PENDING-HARSH-backfill.md) | ⏳ **PENDING** | Harsh | ❌ no |
| 10 | [The needs queue gets worked](STEP-10-DONE-needs-queue-worked.md) | ✅ **DONE** — 21 tests | us | — |

> **Layer 1's buildable work is complete.** Steps 1–3, 5–7 and 10 are done; 4, 8 and 9 are
> operational and belong to Rohit and Harsh.

⛔ **Step 10 was added on 2026-09-30**, after Layer 3 landed. L1 and L3 together had built a pipeline
that asks questions and never listens: `context/` filed needs, `execute()` worked one need, and
**nothing ran the loop between them.** Step 10 is that loop — and the thing it mostly does is
**refuse to run**, because a closure is permanent and closing the queue as *"not connected"* would
destroy every question Layer 2 has asked.

⛔ **Nothing pending blocks the build.** Steps 5, 6 and 7 proceed with the model switched off.
What the pending items block is **measurement** — every production number taken since
25 September was taken with no model answering.

## Every step file answers the same six questions

1. What was expected?
2. What is actually true?
3. What did we change — or why did we change nothing?
4. What did we deliberately **not** do, and why?
5. Scenario → expected result
6. What is still pending, and whose it is

## The other documents

| File | What | Who reads it |
|---|---|---|
| [`01-CROSSCHECK.md`](01-CROSSCHECK.md) | the audit — what is built vs what the Design Atlas claims | CTO |
| [`02-PLAN.md`](02-PLAN.md) | the decomposition to unit level, with verify commands | coding agent |
| [`10-LAYER-REFERENCE.md`](10-LAYER-REFERENCE.md) | what L1 owns, subsystem by subsystem, and what is measured today | anyone new to `capture/` |
| [`findings/`](findings/) | the raw measurements each step rests on | anyone checking a number |

---

## What we found, in three lines

**Layer 1 is the most complete layer in the system.** Of the nine things the Design Atlas lists as
missing or planned here, **five are already built**, two are built one layer up, and two are
genuinely missing — the bundle (Step 6) and the evidence-need door (Step 7).

**Two real defects were found, and both are fixed** — neither was on the Atlas's list.

⛔ **Four confident explanations were disproved along the way**, and every one of them would have
produced a code change to a file that was already correct. The rule that came out of it:

> **A count without its dimension is not a measurement.** `no_model_wired = 632` and
> `no_model_wired = 632, all of them screen sessions` are the same number and opposite findings.
