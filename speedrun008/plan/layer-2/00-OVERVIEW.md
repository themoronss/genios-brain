# Layer 2 — Situation Intelligence

**Written:** 2026-09-24 · against `speedrun008` @ `22000d07`
**Reading order:** this page → [`ARCHITECTURE.md`](ARCHITECTURE.md) → the step files → [`STATUS`](../STATUS.md)

---

## The contract, in one sentence

> **Layer 2 takes what Layer 1 saw, reads it with the domain's expertise, and states what is
> happening — separating what was observed from what was inferred, and pointing every word at a
> receipt.**

Its input is `QualifiedEnterpriseSignal`. Its output is `BusinessSituationObject`.

### The one rule that defines the boundary

```
Observation  ≠  Inference  ≠  Hypothesis
```

A model may propose an inference. **It may never write an observation.** That is L1's
`EvidenceSpan.verified` doctrine one layer up — *"the moment another caller can set that flag, it
stops meaning 'checked' and starts meaning 'claimed'."*

---

## ⛔ Three measured facts this plan is built on

### 1. Layer 2 is bigger than Layer 1 and produces shallower output

```
L1  capture/   138 files   42,311 LOC
L2  context/   111 files   48,322 LOC      ← larger
```

And the card it produces reads *"Nitesh's inbound messages dropping over 28 days"* — a measurement.
**Size is not the problem. Shape is.**

### 2. The card is built from a SIGNAL, not a situation

`deliver/pipeline.py:269`:

```python
signals = _open_signals_without_cards(graph, org_id, eval_time)
for sig in signals:
    ...                       # one signal → one card
```

`situation` appears nine times in that file and `expertise` six, **but the loop runs over signals.**
Three measurements about one person therefore become three cards, and no layer between them can
merge them — because the builder never sees a situation.

### 3. ⛔ The dominant failure is a refusal that is RIGHT and INVISIBLE

Four defects, one shape — each quoted from the code that carries it:

| | measured | the refusal | the defect |
|---|---|---|---|
| held situations | **63 of 159** | correct — evidence scored 528–1920 against a floor of 2500 | **no surface says so** |
| support corpus | **33 situations** | a spelling seam, `support` vs `customer_support` | *"which is why the miss was invisible"* |
| fundraising | **every one** | correct — no corpus authored | dark on every tenant configuration |
| untraceable promises | **21**, ten of them carded | correct, and now early | *"the founder saw promises nobody made"* |

`situation_bso.py:565` names it exactly:

> *"**THE REFUSAL IS CORRECT** ... **THE SILENCE IS NOT.** Such a card today simply exists, ranks,
> and quietly never becomes anything, while no surface says 'its best evidence scored 1360 against a
> floor of 2500'. That is **the fifth time** this codebase has carried a refusal that was right and
> invisible."*

**L1 solved this for signals and wrote the rule down — `DROP ≠ DELETE`. L2 has the refusals and not
the ledger.**

### 4. ⛔ Layer D is authored, wired — and 63% inadmissible

`Domain Expertise/` sits in this repository: **1,425 YAML files, 534 capabilities** across Admin
(211), Sales (156) and Customer Support (167), plus 228 playbooks, 283 heuristics, 88 models.

**Only 200 of the 534 satisfy the admission ceremony** — stable **and** approved **and** hash-
stamped. ⛔ **L2-8 flips `require_admission=True`, and at that instant 334 capabilities stop
carrying authority.** Turning the layer on would look like breaking it.

**And `fundraising` is not one of the three domains.**

### 5. The contract itself proves the diagnosis

`BusinessSituationObject` v2 holds 28 fields. Against the 19 the new architecture names, six are
missing:

```
observed_facts · inferred_state · hypotheses · implications · reasoning_trace · valid_until
```

**Every field present is an observation field. Every field missing is an interpretation field.**
That is the exact signature of a layer that correlates and does not reason.

> So Layer 2 is not broken and does not need replacing. **It is half-built, and the missing half has
> a name.**

---

## What changes, in one diagram

```
TODAY
  QES ──→ correlate ──→ situation ──→ [expertise, unread] ──→ ⌀
   └────────────────────────────────────────────────────────→ CARD

PLANNED
  QES ──→ correlate ──→ CANDIDATE
                           + evidence slice      (Evidence Graph)
                           + ExpertisePackage    (Plane D · 5 brains)
                           + goals & policies    (Organization Brain)
                                  ↓
                          CONTEXT REASONER       (Plane R · the one new model site)
                                  ↓  a PROPOSAL, not a truth
                          VALIDATION GATE        (deterministic · free)
                                  ↓
                          BUSINESS SITUATION ──→ Intelligence Graph
                                  ↓
                          DECISION MAKER         (one call · object is its result)
                                  ↓
                          DECISION OBJECT    ──→ Intelligence Graph
                                  ↓
                                CARD
```

**The deterministic half stays deterministic.** The model interprets what correlation assembled; it
does not replace it. So *"the same graph re-swept tomorrow produces the same answers"* stays true of
the **assembly**, and the new uncertainty is confined to the **interpretation**, where it is
labelled.

---

## Two graphs, not one

| | holds | written by | may a model write here? |
|---|---|---|---|
| **Evidence Graph** | facts, entities, events, edges | deterministic, as data lands | ⛔ **never** |
| **Intelligence Graph** | situations, inferences, hypotheses | only a validated reasoner output | yes, and every row carries `evidence_refs` pointing **into** the Evidence Graph |

Both already exist physically — `graph_nodes`/`graph_facts`/observations/edges versus
`context_situations`. **The intelligence half is simply filled by the wrong writer today:**
`situations.py`, `periodic.py`, `meeting_touch.py`, `document_register.py` — correlators, not
reasoning.

---

## The nine steps

| | step | needs Harsh? |
|---|---|---|
| **L2-0** | ⛔ **Make every refusal visible** — the denominator for every later number | counts only |
| **L2-1** | Name it — Situation Intelligence, Plane D/R, `SituationCandidate` | no |
| **L2-2** | The six interpretation fields, with write authority enforced | migration only |
| **L2-3** | The evidence slice — handed, never fetched | no |
| **L2-4** | Domain Compiler — stop failing silently, close the `fundraising` hole | no |
| **L2-5** | The Context Reasoner — the one new model site | cost check needs corpus |
| **L2-6** | The validation gate — a proposal becomes a situation | no |
| **L2-7** | Cut the card over from signal to situation | no |
| **L2-8** | Turn it on, then the adversarial pass | parity needs corpus |

**L2-1, 2, 3, 4, 6 and 7 need nothing from Harsh. L2-0 needs only a count.** That is the order to build in.

---

## What Layer 2 must never do

* **Never write a fact.** The Evidence Graph is deterministic and append-only; a model proposes into
  the Intelligence Graph or nowhere.
* **Never let a claim travel without a receipt.** Every `inferred_state`, `hypothesis` and
  `implication` resolves to an `evidence_ref` inside the Evidence Graph, or the gate refuses it.
* **Never convert unknown into false.** An empty `unknowns` under low coverage is a refusal, not a
  clean bill.
* **Never decide.** *"What is happening"* is L2. *"What should happen"* is Decision Intelligence,
  and merging them makes a wrong card undebuggable.
* **Never fetch its own context.** A reasoner that can query the graph cannot be replayed.
