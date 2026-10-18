# Step 17 — DONE · nine packages nobody asked the question

**Unit:** `M13.C3.U17` · **Owner:** me · ✅ **2026-10-01** · 71 tests
⛔ **Planned as nine units. It became ONE guard over eleven packages — and the scope fell from 147 to 109 before a single entry was written.** Full measurement:
[`../18-AUDIT-the-engine-wide-reachability-gap.md`](../18-AUDIT-the-engine-wide-reachability-gap.md)

## 1 · What is there

**147 top-level public functions in `genios_engine/` are not called by production code and are
declared nowhere.**

```
context 48 · reason 29 · platform 26 · feedback 17 · capture 8 · contracts 8 · mcp 5 · packs 3 · api 3
```

| | |
|---|---|
| hidden by the old resolver's name collapse | **18** |
| ⛔ **visible to both resolvers all along** | **129** |

⛔ **So this was never mainly a tool problem.** Only `executive/` and `deliver/` have a reachability
guard. `reason/unit_health.py` and `context/lane_health.DORMANT_LANES` declare *lanes and eras*, not
functions — nine packages have never been asked.

> ⛔ **A guard that exists in two places out of eleven reads, from either of those two, as a solved
> problem.**

## 2 · ⛔ Why this is a level and what the units are

L5's 24 took a full triage pass — reading each function, writing a reason and a mover — and produced
**five** real steps. 147 is six times that, across nine packages with nine different situations.

**Data-flow order, one unit each:**

| Unit | Package | Count | Known shape |
|---|---|---|---|
| `U17a` | `capture/` | 8 | smallest. The right place to prove the generalised guard |
| `U17b` | `context/` | **48** | ⛔ largest. Already holds `lane_health.DORMANT_LANES`, so the two declarations must not disagree |
| `U17c` | `packs/` | 3 | trivial |
| `U17d` | `reason/` | 29 | ⛔ already holds `unit_health.py` — the guard goes **into** it, not beside it |
| `U17e` | `feedback/` | 17 | L6/L7. ⛔ `outbox.py:804` records that L7 was starved of DeliveryFacts for months; expect related silences |
| `U17f` | `platform/` | 26 | ⛔ **blocked on the `scripts/` decision — §4** |
| `U17g` | `contracts/` | 8 | ⛔ `contracts/` may depend only on platform and stdlib, so the guard's import direction must be checked first |
| `U17h` | `api/` | 3 | ⛔ **after** the decorator exclusion is in the shared machinery |
| `U17i` | `mcp/` | 5 | `mcp` is in `CROSS_CUTTING`, not `LAYERS` — it escaped the import ratchet once already |

⛔ **`U17a` first, and not because it is smallest** — because the generalised guard has never run
against a package that has no declaration module at all, and proving the machinery on 8 functions is
cheaper than discovering its shape is wrong on 48.

## 3 · ⛔ What must be extracted, not copied

| | |
|---|---|
| the resolver | ⛔ already shared: `STEP-13` promoted it into `executive/unreached.py` and `deliver/delivery_health.py` imports it. **Two users is an import, three is an extraction** — at eleven packages the target is `platform/` |
| the AST walk | `public_functions` / `qualified_call_counts` / `undeclared` / `missing` / `now_called` |
| ⛔ the table SHAPES | L5 needed **three** (`UNCUT_OVER`, `UNREACHED`, `KNOWN_UNWIRED`) and L4 needed two. **A package gets the tables its triage needs**, not a fixed set — *a declaration that cannot distinguish a decision from a defect is paperwork* |
| the test | one per package, each asserting its **own** source set in code |

⛔ **The import direction has to be measured before anything moves.** `tests/test_layer_topology.py`
fails the build on an upward import, `contracts/` may depend on platform and stdlib only, and
`capture/` is layer 1 — so it cannot import `executive/` (5). **`platform/` is `CROSS_CUTTING`, which
is why it is the target**, but that must be confirmed rather than assumed.

## 4 · ⛔ Two decisions this level needs before `U17f`

**Is `scripts/` production?** A function whose only caller is `scripts/runtime_receipts.py` reads as
unreached. ⛔ Excluding `tests/` is already settled — *a test is not a caller* — and `scripts/` is the
same question with a different answer available: a CLI that ops actually run is closer to production
than a test is. `platform/`'s 26 are the most likely place for this to matter.

