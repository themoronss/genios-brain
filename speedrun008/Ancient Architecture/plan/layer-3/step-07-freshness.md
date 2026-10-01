# L3-07 · One answer per decay question

**Needs Harsh:** ⛔ **a decision** (handoff §1.3) · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-07-freshness.md)
>
> +8 tests · 13,216 passed · 0 regressions.
>
> ⛔ **Half the premise held.** `freshness_policy_id` really does appear exactly once in the repo —
> its own declaration. **The other half was wrong for the fifth time:** GE-HCS-05's echo case is
> already handled at L1 by Rule 11 with a required independence assertion, and there is no double
> decay, because L1's curve is a **read view** that never writes back.
>
> ⛔ **And a behavioural test found a live defect a text assertion could not.** `half_life_days` is
> an **e-folding constant, not a half-life** — at the configured 30 days the weight is **0.368, not
> 0.5**. Nothing was changed; the choice is routed to the handoff.

## Done criteria

- [x] the two staleness curves declared, each with **its question and its shape**
- [x] L1's decay pinned as a **read view** — the property that makes two curves safe together
- [x] no third curve may define itself without being a declared owner
- [x] ⛔ the L4 curve pinned **behaviourally**, which is how the misnomer was found
- [x] the dead column pinned **dead**, so nobody reads it as an unfinished feature
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,216 passed · 14 pre-existing · 0 regressions**
