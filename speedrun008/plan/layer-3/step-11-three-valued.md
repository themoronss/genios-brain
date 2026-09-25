# L3-11 · `unknown` never becomes `false` — and the gap gets a number

**Needs Harsh:** ⛔ **one number to read after a pilot sweep** (handoff §5.1) · **Model:** none ·
**Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-11-three-valued.md)
>
> +10 tests · 13,254 passed · 0 regressions.
>
> ⛔ **Ninth and tenth premises wrong.** `PredicateState.TRUE/FALSE/UNKNOWN` exists,
> `quality/inference.may_infer_absent` is **wired** into the evaluator, and tri-state is idiomatic
> — `bool | None` in 42 files.
>
> ⛔ **What is open is declared by the code that has it:** a path nobody classified **falls through
> to licensed**, so absence is concluded from silence — a fail-OPEN default where every other branch
> fails closed. It was deferred because closing it *"would turn **most** `absent:` answers into
> abstentions"*, **and nobody has measured "most."** This step makes it countable.

## Done criteria

- [x] the three values pinned, and an unlicensed absence **abstains rather than asserts**
- [x] the licence is **asked**, not re-derived — two copies is how the next consumer gets a third
- [x] ⛔ the fail-open gap stays **declared where it happens**
- [x] ⛔ the no-op "fix" **cannot come back** — pinned by its own warning
- [x] ⛔ the gap **counted at the branch**, because TRUE-from-typed and TRUE-from-silence are one value
- [x] ⛔ the tally **cannot raise** — L2-7's lesson at a third seam
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,254 passed · 14 pre-existing · 0 regressions**
