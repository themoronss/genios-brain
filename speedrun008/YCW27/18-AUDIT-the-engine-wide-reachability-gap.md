# Cross-cutting audit · the engine-wide reachability gap — 147 functions nobody declared

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01. **Found by:** L5 `STEP-13`.
**Scope:** every package under `genios_engine/`. **No code written for this; it is a measurement.**

This is the largest single finding in the YCW27 programme, and it is not a list of bugs. It is the
answer to a question that had only ever been asked of two packages out of eleven.

---

## 1 · The number

**147 top-level public functions in `genios_engine/` are not called by production code and are
declared nowhere** — ⛔ **109 after all four wiring mechanisms were measured (§5b, §5c), of
which 46 turned out to be wired by reference. CLOSED 2026-10-01.**

| | |
|---|---|
| hidden by a name collision in the old resolver | **18** |
| ⛔ **visible to both resolvers all along** | **129** |
| decorator-registered (route handlers — correctly uncalled by Python) | 25, **excluded** |
| already declared by `executive/unreached.py` and `deliver/delivery_health.py` | 36, **excluded** |

```
context   48      reason  29      platform 26      feedback 17
capture    8      contracts 8     mcp       5      packs     3      api  3
```

⛔ **So this was never mainly a tool problem.** `STEP-13` fixed a resolver that was hiding 18 of them.
The other **129 were always visible, and nobody had a guard to see them with.**

---

## 2 · Why only two packages were ever asked

| Package | What it declares | Does it inventory unreached functions? |
|---|---|---|
| `executive/` | `unreached.py` — `UNREACHED` (10), `PULL_ONLY` (4) | ✅ yes, AST-walked, both directions |
| `deliver/` | `delivery_health.py` — 26 entries in three tables | ✅ yes, since 2026-10-01 |
| `reason/` | `unit_health.py` — four grains of silence, `REASONING_ERAS` | ⛔ **no** — it declares *lanes and eras*, not functions |
| `context/` | `lane_health.DORMANT_LANES` | ⛔ **no** — same shape, about lanes |
| `capture/` · `packs/` · `feedback/` · `platform/` · `contracts/` · `api/` · `mcp/` | — | ⛔ nothing |

> ⛔ **The two declaration modules that exist were both written in response to a finding.** Nobody
> generalised the guard, because each was built to answer *"what does THIS layer not do"* — and a
> guard that exists in two places out of eleven reads, from any one of those two, as a solved
> problem.

---

## 3 · ⛔ 147 is NOT 147 defects, and the evidence for that is L5's own triage

`deliver/` had 24. Read one at a time, they were:

| | | Share |
|---|---|---|
| an **un-cut-over architecture** — a complete v2 control plane beside the running one | 12 | 50% |
| **deliberate**, explained, with a mover — including a shim that raises on purpose | 7 | 29% |
| ⛔ **defects** — built, correct, should be called, and are not | 5 | 21% |

⛔ **Extrapolating 21% onto 147 would be exactly the mistake this audit exists to prevent.** `deliver/`
was unusual: it is the only package carrying a second architecture. `context/`'s 48 are more likely
pure helpers, re-exported APIs and test seams; `platform/`'s 26 include activation and crypto
utilities whose callers may be scripts rather than engine code — ⛔ and `scripts/` is **not** in the
source set, by the same rule that excludes `tests/`.

**What is certain is the shape of the ignorance, not the size of the problem:** for 147 functions,
nobody can say from the code whether production is supposed to call them.

---

## 4 · The 18 the old resolver hid, with their apparent caller counts

These read as REACHED because `called_names` counted by name alone, so any method of the same name
anywhere in the engine voted for them.

| Package | Function | apparent callers |
|---|---|---|
| `context` | `domain_spec.extend` | ⛔ **96** — `list.extend` |
| `contracts` | `situation_stages.resolve` | ⛔ **48** — `Path.resolve` and others |
| `api` | `approval_routes.enqueue` · `policy_routes.evaluate` | 11 each |
| `platform` | `l2_activation.deactivate` · `l3_activation.deactivate` · `realtime.purge_expired` | 4 each |
| `feedback` | `attribution.route` | 3 |
| `context` | `lane_health.undeclared` · `slice_silence.reason_for` · `tenant_profile.declare` | 1 each |
| `reason` | `situation_binding.undeclared` · `uncited_lanes.undeclared` · `baselines.load_baselines` · `telemetry.aggregate` | 1 each |
| `packs` | `substrate_demand.measure` | 1 |
| `platform` | `crypto.generate_key` | 1 |
| `contracts` | `learned_state.snapshot` | 1 |

