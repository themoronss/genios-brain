# Step 10 — ✅ DONE · the pass that works the needs queue

> **Tree:** `M9.C2.U10` — added 2026-09-30, not in the original 9 steps.
> **Status:** ✅ DONE · 21 tests · **the connector map is still Harsh's**
> **Why it exists:** L1 and L3 together built a pipeline that asks questions and never listens.

---

## 1 · What was expected

That the evidence-need door was finished. Three pieces were built and green:

| Piece | Where | State |
|---|---|---|
| file a need | `context/evidence_need_store.py` | ✅ called by the sweep |
| work ONE need | `capture/acquire/evidence_need.py` `execute()` | ✅ 17 tests |
| close a need | `context/evidence_need_store.close_need` | ✅ |

## 2 · What was actually true

**Nothing ran the loop between them.** Verified:

```
$ grep -rn "read_open_needs\|evidence_need.execute" genios_engine scripts
  (no results outside the two modules themselves)
```

So the queue was **write-only.** The sweep filed questions every run and not one was ever worked.
Three modules, all correct, all tested, and the chain between them absent — the seventh time this
programme has found that shape.

## 3 · ⛔ What I found while building it, and it is the most important thing here

**A closure is PERMANENT.** `need_id` is deterministic and the insert is `on conflict do nothing`, so:

> A need closed `unavailable` because we had not wired a connector yet is a question **destroyed.**
> When the connector arrives, the question does not come back — nothing re-asks it, because the row
> says it was answered.

⛔ **So a naive first run of this pass against today's production — where no connector is wired —
would close the ENTIRE queue as "not connected" and permanently erase every question Layer 2 had
asked.** That is strictly worse than never running the pass at all.

The `on conflict do nothing` rule that L3 Step 5 got right for one reason turns out to be dangerous
for a completely different one. Both are correct; the second was not foreseen.

### Two refusals, and they are why this is a module and not four lines inside a sweep

| # | Refusal | Why |
|---|---|---|
| 1 | ⛔ **No fetchers at all → the pass refuses to start.** Closes nothing, says why | an executor with nothing to execute with is not an executor. Letting it "work" the queue records our own missing plumbing as a permanent fact about the tenant's evidence |
| 2 | ⛔ **A need whose fetch kind has no fetcher is LEFT OPEN** — deferred, not closed | `fetch_thread` wired while `reextract` is not is the **normal state during a rollout**, and those questions must survive it |

### And the distinction that makes refusal 2 coherent

`plan_fetch()` returning `None` **IS** closed. That means no Layer 1 fetch of any kind could ever
answer this need — a fact about the **question**, not about our deployment. No connector will ever
make `capability:expertise.accounts` fetchable.

| | Closed? | Because |
|---|---|---|
| `plan_fetch` → `None` | ✅ yes | the question is unanswerable **here**, permanently |
| kind wired, fetch found nothing | ✅ yes | a real negative result |
| kind wired, wrong source found | ✅ yes | a substitute cannot carry the claim |
| **kind NOT wired** | ⛔ **no** | a fact about **us** |
| **sweep budget exhausted** | ⛔ **no** | a fact about **this pass** |

## 4 · ⛔ The topology gate caught the first draft, and the fix was not a workaround

The first version imported the store directly:

```
FAILED tests/test_layer_topology.py::test_import_direction
  genios_engine/capture/acquire/need_executor.py (layer 1)
  imports genios_engine.context (layer 2) — upward
```

`capture/` is layer 1; the `evidence_needs` table belongs to `context/` at layer 2. **The gate is
right, and so is its implication:** `capture/` must not know where a need is stored. It answers
questions; the row is `context/`'s.

So `read_open` and `close` arrive as **callables**, exactly as `fetchers` does, and the composition
root joins the two halves. That is the same data-not-import rule `docs/LAYER_MAP.md` records for the
downward direction, applied upward.

## 5 · A second defect found by a test I had just written

`test_a_malformed_row_does_not_break_the_pass` passed — and passing was the problem. The pass refused
entirely on one malformed row.

