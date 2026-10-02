# Step 13 — DONE · a call resolved by name alone

**Unit:** `M13.C3.U13` · **Owner:** me · ✅ **2026-10-01** · 9 tests · 5 mutations
⛔ **It did affect L4: its declared inventory went from FIVE to TEN.**

## 1 · What is there

`executive/unreached.called_names` is the reachability resolver the whole programme uses. It counts an
`ast.Call` whose callee resolves to a name, *"whether called bare (`f()`) or through an attribute
(`mod.f()`)"* — and the attribute branch is deliberate: it is what makes an aliased import resolve
correctly, and its own docstring records that the hand-written grep it replaced *"reported two
functions as dead that are called on live paths."*

⛔ **And it is what makes a same-named method anywhere in the engine mask an unrelated function.**

```
genios_engine/capture/parked/refetch.py:267     queue.claim_due()
```

That is `InMemoryRefetchQueue.claim_due` — a different function, in a different package, with a
different signature (`eval_time=`/`policy=`/`org_id=` against the spine's
`worker_id=`/`at=`/`lease_seconds=`). On the strength of it, **`deliver/spine.claim_due` is reported
reached, and nothing in the engine calls it.** A whole tier of the v2 delivery path was invisible.

> ⛔ **Doctrine: *a call resolved by name alone is a call to any function with that name.*** It is the
> reachability form of the blunt grep, and it fails in the comfortable direction — toward declaring
> things reached, which is the direction that reports fewer problems.

## 2 · ⛔ Why this is L4's problem too

`executive/unreached.UNREACHED` is a CLOSED table checked in both directions, and the
*"is it called now"* direction uses this resolver. So **an `executive/` function that shares a name
with any method anywhere in the engine would be reported reached and silently dropped from the
declaration** — the exact failure `unreached.py`'s own docstring says one direction alone produces.

**Nothing has been shown to be wrong in L4.** But nothing has shown it is right either, and that
distinction is what this programme keeps paying for: *a grep that finds nothing is not evidence that
nothing is there*, and neither is a resolver that finds something.

## 3 · What is already built, and why this step is small

`deliver/delivery_health.qualified_call_sites` (STEP-05) is the precise resolver: a call counts for
`module.function` only if the calling file **imports** that function or its module, plus calls from
inside the defining module itself.

⛔ **The intra-module clause was found by a test, not by thought.** Without it,
`outbox.shadow_resolve_v2` — invoked at `outbox.py:1441`, inside its own file — came back unreached,
which would have reported the one production measurement this package has as dead. *No file imports
itself.*

So the resolver exists, is tested, and is proven on the collision it was written for:

```
qualified_call_sites("spine.claim_due",         engine)  ->  0     ⛔ the collision excluded
qualified_call_sites("spine.log_delivery_event", engine)  ->  3
qualified_call_sites("outbox.shadow_resolve_v2", engine)  ->  1     the intra-module call
```

## 4 · What to build

| | |
|---|---|
| `executive/unreached.py` | ⛔ add `qualified_call_sites`, **beside `called_names` and not replacing it** |
| `deliver/delivery_health.py` | import it from there instead of defining its own, so the two cannot disagree |
| `tests/test_the_executive_says_what_it_does_not_call.py` | switch the *"has it acquired a caller"* direction to the precise resolver, and ⛔ **re-derive L4's `UNREACHED` and `PULL_ONLY` against it** |
| `tests/executive/test_a_call_resolved_by_name_is_not_a_call.py` | ⛔ NEW |

⛔ **`called_names` keeps its job.** The *undeclared* direction should stay imprecise, and the reason is
asymmetric: a false REACHED there only hides a problem from us, while a false UNREACHED would demand a
declaration for a function that is genuinely wired — and a declaration nobody can justify is how a
table fills with entries that mean nothing. **Two resolvers, two directions, written down.**

## 5 · ⛔ The measurement this step must do FIRST

```
for every name in executive/unreached.UNREACHED and PULL_ONLY:
    called_names(engine)[name]  vs  qualified_call_sites(...)
```

**If any L4 declaration changes, that is a finding and it belongs in `layer-4-executive/03-FINDINGS.md`,
not here.** The expected result is that nothing changes — L4's names are distinctive — but *expected*
is a prediction, and this programme has four retracted findings that were predictions.

