# Harsh → Rohit · what is done, what it measured, and five corrections

> **Written:** 2026-09-29 · branch `harsh/mvp` @ `b88c6a1f` · suite **13,332 passed · 0 failed**
> **Purpose:** the reply to `handoff/` and `DO-THIS-NOW.md`. Everything below was run, not planned.

`speedrun008` is merged into `harsh/mvp` and pushed — Layers 1, 2, 3 and 4, plus
`ARCHITECTURE.md`. Local and origin are level.

---

## 1 · Done

| | |
|---|---|
| **All ten migrations applied** — `0176`…`0185` | verified in `schema_migrations`, columns checked one by one |
| Hermetic suite | **14 failed → 0**, 13,332 passing |
| `pg` lane | **run for the first time**: 611 pass, 7 fail (was 554/48+16) |
| Five production bugs | fixed and pushed — two of them broke prod on deploy |
| Database read-only | lifted; 1,585 MB → 894 MB |
| M6 shadow pass | run; full tallies in §3 |

### The two bugs that mattered

**Every `qualified_signals` INSERT was failing.** `subject_key` reached `_COLUMNS` with step 3's
widening and stopped there — the VALUES list and `as_params()` were never updated. Postgres
refuses 39 target columns against 38 expressions, and `put()` catches everything by design, so
the sweep reported success and stored nothing: **321 signals silently lost in one run.**
`_to_row` had the same omission on the read side. Fixed, with a test that counts the three halves
rather than round-tripping one.

**`teams` was allowed and never read.** P15 added it to `APP_IDS` and left the other two copies of
the app list behind — 0141's column default and the SQL literal inside `save_org_policy`. The
upsert names the column explicitly, so the default never applied, and `effective_policy`
intersected Teams away on every tenant while the API reported it allowed. Migration `0185`, with
a backfill matched only to untouched rows.

Also: `live=True` with no activation rows handed the resolver an EMPTY frozenset, which reads as
"this tenant has activated nothing" — so the global cutover flag refused every situation on every
tenant. Production path unchanged (`runner.py` passes a non-empty set).

---

## 2 · Your measurements, answered

| Item | Answer |
|---|---|
| **8 · re-extraction bill** | 416 rows · 2.34 M in / 1.06 M out on Haiku 4.5 = **≈ $7.67**. Accept it |
| **10 · domain coverage** | **125 of 162 really tagged (77%)**, 0 fallback-only, 37 no domain |
| **13 · relevance** | `ambiguous_over_budget` = **0** — metric 5 is closed. Top bucket is `no_model_wired` at **251**: relevance has no model wired in prod |
| **15 · step 10 gate** | 148 drops; `relationship_change` **55 (37%)** dominates. Your own rule ⇒ that is 8-U3, not a review queue. **Cancel step 10** |
| **18 · joinability** | **83 of 85 (97.6%)**. P4 is falsifiable |
| **19 · threads** | 705 messages, **358 (51%)** in multi-message threads, 132 threads, longest 9 |
| **1 · OCR** | 122 rows, **not one** ever carried an engine. 30 images addressable |
| **9 · the 19 Sept re-sync** | see correction §4.2 |

---

## 3 · M6 — the shadow tallies, and why the gate fails

```
situations            66
  admission_hold      19      ← evidence/coverage, not routing
  no_route             5      ← 1 is fundraising
  incomplete           3
  compiled            39
  reasoned            39
  reasoner_consulted   2
  error                —      (not emitted)
  persist_error        —      (not emitted)
  reasoner_failed      —      (not emitted)
```

`evaluate_parity` ⇒ **FAIL**, on five rules: three tallies absent, and `compiled`/`reasoned` at 39
against a threshold of 100.

**⛔ The threshold is unreachable, and not because the pass is weak.** `PARITY_GATE`'s own
justification reads *"the pilot carries 159 active situations"*. Measured today the pilot carries
**66**. One hundred of sixty-six is arithmetic, not quality — the gate cannot pass on this tenant
however well Layer 2 performs.

39/66 = **59%** against the gate's stated intent of a majority (100/159 = 63%).

**This is yours to re-base**, and I deliberately did not touch it: weakening a gate to land a
change is the failure this repository is written against, and `PARITY_MEASURED_AT is None` with a
test on it is your own guard against exactly that. If the intent is "the majority", the rule wants
a ratio.

---

## 4 · Five corrections

### 4.1 · Four of the handoff's queries do not run

