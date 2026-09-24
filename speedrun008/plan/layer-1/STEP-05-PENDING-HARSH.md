# Step 5 — PENDING · owner: Harsh

> **Status:** code COMPLETE and green · **one migration · one DECISION that affects the benchmark**
> **What it does:** a backfill that stopped halfway used to file a row saying it finished.
> **Written:** 2026-09-23 · **Evidence:** [`findings/step-05-coverage.md`](findings/step-05-coverage.md)

---

## 1. TL;DR — what you have to do

| # | Action | Blocking? | Effort |
|---|---|---|---|
| **1** | **⛔ DECIDE: the backfill window is 60 days, not 540.** Benchmark P3 (6mo) and P4 (12mo) cannot be answered on a default connection — the data was never fetched. See §2 | **YES — it decides what we can claim** | 15 min |
| **2** | Apply `migrations/0178_sync_completeness.sql` | **YES** — the ledger insert names four columns that do not exist yet | minutes |
| **3** | Run a real backfill and read its completeness row (§4) | no, but it is the proof | ~20 min |
| **4** | Scratch Postgres *(same standing ask as steps 1–4)* | no | ~30 min |

---

## 2. ⛔ THE DECISION — and I think this is the most important thing in the whole plan so far

### 2.1 What I found

The step file said *"`connectors/backfill.py` sets a 540-day window per connection."* It does not:

```python
#: Two months — what a first Sync pulls unless the connection says otherwise.
DEFAULT_BACKFILL_DAYS = 60
```

It **was** 540, and the module says in its own words why it was reduced:

> *"It was 540 for a while; a first Sync then walked 18 months of mail before Layer 2 ran at all —
> hours with an empty graph — which is not what a user pressing Sync asked for."*

Migration 0082 stamps `{"backfill_days": 60}` onto every connection that has no explicit value.

### 2.2 What that does to the benchmark

| Benchmark | Window it asks about | A default connection holds |
|---|---|---|
| **P3** | 6 months = **180 days** | **60 days** |
| **P4** | 12 months = **365 days** | **60 days** |

> **P3 and P4 are not "unproven". On a default connection they are structurally impossible — the
> mail was never fetched.** No amount of coverage reporting makes a 60-day corpus answer a
> 12-month question.

This does not make step 5 less worth doing — a denominator is what tells us this *honestly*
instead of hiding it, which is the exact thing Gemini failed at in the benchmark. But the
denominator is not the fix. The window is.

### 2.3 The trade-off, as the person who reduced it already understood

| | 60 days | 180–540 days |
|---|---|---|
| Time to first useful graph | fast — what somebody pressing Sync expects | hours with an empty screen |
| P3 / P4 answerable | **no** | yes |
| One-time extraction cost | low | proportionally higher |

### 2.4 Options

| Option | What it means |
|---|---|
| **A — raise it for the benchmark tenant only** *(my recommendation)* | `POST` → `with_backfill_days` on that one connection. Nothing changes for other users, the demo becomes possible, cost is bounded to one mailbox |
| **B — raise the default** | every new connection gets deep history and the slow-first-sync problem comes back for everyone |
| **C — leave it** | P3 and P4 stay unanswerable and we should stop citing them |

**A is reversible, bounded, and needs no deploy** — it is an admin write on one connection.

---

## 3. The migration

```bash
psql "<url>" -f migrations/0178_sync_completeness.sql
```

Four nullable columns on `l1_sync_runs` plus a partial index on the incomplete ones.

> **⚠️ APPLY BEFORE THE CODE SHIPS.** `_run_ledger`'s INSERT now names `cursor_exhausted`,
> `page_budget_spent`, `claimed_total` and `claimed_is_estimate`. Without the columns **every
> ledger write fails**. The write is wrapped in a `try/except` that never raises, so it will not
> crash a sync — it will silently stop recording runs, which is worse. Same
> **column-then-writer** ordering as step 3.

**Nullable, deliberately.** A `not null default false` would state that every sweep this product
has ever run was INCOMPLETE — a claim about the past nobody measured, and a false
"your history is truncated" banner in front of every existing tenant.

---

## 4. What actually changed

### 4.1 A sweep now says whether it finished

`SyncSummary` gained four fields; `run_sync` and `backfill_drain` populate them; `_run_ledger`
writes them.