⛔ **The pattern is the names.** `read`, `stop`, `resolve`, `extend`, `route`, `measure`, `declare`,
`snapshot`, `aggregate`, `evaluate` — the shortest and most natural names in the codebase are the
ones a name-keyed resolver cannot see. **A call resolved by name alone is a call to any function with
that name**, and the failure direction is *reached*: the direction that reports fewer problems.

⛔ **Three of the 18 are `*.undeclared`** — `lane_health`, `situation_binding`, `uncited_lanes` — the
own-walk functions of declaration modules, which are test-facing by design. Five functions named
`undeclared` existed and one call somewhere made all five read as reached. **The purest possible
illustration of the defect, inside the declaration machinery itself.**

---

## 5 · ⛔ The limitation any engine-wide guard must know before it is written

**25 public functions are registered by a decorator** — FastAPI route handlers. The framework calls
them; Python code does not. Both resolvers correctly return zero qualified callers.

So a naive engine-wide guard pointed at `api/` **reports a working HTTP surface as dead**, and
`api/` would be asked for 25 declarations that all say *"a route handler has no Python caller."*
`executive/` and `deliver/` have no routes, which is why neither declaration module ever had to care.

⛔ Pinned in `tests/executive/test_a_call_resolved_by_name_is_not_a_call.py::
test_a_decorator_registered_function_has_no_python_caller_by_design`, because **discovering this
after writing 25 declarations is the expensive order.**

⛔ **And a second exclusion is needed and does not exist yet:** `scripts/` is outside the source set,
so a function whose only caller is `scripts/runtime_receipts.py` reads as unreached. That is the same
decision as excluding `tests/` — *a script is not production* — but it has to be stated, because
`platform/`'s 26 are the most likely place for it to matter.

---

## ⛔ 5b · MEASURED 2026-10-01 · the two decisions resolve 24 of the 147 before any triage

`§5` named two decisions this level needs first and did not price them. Both are now measured, and
together they take the scope from **147 to 123** — a sixth of it, for two sentences of policy.

### ⛔ Decision 1 · is `scripts/` production? — **13 functions**

Adding `scripts/` to the source set makes 13 of the 147 reached. **And what they are is the
argument:**

| Package | Function |
|---|---|
| `reason` | `unit_health.undeclared_unwritten` · `written_after_all` · `is_silent` · `undeclared_silent` · `drifted` |
| `reason` | `uncited_lanes.undeclared` · `now_citing` |
| `context` | `lane_health.revived` · `slice_weight.budget_reason` · `slice_weight.weigh_all` |
| `platform` | `l2_activation.activated_orgs` · `stage_timer.count_statements` |
| `capture` | `journey.unclassified_actions` |

⛔ **Every one is a diagnostic or an ops read whose caller is a CLI an operator runs.** That settles
it in the same direction `tests/` was settled, and for the opposite reason: **a test is not a caller
because nobody runs it to learn something about production; a script an operator runs is exactly
that.**

⛔ **But seven of the thirteen are a package's own declaration-module helpers** — `unit_health` ×5
and `uncited_lanes` ×2, the `reason/` equivalents of `delivery_health.undeclared/missing/
now_called`. Those are **self-excluded** once `reason/` gets its own guard, the way `executive/` and
`deliver/` already exclude theirs. **So the `scripts/` decision genuinely resolves SIX; the other
seven were going to resolve themselves.**

### ⛔ Decision 2 · the declaration modules exclude themselves — **11 more**

`tests/test_the_executive_says_what_it_does_not_call.py` already skips `unreached.py` with the
reason written in: *"its callers are this file by design. Scanning it would demand a declared
silence for each of its own helpers — noise that says nothing about the layer."*
`delivery_health.package_functions` does the same. **Applying that existing rule to the other
packages' declaration modules removes 11 more.**

### The scope, after both

```
147   engine-only callers, nothing excluded
134   - 13   scripts/ counts as a caller
123   - 11   declaration modules exclude themselves

    context   41      platform 24      feedback 17      reason  15
    contracts  8      capture   7      mcp       5      packs    3      api 3
```

