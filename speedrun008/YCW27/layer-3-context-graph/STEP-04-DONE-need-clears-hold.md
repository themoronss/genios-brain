# Step 4 — ✅ DONE · a met need clears its hold

> **Tree:** `M10.C2.U05` · needs [Step 3](STEP-03-hold-raises-a-need.md)

## What must be true

The loop closes. A need that was **met** lets the situation try admission again on the next sweep. A
need that came back **unavailable** stops the situation waiting for something that will never come.

## Scenario → expected result

| Scenario | Expected |
|---|---|
| the need is met | the hold is retried on the next sweep, and may now ADMIT |
| the need is met but the situation still fails another law | it holds again — on the **new** reason, not the old one |
| the need closes `unavailable` | ⛔ the situation stops waiting and says **why** — the reason reaches the card instead of silence |
| the need is still open | nothing changes; the hold stands |

⛔ **`unavailable` must not look like `met`.** A situation that gave up because the document does not
exist and a situation that is still waiting are different states, and a card that cannot tell them
apart will either nag forever or go quiet with no explanation.

---

# ✅ DONE — 2026-09-30

## What was built

`genios_engine/context/hold_resolution.py` — reads the state of a held situation's evidence needs and
says what should happen to the situation. A pure decision: no database, no clock of its own.

```
$ .venv/bin/python -m pytest tests/context/test_a_met_need_clears_its_hold.py -q
......................                                                   [100%]
22 passed in 0.05s
```

## ⛔ The distinction is three-way, not two-way

The spec said *"`unavailable` must not look like `met`."* True, and only half of it. There are three
need states and **four** dispositions, and both easy mistakes collapse a different pair:

| Need states | Disposition | What it means |
|---|---|---|
| no needs at all | `no_evidence_question` | this hold waits on a **ruling**, not a fetch — four of seven hold reasons raise nothing |
| any still open | `keep_waiting` | nothing changed; re-running admission would spend a sweep to re-derive the same reason |
| all closed, ≥1 met | `retry` | new evidence exists; admission gets another go, and may hold again on a **new** reason |
| all closed, none met | `give_up` | ⛔ stop waiting, **and say why** |

The two collapses, and what each costs:

- treating `unavailable` as `met` → the card claims evidence it never got
- treating `unavailable` as `open` → the situation waits forever for a document that does not exist

## ⛔ Two edges the spec did not name, and both are permanent-hold bugs

**An expired open need is not still waiting.** A need past `expires_at` will never be met — but if the
executor has not run, its row still says `open`. Counting that as waiting is exactly how a hold
becomes permanent: the situation waits on a question nobody will answer, forever, and no surface says
so. So expiry is evaluated here too, at the same `<=` boundary the executor uses — two different
answers at the same instant would let a need be fetched by one path and refused by the other.

**A partial arrival is not a complete one.** When one need was met and another came back unavailable,
the disposition is `retry` **and the unavailable reasons travel with it**. Dropping them would let the
retry read as *"we have everything now"* — the `not_carried` defect, a value computed at one boundary
and silently lost at the next. `explain()` says `retrying with X; still missing: Y`.

## Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| the need is still open | nothing changes | ✅ `keep_waiting`, `still_open == 1` |
| the need is met | retried on the next sweep | ✅ `should_retry_admission is True` |
| the need closed `unavailable` | stops waiting **and says why** | ✅ the reason is in `explain()` |
| the hold asked nothing | not called "waiting" | ✅ `no_evidence_question` — implying a pending fetch would be a lie |
| two unavailable needs | never a retry | ✅ `give_up`, `met_sources == ()` |
| one met, one still open | keeps waiting | ✅ **and remembers what did arrive** |
| one met, one unavailable | retries, carrying what is missing | ✅ `"still missing"` in `explain()` |
| an expired **open** need | stops waiting | ✅ `give_up`, `"expired"` in `explain()` |
| a need expiring exactly now | expired | ✅ matches the executor's `<=` |
| a **met** need that has since expired | still met | ✅ expiry governs the question, not the answer |
| the same needs replayed | the same disposition | ✅ `a == b` |
| `resolve_hold` with no `eval_time` | `TypeError` | ✅ ⛔ no default, because a default would be `now()` |
| three states, three explanations | all different, none blank | ✅ four distinct lines |

## Where the withdrawn Step 2 went

[Step 2](STEP-02-WITHDRAWN-compare-and-set.md) was retired because `reason/runner.py`'s
`_graph_version_guard` already is the compare-and-set, tested and honoured. Its one surviving
fragment — *"a read-modify-write in `context/` has no guard of its own"* — was folded into here.

**It turned out not to be needed.** `resolve_hold` decides and does not write, so there is no
read-modify-write to guard. The concurrency question moved to where the write actually happens —
`evidence_need_store.close_need`, which uses `where need_id = :id and state = 'open'`. One statement,
no read-modify-write, so two concurrent executor passes cannot both win, and a `False` return means
another pass settled it first and its answer stands.

That is a better answer than the guard I was going to build, and it is smaller. A test asserts this
module imports no database at all.

## For Rohit — what you have to do

Nothing.

## For Harsh — what to know

`resolve_hold` has no caller yet, by design: the hold-side filing (Step 3's other half) is the
integration that produces its input. When you wire it, the disposition's `explain()` is the line a
card should carry — it is written to be shown, not logged.


---

## ⛔ 2026-10-01 · the title line of this file was stale, and is corrected above

This file's **first line** read `Step 4 — TO BUILD · a met need clears its hold` while the `✅ DONE — 2026-09-30` section below recorded the
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