⛔ **The queue is read oldest-first.** So a row that failed the whole pass would sit at its head
**forever** and block every need behind it — a permanent stall, and an invisible one.

Fixed: a malformed row is **skipped, counted, and never closed** (we do not know what it was asking,
so we cannot honestly record that it was answered). The other forty-nine questions still get worked.

## 6 · Verify

```
$ uv run --no-sync pytest tests/capture/test_the_needs_queue_gets_worked.py -q
.....................                                                    [100%]
21 passed in 0.05s

$ uv run --no-sync pytest tests/capture tests/context tests/test_layer_topology.py -q
1 failed, 7984 passed, 466 skipped in 76.70s
```

The one failure is Step 8's known `pytesseract`-missing test — **not this work**, and it fails on any
machine without the binding.

## 7 · Scenario → expected result

| Scenario | Expected | Actual |
|---|---|---|
| no fetcher wired | ⛔ refuse, close **nothing** | ✅ `ran is False`, `closed == []` |
| `build_fetchers()` today | honestly `{}` | ✅ which is what makes the pass refuse |
| the two halves composed as production will | a **no-op**, not a purge | ✅ |
| a `document:` need, only `fetch_thread` wired | left **open** | ✅ `deferred == 1`, nothing closed |
| a `thread:` and a `document:` need, `fetch_thread` wired | one worked, one waits | ✅ |
| `deferred` vs `unavailable` | different numbers | ✅ one is about us, one about the evidence |
| `plan_fetch` → `None` | **closed** unavailable | ✅ with `"no Layer 1 fetch answers"` |
| the right source found | met, closure recorded | ✅ |
| an expired need | closed unavailable, **never fetched** | ✅ |
| another pass closed it first | counted, **never retried** | ✅ `already_closed == 1` |
| the read is capped | yes | ✅ `limit=3` → `examined == 3` |
| the sweep budget runs out | **defer** the rest | ✅ next pass reads the same queue, oldest first |
| an empty queue | a clean run, not a refusal | ✅ |
| the database is down | ⛔ ingestion survives | ✅ `refused` names the exception |
| a malformed row | ⛔ skipped + counted, rest worked | ✅ `malformed == 1`, `met == 1` |
| a malformed row | never closed | ✅ |
| this module importing `context` | ⛔ impossible | ✅ asserted on the source |

## 8 · What I deliberately did NOT do

| Not done | Why |
|---|---|
| wire real connectors into `build_fetchers()` | needs live connection ids and credentials. **The seam is here so that work is a mapping, not a redesign** |
| return a stub fetcher that yields `None` | ⛔ it would close every need as *"found nothing in the window"* — indistinguishable from a real negative result, permanent, and wrong |
| call this pass from a sweep | it would refuse on every run and log noise. **It gets called when the connectors land**, not before |
| change `on conflict do nothing` | it is right. The danger it creates is handled by refusing to run, not by weakening the rule |

## 9 · For Rohit — what you have to do

**Nothing.** The pass is not called from anywhere yet, deliberately — today it would refuse on every
run.

One thing to know: **this step is the reason the queue is safe to leave running.** The sweep files
questions and nothing destroys them while we wait for the connectors.

## 10 · For Harsh — one task, and it is now small

**Wire `build_fetchers(org_id)`** in `genios_engine/capture/acquire/need_executor.py`:

| Kind | What it must do |
|---|---|
| `fetch_thread` | fetch one Gmail/Slack thread by the need's `thread:<id>` subject |
| `reextract` | re-run extraction on `document:<id>` / `attachment:<id>` |
| `backfill_window` | re-read the window around `signal:<id>` |

Each returns `None` (nothing found) or a mapping carrying at least `source`. **Return only kinds you
have actually wired** — an unwired kind left out of the map is *deferred*, which is correct; an
unwired kind stubbed in would destroy questions.

Then call `run_needs(org_id, read_open=..., close=..., fetchers=build_fetchers(org_id))` with the two
queue callables from `context/evidence_need_store`, from the composition root — **not from inside
`capture/`**, which may not import `context/`.

⛔ **And apply `migrations/0186` and `0187` first.** Neither has ever run in production.
