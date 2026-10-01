# L3-12 · The node vocabulary is closed

**Needs Harsh:** none (⛔ **one query, handoff §4.6**) · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-12-graph-views.md)
>
> +11 tests · 13,265 passed · 0 regressions.
>
> ⛔ **Eleventh premise wrong, and the grep behind it was the reason.** *"Four views return zero
> files"* came from a pattern looking for the word **"view"** near the word — **measuring prose,
> not capability.** All eight concerns are queryable, and `read_models.py` builds per-ENTITY
> projections, which is what a card actually reads.
>
> ⛔ **What was wrong is the third free-string vocabulary.** `node_type text not null -- person |
> company | deal | meeting | ...` — the `| ...` is the tell.

## Done criteria

- [x] `NODE_TYPES` closed, **each saying what anchors it**
- [x] ⛔ the **mention whitelist** held as a strict subset, and its scope comment pinned
- [x] ⛔ the guard reads **both spellings** — literal and `*_NODE_TYPE` constant
- [x] the read-model map lifted out of a function body
- [x] a node type and an edge type may never share a name
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,265 passed · 14 pre-existing · 0 regressions**
