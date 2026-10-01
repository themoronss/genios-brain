# Step 5 — ✅ DONE · residue reaches the sweep

> Inherited from Layer 1. The conversion is built and tested (`context/evidence_needs.py`, 15
> tests); **nothing calls it.**

## What is true now

`context/runner.py:1347` runs `detect_residue` on every sweep and files the counts. The conversion
from residue to `EvidenceNeed` exists beside it and is never invoked — so Layer 1's missing wire is
now *half* built: the question can be formed and is never asked.

## What must be true

The sweep converts the residue it just measured into needs, and files them.

## Scenario → expected result

| Scenario | Expected |
|---|---|
| a sweep finds `signal_unreached` residue with a subject | a need is filed |
| the next sweep finds the same residue | **no second row** — the id is deterministic |
| a sweep finds only the other three residue kinds | **no needs** — they are missing readings, not missing evidence |
| the need store is unavailable | ⛔ the sweep completes anyway. Losing a need costs an answer; raising costs the tenant their mail |

## ⛔ Where it goes, and where it must not

Immediately after `detect_residue`, in the same pass, **as a write and not a fetch.** A sweep that
fetched inline would make a graph pass wait on a network — which is why the executor is a separate
pass reading a table, and why `context/evidence_needs.py` has a test asserting the string
`genios_engine.capture` never appears in it.

---

# ✅ DONE — 2026-09-30

## What was built

Two things, because the gap was two gaps:

| Artifact | What |
|---|---|
| `genios_engine/context/evidence_need_store.py` | the writer, the executor's queue read, and the close |
| `genios_engine/context/runner.py` (in `process_pending`) | the call, right after `detect_residue` |

```
$ .venv/bin/python -m pytest tests/context/test_residue_reaches_the_sweep.py -q
....................                                                     [100%]
20 passed in 0.12s

$ .venv/bin/python -m pytest tests/context -q
2679 passed, 270 skipped in 19s
```

## The six-times defect, closed

`detect_residue` has measured what a sweep could not explain since the day it shipped.
`needs_from_residue` (Layer 1, U09) turned that measurement into a question. **Neither filed a row.**
So the executor read an empty table: built, tested, green, and called by nothing — the sixth instance
of that shape this programme has found, and the first one it created itself.

`test_the_sweep_files_needs_from_its_own_residue` is the test that fails if it happens again.

## ⛔ The design of this step is one SQL verb

`on conflict (need_id) do nothing` — **never** `do update`.

Residue is re-derived every sweep. That is what *"unexplained as of the last sweep"* means. A
re-derived need is always born `open`. So an upsert that UPDATED would reset every `met` and
`unavailable` need back to `open` on the very next sweep. In order of how bad that gets:

1. A question answered *"the document does not exist"* would be asked again every sweep, forever.
2. The executor would fetch again each time, and charge the tenant again each time.
3. ⛔ The system would learn that **its questions are always eventually answered**, because every
   closed need would keep reopening and closing.

Point 3 is the failure `evidence_needs.py` excludes three of four residue kinds to avoid — undone by
one verb. A need is written once; after that only the executor moves it. A re-derivation is not new
information, it is the same question still on file.

## Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| the insert | `do nothing`, never `do update` | ✅ asserted on the statement text |
| three needs, one already on file | **2** | ✅ counts rows the queue did not have |
| an empty list | no SQL at all | ✅ and `file_needs` opens no transaction |
| closing as `open` / `pending` / `MET` | refused | ✅ `ValueError` |
| closing `unavailable` with a blank reason | refused **by name** | ✅ not an `IntegrityError` three frames down |
| closing a need someone else closed | `False`, not an error | ✅ their answer stands |
| the executor's queue | oldest first | ✅ a stream of new needs cannot starve a week-old one |
| the sweep | calls it, **after** measuring | ✅ `detect_residue` precedes `needs_from_residue` |
| the count | reaches the sweep result | ✅ `evidence_needs_filed` |
| the database is down | 0 filed, ingestion survives | ✅ |

## Three smaller decisions worth knowing

**The count is NEW rows, not rows offered.** A count of needs derived would report the same number
every sweep — it would read as activity and mean nothing. `evidence_needs_filed == 0` means *"nothing
new to ask"*, which is the useful reading.

**The trace id is derived, not minted.** `process_pending`'s own docstring promises the same graph at
the same `eval_time` replays identically. A fresh `new_id("trace")` would be the one field in the row
a replay could not reproduce, so it is `stable_id("trace", {org, sweep_at})`.

**`close_need` guards with a predicate, not a lock.** `where need_id = :id and state = 'open'` — one
statement, no read-modify-write, so two concurrent executor passes cannot both win. This is where the
withdrawn Step 2's surviving fragment actually landed; see
[STEP-04](STEP-04-DONE-need-clears-hold.md).

## ⛔ What is still NOT wired, stated plainly

| Door | Filed by a sweep? |
|---|---|
| residue → need | ✅ **wired here** |
| hold → need (`hold_needs.py`, Step 3) | ❌ **not wired** |
| need → fetch (`capture/acquire/evidence_need.py`) | ❌ **not wired** — no pass reads `read_open_needs` and calls `execute` |
| fetch outcome → `close_need` | ❌ **not wired** |

So today a sweep files questions and nothing works them. The queue will accumulate and no need will
close. That is a deliberate stopping point, not an oversight — the executor needs real connector
`fetchers`, which is the Layer 1 integration gap already recorded as PENDING in
[layer-1 STEP-08](../layer-1-enterprise-signals/) and owned by Harsh.

**Consequence to be aware of before this ships:** because nothing closes a need yet, every filed need
stays `open`, and `hold_resolution.resolve_hold` will return `keep_waiting` for all of them. Nothing
regresses — situations hold today anyway — but the queue is write-only until the executor pass exists.

## For Rohit — what you have to do

Nothing for the code. One thing to know: migration `0187_evidence_needs.sql` has **not been applied to
production** — it was written in the Layer 1 work and has never run. The sweep's filing pass is inside
`try/except` and logs, so on a database without that table the sweep still completes and
`evidence_needs_filed` stays 0. Nothing breaks; nothing is asked either.

## For Harsh — the two things to do

1. **Apply `0187_evidence_needs.sql`.** Until then the filing pass logs an exception every sweep and
   files nothing.
2. **Write the executor pass.** `read_open_needs(conn, org_id)` → `capture.acquire.evidence_need.execute(need, fetchers=...)` → `close_need(conn, id, state=..., reason=...)`. All three pieces exist and
   are tested; what is missing is the real `fetchers` mapping to live connectors, which is your
   integration gap from Layer 1, not a new one.


---

## ⛔ 2026-10-01 · the title line of this file was stale, and is corrected above

This file's **first line** read `Step 5 — TO BUILD · residue reaches the sweep` while the `✅ DONE — 2026-09-30` section below recorded the
work as built, and the filename had already been renamed to `...-DONE-...`. Three labels on one
piece of work and one of them disagreed with the other two.

**Why this is recorded rather than quietly fixed.** A heading that says *TO BUILD* on finished work
is the same defect as a stale comment: it reads as a status somebody checked. Anyone auditing the
programme by scanning headings would have counted this step as outstanding and, worse, might have
rebuilt it. Found while assembling `07-LEDGER-every-step-what-why-how-outcome.md`, which reads the
first line of every step file — the ledger could not have been written without resolving it.

**What was verified before the title was changed:** the artifacts named in the DONE section exist in
the tree, and the full suite is 14,534 passed / 0 failed. The title was not made to agree with the
others; it was made to agree with the code.
