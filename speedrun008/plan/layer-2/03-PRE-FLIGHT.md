# Pre-flight — eight questions, measured before step 0

**Run 2026-09-24** against `speedrun008` @ `edc1c92a`. Every number counted, not quoted.
⛔ **This pass corrected the plan in three places. Those corrections are §9.**

---

## ⛔ The headline: Layer D is not thin. It is 63% inadmissible.

The corpus is **in this repository** — `Domain Expertise/` at the root, **1,425 YAML files**:

| domain | capabilities | rules | playbooks | models | objects | offerings | heuristics |
|---|---|---|---|---|---|---|---|
| **Admin** | **211** | 9 | 58 | 20 | 25 | 15 | 60 |
| **Sales** | **156** | 40 | 59 | 33 | 29 | 12 | 69 |
| **Customer Support** | **167** | — | 111 | 35 | 21 | 12 | 154 |
| | **534** | 49 | 228 | 88 | 75 | 39 | 283 |

**Both circulating numbers were wrong.** `domain_shadow`'s docstring says *"152 authored
capabilities"* — **stale**. The working note said *"211 Admin capabilities"* — **right, and it is
Admin alone.** The real figure is **534 across three domains**.

### And the admission ceremony admits 37% of it

`_tools/admit.py` states the ceremony the resolver enforces — **all three, or nothing**:

```
identity.status == 'stable'
metadata.review_status == 'approved', with a non-empty metadata.reviewed_by
admission.accepted_content_hash == semantic_hash(document MINUS the admission block)
```

| domain | authored | **satisfy all three** | |
|---|---|---|---|
| Admin | 211 | **85** | **40%** |
| Sales | 156 | **62** | 39% |
| Customer Support | 167 | **53** | 31% |
| | **534** | **200** | **37%** |

⛔ **L2-8 flips `require_admission=True`. At that instant 334 of 534 capabilities stop carrying
authority.** Turning the layer on would look like making it worse, and the cause would be in a
YAML header rather than in any code this plan touches.

**This is the largest un-owned risk in the plan and nothing in the eight steps addressed it.**

---

## Q5 · Is the Domain Expertise plane working?

**Loaded: yes. Wired: yes. Admitted: 37%. Complete: no.**

```
Domain Expertise/*.yaml
   ↓  platform/corpus.py      ← "FOUR LAYERS NEED THE SAME THREE LINES OF YAML"
   ↓  ExpertBrainCatalog       (packs/compiler/authoring.py:91)
   ↓  capability_resolver
   ↓  ExpertisePackage
```

The chain is real and it reads from disk. `platform/corpus.py` exists precisely because
`capture/domain/hints.py` used to reach **up** into `packs` and the topology test refused it.

**Every read fails soft, deliberately** — *"a corpus that cannot be read is a DEPLOYMENT problem…
turning it into an ImportError would take the admin console, the capture path and the activation
table down over a typo in one situation file."*

### What is missing

| | |
|---|---|
| **fundraising** | ⛔ **not a domain.** Three folders exist: Admin, Sales, Customer Support. The pilot is a fundraising founder |
| **Persona Brain** | not in `BrainKind`, not an `ExpertisePackage` lane |
| **Goals** | `org_goals` → 0 files. Belongs in Organization Brain as a category row |
| **63% of capabilities** | authored, not admitted |

---

## Q6 · How perfectly is Admin working?

**211 authored · 85 admissible · 40%.**

Also authored for Admin: 9 rules, 58 playbooks, 20 models, 25 objects, 15 offerings, 60 heuristics,
1 role, 1 vertical, plus `deferrals.yaml` and a `registry/situation-capability-map.yaml`.

⛔ **The three admission counts do not agree with each other** — 85 stable, 90 approved, 87 hashed.
If the ceremony were followed uniformly these would name one set. They do not, so **some capability
is approved but not stable, or hashed but not approved**. That is drift inside the ceremony itself,
and it is invisible until a compile refuses something a human believes is live.

**→ a unit: report the three sets and their differences, per domain.**

---

## Q7 · Are the two planes complete?

### Plane R — far more complete than the plan assumed

```
genios_engine/reason/     114 files   39,012 LOC
```

