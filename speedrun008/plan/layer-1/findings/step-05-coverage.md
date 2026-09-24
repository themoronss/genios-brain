# Step 5 · The coverage denominator — findings

**Run:** 2026-09-23 · premise checked against code BEFORE any code was written
**Status:** 5-U1 · 5-U2 · 5-U4 **DONE** · 5-U3 is Harsh's · 5-U5 **DEFERRED, with a reason**

---

## 1. Premise check — one premise WRONG, one narrower than written, one sharper than written

| Written premise | Verdict |
|---|---|
| Nothing stores "how many objects exist in the window" | ✅ confirmed — `grep -rl sync_completeness` returns nothing |
| Pagination completeness is invisible | ⚠️ **narrower** — the value exists in memory, it is never persisted |
| No sent/received symmetry check | ✅ confirmed |
| *"`connectors/backfill.py` sets a 540-day window per connection"* | ❌ **WRONG — it is 60** |
| 5-U1 needs a new `sync_completeness` table | ⚠️ **cheaper than written** — `l1_sync_runs` already exists |

---

## 2. ⛔ The wrong one, and it is bigger than this step

`connectors/backfill.py`:

```python
#: Two months — what a first Sync pulls unless the connection says otherwise.
DEFAULT_BACKFILL_DAYS = 60
```

The module says in its own words that it **used** to be 540 and was deliberately reduced:

> *"It was 540 for a while; a first Sync then walked 18 months of mail before Layer 2 ran at all —
> hours with an empty graph — which is not what a user pressing Sync asked for."*

Migration 0082 stamps `{"backfill_days": 60}` onto every connection that has no explicit value.

### What that does to the benchmark

| Benchmark | Window it asks about | Default connection holds |
|---|---|---|
| **P3** | 6 months = **180 days** | 60 days |
| **P4** | 12 months = **365 days** | 60 days |

> **P3 and P4 are not "unproven" on a default connection. They are structurally impossible — the
> data was never fetched.** A coverage denominator would report this honestly instead of hiding
> it, which makes step 5 *more* worth doing, not less. But no amount of denominator makes a
> 60-day corpus answer a 12-month question.

**This is a step-5 finding that belongs to a decision, not to a code change.** Raising the window
is a per-connection admin act (`POST` → `with_backfill_days`, `routes.py:2367`), it is reversible,
and it costs one-time model spend. It is §2 of the Harsh runbook.

> **Fifth step in a row whose written premise the code corrected.** Steps 2, 3, 4 and now 5. The
> rule — *measure before you change* — has now paid for itself five times, and not once has the
> correction been cosmetic.

---

## 3. The narrower one, stated sharply

Completeness is not *absent* from the system. It is **computed, held in memory, used for a branch,
printed in one log line in one of two doors, and persisted nowhere.**

```python
# sync_runner.backfill_drain — the value exists
total.next_cursor = cursor        # None => the provider is exhausted
```

There are **two** backfill doors and they do not agree about whether this matters:

| Door | What it does with the fact |
|---|---|
| `api/routes.py:3221` · onboarding backfill | **knows**: `capped = cursor is not None`, logs `"CAPPED"` vs `"done"` plus *"safety ceiling hit, older tail remains"* |
| `api/routes.py:1522` · manual `/backfill` | **does not**: logs `"backfill drain done ... scanned=%s emitted=%s"` — the word **"done"** whether the provider exhausted or the 500-page runaway guard stopped it |

Neither persists it. `l1_sync_runs` has fifteen columns and not one of them can answer *"was this
sweep complete?"*:

```
run_id · org_id · connection_id · source · mode
scanned · emitted · dropped · parked · duplicate · quarantined
error · started_at · finished_at
```

### The one-sentence version of the defect

> **The manual backfill door prints the word "done" when it means "stopped", and no record
> anywhere can tell the two apart afterwards.**

That is the same failure Gemini made in the benchmark — reporting the size of what it read as the
size of what exists — reproduced inside our own ingestion.

### Three states, not two

A nullable boolean is required, because "complete" and "incomplete" do not cover it:

| `cursor_exhausted` | Means |
|---|---|
| `true` | the provider said there is no more. The sweep is complete for its window |
| `false` | there IS more and we stopped — **and the reason matters** (see below) |
| `null` | not applicable: a webhook or push source has no pagination to exhaust. **E5** — storing `true` here would be a fabricated 100% |

And `false` splits again, which the plan did not name:

