# Step 5 — The coverage denominator

**Status:** NOT STARTED · **Effort:** days · **Depends on:** nothing (measure with 3) · **Engine:** D
**Moves:** metric 6 · benchmark check #4

> **Re-measure before starting.** Steps 1–3 change what is indexed and what is visible.

## 1. Why this step exists

Gemini's single worst failure in the benchmark was reporting **"18 threads read of 18 that exist"**
when Gmail's own estimate for the window was **~465**. It reported the size of its context as the
size of the mailbox. Claude's strongest behaviour was the opposite — it published a coverage table
first, and said `~8%`.

**GeniOS cannot beat that failure without storing the denominator, and today it stores only the
numerator.**

This is also what makes every *negative* claim safe. `coverage/declaration.py` already states the
principle for **channels**:

> *"It is the difference between 'this customer has no support tickets' and 'we have no source
> that could carry a support ticket.' The first is a finding; the second is a blind spot wearing a
> finding's clothes."*

The same argument applies one level down, to **objects within a connected channel**: "no follow-up
email exists" and "we indexed 8% of the mail" are two different sentences.

## 2. Current status

| Question | Answered today? | Where |
|---|---|---|
| Is a channel connected and flowing? | **yes** | `coverage/declaration.py`, `coverage_ready` on every event |
| How many objects exist in the window? | **no** | nothing stores it |
| How many did we fetch? | partially | the sync run knows; it is not persisted as a ratio |
| Did the cursor exhaust? | **no** | pagination completeness is invisible |
| Did both sides of a thread land? | **no** | no symmetry check |

`connectors/backfill.py` sets a 540-day window per connection. **Nobody has proven a 540-day sweep
completes** — and benchmark P3 (6 months) and P4 (12 months) are exactly that claim.

## 3. Expected result

| | Before | After |
|---|---|---|
| Per-sync completeness row | none | source · window · claimed · fetched · cursor-exhausted |
| A sayable sentence | "we found no follow-up" | "we found no follow-up **across 465 of 465 indexed threads**" |
| 540-day backfill | configured, unproven | proven, with a row saying so |

## 4. Edge cases

| # | Scenario | What must happen |
|---|---|---|
| E1 | The API gives no total (Gmail's is an estimate) | store it **as an estimate**, labelled — never as a fact |
| E2 | Fetched > claimed | legal when the estimate is low; do not treat as an error |
| E3 | Cursor dies mid-sweep | `exhausted=false` — this is the row's most important field |
| E4 | Rate-limited partway | partial, recorded, resumable |
| E5 | A source with no pagination (a webhook) | completeness is not applicable; say so rather than storing a misleading 100% |
| E6 | The window moves between runs | completeness is per **run + window**, never global |

## 5. How to do it

| Unit | What | Artifact |
|---|---|---|
| 5-U1 | a `sync_completeness` row per (connection, window, run) | migration + store |
| 5-U2 | the sync runner writes it; every connector reports what it saw | `acquire/sync_runner.py` |
| 5-U3 | a 540-day backfill is run and its row asserted exhausted | operational |
| 5-U4 | sent/received symmetry: every thread with an inbound has its outbound and vice versa | a check + a report |
| 5-U5 | the ratio reaches the signal, so a negative claim can carry it | follows step 3's widened seam |

## 6. Test cases
T1 a completed sweep writes `exhausted=true` · T2 an interrupted sweep writes `false` (RED today:
no row) · T3 an estimated total is labelled as an estimate · T4 a webhook source records
"not applicable", not 100% · T5 a thread with an inbound and no outbound is flagged by the
symmetry check.

## 7. Verify
```bash
uv run --no-sync pytest tests/capture/acquire tests/capture/connectors -q -p no:randomly
python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"
```

## 8. Done criteria

**Ticked 2026-09-23.** Two closed, two **cannot be closed from this machine** and are named in the
Harsh runbook rather than quietly ticked. Detail:
[`findings/step-05-coverage.md`](findings/step-05-coverage.md).

- [x] **every sync writes a completeness row** — `run_sync` and `backfill_drain` set
      `cursor_exhausted` / `page_budget_spent` / `claimed_total` / `claimed_is_estimate`;
      `api/routes._run_ledger` names all four in its INSERT; migration **0178** adds the columns.
      Driven end to end by `test_the_total_reaches_the_summary_through_run_sync`, not asserted on
      the dataclass.
- [x] **an estimate is never stored as a fact** — `claimed_is_estimate` travels with the number
      and **defaults to True**, so a connector that sets a total without saying which kind gets
      the cautious reading. A missing, non-integer or negative total becomes `None` and never `0`:
      *"the window is empty"* is a reason to stop looking and *"we were not told"* is not.
      `test_a_missing_or_nonsense_total_is_none_and_never_zero`.
- [ ] **a 540-day backfill has been run and is recorded exhausted** — **NOT DONE, and the
      criterion contains the error this step found.** The window is **60 days**
      (`DEFAULT_BACKFILL_DAYS`); 540 is what it used to be. Running one needs a real tenant and a
      deliberate window change, so it is §2 and §5.2 of the Harsh runbook. **Not ticked.**
- [ ] **the symmetry check runs and its result is in `STATUS.md`** — the check and its 11 tests
      exist and are green (`capture/coverage/symmetry.py`), but it has been run against **no real
      corpus**, so there is no result to record. Putting a number in `STATUS.md` from a fixture
      would be the fabricated denominator this step exists to prevent. §5.3 of the runbook.
      **Not ticked.**

> **Two of four are Harsh's, and they are ticked as open rather than as done.** The rule in
> `plan/README.md` is *"a step is done when its NUMBER moves, not when its tests go green"* —
> metric 6's number cannot move until a sweep runs against a real mailbox.

### 8.1 · The defect this step's own build committed, and how it was caught

The first implementation read the provider's count as:

```python
claimed = getattr(batch, "claimed_total", None)     # defensive, against a field that DID NOT EXIST
```

`SourceBatch` had `objects` and `next_cursor` and nothing else, and **no connector set a total** —
so `claimed_total` was `None` on every row forever. The test still passed, because it asked
whether `SyncSummary` had somewhere to put a number rather than whether any number arrived.

> **That is the "six times" defect, committed inside the step written to prevent its cousin: a
> unit built, tested, green — and called by nothing on a real request path.**

Closed by putting the field on the CONTRACT (`SourceBatch`), having Gmail's `_to_batch` read
`resultSizeEstimate` at all three of its return points, and replacing the field-existence
assertion with `test_the_total_reaches_the_summary_through_run_sync`, which drives
connector → `run_sync` → `SyncSummary`.

## 9. Must NOT do
Do not store a fabricated 100%. Do not treat an estimate as exact. Do not let a partial sweep look
complete — **that is the exact failure this step exists to prevent.**