| module | LOC | what |
|---|---|---|
| `store.py` | 2,419 | |
| `runner.py` | 1,495 | the sweep |
| **`decision_maker.py`** | **1,234** | ⛔ **the Decision Maker EXISTS** |
| `domain_shadow.py` | 1,044 | the shadow compile |
| **`llm_decision_maker.py`** | **862** | its model half |
| `critique.py` | 668 | advisory verdict — `proceed` / `modify` / `hold` |
| **`interpretation.py`** | **572** | ⛔ **R-1, the ambiguity interpreter** |
| `narration.py` | 546 | |
| `plan.py` · `brief_ranking.py` · `foresight.py` · `evidence.py` · `guards.py` · `authority.py` | | |

### Plane D — authored, wired, 37% admitted

Covered above.

---

## Q8 · Domain compiler, decision maker, reasoning orchestrator

### ⛔ The single most important thing this pass found

`reason/llm_sites.py`:

> **"THERE IS EXACTLY ONE C5 GATE, AND IT IS `reason/bundle/gate.RSiteGate`. This module does not
> re-implement activation, budget, retry or receipting; it delegates all four."**

`reason/bundle/gate.py`:

> **"no R-site may call a model directly."** Every consult runs seven steps in order:
>
> 1. is this site permitted for this org? — `l4_activation`
> 2. is the precondition met? — the SITE's own, never "just in case"
> 3. is there budget left today? — else **a deterministic template**
> 4. is a cached result available? — keyed on decision hash / fact digest
> 5. run under its **tier and timeout**, T1/T2
> 6. **validate the output** — the caller's validator (**the V-gauntlet**, for R-2)
> 7. on any failure: **deterministic fallback**, recorded — *"never a retry storm, never silence"*
>
> **"The gate decides nothing about the business."**

⛔ **Activation, budget, cache, tier, validator and deterministic fallback all already exist, behind
one door, with a property test.** That is the architecture L2-5 and L2-6 proposed to build.

### The interpreter already holds the doctrine — and it is stronger than the plan's

`reason/interpretation.py`:

> *"The model returns `{classification, confidence_bp}` **as evidence**; a unit reads it like any
> other input; **the formula decides**. The model never says 'this is urgent.'"*
>
> **"1 · IT RUNS BEFORE THE UNITS, NOT INSIDE THEM** — the model's output is an *input* to a
> deterministic computation, **which is the only shape in which a model may participate in a
> decision at all**."
>
> **"2 · IT CANNOT RAISE CONFIDENCE"** — every interpretation ref is minted into the UNSTATED pool.

**"Cannot raise confidence" is stronger than anything this plan wrote**, and it belongs in L2's
reasoner contract verbatim.

### And it has never run

`llm_interpretation.py`:

> **"It has never fired on the pilot tenant: it runs only when the compiled lane is live AND
> `bundle` is activated, and the legacy lane never calls it."**

⛔ **The same sentence, a third time.** `domain_shadow` — compiled, dropped. R-1 — built, never
fired. The corpus — authored, 63% inadmissible. **The engine's problem is not absence. It is
things built correctly and never switched on.**

---

## Q1 · Do tests exist, and do they test the right thing?

| | test files | root-level tests importing it |
|---|---|---|
| `context` | **125** | 78 |
| `reason` | **36** | 66 |
| `packs` | **7** | 35 |

Coverage by count is not thin. **What is untested is the seam**, and that is what the scenario
registry in §8 is for — no test today asserts that a card corresponds to a situation, because no
card does.

---

## Q2 · Q3 · Does it beat the LLM baseline?

**Unknown, and it must stay unknown until it is run.** The benchmark's own status line:

> *"It is currently a two-way comparison, not three. The GeniOS column is empty."*

The six checks that document sets are the acceptance test, and three of them are L2's:

| check | L2's answer today |
|---|---|
| catch the bounced emails | L1's job — `delivery_failure` is a signal type ✅ |
| **catch the Radhesh miss** — replied to the introducer, never to the introduced | ⛔ **needs the recipient graph to be read at situation level.** L1 step 13 closed S39 *"a warm intro is answerable from the recipient graph"* — **L2 has never asked it** |
| **P3 / P4 at full coverage** | ⛔ the database is the context window, which is the product claim; **unproven** |
| report true coverage | L1 carries `coverage` since step 15; **L2 does not surface it** |
| resolve the 3one4 contradiction with the verbatim quote | evidence spans exist end to end ✅ |
| stay in scope | a window is a parameter, not a habit ✅ |

