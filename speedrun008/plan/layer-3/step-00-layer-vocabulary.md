# L3-00 · Carry the product vocabulary into `LAYERS.py`

**Needs Harsh:** none · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-00-layer-vocabulary.md)
>
> +3 tests · 13,135 passed · 0 regressions.
>
> ⛔ **The premise check found a live hole beside the documentation job.** `genios_engine/mcp/` was
> in neither `LAYERS` nor `CROSS_CUTTING`, and an unmapped package escapes the import ratchet **in
> both directions** — so `capture` (1) could reach `feedback` (7) through it while the test stayed
> green. Nothing has gone through it yet; the guard that would notice did not exist.
>
> ⛔ **And the blunt-grep mistake was made a fourth time** — the translation-table test asked
> whether a package appeared *anywhere* in the document. Its own mutation probe stayed green, which
> is how it was caught.

## Done criteria

- [x] the product vocabulary is a fourth column in `LAYERS.py` and `docs/LAYER_MAP.md`
- [x] both collisions stated: *"Layer 3"* is Domain Expertise here and Context Graph there; the tail is off by one
- [x] every package under `genios_engine/` is declared — reverse totality guard
- [x] a package cannot be both a layer and cross-cutting
- [x] the translation table cannot drift from `LAYERS`
- [x] technique 3: **four** mutations, all red, restore green
- [x] full suite: 0 regressions

## What this step does NOT do

* **It changes no import rule.** The digits in `LAYERS` are import ordering and are untouched.
* **It does not renumber anything.** 115 files still say *"Layer 3"* meaning Domain Expertise; the
  fix for that is the rule the file already carries — ⛔ **always name the package, never the digit
  alone.**
* **It does not constrain `mcp`.** Cross-cutting packages are exempt from the direction rule, as
  `api` is. What it buys is that the *next* unmapped package cannot be invisible.
