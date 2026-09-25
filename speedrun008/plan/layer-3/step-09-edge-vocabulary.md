# L3-09 · The edge vocabulary is closed

**Needs Harsh:** none (⛔ **one query worth running, handoff §4.5**) · **Model:** none ·
⛔ **Migration: none — the plan was wrong**

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-09-edge-vocabulary.md)
>
> +13 tests · 13,237 passed · 0 regressions.
>
> ⛔ **Seventh premise wrong.** All seven "missing" relations are implemented — in other layers:
> `same_entity_as` is identity, `responds_to` is thread structure, `satisfies_condition` is
> `DormantCondition`, `fulfills` is the commitment state machine. **Adding seven parallel edge
> types would have created two answers to every one of those questions.**
>
> ⛔ **What was actually wrong:** `edge_type` was free text with **no constraint and no vocabulary
> anywhere**. A typo — `work_at` for `works_at` — wrote a relation every reader walks past: a fact
> in the graph that can never be found, with no error. And the specs' hazard (*"`related_to` must
> not silently become `blocks`"*) **could not be violated, because there was nothing to violate.**

## Done criteria

- [x] `EDGE_TYPES` closed, each stating its direction **and what it does not mean**
- [x] ⛔ `causes` · `blocks` · `related_to` refused, **each with its own reason and an alternative**
- [x] `write_edge` **raises** rather than skipping — an unknown type is a caller bug
- [x] totality both ways, at build time: declared ⟷ written
- [x] ⛔ no live call can raise — proven by walking the whole engine
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,237 passed · 14 pre-existing · 0 regressions**
