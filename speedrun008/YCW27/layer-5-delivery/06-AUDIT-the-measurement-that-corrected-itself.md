# L5 · audit — the measurement that corrected itself, and the tool that was hiding one

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01. **Written during STEP-05, before any
code.** **Corrects:** `05-RECROSSCHECK-the-silences-of-the-delivery-spine.md`, `03-FINDINGS.md`,
`00-START-HERE.md`, `../STATUS.md`.

STEP-05's first instruction to itself was a measurement, not a build. That measurement found that
**STEP-05's own premise was wrong**, and then found a defect in the tool the whole programme measures
reachability with. Both are recorded here rather than quietly fixed, because the second one affects
L4's conclusions as well as L5's.

---

## 1 · What I claimed, and what is true

| | Claimed in the re-cross-check | ⛔ True |
|---|---|---|
| public functions in `deliver/` | 133 | **123** top-level — the 133 included `channels/` |
| unreached | **4** | ⛔ **23 reported · 24 actual** |
| modules containing one | not stated | **14 of 35** |
| of the unreached, having no test caller either | not stated | **4** — *these are the 4 I reported* |

**So the "4" was a real number answering a different question.** It is the count of public functions in
`deliver/` with **no caller anywhere, including tests** — unwired *and* untested. That is a stricter and
narrower set than the one L4's declaration module is built around.

### How the error happened

`executive/unreached.py` is generic — `public_functions(path)` and `called_names(sources)` take their
inputs — so **the convention lives in the caller, not the tool.** L4's test fixes it:

```python
def _sources() -> dict[str, str]:
    for path in ENGINE.rglob("*.py"):      # the ENGINE only. Tests are not callers
    ...
    for path in sorted(EXECUTIVE.glob("*.py")):   # glob, NOT rglob — top-level files only
```

I passed `tests/` into the source set alongside the engine, and `rglob` over the package. Two deviations,
both in the direction of **reporting fewer problems**: a test caller made a function look reached, and
`channels/` inflated the denominator.

> ⛔ **The lesson is not "be careful."** It is that **a reachability number is meaningless without its
> source set**, and mine was stated without one. L4's number has its convention written into the test
> that produces it. Mine was written into a document, where nothing checks it. **STEP-05 must therefore
> assert the convention in code**, which was not in its original plan.

---

## 2 · ⛔ The tool finding · `called_names` resolves by bare name, so a name collision hides a function

`spine.claim_due` is reported **reached**. It is not. The single engine call site:

```
genios_engine/capture/parked/refetch.py:267     queue.claim_due()
```

That is `InMemoryRefetchQueue.claim_due` — **a different function, in a different package, with a
different signature** (`eval_time=`, `policy=`, `org_id=` against the spine's `org_id=`, `worker_id=`,
`at=`, `limit=`, `lease_seconds=`). `called_names` counts an `ast.Attribute` call whose `attr` matches
the name, which is what makes it resolve aliased imports correctly — and is also what makes any
same-named method anywhere in the engine mask an unrelated function.

| | |
|---|---|
| reported unreached | 23 |
| ⛔ **actually unreached** | **24** — `spine.claim_due` makes the 24th |

### ⛔ This affects L4, not only L5

`executive/unreached.py`'s `UNREACHED` table is CLOSED and checked in both directions, and the
"function is now called" direction uses this same resolver. **So an `executive/` function that shares a
name with any method anywhere in the engine would be reported reached and silently dropped from the
declaration.** Nothing has been shown to be wrong in L4 — but nothing has shown it is right either, and
that is the distinction this programme keeps paying for.

> **Doctrine: *a call resolved by name alone is a call to any function with that name.*** It is the
> reachability equivalent of the blunt grep, and it fails in the safe-looking direction: toward
> declaring things reached.

**Logged as `STEP-13`, owner me.** Not fixed here — it changes a tool four L4 tests depend on, and
**noticed something adjacent is a new unit, not a silent fix.**

---

## 3 · The corrected inventory — 24 functions in 14 of 35 modules

| Module | Count | Functions (`t` = test callers) |
|---|---|---|
| ⛔ `spine` | **5** | `materialize`(t7), `claim_due`(t2 — §2), `logical_dedupe_key`(t6), `record_materialization_failure`(t1), `recover_expired_claims`(**t0**) |
| `lane_recall` | 3 | `recall_verdict`(t5), `low_confidence_is_never_silent`(t3), `every_lane_is_visible_or_deliberately_silent`(t1) |
| `rate_limiter` | 3 | `hour_recipient_key`(t3), `reserve_slot`(t5), `release_slot`(t1) |
| `push` | 2 | `push_card_to_agents`(**t0**), `push_action_to_agents`(t1) |
| `retry` | 2 | `next_attempt_at`(t5), `may_cross_channel_failover`(t2) |
| `card_builder` | 1 | `resolved_person_name`(**t0**) |
| `gate` | 1 | `describe_decision`(**t0**) |
| `presence` | 1 | `absent`(t11) |
| `claim_validator` | 1 | `observed_claims`(t1) |
| `claims` | 1 | `by_state`(t1) |
| `outbox` | 1 | `revive_undeliverable`(t1) |
| `routing` | 1 | `is_agent_transport`(t1) |
| `scheduler` | 1 | `schedule_order`(t1) |
| `units` | 1 | `get_unit`(t2) |

**24 of 123 top-level public functions — 19.5% of the layer's public surface is not called by
production code.**

---

## 4 · The three kinds, and the one that matters most

### 4.1 ⛔ The v2 spine — **all five functions, the entire path**

`materialize` · `claim_due` · `logical_dedupe_key` · `record_materialization_failure` ·
`recover_expired_claims`. Nothing in the engine calls **any** of them. 21 test callers across four, and
**zero** for the recovery.