**What counts as a caller for a decorator-registered function?** 25 route handlers have no Python
caller by design. The exclusion is pinned in
`tests/executive/test_a_call_resolved_by_name_is_not_a_call.py` and must move into the shared
machinery **before** `U17h`. ⛔ Asking `api/` for 25 declarations that all say *"a route handler has
no Python caller"* is paperwork, and discovering that after writing them is the expensive order.

## 5 · What this level does NOT do

| | Why |
|---|---|
| ⛔ declare all 147 | **147 is not 147 defects.** L5's 24 were 12 un-cut-over, 7 deliberate, 5 defects — and `deliver/` was unusual in carrying a second architecture. Extrapolating is the mistake this audit exists to prevent |
| add a global count guard | ⛔ count guards are **per layer**, never global. `test_activation_changes_the_pass.py`: *"the cheap fix for that is to bump the number, which is how a decision gate becomes a rubber stamp"* |
| delete anything | a public function with no caller is not dead. L5 found a shim that **raises on purpose** and must never be wired |
| run before L5's own steps finish | ⛔ `STEP-06` … `STEP-16` are L5's, and this is nine other packages. **It is the last thing in the programme, not the next** |

## 6 · Verify (per unit)

```
.venv/bin/pytest tests/<pkg>/test_<pkg>_says_what_it_does_not_call.py -q
.venv/bin/pytest tests/test_layer_topology.py -q
.venv/bin/pytest -q                     # ⛔ the FULL suite, per unit
```

## 7 · Expected outcome

Every package states what it does not call, with a reason and a mover per entry, and the question
*"is production supposed to call this?"* becomes answerable from the code in all eleven packages
rather than two.

⛔ **And the honest expectation about findings:** a minority of the 147 will be defects, most will be
helpers, seams and deliberate decisions — and **which is which is not knowable before the triage.**
That is the whole reason the level exists.


---
---

# ✅ DONE — 2026-10-01

## 1 · ⛔ The scope fell from 147 to 109, and every subtraction was a measurement

```
147   engine-only callers, nothing excluded
134   - 13   `scripts/` counts as a caller          every one of the 13 a diagnostic or ops read
123   - 11   declaration modules exclude themselves the rule L4 and L5 already used
109   - 14   decorator-registered route handlers    no Python caller, by design
```

⛔ **And then 46 of what remained were wired by REFERENCE** — `Depends(f)`, a dispatch table, a
registry. **Had the 123 been declared without that measurement, 46 of the entries would have been
lies**, each reading as a considered decision about live code.

## 2 · ⛔ FOUR wiring mechanisms, and the fourth cannot be measured at all

| | Mechanism | How it is handled |
|---|---|---|
| 1 | `f()` — a **call** | `qualified_call_counts`, keyed `(module, name)` |
| 2 | `@router.get(...)` — a **decorator** | `decorated_functions`, dropped before the scan |
| 3 | ⛔ `Depends(f)` · `{"k": f}` · `key=f` — a **reference** | `qualified_value_refs` — **the biggest one** |
| 4 | ⛔ `store.purge_expired()` — **duck-typed dispatch** | ⛔ **impossible statically. Hand-checked, every entry** |

⛔ **Mechanism 3 is the dominant pattern in this engine: REGISTRY WIRING.** `platform/auth.
require_owner` has **35** references and zero calls; `get_auth_ctx` 29; `require_admin` 25.
`context/outreach_situations.read_*_for_dispatch` — twelve of them, one reference each.
`feedback/units.unit_*` — twelve. `mcp/server.tool_*` — five, which took **`mcp/` to zero** and means
it needs no declaration module at all.

⛔ **Mechanism 4 produced exactly one rescue and sixteen false alarms.** `realtime.purge_expired`
looked unreached, claimed *"(maintenance heartbeat)"* in its own docstring, and **is called** at
`api/routes.py:964` as `store.purge_expired()` behind a `hasattr`. **Retention IS enforced**, and
I was one grep away from recording the sixth instance of *a stale comment reads as a measurement* —
falsely. The other sixteen candidates were name collisions: `list.extend` with **96** apparent hits,
`Path.resolve` with **74**, `.read()` with 8.

> ⛔ **A function reached by duck-typed dispatch looks identical to one nobody calls, and only the
> call site can tell them apart.** That is a property of the language, not a gap in the tool.

