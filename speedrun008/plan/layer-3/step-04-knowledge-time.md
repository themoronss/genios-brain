# L3-04 · Knowledge time

**Needs Harsh:** ⛔ **migration 0184** (item 22) · **Model:** none

> ## ✅ COMPLETE — 2026-09-25 · ⛔ PENDING HARSH (0184) · [findings](findings/step-04-knowledge-time.md)
>
> +11 tests · 13,198 passed · 0 regressions.
>
> ⛔ **The premise was half wrong and the half that was right was worse than stated.** `valid_from`
> IS knowledge time — on two of three tables. `graph_edges` binds it to the **event's** time, and
> one predicate reads all three. A backfilled six-month-old email produced an edge dated six months
> ago, so an as-of read of five months ago saw a relationship we learned this morning.
>
> ⛔ **And the column could not simply be redefined:** `reason/moments` reads it as event time and
> is right to. Redefining would have moved every one of those answers **with nothing failing.**

## Done criteria

- [x] the as-of predicate reads knowledge time, uniformly across all three tables
- [x] all three writers stamp it, and ⛔ **the database does the stamping** — no bind parameter
- [x] `graph_edges.valid_from` keeps the event time its other readers depend on
- [x] ⛔ the migration **refuses to fabricate** history for existing rows
- [x] technique 3: **six** mutations, all red, restore green
- [x] full suite: **13,198 passed · 14 pre-existing · 0 regressions**
