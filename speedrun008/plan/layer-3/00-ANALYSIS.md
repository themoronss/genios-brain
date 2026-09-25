# Layer 3 — the analysis, before any plan

**Read from the code, 2026-09-25** · against `speedrun008` @ `868208b3`
**Corrected by Rohit**, and the correction dissolves the contradiction the first draft raised.

---

## 0. ⛔ THE CORRECTION, AND IT IS THE WHOLE ANALYSIS

The first draft of this file said Layer 3 could not be *"the context graph"* because the graph is
**upstream** of the business situation — `graph_facts` feeds the correlators, which feed the
producers. That is true and it was answering the wrong question.

> **"Layer 2 ka outcome hai Decision Object. Layer 3 toh un objects ki madad se graph hi banana
> hua na."**

**There are two graphs, and only one of them is upstream.**

| | built from | direction | where |
|---|---|---|---|
| **Evidence Graph** | what sources said | ⬆ **feeds** situation assembly | `graph_nodes` · `graph_facts` · `graph_observations` · `graph_edges` — 10 tables, written by L1→L2 |
| **Intelligence Graph** | **what was concluded** | ⬇ **accumulates after** the decision | ⛔ **does not exist** |

**Layer 3 is the second one.** It is not the graph that produces a decision; it is the graph the
decisions *become*. Nothing in this repository builds it.

⛔ **So Layer 3 is a real BUILD** — which is the opposite of Layer 2, where nine steps found that
almost everything already existed and was merely unswitched.

---

## 1. The chain today: two hops exist, one is missing

```
    a situation                    a decision                     an outcome
  context_situations   ──⛔ NOTHING──▶  reasoning_* / l4_*  ──decision_hash──▶  execution_outcomes
       21 columns                          16 tables                         29 columns
```

Measured across all 185 tables:

| link | exists? | evidence |
|---|---|---|
| decision → outcome | ✅ | `execution_outcomes.decision_hash` |
| decision → the play, capability, assignee, band | ✅ | nine more columns on the same row |
| **situation → decision** | ⛔ **NO** | **not one of the 16 `reasoning_*`/`l4_*` tables carries a `situation_id`**. `l4_reasoning_bundles` mentions a situation only in its comments |
| **decision → situation** | ⛔ **NO** | `context_situations` has 21 columns and **none of them names a decision** |
| decision → decision (superseded, revised) | ⛔ **NO** | no `parent_decision`, no `prior_decision`, no decision edge table |

### 1.1 · ⛔ It is L2-7's defect, one layer up

L2-7 found that `shadow_compile` reads `row["situation_id"]` **four times within twenty lines of
emitting a signal** and then drops it, because there was nowhere to put it. Migration 0182 gave it
somewhere.

**The same value is in scope when the decision is persisted, and is dropped again.** `not_carried`,
at the next seam.

---

## 2. ⛔ "The Decision Object" is not one thing today. It is five.

| shape | where | what it actually is |
|---|---|---|
| `DecisionCandidate` | `contracts/` | the in-memory candidate the reasoner ranks |
| `reasoning_run_outputs` | audit | what one run produced, with its hash |
| `l4_reasoning_bundles` | audit | the narrative, keyed on `decision_hash` |
| `decisions` | `0015` | ⛔ **the QUERY API's cache.** Written by `api/intelligence_routes.py` **and nothing else**, keyed on `sha256(org│module│question│graph_version)`. It is not the sweep's output at all |
| `execution_outcomes` | `0041` | what happened afterwards |

⛔ **This is L2-1's defect at five times the scale.** Two classes sharing one name cost fifteen
wrong annotations across the Domain Expertise compiler. **Five shapes sharing one concept is why
"the Decision Object" can be described in a sentence and cannot be pointed at in the schema.**

**Layer 3 cannot build a graph of decision objects until one of those five is the decision
object.** That is step one, and it is a naming step before it is a graph step — exactly what L2-1
was.

---

## 3. What the Intelligence Graph would hold

Not proposed — derived from what the five shapes already carry and what the chain already links.

```
NODES                                    from
  situation        what was concluded    context_situations           (exists)
  decision         what we chose         reasoning_run_outputs        (exists)
  outcome          what happened         execution_outcomes           (exists)
  entity           who it was about      graph_nodes                  (exists, Evidence Graph)

EDGES                                    from
  decision  ─about→        situation     ⛔ MISSING — §1
  decision  ─supersedes→   decision      ⛔ MISSING — no edge table
  outcome   ─followed→     decision      ✅ execution_outcomes.decision_hash
  situation ─anchored_on→  entity        ✅ context_situations.anchor_node_id
  decision  ─cited→        evidence      ✅ reasoning_evidence_id_map
```

