# Step 5 — DONE · `deliver/` declares what it does not call

**Unit:** `M13.C3.U05` · **Owner:** me · ✅ **2026-10-01** · 16 tests · 8 mutations

## 1 · What is there

Three of the four large packages state in code what they deliberately do not do:

| Package | Declaration |
|---|---|
| `reason/` | `unit_health.py` — four grains, `neutral_default_boundary()`, `REASONING_ERAS` |
| `context/` | `lane_health.DORMANT_LANES` |
| `executive/` | `unreached.py` — `UNREACHED` (5), `PULL_ONLY` (4), each with a reason **and a mover** |
| **`deliver/`** | ⛔ nothing |

Measured with L4's own tooling (`executive/unreached.public_functions` + `.called_names`, which resolves
aliased imports) over all 40 files:

```
123 top-level public functions · 24 reached by nothing · 0 declared
   of the 24, 4 have no test caller either    (⛔ corrected — see 06-AUDIT)
```

## 2 · Why this is the first step and not the last

The four unreached functions are **four different kinds of thing** — an unguarded cutover, a PULL_ONLY
surface, a measured defect whose fix was never wired, and an unlogged record. Steps 06–09 each resolve
one. They all need somewhere to write the resolution down, and a reader of the package today cannot tell
any of the four apart from an oversight.

⛔ **L4 proved the shape is load-bearing**: `executive/unreached.py` is where `summary.build_summary` was
caught sitting in `PULL_ONLY` after it had quietly acquired a producer, and where `monitor.blocking_action`
was deleted the moment it was wired. A declaration that nothing checks rots in exactly that way.

## 3 · What to build

| | |
|---|---|
| `genios_engine/deliver/delivery_health.py` | ⛔ NEW. `UNREACHED` and `PULL_ONLY` tables, each entry carrying the function, the reason **and the mover**, in `unreached.py`'s shape. Plus `public_functions()` / `call_sites()` / `called_names()` / `undeclared()` / `missing()` over `deliver/` |
| `tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py` | ⛔ NEW |

⛔ **Reuse, do not re-implement.** `executive/unreached.py` already has the AST walk, including the
aliased-import resolution that a naive `called_names` gets wrong. `delivery_health.py` imports the
helpers and supplies its own tables, or the two will disagree the first time one is fixed.
**Check the layer topology first** — `tests/test_layer_topology.py` fails the build on an upward import,
and L5 importing from L4 is exactly that. ⛔ **If the import is upward, the helpers move to
`platform/` and both packages import them from there.** That is a real possibility and the step must
measure it before writing a line.

## 4 · The tests, and the three ways this guard gets written wrongly

| Test | The failure it exists for |
|---|---|
| `test_every_unreached_public_function_is_declared` | the whole point |
| `test_no_declared_entry_names_a_function_that_does_not_exist` | ⛔ **declared and written are two directions; one alone is half a guard** |
| `test_no_pull_only_surface_has_quietly_acquired_a_producer` | ⛔ L4's actual bug — a `PULL_ONLY` entry that became stale when something started calling it |
| `test_every_entry_names_a_mover` | `reason/unit_health.DeclaredSilence` refuses construction without one, for the same reason |
| `test_the_declaration_is_reached_by_the_walk_it_describes` | ⛔ the M2 mutation shape: a table that is imported but never used by the assertion |

