# Step 6 — DONE · the cutover nobody guards

**Unit:** `M13.C3.U06` · **Owner:** me · ✅ **2026-10-01** · 18 tests · 5 mutations
⛔ **4 of the 18 need a database and have NOT been run here — see §5.**

## 1 · What is there

`deliver/spine.py` is the Phase-3 durable outbox spine: `materialize` → `claim_due` → attempt →
settle. `recover_expired_claims` (`spine.py:138`) is its ambiguity-marker:

> *"An expired worker may have POSTed to a provider before dying; **we must never silently retry over
> that ambiguity.** Attempts with no settle time under an expired claim become `unknown`; the row itself
> is freed for a fresh claim by `claim_due` (its expired lease no longer protects it)."*

It is in `__all__`, it is correct, and **nothing calls it** — not production, not a test.

## 2 · ⛔ The finding I was one grep away from writing, and why it was wrong

The alarming version: `claim_due` frees an expired row regardless (`and (claimed_by is null or
claim_expires_at < :at)`) and writes a **new** fence on reclaim, while the recovery matches on
`a.claim_token = d.fence_token` — so after a reclaim the recovery can never match, the orphaned
`started`/`settled_at is null` attempt is permanent, and the retry happens over exactly the ambiguity
the docstring forbids.

⛔ **`spine.claim_due` is called by nothing in production either.** Two tests and an
`inspect.getsource` assertion. The production drain is `outbox.drain`, and `outbox.py:838` states it
plainly: *"Risk was zero only because the v2 path has never written a row yet."* The two paths are now
mechanically disjoint — the legacy drain takes `dedupe_key is null`, the v2 claimer `is not null`.

**So the honest finding:** the v2 spine is a complete, correct, un-cut-over path, and
`recover_expired_claims` is the one component of it that nothing exercises **at all** — `claim_due` at
least has tests proving claim-and-reclaim. The cutover, on the day it is taken, takes a path whose
ambiguity-marking step has never once executed, and nothing in the repo would tell anyone.

> ⛔ **Doctrine: *an uncalled function on an un-cut-over path is not a bug; it is an unguarded
> cutover.*** The two want **opposite** fixes. A bug wants wiring now. An unguarded cutover wants a
> guard that fires when the cutover is taken — wiring it into a path that runs zero rows would be
> presence without effect, and *presence is not effect.*

## 3 · What to build

| | |
|---|---|
| `tests/deliver/test_the_spine_cutover_cannot_be_taken_unguarded.py` | ⛔ NEW. The core assertion: **if anything in `genios_engine/` outside `spine.py` calls `claim_due`, then something must also call `recover_expired_claims`.** Vacuously true today, and it fails the build on the commit that takes the cutover without the recovery |
| `deliver/delivery_health.py` | the `UNREACHED` entry: unreached **because the path is not cut over**, mover = whoever takes the cutover, pointing at the test above |
| `platform/receipts.py` | a receipt counting orphaned attempts — `outcome='started' and settled_at is null` under an expired claim. ⛔ Reads **0** today because the table is empty, and becomes meaningful the instant the cutover happens |
| `tests/deliver/test_the_recovery_marks_an_ambiguous_attempt.py` | ⛔ NEW. The test the function has never had: an expired claim with an unsettled attempt becomes `unknown`; a live claim's attempt is untouched |

⛔ **The receipt must be able to fail.** *A receipt that cannot fail is not a gate.* This one can: the
moment the v2 path writes rows and a worker dies, it goes non-zero. A receipt that is structurally 0
forever would be decoration — so the test must prove it returns non-zero on a seeded orphan, not merely
that it returns 0 on an empty table.

⛔ **It must also survive the M1 mutation shape.** `and not exists (` → `and false and not exists (`
left every substring in place and 10 tests passed. So: a **contiguity** assertion on the SQL plus
`test_no_tautology_can_neutralise_the_guard`, rejecting `and false`, `or true`, `and true`,
`where false`, `where true`, `1=1`.

## 4 · What this step does NOT do

⛔ **Take the cutover.** Nobody asked for it, and it changes which code path delivers every
notification in the product. **Noticed something adjacent? New unit, not a silent fix.** Logged as a
candidate, not built.

### ⛔ CORRECTED 2026-10-01 · this step said the cutover has no measurement. It has one

This step originally read *"the measurement that would justify it — `COMPARISON_KEYS`-style counters
over both paths — does not exist for the outbox."* **It exists.** `outbox.shadow_resolve_v2`
(`outbox.py:1254`) runs the v2 control plane's resolution over every live card, sends nothing, and
accumulates `v2_shadow_resolved` / `v2_shadow_unroutable` into the sweep totals at `outbox.py:1441`.
I searched for a both-paths comparison and did not search for a **shadow** — *a measurement can be
present under a name you did not search for.*

