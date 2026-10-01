# Step 9 — PENDING · the 60-day window · owner: Harsh (CTO)

> **Status:** PENDING · **not blocked on any code in this repo** · **owner: Harsh**
> **Prerequisite:** migration `0184` — applied.

---

## 1 · The finding

The pilot connection fetches **60 days**. Messages older than that exist as `"message 1 of 1"`
extractions — a twelve-message thread reads to the model as a single isolated note.

## 2 · Why it matters more than it sounds

Two of the five benchmark prompts ask beyond the window:

| Prompt | Horizon | Status today |
|---|---|---|
| P3 | 6 months | ⛔ **structurally unanswerable** — the mail was never fetched |
| P4 | 12 months | ⛔ same |

These are not *unproven*. They are **impossible**, and no model or prompt change moves them.

## 3 · What to do

Widen the pilot connection's backfill window **60 → 365**.

⛔ `0184` must already be applied — it is what stops a widened window backdating a year of edges
into the as-of history and rewriting what we knew and when. It is applied.

## 4 · Scenario → expected result

| Scenario | Expected |
|---|---|
| the window widens | older threads re-extract with real `turn_index`, not `1 of 1` |
| a P3 question is asked afterwards | it is answerable, and answered against a stated coverage |
| the as-of history is replayed | ⛔ unchanged — `0184` holds what we knew on each date |

## 5 · The relationship to Step 7

Widening the window is the **blunt** fix: fetch everything, hope it helps. [Step 7](STEP-07-evidence-need.md)
is the **precise** one: ask for one thread, for one decision, with a cost limit.

**Both are wanted.** The window makes history reachable; the evidence-need makes it askable.