| | Meaning |
|---|---|
| budget spent | **we** stopped — the 500-page runaway guard. Recoverable: re-run `/backfill` |
| budget remaining | the **provider** or an error stopped us. Not recoverable by re-running alone |

---

## 4. The cheaper one

5-U1 says *"a `sync_completeness` row per (connection, window, run) — migration + store."*

`l1_sync_runs` (migration 0027) is already exactly that: one row per run, carrying `connection_id`,
`source` and `mode`, written by `api/routes._run_ledger` from every `run_sync` call. It needs
**columns, not a table**, which means no new writer, no new store, and no second thing that can
drift from the first.

---

## 5. Cost / cache-key check — done BEFORE building

The step-4 lesson, applied. Checked whether step 5 invalidates the extraction cache:

```
grep -rn "vocabulary_fingerprint\|prompt_version\|schema_version" genios_engine/capture/acquire/*.py
→ (no matches)
```

**No cache-key consequence.** Everything step 5 touches is in `acquire/`, upstream of `semantic/`.
No prompt changes, no vocabulary changes, nothing re-extracts.

**One cost is real and is NOT this code's:** raising a connection's `backfill_days` (§2) fetches
more history, and history costs extraction. That is a deliberate operator act with its own price,
recorded in the runbook rather than hidden in a default.


---

## 6. What was built

### 6.1 · 5-U1 + 5-U2 — the sweep says whether it finished

`SyncSummary` gained four fields, `run_sync` and `backfill_drain` populate them,
`api/routes._run_ledger` writes them, and migration **0178** adds the columns to `l1_sync_runs`.

| Field | Meaning |
|---|---|
| `cursor_exhausted` | `True` complete for this window · `False` we stopped · **`None` not applicable / not measured** |
| `page_budget_spent` | when `False` above: `True` = the runaway guard (re-run recovers it) · `False` = the provider or an error (it does not) |
| `claimed_total` | the denominator, when the provider offers one |
| `claimed_is_estimate` | Gmail's `resultSizeEstimate` is one, and the label travels with the number |

**Where the flag is set is the whole correctness argument.** `cursor_exhausted = True` is set
**inside the break** in `run_sync`'s page loop, never after it. Falling out of
`for _page in range(max_pages)` means the budget ran out with a live cursor — the opposite
conclusion — and setting it after the loop would report every truncated sweep as complete.

**The boundary case has its own test.** A drain of exactly N pages with a budget of exactly N
finishes *on* its last permitted page. Reading `budget == 0` as truncation would report a correct
sweep as a failure and send an operator chasing mail that is already here.
`test_the_exact_boundary_is_complete_and_not_truncated`.

### 6.2 · The manual backfill door stopped saying "done" when it means "stopped"

```python
capped = summary.cursor_exhausted is False
_log.info("backfill drain %s ...", "TRUNCATED" if capped else "done",
          ... " — older tail remains; re-run /backfill to resume" if capped else "")
```

Now matching the onboarding door twenty screens away, which had computed the same fact and logged
`"CAPPED"` since it was written. One file, one fact, one answer.

### 6.3 · The denominator actually arrives — and it nearly did not

**THE MISTAKE THIS STEP MADE, and it is the same class the whole plan exists to find.** The first
implementation read the provider's count as:

```python
claimed = getattr(batch, "claimed_total", None)     # defensive — against a field that DID NOT EXIST
```

`SourceBatch` had `objects` and `next_cursor` and nothing else, and **no connector set a total**.
So `claimed_total` was `None` on every row forever, and the test still passed — because it asked
whether `SyncSummary` had somewhere to *put* a number rather than whether any number *arrived*.

> **A unit built, tested, green — and called by nothing on a real request path.** The denominator,
> which is the entire headline of step 5, was plumbing nothing fed.

It was not caught by the suite. It was caught by **ticking the done criteria** — the same mechanism
that found step 4's cache bill, two steps running.

**Closed properly:**

| | |
|---|---|
| The CONTRACT | `SourceBatch.claimed_total: int \| None = None` and `claimed_is_estimate: bool = True` |
| The PRODUCER | Gmail's `_to_batch` reads `resultSizeEstimate` at **all three** of its return points |
| The TEST | `test_the_total_reaches_the_summary_through_run_sync` drives connector → `run_sync` → `SyncSummary`, replacing the field-existence assertion |

**`claimed_is_estimate` defaults to True** — a connector that sets a total without saying which
kind gets the cautious reading. The mistake that costs something is presenting an estimate as
exact, never the reverse. A missing, non-integer or negative count becomes `None` and **never
`0`**: *"the window is empty"* is a reason to stop looking, *"we were not told"* is not.

