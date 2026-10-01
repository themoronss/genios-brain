# Step 10 — ✅ DONE · the declaration had one stale line, and half a guard

> **Units** U6 + U7 · **9 + 1 tests · 3 mutations, all caught**
> ⛔ Found by re-auditing L4 for completeness **after** claiming nothing was left.
> **PULL_ONLY 5 → 4.** The two untested `UNREACHED` entries are now zero.

---

## 1 · Why this step exists

STEP-09 closed U1–U5 and the summary said *"what is left, and none of it is mine."* ⛔ **That was
an assertion, not a measurement.** Re-deriving from the source of truth — `executive/unreached.py`
— found two things that were mine and buildable.

> ⛔ **"Nothing is left" is a claim like any other and has to be measured.**

## 2 · ⛔ U7 · `summary.build_summary`'s entry was false, and had been for weeks

Its `PULL_ONLY` entry said:

> *"The one_line / one_minute / five_minute ladder. `deliver/outbox.py:315` does import it, so this
> one is closer to pushed than the others — it is listed because the ladder itself is still only
> composed where a caller asks for a summary, **never as a scheduled digest**."*

Measured:

    deliver/outbox.py:313   _current_digest_payload  -> "Build a non-actionable digest from
                                                         current authority immediately before send"
                            composes build_summary(store, org_id, "one_minute", ...)
    deliver/outbox.py:1073  inside `_drain_claimed`, called from `drain(engine, ...)`
                            payload = _current_digest_payload(...)
                            res = ch.send(payload, cfg)        ⛔ THE VERY NEXT LINE

⛔ **It has a route AND a producer, and the digest is sent on every drain that claims one.** It was
not pull-only; it was simply shipped. **Removed**, with the reason recorded where a reader will
look.

### ⛔ And the only reason it survived is that the table had half a guard

`UNREACHED` is checked **both** ways — an undeclared silence fails, and a declaration for
something now called fails too. `PULL_ONLY` had three tests, and they asked:

| | Test | What it asks |
|---|---|---|
| 1 | `test_the_pull_only_surfaces_really_have_routes` | does each route exist |
| 2 | `test_no_surface_is_in_both_tables` | do the two tables overlap |
| 3 | `test_the_preventive_surface_records_that_no_card_is_built` | ⛔ **one surface only** |

**Nothing asked the other four whether they had grown a producer.** Test 3 is exactly the right
shape and was never generalised — so four of five surfaces were never asked the question that
matters.

> ⛔ **One direction alone is half a guard, and a guard written for one member of a closed table is
> half of that.**

`test_no_pull_only_surface_has_quietly_acquired_a_producer` is the general form: for every surface,
the function it names must have **zero** calls anywhere under `deliver/`, read through
`unreached.called_names` — which resolves renamed imports, because `deliver/actions.py` already
aliases one of this module's functions and a bare-name count once reported a live function as dead.

The preventive test **stays**, renamed, because it makes a *stronger* claim: `deliver/` must not
reach preventive mode by **any** spelling, not merely by calling `load_preventive`.

## 3 · ⛔ U6 · `is_terminal` had no tests — and the caller that wants it may not have it

Two of the five `UNREACHED` entries carried **no tests at all** — *"unreached and unexercised,
which is the weaker of the two states"*. `blocking_action` was one (wired in U3).
`lifecycle.is_terminal` was the other.

### Its declaration predicted exactly what happened

> *"`TERMINAL_STATES` is the closed set that decides when a commitment stops being advanced, and a
> named predicate over it is where a future reader will look. **Deleting it would push the next
> caller to re-inline the membership test, which is how a closed set acquires a second spelling.**"*

⛔ **The second spelling already exists.** `execution_guard.py:126` opens `validate` with
`if state.state in TERMINAL_STATES:` — the most authoritative branch in the guard, phrased as set
membership rather than as the predicate written for it.

### ⛔ And it cannot have the predicate — a cycle, found by reading the imports

    lifecycle.py:39   from genios_engine.executive.execution_guard import GuardAction, GuardVerdict

The dependency runs **lifecycle → guard**. Importing `is_terminal` back is a circular import.

> ⛔ **An unreached function is not always a forgotten one; sometimes it is an unreachable one.**
> **Twenty-third near-miss**, caught by checking the import direction before editing the guard —
> the plan for this step said *"wire it"*.

So the entry **stays**, and its declaration now says *why*, measured: the one caller that wants it
is the one caller that may not have it, and what would resolve it is moving the predicate to
`contracts/execution` beside the `TERMINAL_STATES` it reads — **which adds no dependency, since
the set is already there.** ⛔ Not done: that changes a public boundary and nobody asked.

### ⛔ And `CREATED` is in neither set

    all states       ARCHIVED BLOCKED CANCELLED COMPLETED CREATED EXPIRED PENDING RUNNING WAITING
    OPEN_STATES      BLOCKED PENDING RUNNING WAITING        (4)
    TERMINAL_STATES  ARCHIVED CANCELLED COMPLETED EXPIRED   (4)
    intersection     EMPTY     ✅
    neither          CREATED   ⛔

The sets are **disjoint but not exhaustive**: `is_open(CREATED)` and `is_terminal(CREATED)` are
both `False`. ⛔ **Pinned, not corrected** — a commitment built and not yet in its lifecycle is a
real third thing and nothing measured a harm from it. If a later reader adds it to either set, the
test fails and they must say which and why.

## 4 · Scenario → result

| Scenario | Result |
|---|---|
| a `PULL_ONLY` surface gains a caller in `deliver/` | ⛔ fails, naming the surface and the count |
| `summary.build_summary` is put back | ⛔ fails — it is called under `deliver/` |
| `deliver/` references preventive by any spelling | ⛔ fails — the stronger claim |
| `CREATED` added to `OPEN_STATES` | ⛔ fails, twice |
| state names inlined inside `is_terminal` | ⛔ fails — a third spelling |
| `lifecycle` stops importing `execution_guard` | ⛔ fails — **the cycle is gone, so wire it and delete the entry** |

## 5 · The mutations

| | Mutation | Caught by |
|---|---|---|
| **M1** | ⛔ put `summary.build_summary` back in `PULL_ONLY` | the new general guard |
| M2 | `CREATED` → `OPEN_STATES` | 2 tests |
| M3 | state names inlined in `is_terminal` | the third-spelling test |

⛔ **M1 is the one that matters**: it reproduces exactly the staleness that survived for weeks, and
the new guard catches it.

## 6 · The declaration tables now

    UNREACHED   5   and ZERO of them untested      (was 6, two untested)
    PULL_ONLY   4   each with a producer-free guard (was 5, one guarded)

| | Entry | State |
|---|---|---|
| `assignment.resolve_approver_seat` | ⛔ real product gap · blocked on H1 **and** an authority rule · counted by receipt #32 |
| `coordination.can_complete` | superseded, with the replacement named · tested |
| `coordination.coordination_snapshot` | no reader exists yet · tested |
| `execution.build_from_decision` | an alternative entry shape · 4 test files, and U3's fixture uses it |
| `lifecycle.is_terminal` | ⛔ **unreachable, not forgotten** · now tested · the cycle is the reason |
