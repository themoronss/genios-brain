# L3-14 premise check · the history already exists — nobody asks for it

**2026-09-25** · ⛔ **no code written yet — this is the premise check, and it changed the step**

---

## 1 · L3-14 as planned is void

> **L3-14 · Lift `about` out of `signals`**
> The edge **already exists as data** … It is a delivery table doing a graph's job — **it dies
> when a signal is archived.**

The struck clause was its **only** argument, and L3-13 measured it false: **0** `delete from
signals` in the tree, **12** `update signals set status`, and **0** statements that null the
column. An expired signal keeps its `situation_id` forever. **The edge cannot die, so there is
nothing to lift it out of.**

---

## 2 · ⛔ And the reader L3-17 asks for already exists, and already runs

L3-17's evidence was a grep:

```
prior_decision 0 · previous_decision 0 · last_decision 0 · past_decisions 0
```

**Those are the wrong words.** `genios_engine/context/correlation_history.py` — *"Cross History —
what happened the LAST time this anchor was in this situation"* — publishes four facts:

| fact | what it says |
|---|---|
| `derived.history.times_seen` | generations of this anchor in this domain |
| `derived.history.days_since_prior` | whole days since the previous generation |
| `derived.history.prior_outcome` | the prior execution's label, from `execution_outcomes` |
| `derived.history.prior_card_verdict` | ⛔ **what the person DID with the last card** — `run_play \| do_it_myself \| wrong:<reason>` |

Its own docstring names the target: *"'We already told them this and they dismissed it' is the
single most useful thing this file can say."* **That is L3-17's sentence, already built.**

⛔ **And it is called on the live path** — `context/runner.py:752`, inside the L2 sweep, every run.

**This is the blunt-grep family's tenth occurrence, and the first one that is in the PLAN rather
than in a test.** The capability was measured by searching for names nobody used.

---

## 3 · ⛔ So what is actually wrong: the engine publishes, the corpus does not ask

`derived.history.*` is declared in `Domain Expertise/_schema/vocabulary.yaml` under
**`substrate.fact_paths`** — the REAL substrate, not `planned_substrate` — sitting immediately
beside `derived.momentum`, `derived.engagement` and `derived.sentiment`.

Those three are used by authored capabilities **83, 191 and 154 times.**

**`derived.history.*` is used ZERO times across 1,425 authored capability files.**

### 3.1 It is not one field. It is half the substrate.

| | count |
|---|---|
| declared `substrate.fact_paths` | **141** |
| consumed by ≥1 authored capability (exact path) | 71 |
| ⛔ **consumed by NO authored capability (exact path)** | **70** |
| …of those, plausibly reached under a leaf-name alias | 13 (weak evidence — e.g. `created_at`) |
| ⛔ **truly unconsumed on the conservative reading** | **57 of 141** |

⛔ **The engine computes and publishes these every sweep. Nothing asks for them.**

### 3.2 ⛔ A number I got wrong on the first pass, corrected before publishing

My first measurement reported *"70 fields named by neither the engine nor the corpus."* **False.**
Re-run against both trees: **0** fields are named by neither — every declared field IS named by the
engine, because the engine is what writes it. The true shape is **"written by the engine, read by
no author"**, which is a different and more precise claim. The first version would have read as
"70 dead strings in a YAML file" when the reality is "70 live computations nobody consumes."

---

## 4 · ⛔ What this means for the benchmark — the answer to Rohit's question

The benchmark asked why the output is thin. The premise everywhere in this plan has been *"the
engine is under-built."*

**Measured, the engine is not the constraint. Half of what it already produces is never asked for.**

`derived.history.prior_card_verdict` is the sharpest case: the system knows *"we sent this exact
card before and they marked it wrong"*, writes it into the graph on every sweep, offers it to
authors in the same list as the three fields they use 428 times between them — **and not one
capability has ever read it.**

⛔ **This is not a code defect and it cannot be fixed by wiring.** Nothing in `genios_engine` is
broken. The gap is in the **authored corpus**, and its owner is whoever writes capabilities.

---

## 5 · What L3-14 becomes

Not *"lift `about` out of `signals`"* — that premise is void.

**Make the unconsumed substrate a number that cannot be lost.** A measurement over
declared-vs-consumed, pinned by a test, with the history four named explicitly — the same shape as
`UNCITED_LANES` and `SIGNAL_WRITERS`, one layer out, over the corpus instead of the code.

⛔ **NOT a hard gate.** Requiring every declared field to be consumed would be wrong — a field may
be declared ahead of the capability that will use it. The guard reports and pins; it does not
refuse.

---

# ✅ BUILT — 2026-09-25

`genios_engine/packs/substrate_demand.py` + `tests/test_the_corpus_asks_for_what_the_engine_publishes.py`
**+13 tests · 7/7 mutations caught · 0 regressions**

| what | why |
|---|---|
| `field_paths(vocabulary_yaml)` | parses `substrate.fact_paths` by indentation, stopping at the next key — absorbing `obs_kinds:` would inflate every ratio |
| `measure(declared, corpus_text)` | splits declared fields by whether the corpus names the **full path** |
| `Demand.ambiguous` | ⛔ fields unconsumed by path whose **leaf** appears somewhere — **reported, never counted.** 13 of them. `document.created_at` and an unrelated `created_at` are not the same field |
| `Demand.strict_unconsumed` | the conservative number, **57** |
| `HISTORY_FIELDS` | the four, named — checked **both ways** against the vocabulary |

## ⛔ The ceilings are a ratchet, not a floor

```
UNCONSUMED_CEILING = 70      # may fall, may never rise
STRICT_CEILING     = 57
DECLARED_AT_MEASUREMENT = 141
```

A field may legitimately be declared before the capability that uses it — that is how a substrate
grows, and a gate would make publishing a new fact impossible until an author had already consumed
it, which is backwards. **What is protected is the direction.**

`test_the_declared_substrate_is_still_the_list_this_was_measured_against` stops the ceiling passing
for the wrong reason: a vocabulary that *shrank* would lower the unconsumed count without anybody
authoring anything.

## ⛔ Mutation 7 found a real gap in my own test

Deleting `derived.history.prior_card_verdict` from `HISTORY_FIELDS` **stayed green** — the constant
was asserting itself. Same failure the totality guards exist for. Fixed by checking `HISTORY_FIELDS`
against what the vocabulary declares under `derived.history.*`, **in both directions**.

## The test that is meant to break

`test_no_capability_asks_for_the_history_the_engine_computes_every_sweep` **fails the day an author
uses one of the four** — and that is its purpose. It is the only reliable trigger to come back and
rewrite the zero in `packs/substrate_demand`, in this file, and in the handoff.