**The lesson, stated so it is reusable:** `getattr(x, "field", default)` against your own contract
is a smell. It cannot fail, so it cannot tell you the field is missing.

### 6.4 · 5-U4 — sent/received symmetry

`capture/coverage/symmetry.py`. Pure: no clock, no I/O, no model — pinned by
`test_the_module_reads_no_clock_and_touches_no_storage`, because a check that queried for its own
input could not be pointed at a corpus somebody is worried about.

**It catches what a completeness ratio structurally cannot.** A connection scoped to `in:inbox`
exhausts its cursor honestly and lands half of every conversation. `cursor_exhausted=true` is then
perfectly true and perfectly misleading, and the cost is the worst failure this product has: L1
derives `ball_in_court` from a thread's messages, L2 builds `awaiting_response` on top, and a
thread whose outbound half never landed reads as *"they wrote, we never answered"* — **the product
tells a founder they owe a reply they already sent.**

**Built on `parent_object_id`, not on the reply chain.** ALG-03's `assemble_chain` walks
`In-Reply-To`/`References`, and the step-16 audit found Gmail captures neither — so a check built
on it would report perfect symmetry on a corpus it could not read.

**A bug in my own first implementation, caught by the test that exists for it.** `asymmetry_bp`
removed singletons from the denominator only, so three newsletters beside one healthy thread
reported **30000 bp** — a rate above 100% from a mailbox with nothing wrong. Singletons are now
out of both sides; the singleton *rows* stay in the report, because an unanswered thread is exactly
what `awaiting_response` is about.

---

## 7. 5-U5 — DEFERRED, and why

5-U5 is *"the ratio reaches the signal, so a negative claim can carry it."* It is **not** built,
and the reason is a dependency rather than time.

The ratio is a property of a **sweep**; a QES is a property of an **event**. Joining them means
deciding which sweep an event belongs to, and `source_events` carries no `run_id` — so the join
does not exist yet. Adding one is a column on `source_events` and a change to every capture door,
which is a larger and more invasive change than the rest of step 5 put together, and it belongs
beside **step 15** (*"coverage on the signal"*), which is about exactly this seam.

**Building it half-way would be worse than not building it.** A completeness figure attached to a
signal by a guessed join is a number that looks like provenance and is not.

---

## 8. Test result

```
FULL SUITE     12498 passed · 1061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before step 5:  12470 passed · 14 failed
```

**Zero regressions, +28 tests.** 14 in `test_a_sweep_says_whether_it_finished.py` (four of them
added after the §6.3 mistake was found), 11 in `test_both_sides_of_a_thread_landed.py`, plus the
step-4 additions.

All 10 sweep tests were **RED first**, for the intended reason, before any production line changed.

---

## 9. What this step does NOT fix

* **It does not widen the 60-day window.** See §2 — that is an operator decision with a cost, and
  it is what actually blocks benchmark P3 and P4.
* **It does not backfill completeness for past runs.** Every existing `l1_sync_runs` row keeps
  `cursor_exhausted = null`, which is the honest value: nobody measured it.
* **It does not put the ratio on a signal.** See §7.
* **It does not run the symmetry check anywhere yet.** The function and its tests exist; wiring it
  to a report over real data needs Postgres and is in the runbook.
* **Only Gmail produces a denominator.** Calendar, Drive, Notion, Linear, HubSpot and the rest
  leave `claimed_total` as `None`, which is honest — those providers give no count on a list call.
  A per-connector audit of what each one *could* report belongs to **step 16** (source field
  coverage), which exists for exactly that question.

---

## 10. Done criteria — two of four, and the other two are named rather than ticked

| Criterion | |
|---|---|
| every sync writes a completeness row | **[x]** driven end to end, not asserted on a dataclass |
| an estimate is never stored as a fact | **[x]** label travels, defaults cautious, never `0` |
| a 540-day backfill has been run and recorded exhausted | **[ ]** the window is **60**; needs a real tenant and a deliberate change — Harsh §2 / §5.2 |
| the symmetry check runs and its result is in `STATUS.md` | **[ ]** no real corpus has been run through it; a number from a fixture would be the fabricated denominator this step exists to prevent — Harsh §5.3 |

`plan/README.md`: *"a step is done when its NUMBER moves, not when its tests go green."* Metric 6's
number cannot move until a sweep runs against a real mailbox, so two criteria stay open on purpose.
