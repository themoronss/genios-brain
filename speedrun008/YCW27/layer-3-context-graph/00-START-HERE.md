# Layer 3 — start here

`context/` — 118 files, 49,713 lines. The largest package. It remembers what the company knows, and
judges which of it is real enough to act on.

In code it is called **Situation Intelligence**, deliberately: *"this layer's output is a SITUATION
— assembled, judged by eight admission laws, and exposed only if admitted. Describing it as a graph
builder is how a card came to be wired to a signal while the situation layer was bypassed."*

---

## The steps — all resolved

| # | Step | Status | Owner |
|---|---|---|---|
| 1 | [The bounded query API](STEP-01-DONE-bounded-read.md) | ✅ **done** · 22 tests | us |
| 2 | [Compare-and-set on write](STEP-02-WITHDRAWN-compare-and-set.md) | ⛔ **withdrawn** · already built | — |
| 3 | [A hold that asks](STEP-03-DONE-hold-raises-a-need.md) | ✅ **done** · 27 tests | us |
| 4 | [A met need clears its hold](STEP-04-DONE-need-clears-hold.md) | ✅ **done** · 22 tests | us |
| 5 | [Residue reaches the sweep](STEP-05-DONE-residue-in-the-sweep.md) | ✅ **done** · 20 tests · wired | us |

**91 new tests. `tests/context` whole: 2,679 passed, 270 skipped, 0 failed.**

## Read in this order

| File | What it is |
|---|---|
| [`01-CROSSCHECK.md`](01-CROSSCHECK.md) | what was found before any code was written — **and one retraction** |
| [`02-PLAN.md`](02-PLAN.md) | the plan: sections → functions → units, with *why* for every decision |
| [`03-FINDINGS.md`](03-FINDINGS.md) | every finding in one place, with the numbers and their sources |
| the STEP files | one per step: what was expected, what happened, scenario → result |

⛔ **`02-PLAN.md` was written LATE — after the build, not before it.** Layer 1 was done properly
(cross-check → plan → steps → build); Layer 3 skipped the plan. That file therefore marks every
decision **[planned]**, **[learned]** or **[open]** so the places the build corrected the plan are
visible rather than hidden. Three of eight functions carry a `[learned]` correction and two of those
changed the design.

---

## The findings, as they stand after the build

**1 · There was no bounded read.** ✅ Built. `read_graph` and `live_graph` return a whole tenant's
graph; a caller wanting three nodes got everything and filtered in Python. `context/bounded_read.py`
is the third read and the first one that can say no — capped by default, breadth-first, and it
**reports truncation** rather than stopping quietly.

**2 · ⛔ The compare-and-set was NOT missing. I was wrong.** `reason/runner.py:570`
`_graph_version_guard` reads the row `for share`, compares against the expected revision, and the
caller at line 1276 refuses to publish on drift. Twelve more sites in `deliver/` and `api/` take the
same lock. Six tests, all passing. The finding came from grepping `context/` only — and the
read-modify-write **spans packages by design**, so the guard could not have been where I looked.

> **A guard lives with the reader, not with the writer. Absence in the writer's package is not
> absence.**

Second wrong finding in this programme from counting along the wrong dimension. The first was Layer
1's `no_model_wired`.

**3 · Held situations were questions nobody asked, and only three of seven reasons are evidence
questions.** ✅ Built — and the codebase corrected the count: `qes_required` and
`verified_evidence_required` are **one** question, not two, measured at 480 of 504 holds carrying
both. So three reasons produce two questions. `conflict_open` and `cross_domain_contradiction` are
adjudication; `identity_review_required` needs a human; `pattern_evidence_required` is **our** missing
rule, not the tenant's missing document.

> ⛔ **The exclusion is the design.** Same rule Layer 1's residue wire is built on.

---

## What this layer can now do that it could not

| | Before | After |
|---|---|---|
| ask the graph a bounded question | ❌ whole tenant only | ✅ seeds, hops, node cap, edge types |
| know a read was cut short | ❌ silently partial | ✅ `truncated_by` names the cap |
| turn a hold into a question | ❌ the reason went to a ledger and stopped | ✅ `hold_needs.py` |
| act on an answered question | ❌ nothing read the outcome | ✅ `hold_resolution.py`, four dispositions |
| file a question at all | ❌ nothing persisted a need | ✅ `evidence_need_store.py`, called by the sweep |
| distinguish "nothing more" from "we stopped looking" | ❌ | ✅ |
| distinguish "gave up" from "still waiting" | ❌ | ✅ |

---

## ⛔ The one thing to carry forward

The loop is **half-closed.** The sweep now files questions and **nothing works them yet**:

```
residue  ──▶ need  ──▶ [ evidence_needs table ]  ──▶  ???
  ✅          ✅              ✅ written              ❌ no executor pass
```

All three pieces of the executor path exist and are tested (`read_open_needs`,
`capture.acquire.evidence_need.execute`, `close_need`). What is missing is the `fetchers` mapping to
live connectors — the Layer 1 integration gap already recorded as PENDING and owned by Harsh, not a
new one. Until then the queue is write-only and every need stays `open`.

Nothing regresses: situations hold today anyway. But do not read `evidence_needs_filed > 0` as
evidence that anything is being fetched.
