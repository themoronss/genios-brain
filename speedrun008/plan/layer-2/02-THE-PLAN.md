# Layer 2 — Situation Intelligence

**The design, and the order to build it in.**
Written 2026-09-24 against `speedrun008` @ `74f6047d`.

---

## 1. The finding the whole plan is built on

`BusinessSituationObject` v2 has 28 fields. Checked against the 19 the new architecture asks for:

| present | missing |
|---|---|
| entities · signal_ids · evidence · dependencies · timeline · conflicts · missing_facts · coverage_ready · confidence · state · visibility · correlations · trends · anomalies | **observed_facts** · **inferred_state** · **hypotheses** · **implications** · **reasoning_trace** · **valid_until** |

⛔ **Every field that exists is an OBSERVATION field. Every field that is missing is an
INTERPRETATION field.** That is not a coincidence — it is the exact signature of a layer that
correlates and does not reason. **The contract proves the diagnosis.**

So Layer 2 is not broken and does not need replacing. **It is half-built, and the missing half is
named.**

---

## 2. The design in one shape

```
            ── DETERMINISTIC ──────────────────┐
QES (L1) ──→ 9 correlators ──→ 7 producers ──→ │ SITUATION CANDIDATE
            replayable · untouched             │
                                               │
            ── INTERPRETIVE ───────────────────┤
            + evidence slice      (Graph)      │
            + ExpertisePackage    (Plane D)    │   ⛔ expertise enters HERE,
            + org knowledge, behaviour, goals  │      before the conclusion
            + current state                    │
                          ↓                    │
            CONTEXT REASONER  (Plane R, LLM)   │  ← the one new model site
                          ↓                    │
                  a PROPOSAL, not a truth      │
                          ↓                    │
            ── THE GATE ───────────────────────┤
            schema · every claim → evidence ref │
            contradiction · uncertainty kept   │
                          ↓                    │
            BusinessSituationObject            │
            ───────────────────────────────────┘
```

**The deterministic half stays deterministic.** The model does not replace correlation — it
*interprets* what correlation assembled. That keeps `"the same graph re-swept tomorrow produces the
same answers"` true of the **assembly**, and confines the new uncertainty to the **interpretation**,
where it is labelled as such.

---

## 3. ⛔ The one rule this layer runs on

```
Observation  ≠  Inference  ≠  Hypothesis
```

**These are three separate fields, and WRITE AUTHORITY differs per field:**

| field | who may write it |
|---|---|
| `observed_facts` | **the machine only** — lifted from L1 signals, each with its evidence ref |
| `evidence` | **the machine only** |
| `inferred_state` | the reasoner, **and only over facts it can point at** |
| `hypotheses` | the reasoner, **and it must carry its own confidence and its unknowns** |
| `implications` | the reasoner |
| `unknowns` | **either — and an empty `unknowns` is refused when coverage is low** |

This is not a new doctrine. It is L1's `EvidenceSpan.verified` rule, one layer up:

> *"The moment another caller can set that flag, it stops meaning 'checked' and starts meaning
> 'claimed'."*

A model that can write `observed_facts` is a model that can invent a fact. **So it cannot.**

---

## 4. What already exists — do not rebuild

| | where | state |
|---|---|---|
| the candidate assembly | 9 correlators + 7 producers | ✅ live |
| v1 → v2 upgrade + **8 admission laws** | `situation_publisher` | ✅ live |
| `ExpertisePackage` + capability routing | `packs/compiler` | ✅ live |
| **situation + expertise, reasoned** | `reason/domain_shadow.shadow_compile` | ⚠️ **built, `live=False`** |
| bounded model use | `context/angles` · 4 angles | ✅ live doctrine |
| metering, cost governor, replay cache | `platform` + `capture` | ✅ live |

**The new build is small.** Most of this plan is ordering, contract and a gate.

---

## 5. The steps