## 6 · Verify

```
.venv/bin/pytest tests/executive/test_a_call_resolved_by_name_is_not_a_call.py -q
.venv/bin/pytest tests/test_the_executive_says_what_it_does_not_call.py \
                 tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py -q
.venv/bin/pytest -q          # ⛔ the FULL suite — this changes a tool four L4 tests depend on
```

## 7 · Mutations

| # | Mutation | Must go red |
|---|---|---|
| M1 | make `qualified_call_sites` ignore the import check | the collision test — `spine.claim_due` would read reached |
| M2 | drop the intra-module clause | the `shadow_resolve_v2` test |
| M3 | return 0 unconditionally | `test_qualified_call_sites_still_sees_a_real_call` |
| M4 | swap the two resolvers' directions | L4's own both-directions tests |

## 8 · Expected outcome

One resolver per question, each in `executive/unreached.py`, and L4's declaration re-derived against
the precise one rather than assumed to be unaffected.


---
---

# ✅ DONE — 2026-10-01

## 1 · ⛔ The measurement this step owed, and what it returned

`§5` required re-deriving L4's whole declaration against the precise resolver **before** anything was
built, and said the expected result was *"that nothing changes — but expected is a prediction."*

**Both halves came true, in different places.**

| | Result |
|---|---|
| L4's **existing** 5 entries | ⛔ **unchanged.** All five read 0 under both resolvers. The prediction held |
| L4's **missing** entries | ⛔ **five more**, every one invisible to the loose resolver |

```
readiness.read              11 apparent callers -> 0    ⛔ and the WHOLE module is unreached
execution_guard.is_live      3                  -> 0    ⛔ third spelling of one closed set
lifecycle.is_open            2                  -> 0    ⛔ second spelling of the same set
execution_store.supersede    2                  -> 0    a race-free replacement path, uncalled
delegation.propose           1                  -> 0    superseded by two better-named siblings
```

> ⛔ **The declaration was never wrong. It was answering a question the tool could not ask.** That is
> a different failure from a stale entry, and it is the one that leaves no trace: nothing goes red,
> no number drifts, and the guard reports success.

## 2 · ⛔ The three sharpest of the five

**`executive/readiness.py` is an entirely unreached MODULE.** `read` → `assess` → `_verdict` is its
whole public chain, and `assess`'s only caller is `read` itself at `readiness.py:172`. **No route
exposes it.** Production still answers the question — `platform/receipts.py` reads the same three
counts through `platform/org_readiness_sql.COUNT_SQL`, the module `readiness.py` also imports,
extracted so *"duplicating them would let one drift from"* the other. ⛔ **So the extraction worked,
the receipt works, and the executive-layer reader of it has no surface.** L4 `STEP-02` built
organisation readiness and nothing reads it.

**A closed set with THREE spellings, not two.** L4 `STEP-10` found `lifecycle.is_terminal` untested
and guarded it in `test_a_closed_set_with_two_spellings.py`. Measured now: `is_terminal`, `is_open`
and `execution_guard.is_live` are three partitions of one closed table, in two files, **and not one
has a production caller.** Two of the three have **no docstring**. ⛔ *A guard written for one member
of a closed table is half of that* — and these were the halves nobody could see, because `is_live`
and `is_open` are names other objects in the engine also use.

**`execution_store.supersede`** — *"Closing the predecessor frees the partial unique key, which is how
the replacement lands without a race."* ⛔ Zero callers, so **a revised plan never closes the
commitment it replaces**, and the unique key this function exists to free is what a replacement would
collide with. It has not bitten because no decision has produced a second plan in production since
2026-09-25.

## 3 · What was built

| | |
|---|---|
| `executive/unreached.py` | ⛔ `_file_bindings` + `qualified_call_counts` + `qualified_call_sites`, **beside `called_names`, not replacing it**. Five new `UNREACHED` entries, each triaged |
| `deliver/delivery_health.py` | local resolver deleted, imports the promoted one; **2 new entries** — `act_pump.stop`, `retry.defer_until` |
| `tests/test_the_executive_says_what_it_does_not_call.py` | `_unreached()` on the precise resolver; the set guard **5 → 10** with the reason written in |
| `tests/deliver/test_...says_what_it_does_not_call.py` | **both** directions on the precise resolver |
| `tests/executive/test_a_call_resolved_by_name_is_not_a_call.py` | ⛔ NEW, **9 tests** |