⛔ **This is F7 at its true size, and it makes F7 stronger rather than weaker.** The re-cross-check said
the v2 path is un-cut-over on the evidence of `claim_due` plus `outbox.py:838`. The measurement now shows
it directly: the whole path, every entry point, with tests and no production caller. **An un-cut-over
path is exactly what that looks like from the AST**, and the only component without even a test is the
one that marks ambiguity.

### 4.2 ⛔ Built, tested, and nothing produces it — **including what this programme built four days ago**

`lane_recall`'s three functions have **9 test callers and no engine caller.** That is M13 `STEP-02`, the
recall guard, written on 2026-09-30 to *"prove nothing died quietly"*.

> ⛔ **It proves nothing on a tick, because nothing calls it.** `lane_recall.py`'s own header records
> that the unit was **rewritten** — *"THIS UNIT WAS REWRITTEN… A CORRECTION TO THE PLAN"* — and the
> rewrite produced a guard that is invoked by its tests and by nothing else. **The ninth instance of
> built-tested-green-and-called-by-nothing, and the second this programme created itself.**

`presence.absent` (11 test callers) is the Phase-2 presence resolver's absence path, same shape.
`claim_validator.observed_claims` and `claims.by_state` are M13 `STEP-03`/`STEP-04` surfaces.

### 4.3 Helpers whose only caller is a test — **and these need triage, not assumption**

`rate_limiter.reserve_slot` · `release_slot` · `hour_recipient_key` · `retry.next_attempt_at` ·
`may_cross_channel_failover` · `scheduler.schedule_order` · `routing.is_agent_transport` ·
`units.get_unit` · `outbox.revive_undeliverable` · `push.push_action_to_agents`.

⛔ **Some of these look like things the outbox ought to be calling.** A rate limiter whose
`reserve_slot` has no production caller is either a limiter that does not limit, or a limiter reached by
a different route than the one its name suggests. **Nineteen functions, nineteen separate questions, and
guessing at any of them is how a declaration becomes decoration.**

---

## 5 · ⛔ What this does to STEP-05's scope

STEP-05 planned **4 entries**. The guard it specifies — *every unreached public function is declared* —
cannot ship with 4 declared while 20 are not: the test would fail on the remainder, and the only ways
out are declaring the rest without reading them, or narrowing the guard to the 4. **The first is
decoration. The second is weakening a verify to make it pass.** Neither is available.

### ⛔ And the split I first proposed was wrong, for the reason stated one paragraph above it

I wrote that STEP-05 should become a level — **05a** shipping the module, the guards and the 4
untested-and-unreached entries, and **05b** triaging the other 20. That is incoherent: *05a's guard
cannot be green with 20 functions undeclared.* The only ways to make it green are to declare the 20
without reading them, or to narrow the guard's scope to the 4 — **the exact two options I had just
ruled out as decoration and as weakening a verify.** The split would have smuggled one of them in under
a step number.

> **A decomposition that makes a step shippable by shrinking its guard has not decomposed the work; it
> has decomposed the guard.** The unit is defined by what its verify must prove, so a unit whose verify
> cannot pass without the triage **contains** the triage.

**So STEP-05 stays one step, and the triage is its work** — 24 entries, each read before it is
declared. It is larger than an hour and that is the honest size of it:

| | | Verify |
|---|---|---|
| **STEP-05** | `deliver/delivery_health.py` + the guards + the engine-only convention asserted in code + ⛔ **all 24 entries triaged, each with a reason and a mover** | the new test file passes with the **full** table |
| **STEP-13** | the `called_names` name-collision defect (§2) | a test proving a same-named method does not mask a function |

⛔ **The triage is the real work of this layer, and it was invisible until the measurement was done
correctly.** Twenty-four functions, each needing its own answer to *"why does production not call
this?"* — and `lane_recall` already shows the answers will not all be benign.

---

## 6 · What is NOT corrected

Everything else in the re-cross-check stands, and two items are **strengthened** by this audit:

| | |
|---|---|
| **F7** — the v2 spine is un-cut-over, and the recovery is an unguarded cutover rather than a live double-send | ⛔ **strengthened.** All five spine functions are unreached by production, which is what un-cut-over looks like from the AST |
| **F8** — `deliver/` is the only large package with no declared silence | ⛔ **strengthened.** The gap is 24 functions, not 4 |
| **F9** — 2 receipts for 9,431 lines | unchanged |
| ⛔ **CORRECTED 2026-10-02** | ⛔ **NO LONGER UNCHANGED** — F9's count was wrong. `L5` is a hand-written LABEL, not a package. `deliver/`'s four tables are guarded by **8** receipts (4 labelled `L5` + 4 labelled `L6`); before YCW27 by **5**, of which **4 worked**. **1,886** lines per guard, not 4,715 — and 1,886 was already true before this pass began. → [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md) |
| **F10** — two stale comments | unchanged |
| **F11** — `resolved_person_name` | unchanged, and it is one of the 4 untested |
| **F12/F13** — three superseded Atlas badges, and the Layer 5.2 omission | unchanged |

---

## 7 · The doctrine this audit produced

| Rule | Where it came from |
|---|---|
| ⛔ **a reachability number is meaningless without its source set** | §1 — mine was stated without one, and a document cannot check a convention |
| ⛔ **a call resolved by name alone is a call to any function with that name** | §2 — `queue.claim_due()` in `capture/` hid the spine's |
| **a measurement that corrects its own plan is the plan working, not the plan failing** | §5 — the scope tripled before a line was written, which is the cheap moment |
| **the stricter number is not the safer number** | §1 — reporting 4 instead of 24 understated the gap by a factor of six, and both deviations erred toward reporting fewer problems |
