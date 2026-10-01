# The baseline — what is measurably true, 30 September 2026

> Everything here is from a run or a file, never from a plan. **If any other document in this
> folder disagrees with this one, this one wins.** Where a figure came from somebody else's run it
> says so and names the run.

**Tree:** `speedrun008` @ `c7cdf4c1` · harsh/mvp merged in · local and origin level.

---

## 1 · Size

| Package | Product layer | Files | Lines |
|---|---|---|---|
| `capture/` | L1 | 154 | 46,377 |
| `context/` | L3 (+ L2 assembly) | 118 | 49,713 |
| `reason/` | L2 · Plane R (+ L4) | 118 | 40,036 |
| `deliver/` | L5 | 36 | 8,674 |
| `packs/` | L2 · Plane D | 34 | 7,957 |
| `executive/` | L4 | 26 | 5,990 |
| `feedback/` | L6 | 12 | 2,737 |
| | | **498** | **≈ 161,000** |

Plus 161 migrations and 657 test files.

## 2 · Test state

| Lane | Result | Source |
|---|---|---|
| Hermetic suite | **13,332 passed · 0 failed** | Harsh, 29 Sep, `b88c6a1f` |
| `pg` lane (real Postgres) | **611 passed · 7 failed** — run for the first time | Harsh, 29 Sep |

The 7 `pg` failures are all tests meeting a real database for the first time, so none is a
regression. One of them is **directly the confidence-vector decision**: `situation_publisher`
asserts five confidence axes including `coverage`, which `situations.py:366` documents as
legitimately unknown for a domain that registers no field expectations. See `02-DECISIONS.md` §1.

---

## 3 · ⛔ The finding that is upstream of the others

**The heartbeat does not appear to run in production.**

| Evidence | Measured |
|---|---|
| `purge_superseded_expertise_packages` keeps 3 per (org, situation) | 27 situations held **19 copies each** before the truncate |
| attachment refetch drain runs on the beat | `document_jobs` holds **341** rows at `fetch_failed` |
| OCR | **830** rows `ocr_unavailable`; 122 document rows, **not one** ever carried an engine |

Both drains run from the heartbeat and neither has run. `scheduler_enabled` defaults `True` and
nothing in `.env` disables it, so **the cause is in the deploy, not the config**. The expertise
retention was wired all along (`routes.py:992`) and simply never fired — which explains the
database read-only incident better than the table does.

Nothing above L1 can be trusted as "measured in production" until this is resolved.

---

## 4 · The pilot tenant, as it actually is

`org_e97e86f858ad48b2bbf64b8a` — **1,490 events from 21 July onward**. The corpus was **not**
destroyed by the 19 September re-sync; the earlier "three metrics unmeasurable" note is withdrawn.

```
active situations        66
  admin      53
  support     8
  fundraising 4
  sales       1
```

⛔ **Two numbers that have been quoted wrongly and must not be repeated.**

- The pilot carries **66** active situations, not 138. The 138 came from an older board.
- `fundraising → sales` is **4 of 66**, not *"the single largest thing in Layer 2"*. The largest
  thing in Layer 2 is **467 held against 223 admitted**, on `verified_evidence_required` (398),
  `qes_required` (398) and `source_coverage_insufficient` (69).

### The shadow pass

```
situations            66
  admission_hold      19      ← evidence/coverage, not routing
  no_route             5
  incomplete           3
  compiled            39
  reasoned            39
  reasoner_consulted   2
```

`evaluate_parity` ⇒ **FAIL**. ⛔ **The threshold is unreachable and not because the pass is weak:**
`PARITY_GATE`'s own justification reads *"the pilot carries 159 active situations"* and sets 100.
The pilot carries 66. 39/66 = **59%** against the gate's stated intent of a majority (100/159 =
63%). **This gate needs re-basing to a ratio — and weakening it to land a change is exactly the
failure this repository is written against.** Owner: Rohit.

---

## 5 · What the Atlas calls a gap that is already built