### L2-1 · Name it, and make the names honest
`LAYERS.py` docstring: **Situation Intelligence**, not Context Intelligence. **Plane D** and
**Plane R** rather than layers 3 and 4 — they are consumed by everyone, not passed through.
`BusinessSituationObject` v1 renamed `SituationCandidate` **at its definition**, not at one import
line. No behaviour changes; every ambiguous name in a traceback stops being ambiguous.

### L2-2 · The six fields, with write authority enforced
`observed_facts`, `inferred_state`, `hypotheses`, `implications`, `reasoning_trace`, `valid_until`
on v2 — and a validator that **refuses a situation whose `observed_facts` carry no evidence ref**.
Migration. The three-way split is the deliverable, not the field count.

### L2-3 · The evidence slice, stated not fetched
`SituationContextSlice` exists and says *"never fetched by Layer 3"*. The reasoner gets the same
treatment: **what it may see is assembled and handed to it**, so a replay can reproduce its input
exactly. A reasoner that can query the graph cannot be replayed.

### L2-4 · The Context Reasoner — the one new model site
Candidate + ExpertisePackage + slice → a **proposal**. Metered, its own purpose, its own prompt
version, its own cache key. It proposes `inferred_state`, `hypotheses`, `implications`, `unknowns`
— **and nothing else**.

⛔ **Cost check before building**, the way every L1 step did it: this is a call per situation, not
per event. Price it against the pilot's situation count before writing the prompt.

### L2-5 · The gate — a proposal becomes a situation
Deterministic, no model. Schema → **every claim resolves to an evidence ref** → contradiction check
against the graph → **uncertainty preserved** (an empty `unknowns` under low coverage is refused) →
versioned object.

This is where L1's coverage doctrine earns its keep a second time.

### L2-6 · Reorder — expertise before the conclusion
`shadow_compile` today: situation → expertise → package. Restructure to: candidate → **resolve
expertise** → reason → situation. **The capability routing already exists**; it moves upstream of
the conclusion instead of downstream.

This is the step that makes *"six VCs became sales opportunities"* structurally impossible rather
than merely fixed.

### L2-7 · Turn it on
The three flips that must happen together: a real publisher, `require_admission=True`,
`ExecutionMode.LIVE` + an emitted `signals` row. Gated on the parity the shadow pass shows.

### L2-8 · Adversarial pass
Scenarios, failure classes, mutation rows — L1's step 17 shape, aimed at the interpretation half.
The rows that matter most are the F20 ones: **a hypothesis that hardened into an observation.**

---

## 6. What this plan deliberately does NOT do

* **It does not move the graph.** The graph is persistent substrate, not a pipeline stage — L1 needs
  it for identity, L2 for evidence, L3 for history. Numbering it as a layer would create a sequence
  that does not exist. `LAYERS.py` already keeps digits out of package names for this reason.
* **It does not let the graph decide.** Storing what is true and deciding what should happen are
  different jobs, and merging them makes a wrong card undebuggable — was the situation wrong, the
  graph stale, the expertise thin, or the policy wrong? **Decision Intelligence is its own layer.**
* **It does not replace the correlators.** They are the replayable half. A model that assembles the
  situation spends the one property that makes a replay an audit.
* **It does not widen the angles.** Those four remain what they are — bounded questions over queues
  the deterministic layer itself refused. The reasoner is a *different* site with a *different*
  contract, not a fifth angle.

---

## 7. What is blocked, and on whom

| | needs |
|---|---|
| L2-4's cost check | the pilot's situation count by type — **Harsh** |
| L2-7's cutover gate | what the shadow pass measures today — **Harsh** |
| every coverage claim L2 makes | the Layer D corpus size, 152 or 211 — **Harsh** |
| L2-2's migration | applied, like 0176–0181 — **Harsh** |

**L2-1, L2-2, L2-3, L2-5 and L2-6 need none of it.** That is the order to build in.