⛔ **Four of the five node types and three of the five edges already exist.** What is missing is
the two edges that make it a graph *of decisions* rather than a log of them — and the naming that
makes "a decision" one thing.

### 3.1 · What the graph is FOR, and it is the reason it must exist

A flat log answers *"what did we decide"*. A graph answers the questions a founder actually asks:

| question | needs |
|---|---|
| *"why did GeniOS tell me this?"* | decision → situation → evidence · **the missing edge** |
| *"did that work?"* | decision → outcome · ✅ exists |
| *"have we been wrong about this account before?"* | decision → decision, over time · **missing** |
| *"what changed since we last looked at this?"* | situation → its decisions, ordered · **missing** |
| *"stop telling me this"* | decision → decision, so a mute reaches the family · **missing** |

**Every one of those is a traversal, and four of the five cannot be answered today.**

---

## 4. What exists that Layer 3 will read, and what state it is in

| | modules | state |
|---|---|---|
| `reason/` | **117** | ⛔ **no layer claims it**, and nobody has audited it. Thirteen files with a metered model call — the most of any package |
| `reason/interpretation` (R-1) | | ⛔ *"has never fired on the pilot tenant"* |
| `reason/domain_shadow` | | `live=False`; L2-8 enumerated the **seven** switches |
| `reasoning_*` / `l4_*` | 16 tables | the audit trail exists and is thorough |
| `situation_interpretations` | 1 table | **new in L2-5** — one reading per (situation, slice), **with the slice**, so a conclusion can be replayed against its premises |

⛔ **`situation_interpretations` is already the first row of the Intelligence Graph**, built two
steps ago without being called that. It records what was concluded, when, from what, and what
expires.

---

## 5. ⛔ What this means for the layer numbering

Under your model the packages line up cleanly, and **nothing has to move**:

```
capture    L1   Enterprise Signals        sources → a qualified signal
context    L2   Situation Intelligence    signals → a situation → a DECISION OBJECT
   ⛔ and `reason/` is where L2's reasoning happens — a PLANE, not a layer after it
   packs   Plane D · Domain Expertise
   reason  Plane R · Reasoning
??????     L3   the Intelligence Graph    the objects, accumulating, traversable
executive  L4   Executive                 a decision → an execution object
deliver    L5   Delivery
feedback   L6   Learning
```

⛔ **There is no package for L3, and that is correct** — because the graph it builds does not
exist. `situation_interpretations` is its first table, and it currently lives in `context/`.

**That is the one structural question this analysis raises:** a new `intelligence/` package, or
does the Intelligence Graph live beside the Evidence Graph in `context/` with a clean internal
seam? The import ratchet decides it — whatever writes it must be importable by `executive/`, and
must not import `reason/` upward.

---

## 6. What Layer 3's first step must be, and it is not a build

Layer 2's plan was written before its premise check and **six of its eight premises were wrong**.
The first step here is the one L2-0 was:

> **Measure `reason/`.** 117 modules, thirteen model sites, one lane that has never fired, and no
> layer claiming it. Find what is built and unswitched *before* deciding what to add.

Then, in order:

| | |
|---|---|
| **1** | ⛔ **Name the Decision Object.** One of the five shapes becomes it; the others become its stages, its audit or its cache. L2-1's exact work, and L2-1 measured what skipping it costs |
| **2** | ⛔ **Carry the situation id into the decision.** L2-7's migration, one seam up. Without it there is no graph, only a log |
| **3** | The decision→decision edge — supersession, revision, and what a mute must reach |
| **4** | The traversals in §3.1, each with the question it answers |
| **5** | Persona Brain · goals in **Organization Brain** · the two things Layer 2 recorded as missing entirely |

---

## 7. What I still need from you

**One thing, and it is smaller than the first draft's question.**

`situation_interpretations` — the first Intelligence Graph table — lives in `context/` today.
**Does the Intelligence Graph get its own package, or does it stay beside the Evidence Graph?**

Everything else in this file follows from the code and does not need a decision:
the two graphs are different, L3 is the second one, it is a genuine build, and its first step is
to measure `reason/` rather than to plan against it.