## 3 · The machinery moved, and the trigger was sharper than "a third user"

`deliver/delivery_health.py`'s own note said it: *"they move to `platform/` when a THIRD package
needs them, not before: two users is an import, three is an extraction."*

⛔ **The real trigger was the layer topology.** `capture/` is PRODUCT layer **1** and `executive/` is
5, so `capture/ -> executive/` is an UPWARD import `tests/test_layer_topology.py` fails the build
over. **The eleventh package could not have imported the machinery from where it was.**

`platform/reachability.py` imports **nothing from the engine** — pure `ast` and `pathlib` — because a
reachability tool that imported a layer could not be used by the layer below it.

### ⛔ And the extraction is proven faithful, set for set

```
executive/ : the shared walk == UNREACHED  (10)     ✅ same SET, not same count
deliver/   : the shared walk == DECLARED   (22)     ✅
capture/   : the shared walk == UNREACHED  ( 7)     ✅
```

## 4 · ⛔ ONE guard over eleven packages, not nine copies of a test

`§2` of the plan called this *"a level, one unit per package"*. It is one module:
`tests/platform/test_every_package_says_what_it_does_not_call.py`, **58 tests**, parametrised over a
registry of the ten declaration modules.

⛔ **And that is what makes a NEW package forgetting its declaration a build failure** —
`test_no_package_is_missing_its_declaration` walks `LAYERS | CROSS_CUTTING` and demands an entry.
**Nine hand-written copies could never have caught the eleventh package**, which is the exact state
all of them were in before this step.

## 5 · The eight new declaration modules

| Package | Module | Entries | Shape |
|---|---|---|---|
| `capture/` | `capture_health.py` | 7 | one table — tooling and reports |
| `context/` | `context_health.py` | **22** | one table — ⛔ the biggest cluster of *built, heavily tested, unwired* |
| `packs/` | `pack_health.py` | 3 | one table — one corpus report |
| `reason/` | `reasoning_health.py` | 14 | one table — beside `unit_health.py`, which answers a different question |
| `feedback/` | `feedback_health.py` | 5 | one table — two are build-time property guards |
| `platform/` | `platform_health.py` | 15 + **1** | ⛔ **two** tables — the second for the duck-typed rescue |
| `contracts/` | `contract_health.py` | 8 | one table — both-directions guards and projections |
| `api/` | `api_health.py` | 2 | one table — ⛔ a pair that says the policy enforcement path does not exist |
| `mcp/` | — | **0** | ⛔ needs none: all five were registry references |

```
109 declared entries engine-wide   (77 new + executive 10 + deliver 22)
```

⛔ **`platform/` needed a second table because putting a REACHED function into `UNREACHED` would be
a lie by that table's own name.** `deliver/` needed four, `capture/` one. **A package gets the tables
its triage needs**, and `test_a_package_gets_the_tables_its_triage_needs` asserts the shapes *differ*
rather than demanding they match — because an empty table asserts nothing, and a table that asserts
nothing teaches a reader to skip the ones that do.

## 6 · ⛔ The findings the triage produced

### ⛔⛔ The sharpest one, and the codebase had already written it down

`capture/acquire/need_executor.py:3` — *"`context/evidence_need_store.py` files needs.
`evidence_need.execute()` works ONE need. **Nothing ran**"* — and at `:125`, naming
`read_open_needs`: **"which this layer may not import."**

**`capture/` is layer 1 and `context/` is 2, so the EvidenceNeed executor cannot read its own
queue.** The chain is four functions — `read_open_needs`, `close_need`, `needs_from_holds`,
`resolve_hold` (⛔ **22 test callers, the most of any unreached function in the engine**) — and it is
broken **at a layer boundary**, not by an oversight.

⛔ **The Atlas listed EvidenceNeed as VERIFIED MISSING at the start of this programme.** It was built
since and never connected, and the seam decision has exactly two shapes: lift the queue read into
`platform/` (what the reachability machinery just did), or invert it so `context/` pushes down.

### The rest, by weight

