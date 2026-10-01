# L3-03 · Connected is not read — the missing half of the absence gate

**Needs Harsh:** none · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-03-scoped-absence.md)
>
> +10 tests · 13,186 passed · 0 regressions.
>
> ⛔ **The gate already existed and was stronger than the one planned** — `GENUINELY_ABSENT` is
> **unconstructible** without `coverage_ready=True` and a non-empty basis, enforced at the type.
> **`scoped_absence()` was not built**: a second, weaker gate beside a stronger one is exactly the
> scaffolding this plan avoids.
>
> ⛔ **The two missing ingredients were the two L3-02 measured.** `coverage_ready` is a fact about
> the **tenant**, not about the **sweep** — so Gmail connected plus a sweep that read 37 of ~465
> reached a licensed negative inference over 8% of a mailbox. **The benchmark's failure, surviving
> inside the module built to prevent it.**

## Done criteria

- [x] ⛔ `window_ok` refuses **last**, after both existing gates
- [x] a well-read window never rescues a claim the earlier gates refused
- [x] `PRESENT` / `STALE` / `NOT_EXPECTED` untouched
- [x] `None` = not asked, unchanged, and ⛔ **declared in `WINDOW_UNCHECKED` with a guard**
- [x] per **subject**, not per sweep
- [x] ⛔ the gate and the card's sentence are **one function**, not two rules
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,186 passed · 14 pre-existing · 0 regressions**