⛔ **Three of six depend on Layer 2 doing something it does not do yet.** The hypothesis is not
tested and must not be claimed.

---

## Q4 + §8 · The scenario registry

L1's step 17 shape, with L2's own classes. Twenty failure classes, `G01`–`G20`:

```
G01 signal arrives, no situation forms              G11 hypothesis hardened into observation  ⛔
G02 situation forms, no expertise routes            G12 inference cites only another inference
G03 expertise routes, package not published         G13 unknowns emptied on thin coverage     ⛔
G04 package published, no card                      G14 interpretation outlived valid_until
G05 card built from a signal, not a situation  ⛔    G15 a refusal with no row
G06 two situations that should be one               G16 a held situation that cannot state its score
G07 one situation that should be two                G17 coverage not carried into the card
G08 evidence ref that does not resolve         ⛔    G18 an admitted capability that is not admissible
G09 a claim with no evidence at all            ⛔    G19 a model raising a confidence            ⛔
G10 visibility leaked through the slice        ⛔    G20 a deterministic fallback that was silent
```

Six marked ⛔ are the ones that reach the founder as a confident falsehood. **They get mutation
probes first** — neutralise the fix, confirm the probe goes red.

### The scenarios that must exist before step 0 closes

| | scenario | expected |
|---|---|---|
| **S-L2-01** | a QES with `ball_in_court='us'` reaches a situation | the situation reads L1's answer, not its own recomputation |
| **S-L2-02** | three signals about one person | **one** situation, three `observed_facts` |
| **S-L2-03** | a fundraising situation | `UNROUTED`, **counted and named** — never silent |
| **S-L2-04** | a situation whose L1 evidence scored below the floor | states *"1360 against a floor of 2500"* |
| **S-L2-05** | a warm intro where the introduced was never emailed | the recipient graph answers it |
| **S-L2-06** | a reasoner proposal citing a non-existent ref | refused, with a row |
| **S-L2-07** | a reasoner returning empty `unknowns` on low coverage | refused |
| **S-L2-08** | a reasoner trying to raise a confidence | ⛔ **impossible by contract**, as R-1 already is |
| **S-L2-09** | budget exhausted mid-sweep | deterministic template, recorded, **never silence** |
| **S-L2-10** | an un-admitted capability | excluded, **and the exclusion counted** |

---

## 9. ⛔ Three corrections to the plan

### 1 · `ARCHITECTURE.md` says the Context Reasoner does not exist. Too strong.

**The pattern exists and works** — R-1 is a model site that returns evidence, cannot raise
confidence, and runs before the deterministic units. What does not exist is **an L2 site using it**.

### 2 · `step-05` proposes a new metered site with its own cache key. Wrong.

⛔ **It must be a new R-site behind `RSiteGate`**, not a second gate. Building a parallel gate would
duplicate activation, budget, retry and receipting — and split the tenant's spend across two
ledgers, which is the one thing `llm_sites.py` says it exists to prevent.

### 3 · `step-06` presents the validation gate as new. Partly wrong.

Step 6 of `RSiteGate.consult` already calls **the caller's validator**, and the **V-gauntlet** is a
working example of one. **What L2 owes is the validator, not the gate.**

---

## 10. What this pass adds to the plan

| | |
|---|---|
| **L2-0-U5** | report the three admission sets per domain and their differences |
| **L2-4-U5** | ⛔ **the admission gap** — 334 of 534 capabilities inadmissible. Owner and date, or the cutover is a downgrade |
| **L2-5** | rewritten: **register an R-site**, do not build a gate |
| **L2-6** | rewritten: **write the validator**, the gate calls it |
| **L2-7-U6** | ask the recipient graph the Radhesh question — L1 closed S39 and L2 never asks it |
| **L2-8** | the benchmark's six checks become the cutover's acceptance test |