| Field | Meaning |
|---|---|
| `cursor_exhausted` | `True` complete for this window · `False` we stopped · **`None` not applicable / not measured** |
| `page_budget_spent` | when `False`: `True` = our 500-page runaway guard (**re-running `/backfill` recovers it**) · `False` = the provider or an error (**it does not**) |
| `claimed_total` | the provider's own count, when it gives one |
| `claimed_is_estimate` | Gmail's `resultSizeEstimate` is one, and the label travels with the number |

The second field is the one that saves you time: with a single "incomplete" flag an operator
re-runs the sweep that cannot get further and leaves the one that could.

### 4.2 The manual backfill door stopped saying "done" when it means "stopped"

`api/routes.py` logged `"backfill drain done"` whether the provider ran out of mail or our runaway
guard stopped us mid-history. Twenty screens down, the **onboarding** backfill already computed
the identical fact and logged `"CAPPED — safety ceiling hit, older tail remains"`. One file, one
fact, two answers. Now:

```
backfill drain TRUNCATED org=... scanned=... emitted=... — older tail remains; re-run /backfill to resume
```

### 4.3 The denominator actually arrives — `SourceBatch.claimed_total`

`SourceBatch` carried `objects` and `next_cursor` and nothing else. It now carries the provider's
own count, and **Gmail's `_to_batch` reads `resultSizeEstimate`** at all three of its return
points — the only provider-side count this product receives from anywhere.

```
claimed_total        465     what Gmail says matches the query
claimed_is_estimate  True    Google named it "Estimate"; the label travels with the number
scanned                1     what we actually fetched
```

A missing, non-integer or negative count becomes `None` and **never `0`**: *"the window is empty"*
is a reason to stop looking and *"we were not told"* is not.

> See §7 — this is the part of step 5 that was nearly shipped as plumbing nothing fed.

### 4.4 Sent/received symmetry — `capture/coverage/symmetry.py`

**This catches what a completeness ratio structurally cannot.** A connection scoped to `in:inbox`
exhausts its cursor perfectly honestly and lands half of every conversation.

The cost is the worst failure mode we have: L1 derives `ball_in_court` from a thread's messages,
L2 builds `awaiting_response` on top, and a thread whose outbound half never landed reads as
*"they wrote, we never answered"* — **the product tells a founder they owe a reply they already
sent.** Our own `Commitment` contract says what that costs: *"the second false chase is the last
time that founder reads a nudge from us."*

