# Layer 3 — the analysis, before any plan

**Read from the code, 2026-09-25** · against `speedrun008` @ `d5328538`
**Purpose:** what Layer 3 *is*, before a single step is written. Layer 2's plan was built on eight
premises and the premise checks corrected six of them — this file exists so that does not repeat.

---

## 1. ⛔ THE ONE QUESTION, AND IT HAS TO BE ANSWERED BEFORE ANYTHING ELSE

You said: *"Layer 3 — context graph usmein kya-kya aayega, correlation aayega, business situation
aayega."*

The architecture you gave earlier says: **L3 = Decision Intelligence.**

**These are two different layers, and the code can only be one of them.**

`01-CURRENT-STATE.md` §9 asked this in September and never got an answer:

> *"Does the Context Graph come before or after the Business Situation? — it decides whether the 9
> correlators stay in L2 or move to L3."*

### 1.1 · Why it cannot be deferred again

**Because the graph, correlation and the business situation are not three things. They are one
pipeline, and it is already built — in `context/`.**

```
graph_facts · graph_edges · graph_observations        ← 10 tables, WRITTEN BY capture (L1→L2 seam)
   ↓
9 correlators                                          ← context/correlation_*.py, deterministic
   ↓
context_correlations · context_correlation_members     ← 8 context_ tables
   ↓
7 situation producers                                  ← context/*_situations.py
   ↓
SituationCandidate → the eight laws → BusinessSituationObject
   ↓
situation_admission_decisions · situation_interpretations   ← 4 situation_ tables
```

**Every box in that diagram is `context/`** — 118 modules, and Layer 2's nine steps just spent
their entire budget making it accountable.

⛔ **So "L3 = context graph + correlation + business situation" means moving 118 modules and 22
tables out of Layer 2 and calling them Layer 3 — and Layer 2 becomes empty.**

---

## 2. What is actually unclaimed today

Here is every package, what it holds, and which layer claims it:

| package | modules | claimed by | holds |
|---|---|---|---|
| `capture` | 153 | **L1**, closed | sources, extraction, qualification, the QES |
| `context` | 118 | **L2**, closed | the graph, 9 correlators, 7 producers, admission, the slice |
| `packs` | 33 | **Plane D** | the authored corpus, the compiler, the brains |
| **`reason`** | **117** | ⛔ **nothing** | ranking, candidates, utility, plays, the decision maker, foresight, baselines, the R-sites |
| `executive` | 25 | L4 | assignment, channel, execution objects, escalation, reminders |
| `deliver` | 36 | L5 | cards, digest, outbox, rendering |
| `feedback` | 12 | L6 | precision windows, nudges, mutes |

⛔ **`reason/` is 117 modules — as large as `context/` — and no layer in the new architecture owns
it.** `decision_maker`, `brief_ranking`, `foresight`, `simulation`, `plan`, `orchestrator`,
`critique`, `authority`, `actionability`, plus seven subpackages.

**That is Decision Intelligence, and it is already built.**

---

## 3. ⛔ The two readings, priced

### Reading A · **L3 = Decision Intelligence** (`reason/`)

| | |
|---|---|
| what moves | **nothing.** `reason/` is named and its 117 modules get the same treatment `context/` just got |
| what Layer 3 does | takes an admitted `BusinessSituationObject` + an `ExpertisePackage`, and produces a **Decision Object** |
| the work | exactly Layer 2's shape — measure what is built and unswitched, name what is silent, wire what is orphaned |
| what it costs | nothing structural. Consistent with **`LAYERS.py`**, `docs/LAYER_MAP.md`, and everything L2-1 renamed |
| ⛔ what we already know is wrong in there | **R-1 has never fired on the pilot.** `reason/` has **13 files with a metered model call** — the most of any package — and the shadow lane's `live=False` |

### Reading B · **L3 = the Context Graph** (`context/`, moved)