⛔ **Not a blunt grep.** This programme has been bitten **fifteen** times by a substring check matching
the author's own prose. The reachability test walks the AST and excludes the docstring **by identity**
(the function's first statement), never by value — `ast.get_docstring()` returns cleaned text while the
node holds raw, and excluding by value lets it through.

## 5 · Verify

```
.venv/bin/pytest tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py -q
.venv/bin/pytest tests/test_layer_topology.py -q
```

## 6 · Mutations this step must survive

| # | Mutation | Must go red |
|---|---|---|
| M1 | delete one entry from `UNREACHED` | `test_every_unreached_public_function_is_declared` |
| M2 | add an entry for a function that does not exist | the second-direction test |
| M3 | make the walk return `frozenset()` | the "reached by the walk it describes" test |
| M4 | drop the mover from one entry | `test_every_entry_names_a_mover` |

## 7 · Expected outcome

`deliver/` can be read by somebody who did not write it, and every function nothing calls says which of
the four kinds of thing it is. Steps 06–09 have somewhere to record their answers.


---
---

# ✅ DONE — 2026-10-01

## 1 · What was expected

A declaration module for `deliver/`'s **4** unreached public functions, in `executive/unreached.py`'s
shape, plus the guards that keep it honest.

## 2 · ⛔ What the first measurement changed, before a line was written

The step's own first instruction was to measure, and the measurement found **the step's premise was
wrong**. Recorded in full in
[`06-AUDIT-the-measurement-that-corrected-itself.md`](06-AUDIT-the-measurement-that-corrected-itself.md)
and [`07-AUDIT-the-second-delivery-architecture.md`](07-AUDIT-the-second-delivery-architecture.md):

| | Planned | ⛔ Actual |
|---|---|---|
| public functions | 133 | **123** top-level (133 counted `channels/`) |
| unreached | 4 | ⛔ **24** — 23 reported, plus one the resolver hid |
| tables needed | 1 | ⛔ **3** — the 24 are three different kinds of thing |
| entries triaged | 4 | **24**, each read before it was declared |

**The "4" was a real number answering a different question** — functions with no caller anywhere,
*including tests*. L4's convention is engine-only callers, which gives 24. Two deviations, both toward
reporting fewer problems.

## 3 · What was actually built

| | |
|---|---|
| `genios_engine/deliver/delivery_health.py` | ⛔ NEW, 470 lines. Three tables + `PULL_ONLY` + the walk |
| `tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py` | ⛔ NEW, **16 tests** |

### ⛔ Three tables, not one — and the shape IS the finding

```
UNCUT_OVER      11   a second delivery architecture, built beside the running one
UNREACHED        8   deliberate, explained, with a mover
KNOWN_UNWIRED    5   ⛔ defects. Built, correct, SHOULD be called, and are not
PULL_ONLY        1   reached and routed, never pushed  (NOT in DECLARED — those are reached)
                ──
                24   = every unreached public function in deliver/, declared
```

Collapsing them would file a broken product promise next to a shim that raises on purpose, under the
same word. ⛔ **A declaration that cannot distinguish a decision from a defect is paperwork** — and
`KNOWN_UNWIRED` is not a parking lot: every entry names a `STEP-NN`, enforced.

### ⛔ `UNCUT_OVER` carries a tier and a structured `measured_by`

The cutover is a **gradient**, not a gap:

| Tier | Modules | `measured_by` |
|---|---|---|
| 1 · resolution | `presence` (+ `orchestrator.resolve`, `audience`) | ⛔ `outbox.shadow_resolve_v2` |
| 2 · persistence | `spine.materialize` · `logical_dedupe_key` · `record_materialization_failure` | `None` |
| 3 · claiming | `spine.claim_due` · `recover_expired_claims` | `None` |
| 4 · policy | `rate_limiter` ×3 · `retry` ×2 | `None` |

So a cutover decision would rest on evidence about **routing**, while the three tiers that touch the
network have none.

### ⛔ `qualified_call_sites` — the resolver L4's tool needed

`called_names` matches an `ast.Attribute` by `attr`, which correctly resolves aliased imports **and**
let `queue.claim_due()` in `capture/parked/refetch.py:267` count as a call to `deliver/spine.claim_due`.
A whole tier was invisible.

```
qualified_call_sites("spine.claim_due",          engine) -> 0    ⛔ the collision excluded
qualified_call_sites("spine.log_delivery_event", engine) -> 3
qualified_call_sites("outbox.shadow_resolve_v2", engine) -> 1    the intra-module call
```

⛔ **Two resolvers, two directions, and the asymmetry is written down.** The *undeclared* direction keeps
`called_names` on purpose: a false REACHED there only hides a problem from us, while a false UNREACHED
would demand a declaration for a genuinely wired function. Promoting the precise one into
`executive/unreached.py` is **STEP-13**, because it changes a tool four L4 tests depend on.

## 4 · ⛔ Two errors of mine, both caught by the tests I was writing

**The intra-module blind spot.** `qualified_call_sites` required the calling file to *import* the
target, so `outbox.shadow_resolve_v2` — called at `outbox.py:1441`, inside its own file — came back
unreached. It would have reported the one production measurement this package has as dead. *No file
imports itself.*

**A substring check on prose — the sixteenth in this programme.**
`test_the_only_measured_tier_is_the_one_that_sends_nothing` was first written as
`"shadow_resolve_v2" in <the prose field>`, and it **failed on correct data**: the string is present
both when a tier names its measurement and when a tier explains that *"`shadow_resolve_v2` stops at
resolution and never persists."*

> ⛔ The repair was not a cleverer pattern. `measured_by` became a structured field that is `None` or a
> qualified name. **A claim worth asserting is worth storing as data.**

## 5 · The mutations

Eight, every one red, `__pycache__` cleared between each:

| # | Mutation | Result |
|---|---|---|
| M1 | delete one `UNREACHED` entry | 🔴 1 failed |
| M2 | declare a function that does not exist | 🔴 1 failed |
| M3 | make `undeclared()` ignore `DECLARED` | 🔴 2 failed |
| M4 | empty one entry's mover | 🔴 1 failed |
| M5 | file a defect as a declared silence | 🔴 **3 failed** |
| M6 | set a `KNOWN_UNWIRED` step to `"soon"` | 🔴 1 failed |
| M7 | claim tier 2 is shadow-measured | 🔴 1 failed |
| M8 | put `tests/` back into `engine_sources` | 🔴 **3 failed** |

⛔ **M8 is the one that matters**: it re-creates the original error, and three tests now refuse it.
The convention lives in code, not in a document.

## 6 · Verify

```
.venv/bin/pytest tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py -q   # 16 passed
.venv/bin/pytest tests/test_layer_topology.py tests/deliver/ \
                 tests/test_the_executive_says_what_it_does_not_call.py \
                 tests/test_programme_step_status_is_consistent.py -q   # 262 passed, 1 skipped
```

```
.venv/bin/pytest -q      # ⛔ the FULL suite — 14,677 passed · 0 failed · 10m28s
```

    14,661  the baseline when the L5 pass began (after L4)
    14,677  now
    +   16  ⛔ exactly this step's 16 tests. Nothing else moved.

⛔ The topology test is in that list deliberately: `deliver/` (PRODUCT 6) importing
`executive/unreached` (5) is **downward** and legal. The helpers move to `platform/` when a **third**
package needs them — two users is an import, three is an extraction.

## 7 · Findings this step produced, which the plan did not have

| | Step |
|---|---|
| ⛔ `lane_recall` is an orphan module — the recall guard this programme built on 2026-09-30, 24 tests, referenced by **three comments** and imported by nothing | **STEP-14** |
| ⛔ `outbox.revive_undeliverable` — a stated product promise (*"a card must become deliverable the moment a channel exists"*) with no caller | **STEP-15** |
| ⛔ `rate_limiter.py` implements a per-recipient hourly ceiling and nothing imports it; the live `budget` rule is per-rule-daily, a different question | **STEP-16** · Rohit |
| ⛔ `called_names` resolves by bare name, so a same-named method masks a function — and L4's own table uses it | **STEP-13** |
| `routing.is_agent_transport` and `units.get_unit` have **no docstring**, so why they are unreached is recorded nowhere | declared as undocumented, flagged for Harsh |

## 8 · Doctrine

| Rule |
|---|
| ⛔ **a reachability number is meaningless without its source set** |
| ⛔ **a call resolved by name alone is a call to any function with that name** |
| ⛔ **a claim worth asserting is worth storing as data** |
| ⛔ **a declaration that cannot distinguish a decision from a defect is paperwork** |
| **a decomposition that makes a step shippable by shrinking its guard has decomposed the guard** |
| **no file imports itself** |