Built on `parent_object_id` (the provider's thread id), **not** on `In-Reply-To`/`References`,
because the step-16 audit found Gmail captures neither — a check built on those would report
perfect symmetry on a corpus it could not read.

---

## 5. How to cross-check me

### 5.1 Hermetic

```bash
.venv/bin/python -m pytest tests -q -p no:randomly          # ~7 minutes
```

**Expect:** `12498 passed · 14 failed`. Before step 5: `12470 passed · 14 failed`. **Zero
regressions, +28 tests.** All 14 failures are pre-existing — §6 lists them and shows how to
verify that claim without trusting me.

```bash
.venv/bin/python -m pytest tests/capture/acquire/test_a_sweep_says_whether_it_finished.py \
                          tests/capture/coverage/test_both_sides_of_a_thread_landed.py -q
```

**Expect:** `25 passed`. All 10 sweep tests were RED before the production change, for the
intended reason.

### 5.2 The real proof — a truncated backfill must LOOK truncated

On a tenant with more than 500 pages of history, or with `max_rounds` lowered:

```sql
select run_id, mode, scanned, cursor_exhausted, page_budget_spent, claimed_total
from l1_sync_runs
where org_id = '<org>'
order by finished_at desc
limit 10;
```

| What you see | What it means |
|---|---|
| `cursor_exhausted = true` | the sweep reached the end of its window. The only case where completeness may be claimed |
| `false` + `page_budget_spent = true` | **our** guard stopped it. Re-run `/backfill` — it resumes |
| `false` + `page_budget_spent = false` | the provider or an error stopped it. Re-running alone will not fix it |
| `null` | not measured (a row written before 0178) or not applicable (a webhook source) |

**If every row reads `null` after a fresh sync, the writer is not reaching the columns** — check
that 0178 actually applied, because `_run_ledger` swallows its own exceptions by design.

### 5.3 The symmetry check against real data

```sql
select e.parent_object_id as thread_key, count(*) filter (where ...) ...
from source_events e where e.org_id = '<org>' and e.source = 'gmail';
```

Feed those rows to `check_symmetry`. **A high `asymmetry_bp` with `cursor_exhausted = true` is the
specific combination that means the connection's SCOPE is wrong** — we read everything we were
shown, and we were shown one side.

---

## 6. Known failures, and why none of them is this step

The suite has **14 failures and all 14 pre-date this branch.** Same list as step 4:

| Test | Reason |
|---|---|
| `test_ocr_enablement.py::test_the_wiring_returns_no_engine...` | no local tesseract — step 1's, and yours |
| `test_g9_gate_probes.py::test_probe_deleting_an_org...` | needs Postgres |
| `test_h0_gate.py::test_every_layer_two_placeholder_skips...` | meta-test; reports the 11 below |
| 11 × `tests/context/...` | L2's angle-audit writer, `store.py:328` |

**Verify that claim yourself rather than taking it from me:**

```bash
.venv/bin/python -m pytest tests -q -p no:randomly 2>&1 | grep ^FAILED | sort > /tmp/now.txt
git stash
.venv/bin/python -m pytest tests -q -p no:randomly 2>&1 | grep ^FAILED | sort > /tmp/base.txt
git stash pop
comm -13 /tmp/base.txt /tmp/now.txt      # must print NOTHING
```

`comm -13` printing nothing means every failure on the branch also fails on a clean tree.

> **A skip is not a pass.** 1061 tests are SKIPPED here, not green — the Postgres-marked lane.
> §5.2 is what turns them green and it needs your scratch database.

---

## 7. The mistake this step made, recorded because it is the useful part

**Step 5 committed the exact defect this whole plan exists to find**, and I want it on the record
rather than quietly fixed.

The first implementation read the provider's count like this:

```python
claimed = getattr(batch, "claimed_total", None)     # defensive — against a field that DID NOT EXIST
```

`SourceBatch` had no such field and **no connector set one**. So `claimed_total` was `None` on
every row, forever — and the test still passed, because it asked whether `SyncSummary` had
somewhere to *put* a number rather than whether any number ever *arrived*.

> **That is the "six times" defect: a unit built, tested, green — and called by nothing on a real
> request path. The denominator, which is the entire headline of step 5, was plumbing that nothing
> fed.**

It was found by ticking the done criteria, not by the suite. Closed by putting the field on the
CONTRACT, wiring Gmail's parser at all three return points, and replacing the field-existence
assertion with `test_the_total_reaches_the_summary_through_run_sync`, which drives
connector → `run_sync` → `SyncSummary`.

**What to take from it:** `getattr(x, "field", default)` against your own contract is a smell.
It cannot fail, so it cannot tell you the field is missing.

---

## 8. What stays with me — do not wait on these

| Item | Why it is mine |
|---|---|
| 5-U5, the ratio on the signal | needs a `run_id` on `source_events`; belongs beside step 15 |
| Wiring the symmetry check to a scheduled report | the pure function is done; the report is a script over real rows |
| Step 6 (domain mapping) | next in the queue, independent of everything above |

---

## 9. What this step does NOT fix

* **It does not widen the 60-day window.** §2 — that is your call and it is what actually blocks
  P3 and P4.
* **It does not backfill completeness for past runs.** Existing rows keep `null`, which is honest:
  nobody measured them.
* **It does not put the ratio on a signal (5-U5).** Deferred with a reason: the ratio is a property
  of a *sweep* and a QES is a property of an *event*, and `source_events` carries no `run_id`, so
  the join does not exist. Adding one is a column plus a change to every capture door, and it
  belongs beside **step 15**. A completeness figure attached by a guessed join is a number that
  looks like provenance and is not.
* **It does not run the symmetry check anywhere.** The function and its 11 tests exist; wiring it
  to a scheduled report needs Postgres.

---

## 10. Send back to me

| Item | Your answer |
|---|---|
| **§2.4 — backfill window: A (benchmark tenant only), B (raise default), or C (leave it)?** | |
| §3 — was 0178 applied? | |
| §5.1 — hermetic run: passed / failed counts | |
| §5.2 — what did `cursor_exhausted` read after a real sync? | |
| §5.3 — `asymmetry_bp` on the pilot org, if you got that far | |
| §5.2 — **did `claimed_total` come back non-null after a real Gmail sync?** (if it is null on every row, Composio is not passing `resultSizeEstimate` through and I need to know) | |
| §6 — did `comm -13` print nothing? | |
