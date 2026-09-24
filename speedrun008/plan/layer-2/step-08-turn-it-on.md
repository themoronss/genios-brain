# L2-8 · Turn it on, then prove it adversarially

**Needs Harsh:** the shadow tallies · **Migration:** none · **This step ships nothing new**

> ## ✅ COMPLETE · PENDING · HARSH (the shadow tallies) — 2026-09-24 · [findings](findings/step-08-turn-it-on.md)
>
> 36 tests · 13,116 passed · 0 regressions · **nothing armed, and a test asserts each switch is off**.
>
> ⛔ **§2 SAYS THREE FLIPS. IT IS SEVEN.** This file was written before L2-0…L2-7 ran, and four of
> those steps each left a switch behind deliberately — declared, evidenced, not armed. **Nothing
> enumerated them.** `reason/cutover.py` is the table, and a test reads the CODE and refuses a row
> that disagrees, so a flip that forgets to update it fails the build.
>
> ⛔ **AND THE SCARIEST PRECONDITION IN THE PLAN HAS NONE.** L2-0 measured `require_admission`
> free: **155 of 155 capabilities admissible.** The 334 this plan budgeted for counted FILES.
>
> ⛔ **THE ADVERSARIAL PASS FOUND A LIVE HOLE IN L2-6.** `_refs_in` read citations with `getattr`
> alone — a proposal arrives as parsed JSON, so every cited claim read as citing nothing and **the
> resolver was never called at all.** The unresolvable-citation half of check 3 was dead on the one
> path that matters. The defence was correct and aimed at an object shape the model never sends.

---

## 1. Premise — B is already built and switched off

`reason/domain_shadow.shadow_compile` is *"L1 signals + Layer D expertise, reasoned"* — wired into
the live sweep at `runner.py:1451`, gated per tenant, and **`live=False` for every existing caller.**

> *"the corpus was 152 authored capabilities that could not produce a single card: the compile ran
> (behind a flag that is off), published nothing, and reasoned in SHADOW."*

**So the last step is not a build. It is a cutover, and then a proof.**

---

## 2. The three flips happen together

From `shadow_compile`'s own contract — any one alone leaves the system in a state that looks working
and is not:

1. **a real publisher** — otherwise `expertise_packages` is never written
2. **`require_admission=True`** — only doctrine a named reviewer accepted may carry authority.
   Measurement mode relaxes this deliberately; live must not.
3. **`ExecutionMode.LIVE` + an emitted `signals` row** — otherwise delivery cannot build a card, and
   the card cannot say which brain authored it

---

## 3. Units

### L2-8-U0 · Read what the shadow pass already measures
⛔ **Nobody has read its tallies.** It has been running, counting, and reporting to no one. The
cutover gate is a number from this pass, and the number exists today.

**Blocked on Harsh** — needs the database.

### L2-8-U1 · The parity gate, stated as a number before the flip
What must the shadow pass show to earn `live=True`? Written down **before** the run, not chosen
after seeing it. A threshold picked post-hoc is not a gate.

### L2-8-U2 · The three flips, together, per tenant
One tenant first. **Not a global flag** — `live_lane`'s own comment records what happened when a
global flag was checked first: *"the one configuration in which the stated safety property is false
is the one a global flag creates."*

### L2-8-U3 · The scenario registry — L2's own
L1's step-17 shape: rows with verdicts (`CLOSED`/`GUARD`/`OPEN`/`CORPUS`/`IMPOSSIBLE`), typed
failure classes, an import-time totality check, and **a reason required on every non-trivial
verdict** — *"a verdict with no reason is a label."*

### L2-8-U4 · ⛔ The F20 rows matter most
L1's F20 is *"unknown → true"*. **In L2 it takes a specific and dangerous shape: a hypothesis that
hardened into an observation.** That is the one failure this entire layer's three-way split exists to
prevent, and the adversarial pass must attack it directly:

* a hypothesis with low confidence rendered as a statement of fact
* an inference whose only citation is another inference
* an `unknowns` list emptied by a confident model on thin coverage
* an interpretation that outlived its `valid_until` and was read as current

### L2-8-U5 · Mutation probes for every fix in L2-1…L2-7
Technique 3, applied to the whole layer. **Neutralise the fix, confirm the probe goes red.** A green
suite that stays green with the fix removed proves nothing about the fix.

### L2-8-U6 · The failure log
Typed, counted, and **counted by a test** — because L1's counts drifted and were caught by counting,
not by reading.

---

## 4. What this step does NOT do

* **It does not flip globally.** One tenant, then the numbers, then the next.
* **It does not pick the gate after seeing the result.**
* **It does not close what is still open.** An OPEN row with a reason is the output; a quiet one is
  the failure.

---

## 5. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | the shadow pass's tallies read and written down | ⛔ **HARSH 29** — it has been counting for months and nobody has read it |
| 2 | a parity number fixed **before** the flip | ✅ five rules · every reading proven to be a tally the sweep emits · an **absent** tally FAILS · `PARITY_MEASURED_AT is None` asserted |
| 3 | three flips together, one tenant, reversible | ✅ **and there are seven**, ordered, each with its precondition and what it breaks alone. **None armed** |
| 4 | a scenario registry, typed, import-time totality | ✅ 37 scenarios · 12 failure classes · both directions |
| 5 | mutation probes for every fix in L2-1…L2-7 | ✅ **nine**, each neutralising the **RULE** rather than the code — and one **found a live hole** |
| 6 | a failure log whose counts a test verifies | ✅ counted, not read — L1's drifted and were caught by counting |

**Five closed. One is a database read.**

### 5.1 · The registry, at a glance

```
closed      25      a step fixed it, and a probe proves the check is sensitive to THAT fix
guard        3      already true — evidence progress cost nothing, not that progress happened
open         1      ⛔ S07 · no test drives the compiler with what production sends it
harsh        7      the logic is proven; the distribution needs the pilot
impossible   1      S20 · `general` is claimed by all three corpora — routing it is a CHOICE
```
