# The architecture — what it is, and how it works

> Six product layers on a foundation floor. Layer 2 is where the system thinks; Layers 1 and 3
> exist to feed it the truth and to remember what it concluded. Together those three are the
> **Reasoning Plane**.

---

## 1 · The one picture

```
   Gmail · Calendar · Slack · Drive · CRM · Screen
                      │
   ┌──────────────────┼──────────────────────────────────────────┐
   │  REASONING PLANE — the intelligence core                    │
   │                                                             │
   │   L1 Enterprise Signals ──── signal bundle ────►  L2         │
   │   capture/                ◄── EvidenceNeed ────  Reasoning   │
   │   what happened, qualified                       (primary)   │
   │                                                     │  ▲     │
   │                                     ReasoningResult │  │     │
   │                                                     ▼  │ ContextSnapshot
   │                                        L3 Context Graph │    │
   │                                        context/         │    │
   │                                        what we now know ┘    │
   └──────────────────┼──────────────────────────────────────────┘
                      │ DecisionObject
                      ▼
        L4 Executive ──► L5 Delivery ──► humans + agents
        executive/       deliver/              │
             ▲                                 │ outcomes
             │                                 ▼
             └────── through data ──────  L6 Learning
                  (rule_mutes, lvl3_config)   feedback/
```

**Inside L2 there are two planes, not one stage.**

| | Plane R · `reason/` | Plane D · `packs/` + `Domain Expertise/` |
|---|---|---|
| answers | **how** a professional thinks | **what** a professional knows |
| holds | versioned thinking contracts — evidence, temporal, ownership, pattern, risk, intervention | capabilities, expected states, patterns, counter-patterns, evidence rules |
| domain-free? | yes — the same temporal unit reads a notice period, a quarter close and an offer expiry | no — it *is* the domain |
| changes when a domain is added | never | always — and only as reviewed YAML |

A plane is **consulted**, not passed through. That is why adding Sales expertise changes no engine
code, and why a new reasoning method benefits every domain at once.

---

## 2 · What each layer owns

| Layer | Package | The one question it answers | Hands out | Hard rule |
|---|---|---|---|---|
| **L0** | `contracts/ platform/ api/` | What holds everything up? | typed contracts, wiring, activation | no business meaning |
| **L1** | `capture/` | What happened, and how reliable is it? | qualified signals + coverage | never concludes a situation |
| **L2** | `reason/` + `packs/` | What does it mean, and what is the best next move? | ReasoningDecision, EvidenceNeed | stores nothing; decides nothing for a human |
| **L3** | `context/` | What does the company now know? | admitted situation, ContextSnapshot | never reasons by itself |
| **L4** | `executive/` | Who decides, and how does it become a commitment? | ExecutionObject | no model decides; nothing fires unrevalidated |
| **L5** | `deliver/` | Who sees it, where, when, in what form? | card + delivery receipt | never authors a fact |
| **L6** | `feedback/` | What did reality teach, and which layer must change? | mutes, pack config, proposals | never edits the Expert Brain |

---

## 3 · How the work actually moves

**Down is data. Up is a request or a row — never an import.**

`tests/test_layer_topology.py` fails the build when a file imports a higher layer. Cross-layer
needs are met one of two ways:

- **injection** — the composition root resolves a value and passes it down; or
- **data** — a table written above and read below. `feedback/calibrate.py` writes `rule_mutes` and
  `tenant_packs.lvl3_config`; `reason/runner.py` and `packs/registry.py` read them. That is the
  whole mechanism behind the learning loop, and it is live today.

**The one edge that does not exist yet** is L2 asking L1 for a named missing fact. `EvidenceNeed`
is the contract for it, and `context/residue.py` already computes the demand — its
`signal_unreached` measures *"the Layer 1 verdicts no Layer 2 reading consumes"* — but that number
reaches the model angles and never reaches `capture/`. Building that wire is M9.C2.

---

## 4 · Where a model may run, and where it may not

> **The model may describe and propose. Code validates. Company state commits.**
> If the output is a number, a route or a permission, no model produces it.

| May | May never |
|---|---|
| parse and extract from messy text and Hinglish (L1) | score importance, priority or confidence |
| propose frames, hypotheses, counterexamples (L2) | choose a recipient, channel, time or escalation |
| word a card inside a validated vocabulary (L5) | grant a permission or exercise authority |
| parse a free-text correction (L6) | write to the graph without validation |

**The law, as the code states it:** *a model may propose a situation; it may never rank one, and
never produces a number a card asserts.* A model runs only where a deterministic pass has already
**refused** — that is what `context/angles/` is: a closed enum, a fixed confidence band, one
batched call per subject, and a gate miss never pays.

Measured today: Plane R makes **zero** model calls on its decision path; four narrow angles run in
`context/`; and `relevance` has **no model wired in production at all** (`no_model_wired` = 251).

---

## 5 · The four numbering vocabularies

`genios_engine/LAYERS.py` is the single place a layer number lives. `docs/LAYER_MAP.md` is the
translation table. **Always name the package, never the digit alone.**

| Package | `LAYERS.py` | Old dossier | Product (this folder) |
|---|---|---|---|
| `capture/` | 1 | L1 Capture | **L1** |
| `context/` | 2 | L2 Context graph | **L3** — and it also assembles situations today |
| `packs/` | plane (import rule 3) | L4 Domain packs | **L2 · Plane D** |
| `reason/` | plane (import rule 4) | L3 Reasoning | **L2 · Plane R** — and it also chooses the action |
| `executive/` | 5 | — | **L4** |
| `deliver/` | 6 | L5 Delivery | **L5** |
| `feedback/` | 7 | L6 Feedback | **L6** |

⛔ Two collisions, stated plainly. *"Layer 3"* means Domain Expertise in 115 repo files and Context
Graph in the product. And the tail is off by one — `executive`/`deliver`/`feedback` are 5/6/7 in
code and 4/5/6 in the product, across 241 files.

⛔ Two packages are not one-to-one, and that is a fact about the packages: `context/` spans product
L2 **and** L3; `reason/` spans L2 **and** L4. Which is why **decision 4** in `02-DECISIONS.md`
exists — two product layers scheduled against one package will collide on the same files.

---

## 6 · The doctrines that shaped every decision above

| Doctrine | What it means |
|---|---|
| Observation ≠ inference ≠ hypothesis | three epistemic statuses, never merged |
| The model may DESCRIBE, never SCORE | an LLM writes words; arithmetic decides |
| Integer basis points, no floats | 7,500 bp not 0.75 — replayable arithmetic |
| No clocks inside logic | `eval_time` is a parameter, never `now()` |
| NULL is an answer | a value that cannot be reconstructed is never fabricated |
| Soft delete only | `status` moves; rows never vanish |
| `not_carried` | a value computed correctly and then dropped at a boundary |
| The six-times defect | a unit built, tested, green — and called by nothing on a real path |
| Declared silence | every silent lane carries a reason **and** a mover |
| Totality guards | a closed constant checked in **both** directions; one way is half a guard |
| A receipt may never abort the thing it is a receipt for | otherwise accounting failure becomes product failure |

`not_carried` and the six-times defect are the same disease at two seams: something exists and
never reaches the place that needed it. Both stay green in a hermetic suite — which is why the
`pg` lane, run for the first time on 29 Sep, immediately surfaced two production bugs.
