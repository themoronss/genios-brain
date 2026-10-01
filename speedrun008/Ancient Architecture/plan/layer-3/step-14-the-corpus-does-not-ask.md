# L3-14 · ~~Lift `about` out of `signals`~~ → ⛔ half the substrate is never asked for

**Needs Harsh:** none · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-14-premise-the-corpus-does-not-ask.md)
>
> +13 tests · 7/7 mutations · 0 regressions.
>
> ⛔ **The step as written was void.** Its only argument was *"it dies when a signal is archived"*,
> which L3-13 measured false. Checking what was true instead produced something larger.
>
> ⛔ **The history reader L3-17 asks for already exists and already runs.**
> `context/correlation_history.py` publishes `times_seen`, `days_since_prior`, `prior_outcome` and
> `prior_card_verdict` — *"we already told them this and they marked it wrong"* — from inside the L2
> sweep at `context/runner.py:752`. L3-17's evidence (`prior_decision 0 · last_decision 0`) was **a
> grep on words nobody uses.** Tenth occurrence of that family, and the first one in the PLAN rather
> than in a test.
>
> ⛔ **Then the measurement that reframes the layer: of 141 substrate fields the vocabulary declares
> to authors, 70 are used by NONE of the 1,425 authored capabilities** (57 on the strictest
> reading). `derived.history.*` sits in the same list as `derived.momentum` / `engagement` /
> `sentiment`, which authors use **83 / 191 / 154** times. The history four are used **zero** times.
>
> ⛔ **So the engine is not the constraint.** Roughly half of what Layer 2 computes and writes on
> every sweep is never asked for. **This is not a code defect and no wiring change closes it** —
> the gap is in the authored corpus. **→ It needs an author, not an engineer.**

## Done criteria

- [x] premise measured first — the step's own argument falsified before any code
- [x] ⛔ the existing history reader found, and its live call site named
- [x] the number measured against **both** the corpus and the engine, and **corrected** — my first
      pass said "70 named by neither", which was false; every field is named by its writer
- [x] the leaf-alias check kept **separate** and never counted as consumption
- [x] ceilings pinned as a **ratchet**, with a guard against the denominator shrinking
- [x] `HISTORY_FIELDS` checked **both ways** against the vocabulary (found by mutation 7)
- [x] a test that is **meant to fail** the day an author closes the gap
- [x] technique 3: **seven** mutations, all red, each asserting the edit applied
- [x] full suite: **0 regressions**

## ⛔ What this step did NOT do

Author capabilities against the unused substrate. That is corpus work with a different owner, and
writing expert doctrine is not an engineering task. **This step makes the gap a number that cannot
be lost; closing it is Rohit's call on who writes them.**