| | |
|---|---|
| what moves | **118 modules and 22 tables**, plus every import in `packs/` and `reason/` that reads them |
| what Layer 2 becomes | **empty** — or a thin qualification layer that duplicates L1 |
| what it costs | ⛔ **`test_import_direction` is a ratchet.** Moving `context` above `reason` inverts a dependency that 117 modules rely on. L2-5's module was moved for importing *one* layer upward |
| what it buys | a diagram that matches the sentence |
| ⛔ and it re-opens | L2-1's naming, L2-4's routing table, L2-7's card seam — each of which encodes "L2 is where situations live" |

### 3.1 · The recommendation, and it is not close

⛔ **Reading A.** Not because B is wrong as a picture, but because:

1. **The Business Situation is Layer 2's output and nine steps just proved it.** `situation_bso`,
   the eight admission laws, `situation_admission_decisions`, the slice, the validator, the
   reasoner — all of it says *this layer produces a situation.*
2. **The graph is UPSTREAM of the situation, not downstream.** Situations are *derived from* graph
   correlations. A Layer 3 that "holds the graph" would sit below the layer that reads it.
3. **`reason/` is 117 unclaimed modules that do exactly what Decision Intelligence means.**
   Leaving it unnamed is how it came to have thirteen model sites and a shadow lane nobody read.

> **Both can be true in the picture.** The graph can feed correlation *and* accumulate what was
> concluded — `situation_interpretations` already does the second half. What cannot be true is
> that the layer which *produces* a situation is also the layer *after* it.

---

## 4. ⛔ What Layer 3 looks like if it is Decision Intelligence

Measured, not proposed. This is what exists in `reason/` today:

| group | modules | what is already there |
|---|---|---|
| **Candidate generation** | `plan` · `simulation` · `reasoners/` | plays, candidate steps, eliminated-by records |
| **Ranking** | `decision_maker` · `brief_ranking` · `baselines` | six-component utility, `ranking_v2` behind an activation |
| **Interpretation** | `interpretation` (R-1) · `llm_interpretation` | ⛔ *"has never fired on the pilot tenant"* |
| **The R-sites** | `bundle/` · `llm_sites` | one gate, six sites, five outcomes, a budget and a ledger |
| **Narration** | `narration` · `bundle/narrator` | R-2, after the decision is fixed |
| **Verification** | `verify/` · `critique` · `guards` | the gauntlet, the V-checks |
| **Authority** | `authority` · `actionability` | what a decision is permitted to assert |
| **Audit** | `audit` · `store` | 16 `l4_*` / `reasoning_*` tables |
| **The L2 seam** | `domain_shadow` | ⛔ `live=False`, and L2-8 enumerated the seven switches |

### 4.1 · What is missing, on today's evidence

| | |
|---|---|
| **The Decision Object as a named contract** | `DecisionCandidate` exists in `reason/`; the architecture calls the output a *Decision Object*. L2-1 measured what two names for one thing costs: fifteen wrong annotations |
| **A Persona Brain** | the fifth brain. Not in `BrainKind`, not an `ExpertisePackage` lane. *How this kind of company and this role works* — what makes a tenant legible before Behavior has history |
| **Goals** | `org_goals` → **0 files.** They belong in **Organization Brain**, beside `approval`/`policy`/`process`/`criticality` |
| **A read of what `reason/` already does and does not do** | the same first step Layer 2 took, and the one that found eight things built and never switched on |

---

## 5. ⛔ What this analysis does NOT do

* **It does not choose.** §1 is a decision only you can make, and everything after it depends on
  which way it goes.
* **It does not plan.** Layer 2's plan was written before its premise check and six of its eight
  premises were wrong. **The measurement comes first this time.**
* **It does not assume `reason/` is healthy.** It is 117 modules nobody has audited, with thirteen
  model sites and an interpretation lane that has never fired. **That is the same shape Layer 2
  was in before L2-0**, and it should be expected to hold the same kind of surprise.

---

## 6. The one thing I need from you

**Which is Layer 3?**

| | |
|---|---|
| **A** · Decision Intelligence — `reason/`, 117 modules, already built, unnamed and unaudited | *recommended* |
| **B** · the Context Graph — move `context/` up, and Layer 2 becomes qualification only | re-opens L2-1, L2-4, L2-7 and inverts a dependency ratchet |

Everything else in this file holds either way. **§4 is the plan if you say A**, and it starts the
way Layer 2 should have: by measuring what is already there.