⛔ **The unit sizes change with it.** `context/` is still the large one at 41; `packs/` and `api/`
are three each and can be done in an hour. **`capture/` drops from 8 to 7 and is still the right
place to prove the machinery**, for the reason `§7` gave: the generalised guard has never run
against a package with no declaration module at all, and proving it on 7 is cheaper than discovering
its shape is wrong on 41.

⛔ **And the 123 is still not a defect count.** L5's 24 were 12 un-cut-over, 7 deliberate, **5**
defects. The only honest prediction is that the proportions will differ per package, because
`deliver/` was unusual in carrying a second architecture.

---

## ⛔ 5c · CLOSED 2026-10-01 · the scope was 109, not 147 — and 46 more were never gaps

`§5b` priced the two policy decisions at 147 → 123. Building `STEP-17` found a **third wiring
mechanism** and then a **fourth that cannot be measured at all**:

```
147   engine-only callers, nothing excluded
134   - 13   `scripts/` counts as a caller
123   - 11   declaration modules exclude themselves
109   - 14   decorator-registered route handlers   ⛔ not priced in §5b
```

⛔ **And 46 of the 109 were wired by REFERENCE** — `Depends(f)`, a dispatch table, a registry —
including `platform/auth.require_owner` with **35** of them, `get_auth_ctx` 29, `require_admin` 25,
twelve `context/outreach_situations.read_*_for_dispatch`, twelve `feedback/units.unit_*` and five
`mcp/server.tool_*`. **`mcp/` went to ZERO and needs no declaration module at all.**

> ⛔ **Had the 123 been declared without that measurement, 46 of the entries would have been lies**,
> each one reading as a considered decision about live code.

⛔ **A fourth mechanism is unmeasurable: duck-typed dispatch.** `store.purge_expired()` on a
variable could be any object's method, so every entry in every table was hand-checked against it.
**One rescue** — `realtime.purge_expired` IS called at `api/routes.py:964` behind a `hasattr`, so
retention is enforced and I was one grep from recording a false *stale comment* finding — and
**sixteen false alarms**, all name collisions (`list.extend` 96 apparent hits, `Path.resolve` 74).

**Final: 109 declared entries across ten declaration modules**, guarded by ONE parametrised test
rather than nine copies — which is what makes a *new* package forgetting its declaration a build
failure. → `layer-5-delivery/STEP-17-DONE-nine-packages-nobody-asked.md`

---

## 6 · What this is NOT asking for

| | |
|---|---|
| ⛔ declaring 147 functions | that is paperwork at scale. L5's 24 took a full triage pass and produced **five** real steps |
| a global count guard | ⛔ count guards are **per layer**, never global — `test_activation_changes_the_pass.py`'s own docstring: *"the cheap fix for that is to bump the number, which is how a decision gate becomes a rubber stamp"* |
| deleting anything | a public function with no caller is not automatically dead. L5 found a shim that **raises on purpose** and must never be wired |
| one step | ⛔ it is a **level** — one unit per package, each with its own triage, in data-flow order |

---

## 7 · What it IS asking for → `layer-5-delivery/STEP-17`

**The guard, generalised, applied one package at a time, in data-flow order** — `capture` → `context`
→ `packs` → `reason` → `executive` ✅ → `deliver` ✅ → `feedback`, then the cross-cutting `platform`,
`contracts`, `api`, `mcp`.

⛔ **The two existing declaration modules become the shared machinery, not two more copies.**
`delivery_health.py` already stopped carrying its own resolver when `STEP-13` promoted it into
`executive/unreached.py` — *two users is an import, three is an extraction*, and at eleven packages
the extraction target is `platform/`.

---

## 8 · The doctrine

| Rule | Where it came from |
|---|---|
| ⛔ **a call resolved by name alone is a call to any function with that name** | the 18, and `claim_due` before them |
| ⛔ **a guard that exists in two places out of eleven reads, from either of those two, as a solved problem** | §2 |
| ⛔ **a declaration can be answering a question the tool cannot ask — and then nothing goes red** | §4 |
| **the shortest names are the least visible** | `read` 11, `resolve` 48, `extend` 96 |
| **a measurement's shape is knowable before its size** | §3 — 147 undeclared is certain; how many are defects is not |
| **a script is not production, and that has to be written down** | §5 |