Spot-checked against the code. **This is why `M8` exists.**

| Atlas badge | Measured reality | File that settles it |
|---|---|---|
| L1 *"no coverage receipts"* — `gap` | **Built, and better than specified.** Per source, never blended; frozen at the observation moment; unknown stays `None`, never 100% | `capture/coverage/signal_coverage.py` |
| — | the coverage READ, *"read 37 of about 465"* | `context/quality/window.py` |
| `ReasoningRequest` — `target` | exists | `contracts/reasoning.py:679` |
| `ContextSnapshot` — `built` | correct | `contracts/reasoning.py:365` |
| *"targeted second pass"* — `target` | `CritiqueVerdict` exists | `contracts/reasoning.py:1760` |
| `DeliveryResult` — `target` name | `DeliveryObject` / `DeliveryDecision` exist | `contracts/delivery.py` |
| `DecisionObject` — `target` | ⛔ **settled already** | `tests/contracts/test_the_decision_object_is_one_object.py` |
| absence signals — `gap` | `situation_absences`, `absent_fields`, `unknowable_fields` | `context/quality/missing.py` |

⛔ The DecisionObject row is the important one. That test's own first paragraph:

> *"The plan that led here assumed that meant five competing definitions to choose between.
> **It did not: `ReasoningDecision` is the object**, fully typed and semantically hashed, and the
> five rows are views of it."*

**This mistake has already been made once and corrected by reading the code.** The Atlas reopens
it. M8 produces a re-runnable check so it cannot be made a third time.

## 6 · What is genuinely missing — verified zero hits

| Missing | Consequence today |
|---|---|
| `EvidenceNeed` contract + executor | a HOLD can only wait; L2 cannot ask L1 for the one fact that would settle it |
| `QualifiedEnterpriseSignalBundle` | related signals arrive as separate situations |
| `SituationSeed` | the situation is framed before any expertise is applied |
| the five funnel counters | the ~20% recall figure is an estimate, not a measurement |
| the five output lanes | low confidence still deletes a finding instead of routing it |

---

## 7 · Other measured facts worth carrying

| | |
|---|---|
| Domain coverage | **125 of 162 really tagged (77%)**, 0 fallback-only, 37 with no domain |
| Relevance | `ambiguous_over_budget` = **0**; top bucket is `no_model_wired` at **251** — relevance has no model wired in prod |
| Joinability | **83 of 85 (97.6%)** — P4 is falsifiable |
| Threads | 705 messages · **358 (51%)** in multi-message threads · 132 threads · longest 9 |
| Re-extraction bill | 416 rows · 2.34 M in / 1.06 M out on Haiku 4.5 ≈ **$7.67** — accepted |
| Step 10 drops | 148; `relationship_change` **55 (37%)** dominates ⇒ that is 8-U3, not a review queue. **Cancel step 10** |
| Admin corpus | 59 capabilities admitted · 34 situations · 7 draft, of which **4 are `pending_l2_types` and must stay draft** |
| Migrations | `0176`…`0185` all applied and column-verified |
| Backfill window | still 60 days on the pilot; 60 → 365 is Harsh's, after `0184` |

⛔ **Four handoff queries name columns that do not exist** and are fixed in
`scripts/speedrun008_measurements.py`: `source_events.relevance_rule` (the rule is on the S4 trace
as `reason_code`), `raw -> 'attendees'` (no `raw` column; attendees are in `recipients`),
`raw -> 'headers'` (the Gmail payload is encrypted — unreadable from SQL), and
`document_jobs.mime_type` (the column is `format`).

---

## 8 · What blocks everything

**No domain is activated for any tenant.** So Layer 2 compiles in shadow, no authoritative
decisions are produced, Layer 4 examines nothing every tick, and the whole lower half of the stack
runs correctly over an empty queue.

Before that row can be written, Layer 4 needs organisation data that is not code: **seats, then
the reporting line** — which lives in `seat_responsibilities.reports_to`, never
`org_seats.manager_seat_id` — **then channels.**