```
UNREACHED  (executive/)   5 -> 10
DECLARED   (deliver/)    24 -> 26
```

⛔ **The asymmetry argument this step was written with no longer holds, and that is recorded rather
than quietly dropped.** `§4` said to keep `called_names` for the *undeclared* direction, because a
false UNREACHED would demand a declaration for genuinely wired code. **The alias-aware resolver
removes that risk** — so both directions now use the precise one, and the reason to tolerate a false
*reached* went with it.

## 4 · ⛔ Two of my own errors, and the second was worse than the bug

**Version one of the resolver credited every imported module with every call name in the file.**
443,610 pairs, and it reported `lane_display.describe` and `runner.run_all` as **unreached** —
both are called through an alias (`describe_lane`, `run_l3`). ⛔ **It would have put two live
functions into a declared-silence table**, which is the opposite error and a worse one: the loose
resolver hides a gap, a wrong strict resolver manufactures one.

> **A resolver that is merely stricter is not more correct.** Found by hand-verifying four of its
> answers with `grep` instead of trusting it. 9,166 pairs after the fix, 1.4s over the engine.

⛔ **And I claimed `called_names` was not alias-aware. It is** — its own comment names the exact case
(`link_card as _link_execution_card`) and says resolving them *"is not optional"*. The defect is
**module collapse**, not alias blindness: it resolves the alias and then counts by bare name.
Corrected here because a wrong diagnosis of a working tool is how the next person deletes the part
that works.

**And a third, smaller:** I grepped `len(UNREACHED)`, found nothing, and assumed no count guard
existed. ⛔ `test_the_count_is_five_and_they_are_the_measured_five` asserts the **set**, which is
stronger. *A grep that finds nothing is not evidence that nothing is there* — second time this
programme has paid for that exact grep.

## 5 · Mutations

| # | Mutation | Result |
|---|---|---|
| M1 | disable alias resolution | 🔴 4 failed |
| M2 | drop the intra-module clause | 🔴 7 failed |
| M3 | disable the module-alias branch (`DLG.propose_action`) | 🔴 3 failed |
| M4 | return `{}` | 🔴 9 failed |
| M5 | revert L4's `_unreached()` to the collapsing resolver | 🔴 1 failed — ⛔ the set guard, 5 vs 10 |

## 6 · Verify

```
.venv/bin/pytest tests/executive/test_a_call_resolved_by_name_is_not_a_call.py -q   #  9 passed
.venv/bin/pytest tests/test_the_executive_says_what_it_does_not_call.py \
                 tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py -q  # 29 passed
```

## 7 · ⛔ The finding this step produced, and it is the largest in the programme

Running the corrected resolver over **every** package: **147 public functions are unreached by
production code and declared nowhere.**

| | |
|---|---|
| hidden by a name collision | **18** |
| ⛔ visible to both resolvers all along | **129** |

```
context 48 · reason 29 · platform 26 · feedback 17 · capture 8 · contracts 8 · mcp 5 · packs 3 · api 3
```

⛔ **This was never mainly a resolver problem.** Only `executive/` and `deliver/` have a reachability
guard. `reason/unit_health.py` and `context/lane_health.DORMANT_LANES` are declarations about *lanes
and eras*, not an unreached-function inventory — so nine packages have never been asked the question.

⛔ **And 147 is NOT 147 defects.** L5's 24 broke down as 5 defects, 11 an un-cut-over architecture, 8
deliberate. Extrapolating is exactly the mistake this step exists to prevent. → **`STEP-17`**, and it
is a **level**, not a unit: one per package, each needing its own triage.

## 8 · Doctrine

| Rule |
|---|
| ⛔ **a call resolved by name alone is a call to any function with that name** |
| ⛔ **a resolver that is merely stricter is not more correct** |
| ⛔ **a declaration can be answering a question the tool cannot ask — and then nothing goes red** |
| **no file imports itself** |
| **a wrong diagnosis of a working tool is how the next person deletes the part that works** |
| **a grep that finds nothing is not evidence that nothing is there** |
