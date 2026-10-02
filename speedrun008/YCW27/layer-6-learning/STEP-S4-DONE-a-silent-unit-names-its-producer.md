# S4 — DONE · the Atlas's only LIVE gap was a wrong conclusion, not missing code

**Unit:** `M14.C2.S4` · **Owner:** me · ✅ **2026-10-02** · **23 tests · 8/8 mutations caught**
**Atlas:** Layer 7 gap **#2** — ⛔ **CLOSED, by refutation**
**Plan:** [`08-PLAN-v2-from-the-atlas.md`](08-PLAN-v2-from-the-atlas.md) §5 — *"measure first: build,
or DECLARE"*

---

## 1 · What the plan said, and what the gate found

`08-PLAN-v2` §5 called this **the only fully LIVE Atlas gap** and gated it:

> *"measure first: what `feedback/store.load_batch` actually puts in a `LearningBatch`, and whether
> a stable parent cohort is derivable from it today. ⛔ If it is not, the honest outcome is a
> DECLARED SILENCE with a mover, not a build."*

⛔ **The measurement never reached `load_batch`, because a different question answered it first:
where is Behavior Evolution actually implemented?**

## 2 · ⛔⛔ The answer, and it is not in `units.py`

`genios_engine/packs/brains/__init__.py` says it outright:

> *"Layer 3 · the CONTENT pipelines for the three runtime brains. … Organization, Behavior and
> Adaptive live in `learned_brain_entries` / `temporary_memories` … **This package is the supply
> side.** … The drivers live on the Layer 6 side — `feedback/brain_pipeline.py` (the evidence
> route) and `feedback/org_rule_ingest.py` (the declaration route)."*

```
packs/brains/behavior_distill.py       776 lines   distill()         → LearningTarget.BEHAVIOR
packs/brains/adaptive_lease.py         301 lines   lease_proposals() → LearningTarget.RUNTIME, 7d TTL
packs/brains/org_discovery.py          655 lines   the Organization route
```

And `feedback/brain_pipeline.brain_pipeline_proposals` appends both into the **same weekly run**,
from the line immediately after `run_all_units`:

```python
proposals = list(run_all_units(batch, policy, now))                      # the 11 units
proposals.extend(brain_pipeline_proposals(conn, org_id=org_id, policy=policy, now=now))
```

…each inside a `begin_nested()` savepoint, because *"a bare try/except is not isolation in
PostgreSQL."* And `run_learning` is driven weekly by the heartbeat.

> ⛔⛔ **Atlas gap #2 — *"Direct personalization evolution is missing. Behavior and Adaptive cohort
> builder returns no proposals"* — is CLOSED. Both components are built, wired, isolated and
> scheduled.**

## 3 · ⛔ Then what are the two units? A placeholder that outlived its replacement

```
365cf7a6  2026-08-08  "Layer 6 Phase 3: the ten analysis units + validation"   ← _cohort_candidate
ed1b10c3  2026-09-07  "Layer 3 v2: … the four brains …"                        ← the real producers
```

⛔ **The stub predates the implementation by a month.** The work was built one package down and the
placeholder was never removed or declared, so `ALL_ANALYSIS_UNITS` — the one list a reader scans to
see which Layer 7 components exist — still shows a silent unit where a built component belongs.

## 4 · ⛔⛔ Two readers reached the same wrong verdict from the same evidence

| | |
|---|---|
| the **Atlas** | *"Behavior Evolution \| `units.py:165-175` calls a cohort builder that returns `[]` \| **Stub** \| Stable person/team behavior does not evolve"* |
| ⛔ **this programme, 2026-10-02** | `07-ATLAS-CHECK` filed gap #2 as **"LIVE — and now less visible than the Atlas found it"**, and `S1`'s declaration called it *"the only fully live one"* |

⛔ **And my own "near-miss" note was itself a wrong conclusion.** I wrote *"I was one step from
recording this as CLOSED from the call site alone"* — congratulating myself for not calling it
closed. **It IS closed.** The call site was the wrong evidence in both directions.

> ⛔ **A call site that looks wired is not a wired call site — and a call site that looks DEAD is
> not a dead feature.** The second half cost two readings and nearly a third.

⛔ **One grep made it worse.** `behavior_distill.py:551` contains the sentence *"**NOTHING wires
this adapter today**: `brain_pipeline_proposals` is called with `labeler=None`"* — which is about
the optional **LLM labeler**, not about `distill`. A grep hands over a sentence without its
subject, and that sentence read as confirmation of the Atlas.

## 5 · The outcome: DECLARED, exactly as the gate required — and not deleted

⛔ **The placeholders stay.** Deleting them would take the Atlas's component names out of the
canonical registry, and they cost nothing: they return `()`.

```
genios_engine/feedback/target_policy.py      DELEGATED — {unit: (producer, target, why, mover)}
                                             undelegated_silent_units() · stale_delegations()
                                             broken_delegations()  ⛔ five links
tests/feedback/test_a_silent_unit_names_the_producer_that_does_its_job.py          23 tests
genios_engine/feedback/feedback_health.py    +3 declared silences (build-time property guards)
```

### ⛔ The five links, and why each one is a link

| | Link | What losing it looks like |
|---|---|---|
| 1 | the producer file and function exist | a rename; the registry still lists the component |
| 2 | the producer does work — not `return []`/`()`, **and not a body with no calls** | ⛔ a chain of placeholders reading as a built feature |
| 3 | `brain_pipeline_proposals` calls it | one component silently stops |
| 4 | `run_learning` calls that driver | ⛔ **both** stop, from one deleted line |
| 5 | ⛔ the producer still emits the **declared target** | the SINK changes — whether a proposal expires, waits for a human, or becomes permanent |