**The guard this step builds is unchanged, and its justification is now sharper.** The shadow measures
**resolution only**. Triaged in `07-AUDIT-the-second-delivery-architecture.md`, the v2 path has four
tiers:

| Tier | Modules | Evidence in production |
|---|---|---|
| 1 · resolution | `orchestrator.resolve` · `presence` · `audience` | ⛔ **shadow-measured** |
| 2 · persistence | `spine.materialize` · `logical_dedupe_key` · `record_materialization_failure` | none — `outbox.py:804` says so |
| 3 · claiming | `spine.claim_due` · `recover_expired_claims` | none, and the recovery has no test |
| 4 · policy | `rate_limiter` · `retry` · `scheduler.schedule_order` | ⛔ **none — two of these modules are not even imported** |

So the cutover would be decided on evidence about **routing**, while the three tiers that touch the
network have none. ⛔ **That is a better reason for this step's guard than the one it was written
with.**

## 5 · Verify

```
.venv/bin/pytest tests/deliver/test_the_spine_cutover_cannot_be_taken_unguarded.py \
                 tests/deliver/test_the_recovery_marks_an_ambiguous_attempt.py -q
.venv/bin/pytest tests/platform/ -q
```

## 6 · Mutations

| # | Mutation | Must go red |
|---|---|---|
| M1 | `and false and` into the receipt's `not exists` | the tautology test |
| M2 | drop the `settled_at is null` clause | the seeded-orphan test |
| M3 | make the cutover test's caller scan return `set()` | a test asserting the scan finds `claim_due` in `spine.py` itself |
| M4 | drop the `claim_token = fence_token` join from the recovery | the live-claim-untouched test |

## 7 · Expected outcome

The one component of the v2 spine that nothing exercised has a test, a declaration with a mover, and a
receipt. **The cutover becomes impossible to take silently.**


---
---

# ✅ DONE — 2026-10-01

## 1 · What was built

| | |
|---|---|
| `tests/deliver/test_the_spine_cutover_cannot_be_taken_unguarded.py` | ⛔ NEW, **14 tests**, no database needed |
| `tests/test_delivery_spine.py` | ⛔ **4 new tests — `recover_expired_claims`'s FIRST, ever** |
| `platform/receipts.py` | ⛔ a new L5 receipt: *"no delivery attempt is left unsettled long enough to be ambiguous"* |

```
receipts  32 -> 33        L5: 2 -> 3
```

## 2 · ⛔ The guard, and what makes it a guard rather than a comment

```python
claimed   = counts[("spine", "claim_due")]
recovered = counts[("spine", "recover_expired_claims")]
assert not (claimed and not recovered)
```

**Both are zero today, so it is vacuously true — and that is correct.** It fails the build on the
commit that takes the cutover without the step that marks an expired worker's unsettled attempt
`unknown`.

⛔ **Mutation M4 is the one that proves it.** Adding a single production caller of `spine.claim_due`
to `deliver/tracker.py` — the cutover, taken in one line — turned **5 tests red**. Without the
guard, that commit would have been green.

## 3 · ⛔ The design decision this step turned on · a guard must not inherit the blind spot of the thing it guards

`recover_expired_claims` joins `a.claim_token = d.fence_token`. `claim_due` writes a **new** fence
when it reclaims a row. So:

> once a row has been handed to a fresh worker, the previous worker's orphaned attempt **can never
> match the recovery's predicate again.** It stays `started`, unsettled, forever — and those are
> exactly the cases where a retry has already happened.

The receipt is therefore **deliberately fence-independent**: `outcome = 'started'`,
`settled_at is null`, `started_at < now() - interval '1 hour'`, and **no mention of
`claim_expires_at` or `fence_token`**. A receipt built on the recovery's own join would have counted
only the orphans that are still recoverable and missed every permanently-lost one.

⛔ **The blind spot is recorded, not fixed.** Changing the join is a behaviour change on a path
nobody runs, and `test_the_recovery_still_joins_on_the_fence_and_the_receipt_still_does_not` asserts
the asymmetry **as a pair**, so whoever does fix it is told which rationale and which test now need
rewriting.

### And the window is justified, not picked

One hour is **twelve** default leases (`claim_due(lease_seconds=300)`) and **nine hundred** provider
timeouts (`push._TIMEOUT_S = 4.0`), asserted arithmetically rather than stated. ⛔ A tighter window
would turn latency into an alarm, and *the fix for a false alarm is always to loosen the check.*

## 4 · ⛔ This receipt CAN run today, unlike L5's other one