| Item | Reads | Reality |
|---|---|---|
| M1/13 | `source_events.relevance_rule` | **no such column** — the rule is on the S4 trace as `reason_code` |
| 18 | `raw -> 'attendees'` | **no `raw` column** — attendees are in the `recipients` array |
| 19 | `raw -> 'headers' ? 'References'` | the Gmail payload is **encrypted** (`raw_payloads.enc_content`) — unreadable from SQL. Thread shape derived from `parent_object_id` instead |
| 1 | `document_jobs.mime_type` | the column is `format` |

All four are fixed in `scripts/speedrun008_measurements.py` and
`scripts/speedrun008_layer2_measurements.py`, which run every query in ONE `read only`
transaction and need no `GENIOS_ALLOW_PROD_WRITE`.

### 4.2 · The pilot corpus was not destroyed

`STATUS.md` records three of six metrics as unmeasurable because the 19 September re-sync took the
corpus. Measured: `org_e97e86f858ad48b2bbf64b8a` holds **1,490 events from 21 July onward**.
Metrics 4 and 5 were measurable and are measured above. Only metric 1 is still open, and that is
the deploy, not the corpus.

### 4.3 · D3 is not the largest item in Layer 2

The handoff calls `fundraising → sales` *"the single largest thing in Layer 2"* on the grounds
that the pilot is a fundraising founder. The tenant's own shape:

```
admin 53 · support 8 · fundraising 4 · sales 1        (66 active situations)
```

Fundraising is **4 of 66**. Worth the one line — the blast radius is four situations — but the
largest thing in Layer 2 is the **467 held against 223 admitted**, on
`verified_evidence_required` (398), `qes_required` (398) and `source_coverage_insufficient` (69).

### 4.4 · D2 cannot be answered from production yet

`BY LAW` is built from `observed:<law>:<subject>` reasons on ADMITTED decisions. Measured: 223
admitted rows, **zero carrying any reason**. `observed_reasons` is your new code
(`situation_publisher.py:504`) and prod is still running the old build, so the number cannot
exist until this deploys and one sweep runs.

I armed V-9/V-10 once on the strength of hold-reason counts, which reads the wrong column — a law
in `OBSERVE` never produces a hold. **24 contract tests went red immediately** and it was reverted
the same hour. The population D2 asks about is not zero.

### 4.5 · ⛔ The heartbeat does not appear to run in production

This is the one I would look at first, because it is upstream of several of the others.

| Evidence | |
|---|---|
| `purge_superseded_expertise_packages` keeps **3** per (org, situation) | before the truncate, 27 situations held **19 copies each** |
| attachment refetch drain runs on the beat | `document_jobs` holds **341** rows at `fetch_failed`, accumulating 6 → 28 Sep (you counted 13) |
| `ocr_unavailable` | **830** rows |

Both of those run from the heartbeat, and neither has run. This is your item 14's finding —
*"the heartbeat is not running in production… it affects every drain, not just this one"* — and it
explains the read-only incident better than the table does: the retention was wired all along
(`routes.py:992`) and simply never fired.

`scheduler_enabled` defaults `True` and nothing in `.env` disables it, so the cause is in the
deploy, not the config.

---

## 5 · Also corrected: five of my own situation flips

I flipped six drafts on 28 Sep reading `review_status: approved` as "finished and never flipped".
Approved is necessary and not sufficient — your L3-20 carries the other half: four of Admin's and
several of Customer Support's are declared `pending_l2_types`, and one records in its own file
that flipping it *"would cost a false assurance"*.

Five of my six were in that list and are **back at `draft`**. The sixth,
`document_under_control`, was yours and stands.

---

## 6 · What is left, and whose

**Mine (Harsh)**

1. **Deploy** — from the `Dockerfile`. Prod builds from `harsh/mvp` (my `0182` landed there
   yesterday) but OCR has still never run, so the build is using the buildpack, not the Dockerfile.
2. **Backfill window 60 → 365** on the pilot connection (L3 §1.2), after `0184` — applied.
3. **Layer 4 data** — `seat_responsibilities` first, then `org_seats`, then the reporting line,
   and `org_channels` last. None of it is code; all of it is who the people are.

**Yours (Rohit)**

1. **Re-base the parity gate** — §3. It cannot pass as written.
2. **L4-01 … L4-04** — the remaining build steps in `02-THE-REMAINING-STEPS.md`.
3. **Step 10** — your own rule says cancel it; see item 15.

**Open, unowned**

The **7 remaining `pg` failures**. Every one is a test meeting a real database for the first time,
so none is a regression: four in `test_g7_g8_g10_gates` where the second sweep ingests nothing
(not the cursor and not the sync ledger — both checked), `resolution`'s `gated_out == 0`, an extra
`analytic_movement` in the shadow diff, and `situation_publisher` asserting five confidence axes
including `coverage`, which `situations.py:366` documents as legitimately unknown for a domain that
registers no field expectations.