### ⛔ Link 5 closes a blind spot in `S1`'s guard

`durable_from_a_measurement()` reads `UNIT_TARGETS`, which is **`units.py`'s registry** — so
"which producer may write which brain" was guarded for eleven units and **unguarded for the two
that actually produce.** ⛔ *A guard that stops at a package boundary catches nothing across it.*

Link 5 walks the producer's **whole module**, not its entry function: both producers build their
`LearningObject` in a private helper the entry function calls, so a function-scoped walk finds no
target and reports every delegation broken. ⛔ **The same mistake as grepping for a keyword
argument, one level up** — and `test_the_resolver_reads_the_module_not_the_function` pins it.

## 6 · The two sinks, and why only one needs a clock

| Producer | Target | Bounded? |
|---|---|---|
| `adaptive_lease.lease_proposals` | **`RUNTIME`** | ✅ `temporary_memories.expires_at` is `NOT NULL`; `LEASE_TTL_SECONDS = 7 * 24 * 3600` clamped to the tenant's `max_runtime_ttl_seconds`; enforced by the column, by `preflight`'s three expiry checks and by `expire_leases` |
| `behavior_distill.distill` | **`BEHAVIOR`** (durable) | ⛔ **correct here** — a behaviour pattern is a **CLAIM** about how a person works, the same category as `unit_pattern_learning`'s ORGANIZATION proposals, and the Atlas's boundary for it is *"population and identity scoped"*, not *"decays and expires"* |

⛔ So `DURABLE_FROM_A_MEASUREMENT` still has **exactly one** entry, and
`test_the_durable_measurement_finding_is_unchanged_by_this_unit` asserts that `S4` did not move
`S1`'s finding while widening its guard.

## 7 · ⛔ One widening I stopped myself from making

`unit_temporary_memory` returns `[]`, and `adaptive_lease` writes exactly its sink — an expiring
runtime directive. I started to add it to `DELEGATED`.

⛔ **The inputs differ.** That unit wants an **explicit human directive** from a structured inbox
that does not exist; `adaptive_lease` **infers** a lease from `card_feedback_verdicts`. **Same
sink, different input**, so one does not do the other's job, and recording it as a delegation would
have been a lie about which capability exists. It stays a declared stub, and its entry now says
why. **Atlas gap #1's residue is real.**

## 8 · The mutation run — and one invalid mutation, reported honestly

```
✅ baseline: 50 passed            (23 from S4 + 27 from S1, run together)

  M1 link 4 — the weekly run stops calling the driver        ✅ CAUGHT
  M2 link 2 — the producer is stubbed to its own signature   ✅ CAUGHT
  M3 link 3 — the driver stops calling the producer          ✅ CAUGHT
  M4 link 5 — the behaviour SINK changes to METRICS          ✅ CAUGHT
  M5 link 5 — ⛔ the LEASE silently becomes a DURABLE row     ✅ CAUGHT
  M6 the shared stub gains a body                            ✅ CAUGHT (9 failed)
  M7 a DELEGATED entry is lost                               ✅ CAUGHT
  M8 link 1 — the producer function is renamed               ✅ CAUGHT

✅ baseline again: 50 passed              8 caught · 0 survived
```

⛔ **`M2` SURVIVED on its first run, and the fault was the mutation.** I appended the stub
`def distill(...)` **before** the real one — and at module level Python's **last** definition wins,
as does `_module_functions`' dict comprehension. So it was dead code, not a stub, and the guard was
right to pass. Moved after the real definition, it is caught.

> ⛔ **An invalid mutation is not a surviving mutation** — and the distinction only exists because
> the harness reported the survival instead of rounding it up. This is `STEP-14`'s lesson holding
> in the opposite direction: that run reported a survivor as caught; this one refused to report a
> non-mutation as a kill.

## 9 · Verify

```bash
.venv/bin/pytest tests/feedback/test_a_silent_unit_names_the_producer_that_does_its_job.py -q  # 23
.venv/bin/pytest tests/feedback tests/platform/test_every_package_says_what_it_does_not_call.py \
    tests/packs -q
.venv/bin/pytest -q                                                                   # FULL suite
```

## 10 · Atlas Layer 7 after `S4`

```
   5 CLOSED            #2 (by refutation) · #7 · #8 · #9 · #10
   3 PARTLY CLOSED     #1 the preference + temporary-memory inboxes · #4 population caps ·
                       #11 the durable ADAPTIVE residue — ⛔ Rohit's
   0 ⛔ LIVE            — none
   3 not yet measured  #3 outcome reconciliation · #5 permitted-use · #6 company reset
```

⛔ **No Atlas Layer 7 gap is fully LIVE any more.**

## 11 · Doctrine

| Rule |
|---|
| ⛔ **a call site that looks DEAD is not a dead feature** — the mirror of the rule `S1` produced, and it cost two readings |
| ⛔ **a grep hands over a sentence without its subject** — *"NOTHING wires this adapter today"* was true about something else |
| ⛔ **a guard that stops at a package boundary catches nothing across it** |
| ⛔ **an invalid mutation is not a surviving mutation** — and only a harness that reports the survival can tell them apart |
| ⛔ **same sink, different input is not the same job** — the widening I did not make |
| **a placeholder that names its replacement is worth more than a deleted one**, because the component name stays in the registry a reader scans |
| **a stub of any shape calls nothing** — the check that catches the shapes an empty-return check cannot |
