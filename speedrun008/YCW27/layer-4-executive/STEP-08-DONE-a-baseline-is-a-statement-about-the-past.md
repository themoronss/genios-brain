# Step 8 — ✅ DONE · a baseline is a statement about the past

> **Unit** U4 · **6 tests · 5 mutations** · ⛔ **F9 RETRACTED, and its retraction found the real
> defect**
> The finding was wrong. The proposed fix would have destroyed correct data. What it turned up on
> the way is live and affects three people.

---

## 1 · ⛔ What F9 said, and why it was wrong

> *"`source_events.occurred_at` max = 2056-04-20. A date 30 years in the future in a production
> column … It is one row shaped like a parser escape. **One row is a finding; the absence of a
> bound at ingest is the defect.**"*

Measured before writing any code:

    future-dated rows        37, not one
    source / object_type     gcal / calendar_event — every single one
    the far ones             2051-04-20 · 2052-04-20 · 2053-04-20 · 2054 · 2055 · 2056
    captured_at              all 2026-09-19 06:15:11, within milliseconds
    captured_at in future    0
    outcome                  'emitted' on all 37

⛔ **An annual recurring calendar event, expanded into yearly instances — a birthday.**
`occurred_at` for a calendar event is **when the meeting happens**, so a future value is *correct
data*. **A bound at ingest would have truncated or rejected legitimate calendar events**, which is
exactly what a calendar connector must not do.

> **Seventeenth near-miss in this programme, and the most dangerous.** The others would have
> produced a wrong report. This one would have produced a wrong *product* — silently discarding
> every future meeting.

## 2 · And every reader was already bounded — except one

| Reader | Bound |
|---|---|
| `capture/esqe/baseline_reader._HISTORY_SQL` | ✅ `occurred_at <= :until` |
| `context/correlation_timeline._CLAIMS_SQL` | ✅ `occurred_at <= :until` |
| `context/correlation_dependency._CLAIMS_SQL` | ✅ `occurred_at <= :until` |
| `capture/landing/unread.py` | ✅ filters on `captured_at` — 0 future rows, and its queue is empty |
| receipt #4 *"the tenant is still being fed"* | ✅ uses `captured_at`, immune by construction |
| ⛔ **`reason/baselines.build_baselines`** | ⛔ **none** |

⛔ **The knowledge that a backward-looking question must bound backwards lived in three `<= :until`
clauses and nowhere as a statement.** That is why the outlier was invisible — and why F9 looked
like an ingest problem instead of a read problem.

## 3 · ⛔ The real defect — and the cost is not what it looks like

The obvious worry is **magnitude**: a 30-year gap destroying a median.

    anisha@vaultex.in   697 events, 30 of them future
                        median gap WITH future = median gap WITHOUT    ⛔ IDENTICAL
    0 of 222 baselines changed value

**667 real gaps drown 30 distant ones.** The magnitude argument is simply false.

The cost is at the **`MIN_SAMPLES` boundary**, where one row is decisive:

    person                 all  past  future   computed(all)  computed(past)
    aditi@noveum.ai          4     3       1       True          False      ⛔ FLIPS
    asmit@supymem.com        4     3       1       True          False      ⛔ FLIPS
    tejas@tryclean.ai        4     3       1       True          False      ⛔ FLIPS

`MIN_SAMPLES = 3`. Three real events is **below** it and must be `cold_start` — *"we do not know
this person's rhythm yet"*, which writes `COLD_START_DAYS` and persists `cold_start = true`. **Four
crosses it**, so each of these three was given a **computed** `reply_cadence` derived from a gap
set that ends in a future year, and `cold_start` stopped being true about them. Downstream, *"this
relationship is going cold"* was judged against that number instead of the honest default.

### ⛔ My first measurement reported zero, and it was asking the wrong question

It compared medians and **skipped every person whose past-only sample fell below `MIN_SAMPLES`** —
which is **exactly the affected population**. It printed *"0 person baselines change"* and I nearly
stopped there.

> ⛔ **A statistic can be unchanged while the verdict flips.** 0 of 222 medians moved; 3 of 222
> people stopped being cold-start. A comparison that skips the cases where the answer changes
> KIND rather than VALUE reports zero and means nothing.

## 4 · The fix — at the read, which is where its siblings already put it

    "select actor->>'email' as email, occurred_at from source_events "
    "where org_id=:o and actor->>'email' is not null "
    "  and occurred_at <= :until "                      ⛔ added
    "order by actor->>'email', occurred_at"),  {"o": org_id, "until": eval_time}

⛔ **`eval_time`, not `now()`.** It is already this function's parameter, so a replay of a
September sweep still uses September's cutoff.

⛔ **No new concept.** This makes `baselines.py` consistent with the three reads that already bound
this column. Nothing was invented; an omission was closed.

## 5 · Scenario → result

| Scenario | Result |
|---|---|
| 3 real events + 1 future calendar instance | ⛔ stays **cold_start** (was: computed) |
| 667 real events + 30 future | median unchanged — it always was |
| a meeting next week | ⛔ still ingested, still stored, **untouched** |
| a replay of an older sweep | uses that sweep's `eval_time`, not today's |

## 6 · The mutations

| | Mutation | Caught? |
|---|---|---|
| M1 | remove the bound (the original defect) | ✅ |
| M2 | `now()` in SQL instead of `:until` | ✅ 2 tests |
| M3 | change `MIN_SAMPLES` | ✅ 2 tests |
| M4 | strip the bound from `baseline_reader` (a sibling) | ✅ |
| M5 | strip the bound from `correlation_timeline` (a sibling) | ✅ |

## 7 · ⛔ Two of my own mistakes, and one of them invalidated a mutation result

**1 · An over-broad assertion, caught by my own test.** The first draft asserted *no `now()`
anywhere in `build_baselines`'s SQL*. It failed — because the function also writes
`computed_at=now()`, which is **correct**: that is when the baseline row was written, not a cutoff
for the measurement. ⛔ An over-broad assertion is a false alarm waiting to be silenced by
weakening it. Narrowed to the one read, via `_history_read()`, which asserts there is exactly one
such query so a second would need its own bound and its own test.

**2 · ⛔ A stale `.pyc` invalidated a mutation run.** M3 wrote `MIN_SAMPLES = 2`; the restore
copied the source back, but Python served **cached bytecode** — so the next mutation and the
"restore" check both ran against `MIN_SAMPLES = 2`. The symptom was two unrelated tests failing
after a clean restore, and `grep` showing `MIN_SAMPLES = 3` in a file whose import returned `2`.

> ⛔ **A mutation harness that restores by copying a file must invalidate the bytecode cache, or a
> later mutation reads an earlier one's compiled output.** M4 and M5 were re-run clean; their
> first results were discarded rather than reported.

## 8 · What this unit did NOT do

| | Why |
|---|---|
| ⛔ bound `occurred_at` at ingest | it would discard every future meeting. **F9's proposed fix was the harm** |
| correct or delete the 37 rows | they are **correct data**, `emitted`, and nothing is stuck on them |
| a receipt for unbounded reads over this column | the scope is wrong for one: most `order by … occurred_at` hits in the engine are over **`graph_facts`**, a different column where the question does not apply. ⛔ An eighteenth near-miss, caught by measuring the scope before writing the guard. The three-sibling consistency test is the narrow version that is actually true |