`migrations/0043_l52_delivery_control_plane.sql` is **applied** — `delivery_attempts` and every
column the receipt reads exist in production. So unlike the *lane* receipt, which **ERRORs** because
`cards.output_lane` awaits `0190`, this one executes and returns **0**.

> ⛔ *A receipt that cannot fail is not a gate.* This one cannot fail **yet**, which is a different
> statement: the v2 path has written no rows, so there are no attempts to be ambiguous. It starts
> answering the moment the cutover is taken — which is precisely when somebody needs the answer.

## 5 · ⛔ FOUR TESTS ARE WRITTEN AND HAVE NOT BEEN RUN

`tests/test_delivery_spine.py` proves the spine against **real PostgreSQL**, because its SQL uses
`for update skip locked` and a partial-index `on conflict` that no fake can model. ⛔ **No database is
configured in this checkout**, so the whole file skips — all 7 tests, including the 3 that predate
this step:

```
.venv/bin/pytest tests/test_delivery_spine.py -q     ->  7 skipped
```

**Collection succeeded, so the imports and syntax are sound. The behaviour is unverified.**
⛔ **A skip is not a pass**, and this is recorded here rather than counted as a win. Added to
`HANDOFF-HARSH.md`: whoever has a database runs this file.

### What was done instead, because a skip is not a pass

Five of the 14 database-free tests assert the recovery's **contract** structurally, so the predicates
those four behavioural tests depend on are guarded everywhere the suite runs:

| | |
|---|---|
| `test_the_recovery_only_touches_an_attempt_with_no_outcome` | ⛔ `delivered` must never become `unknown` |
| `test_the_recovery_is_bounded_by_the_lease_and_not_by_the_clock_alone` | without it, every in-flight attempt is marked on the next tick |
| `test_the_recovery_settles_what_it_recovers` | or the count is meaningless |
| `test_no_tautology_can_neutralise_the_recovery` | the M1 shape, on the recovery's own SQL |
| `test_the_recovery_still_joins_on_the_fence_and_the_receipt_still_does_not` | §3's asymmetry |

⛔ **A behavioural test that skips everywhere it is run is not a guard.** Structural assertions are
weaker evidence than behaviour and they are not zero, and the difference is written down rather than
blurred.

## 6 · Mutations

⛔ **RE-RUN against a verified baseline of 30 passed.** The first run was taken while a stale
`STEP-05` assertion was failing — see `STEP-14 §4` — so every count was one too high. All five are
still caught; only the numbers were wrong.

| # | Mutation | first reported | ⛔ actual |
|---|---|---|---|
| M1 | `and false and` into the receipt predicate | 2 failed | 🔴 1 failed |
| M2 | drop `settled_at is null` from the recovery | 2 failed | 🔴 1 failed |
| M3 | drop the `claim_expires_at` lease bound | 2 failed | 🔴 1 failed |
| M4 | ⛔ **take the cutover: one production call to `claim_due`** | 5 failed | 🔴 **4 failed** |
| M5 | add a fence join to the receipt | 3 failed | 🔴 2 failed |

⛔ **The lesson is not the arithmetic.** A mutation count inflated by a pre-existing failure is a
mutation run that proves nothing — and in `STEP-14` exactly that hid a surviving mutation.
**Establish the baseline, or the harness is theatre.**

## 6b · ⛔ CORRECTED 2026-10-01 · this document called the new receipt "#21", and numbers move

`STEP-10` inserted two L5 receipts earlier in the list, so the one this step added went from **#21 to
#23**. Every number in this document was a **live cross-reference**, and every one of them rotted the
moment somebody added a receipt above it.

⛔ **The tests never had this problem**: they all filter by claim — `[r for r in receipts(None) if
"lane" in r.claim]` — which is why the full suite stayed green while the prose went wrong.

⛔ **And there is a legitimate use of the number, which is why this is a distinction and not a ban.**
`platform/receipts.py:190` quotes `#19 / #21 / #22 / #14` with values under *"Measured 2026-10-01"*.
That is a **dated snapshot of one run**, and the numbering belongs to that run: it is part of the
measurement and correct forever. A live cross-reference is a different thing and must use the claim.

> ⛔ **Refer to a receipt by its claim, never by its position — unless you are quoting a dated run,
> where the position is part of what was measured.**

## 7 · Doctrine

| Rule |
|---|
| ⛔ **a guard must not inherit the blind spot of the thing it guards** |
| ⛔ **a behavioural test that skips everywhere it is run is not a guard — and a skip is not a pass** |
| **a receipt that cannot fail *yet* is not the same as one that cannot fail** |
| **an uncalled function on an un-cut-over path is not a bug; it is an unguarded cutover** |
| **a window must be justified against the thing it measures, not picked** |
| ⛔ **refer to a receipt by its claim, never by its position — unless quoting a dated run** |
