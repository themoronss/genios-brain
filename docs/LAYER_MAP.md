# GeniOS Layer Map — the one translation table

**Four** specs number the layers four different ways. **Nobody says "L5" without a package
name attached.** The layer index lives in code at `genios_engine/LAYERS.py`; import
direction (same-or-lower only) is enforced by `tests/test_layer_topology.py`.

| Package (code) | Layer # | Name | Old dossier name | What it owns |
|---|---|---|---|---|
| `capture/` | 1 | **Enterprise Signals** | L1 Capture | Read + normalize reality. Connectors, envelope, dedup, preprocess, gate, triage, parked, payloads, traces. Zero reasoning. |
| `context/` | 2 | **Situation Intelligence** | L2 Context graph | Assembles a **situation**, judges it against eight admission laws, and exposes only an admitted one. The live digital twin underneath it: entities, relationships, facts, observations, timeline, attention. The ONE extraction LLM call lives here. |
| `packs/` | **Plane D** (import rule: 3) | **Plane D · Domain Expertise** | L4 Domain packs | The four brains + capability content, shipped as data. Universal = pack manifests; Organization = org settings/knowledge; Behavioral = user_models; Adaptive = calibration + outcomes. |
| `reason/` | **Plane R** (import rule: 4) | **Plane R · Reasoning** | L3 Reasoning | Deterministic cognition: rule eval, integer-bp scoring, baselines, derived signals, foresight. Zero model calls. |
| `executive/` | 5 | Executive Engine | — | **Two halves.** *Decision intelligence:* Decision Briefs (brief.v1), verb taxonomy, four modes incl. **preventive** (distance-to-flip), summary ladder, executive memory, why-not receipts, the invention validator's canonical home. *Executive engine:* the Execution Object (execution.v1) — interpret → plan actions → resolve owner → choose channel → validate → track → remind → escalate → monitor → emit outcome. **Owns who and where** (`assignment.py`, `communication.py`); deliver executes the plan it authors. No model decides anything. Surface: `/v1/executive/*`. |
| `deliver/` | 6 | Intelligence Distribution | L5 Delivery | Cards, channels, digest, outbox, agent gateway, rendering. *Executes* Layer 5's communication plan — adapters, retries, budget, copy. `router.py` delegates ownership to `executive/assignment.py`. |
| `feedback/` | 7 | Learning Engine | L6 Feedback | Precision windows, nudges, mutes, MACV. Writes learned state DOWN as data (rule_mutes, lvl3_config) — never imported upward. |

Cross-cutting (outside the ordering): `contracts/` (boundary types; imports platform only),
`platform/` (config/db/crypto/wiring — the composition root), `api/` (transport surface).

## ⛔ `packs` and `reason` are PLANES, not stages — L2-1, 2026-09-24

A digit implies a position in a pipeline. These two are what `context` reasons **with**: consulted
during situation assembly and interpretation, not passed through in sequence. The numbers 3 and 4
survive in `LAYERS.py` because the topology test reads them and **the import ordering they encode
is correct** — a plane may still import same-or-lower only. **The number is an import rule, not a
claim about sequence**, and `LAYERS.py` now says so in its docstring.

`context` is **Situation Intelligence** rather than "Context Intelligence" for the same reason the
two `BusinessSituationObject`s were renamed: the old name says *where the layer sits*, not *what it
produces*. Describing L2 as a graph builder is how a card came to be wired to a signal while the
situation layer was bypassed entirely.

## The two situation stages, and the name that used to be shared

`contracts/situation_stages.py` is the table, checked in both directions at import time.

| stage | class | produced by | fields |
|---|---|---|---|
| **candidate** | `contracts.domain_expertise.SituationCandidate` | `situation_bso.build_business_situation` | 16 |
| **admitted** | `contracts.situation.BusinessSituationObject` | `situation_publisher.upgrade_situation` | 28 |

Both were called `BusinessSituationObject` until 2026-09-24. The old name survives as a deprecated
alias until **2026-12-24** (`situation_stages.ALIAS_REMOVAL`). ⛔ The shared name had left **fifteen
parameters across the whole Domain Expertise compiler annotated with the candidate while every
production sweep handed them the admitted object** — invisible because the two spelled the same and
the admitted object carries seven v1-named compatibility properties.

**The rule that matters:** a lower layer never imports a higher one. Cross-layer needs are
met by *injection* (platform/wiring resolves and passes values down) or by *data* (a table
written above, read below — e.g. `rule_mutes`, `lvl3_config.rule_offsets`).

**Where the 5/6 line sits, and why it moved.** Owner and channel selection used to live in
`deliver/router.py`, which made Layer 6 the authority on who owns a recommendation. That was the
wrong home: deciding whether to interrupt somebody is part of the commitment, not part of its
transport. "Page this person now" and "let them find it in tomorrow's digest" are two different
promises about how much of their attention the work is worth, and that judgement belongs with
the layer that decided the work was worth doing. Layer 5 now authors the communication plan
(audience, seat, channel, interrupt, tone) and freezes it into the Execution Object; Layer 6
executes it — adapters, retries, budget, copy, the outbox. Deliver imports executive; executive
never imports deliver, and `executive/validate.py` documents the same downward-import pattern
for the render validators.

---

## ⛔ The fourth vocabulary — how the product is described, 2026-09-25 (L3-00)

The product is described to a founder as six layers, and **that numbering is not this file's
numbering**:

```
L1 Enterprise Signals
L2 Signals Qualification   (Signals + Domain Expertise = Reasoning)
L3 Context Graph
L4 Executive
L5 Delivery
L6 Learning
```

| package | `LAYERS.py` | old dossier | Atlas | **product** |
|---|---|---|---|---|
| `capture/` | 1 | L1 Capture | 1 | **L1** |
| `context/` | 2 | L2 Context graph | 2 | ⛔ **L2 *and* L3** |
| `packs/` | – (import rule 3) | L4 Domain packs | 3 | ⛔ **folded into L2** |
| `reason/` | – (import rule 4) | L3 Reasoning | 4 | ⚠️ **L2 *and* L4** |
| `executive/` | **5** | – | 5 | ⛔ **L4** |
| `deliver/` | **6** | L5 Delivery | 5.2 | ⛔ **L5** |
| `feedback/` | **7** | L6 Feedback | 6 | ⛔ **L6** |

### Two collisions, stated plainly

**⛔ "Layer 3" means Domain Expertise in this repo and Context Graph in the product.**
115 files say *"Layer 3"* or *"L3"*; `reason/domain_shadow.py`'s first line is literally
*"Layer 3 Domain Expertise compiler"*, and under the product vocabulary that module is **L2**.

**⛔ The tail is off by one.** `executive`/`deliver`/`feedback` are **5/6/7** here and **4/5/6**
there. 241 files mention L5 or L6.

### Two packages are not one-to-one, and that is a fact about the packages

`context` spans product **L2 and L3** — it assembles situations *and* holds the graph they are
derived from. `reason` spans product **L2 and L4** — `domain_shadow` is expertise reasoning,
`runner`/`composer`/`store` choose an action. Their own docstrings say so **in the old numbering**,
in the same package.

**Neither is a bug and neither is urgent.** `LAYERS.py` already declares `packs` and `reason` to be
**planes, not stages** — *"consulted rather than passed through"* — and the import rule it enforces
is correct under every vocabulary. This is recorded so nobody later reads a package boundary as a
layer boundary.

### The rule that survives all four

> ⛔ **Always name the package, never the digit alone.**

