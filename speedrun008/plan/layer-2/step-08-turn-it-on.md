# L2-8 · Turn it on, then prove it adversarially

**Needs Harsh:** parity needs the corpus · **Migration:** none · **This step ships nothing new**

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

1. The shadow pass's existing tallies **read and written down**.
2. A parity number fixed **before** the flip.
3. Three flips together, one tenant, reversible.
4. A scenario registry with typed classes and an import-time totality check.
5. Mutation probes for every fix in L2-1…L2-7, each proven sensitive.
6. A failure log whose counts a test verifies.
