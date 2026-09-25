# L3-13 · The Intelligence Graph is already foreign keys

**Needs Harsh:** none · **Model:** none · **Migration:** ⛔ **none — the plan asked for one and it was wrong**

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-13-the-graph-already-exists.md)
>
> +12 tests · 13,277 passed · 0 regressions · 7/7 mutations caught.
>
> ⛔ **Twelfth, thirteenth and fourteenth premises wrong — and they were the three holding up
> `intel_nodes` + `intel_edges`.** *"No table holds both a situation and a decision"* is false:
> **`signals` holds both**, via `situation_id` (0182) and `reasoning_decision_hash` (0031, FK'd).
> The earlier scan missed them because **both were added by `alter table`**, and it read
> `create table` blocks.
>
> ⛔ **The fallback was false too.** L3-14 justified the tables with *"it dies when a signal is
> archived"* — there are **0 `delete from signals`** in the tree and **12 `update signals set
> status`**. Nothing deletes a signal.
>
> ⛔ **And the chain does not stop at the decision.** `executions.decision_hash` →
> `execution_outcomes.decision_hash` means **situation → decision → delivery → outcome is joined
> today** — and the fifth kind, `interpretation`, is `situation_interpretations` (0183). ⛔ **All five
> already exist.** Two tables would have been a second copy of a
> graph the schema already enforces.
>
> ⛔ **What is actually broken is worse and smaller.** **Five writers insert into `signals`; one
> names `situation_id`** — and it is the feature-flagged compiled lane. So the column is null on
> essentially every live row and `card_source.classify` calls every main-path card
> **UNINTERPRETED**. That is the benchmark's complaint, at its source.
>
> ⛔ **It is NOT wired, and that is deliberate.** `runner.run()` already has the situation in
> scope for all three silent writers — zero queries, zero migration — but a pack rule never
> *reads* the situation, `classify` is **binary** so there is no value meaning *"co-located but
> not reasoned from"*, and binding them would move rows from `cards_uninterpreted` to
> `cards_from_situation` **without changing a single decision**, corrupting the very measurement
> that decides the cutover. `uncited_lanes` measured it on 2026-09-16 — **9 of 11** — and recorded
> that it *"is the user's to make."* **→ ✅ DECIDED 2026-09-25: HOLD (handoff §1.4).** Moves when `CardSource` gains a third value.

## Done criteria

- [x] ⛔ the premise measured before any code — **three separate falsifications**, all recorded
- [x] ⛔ **no migration and no table written** — the graph that was asked for already exists
- [x] the existing chain **pinned** so nobody rebuilds it: situation → decision → delivery → outcome
- [x] the hard-delete argument pinned — `delete from signals` appearing anywhere is a build failure
- [x] `SIGNAL_WRITERS` closed over **all five** writers, checked in **both directions**
- [x] ⛔ each silent writer carries a **reason and a mover**, enforced
- [x] `binding_drift` — declared `binds` vs the **real parsed column list**, so it cannot go stale
- [x] ⛔ the parser reads the **AST**, not the text — comments cannot reach it
- [x] ⛔ **the guard found a defect in itself**: a docstring is an `ast.Constant`; fixed by the
      statement's *shape* (column list, then `VALUES`), pinned
- [x] `classify`'s binary-ness pinned — if a third `CardSource` appears, the held decision changes shape
- [x] `bound_fraction() == (1, 5)` pinned, so the gap is a number rather than an impression
- [x] technique 3: **seven** mutations, all red, each asserting the edit applied, restore green
- [x] full suite: **13,277 passed · 14 pre-existing · 0 regressions**

## ⛔ What this step did NOT do, on purpose

Wire the four silent writers. It is one line each and costs nothing to run — and it is a claim
about provenance that the code cannot currently qualify. ✅ **Put to Rohit on 2026-09-25 with three
options; the answer was HOLD.** The refusal and its mover are now recorded in
`reason/situation_binding`'s docstring, not only here — a silence whose reason lives in a plan file
is a silence the next reader "fixes".