| | Finding |
|---|---|
| ⛔ `reason/situation_reasoner.clamp_confidence` | *"R-1'S LAW, VERBATIM: IT CANNOT RAISE CONFIDENCE"* — 7 test callers, and the live reasoner clamps **inline**. **Two implementations of a one-way law is the shape that lets one of them start raising** |
| ⛔ `context/situation_bso.gather_l1_signals` | *"THE READ THIS MODULE EXISTED WITHOUT"* — 15 test callers, zero production. **The module still exists without it**, and the capitals read as fixed |
| ⛔ `platform/l*_activation.deactivate` ×2 | **the rollback halves of live features.** A feature an operator can enable through a surface can only be disabled from a Python shell |
| ⛔ `api/` — the pair | `policy_routes.evaluate` says *"kept importable for a **future** enforcement path"*; `approval_routes.enqueue` says *"**Called from** the policy enforcement path"*. **One is honest about the tense.** ⛔ Not L4's `requires_approval`, which is a live FIELD — *two implementations of one word can be two different questions* |
| ⛔ `platform/l3_activation.is_l3_activated` | calls itself *"The hot-path read"* and no path reads it — **superseded in place** by a batched read the module's own `:274` calls *"distinct from calling `is_l3_activated` three times"* |
| ⛔ `contracts/brain_address.build_address` | exists *"so no producer can forget"* a token, and **all three producers bypass it**. The token IS present today — so the guarantee is kept by **discipline rather than by construction** |
| ⛔ `reason/baselines.load_baselines` | a *"back-compat"* shim with **no callers, no tests, not even a script**. **Nothing is compatible with it any more** — the clearest delete candidate in the programme |
| ⛔ `platform/funnel` ×3 reads | five counters written every pass, **three reads with no reader** — which is why `19-PENDING` quotes the funnel by hand |
| ⛔ 6 functions with **nothing anywhere** | `source_registry.is_buildable`, `calibrate.muted_rules`, `learned_state.may_consume`, `canon.anchoring_node_types`, `plan.describe_plans`, `analytics.stats` — no docstring, no test, no caller. ⛔ **Declared as undocumented**: a guessed reason is decoration and a guessed severity is worse |

## 7 · ⛔ Three faults of mine, all caught before they shipped

**The self-exclusion was a hand-maintained list for about a minute.** `SELF_DECLARING` named the
declaration modules; the first thing I did after writing it was add `capture_health.py` and forget
its name, so the scan demanded that module's own four helpers as declared silences. ⛔ **A list you
must remember to extend is a list that will be wrong** — and the evidence arrived within the minute.
It is now **derived**: a declaration module is one that imports `platform/reachability.py`.

**The generic mover check demanded two long strings and failed on two correct tables.**
`executive/PULL_ONLY` is keyed `(route, why)` and a route is eleven characters; `deliver/UNCUT_OVER`
is a four-tuple with `None` for every unmeasured tier. ⛔ **The tables deliberately differ in
shape**, so a generic guard may only assert what is actually common.

**And the decorator check took a UNION across `api/` instead of going per module** — so a plain
`evaluate` in `policy_routes` collided with a decorated `evaluate` elsewhere and the test failed on
correct code. ⛔ **The same name-collision class the qualified resolver exists to fix, reproduced in
the test that documents it.**

## 8 · Verify

```
.venv/bin/pytest tests/platform/test_every_package_says_what_it_does_not_call.py -q   # 58 passed
.venv/bin/pytest tests/capture/test_the_capture_layer_says_what_it_does_not_call.py -q # 13 passed
.venv/bin/pytest tests/test_layer_topology.py -q    # capture -> platform is legal; -> executive is not
.venv/bin/pytest -q                                 # ⛔ 14,846 passed · 0 failed · 10m46s
```

    14,775   the baseline when STEP-17 began
    14,846   now
    +    71  ⛔ exactly this step's tests — 13 for capture/, 58 for the engine-wide guard.
             Nothing else moved.

## 9 · Doctrine

| Rule |
|---|
| ⛔ **a function is reached four ways and only three can be measured** — call, decorator, reference, and duck-typed dispatch |
| ⛔ **a reference is a wiring mechanism** — 46 of 123 were wired by one, and declaring them would have been 46 lies |
| ⛔ **a list you must remember to extend is a list that will be wrong** |
| ⛔ **one guard over eleven packages catches the twelfth; nine copies catch none of it** |
| **a package gets the tables its triage needs — an empty table asserts nothing** |
| **the layer topology, not the user count, is what forces an extraction** |
| **a guessed reason is decoration and a guessed severity is worse — an honest "nobody wrote this down" is a declaration** |
