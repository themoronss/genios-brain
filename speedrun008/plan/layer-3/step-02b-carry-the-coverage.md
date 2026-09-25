# L3-02b · Carry the coverage sentence to the situation

**Needs Harsh:** none · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-02b-carry-the-coverage.md)
>
> +12 tests · 13,176 passed · 0 regressions.
>
> ⛔ **It is one seam, not the three the plan named.** *"read 37 of about 465"* is only meaningful
> with a window, and **the window belongs to the claim, not to the message** — so it does not cross
> the QES at all. `context/` may import `capture/`, so the situation asks at the moment it claims.
>
> ⛔ **And the seam already held the right idiom.** `unmet_source_families` names which system of
> record is missing; `window_coverage_gaps` is its sibling one question over — how much of a
> *connected* one we actually read.

## Done criteria

- [x] `window_coverage_gaps()` beside `unmet_source_families`, reads-never-writes, `()` on failure
- [x] wired into **both** producers — outreach and support
- [x] ⛔ the window is the finding's **own evidence span**, never a constant
- [x] ⛔ no span → **skip, do not guess**
- [x] the memo is keyed on the span, not the domain
- [x] ⛔ **no threshold** — the rule is `can_support_absence`, shared with L3-02 and L3-03
- [x] four failures produce four different sentences
- [x] technique 3: **four** mutations, all red, restore green
- [x] full suite: **13,176 passed · 14 pre-existing · 0 regressions**
