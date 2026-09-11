# Layer 2 v2 — Overview and Doctrine

> **Read `01-Layer-1-Plan/00-Overview-and-Doctrine.md` first.** L2 v2 consumes what
> L1 v2 produces, and the two plans share vocabulary, numbering and the unit spec template.

---

## 1. What Layer 2 is

**Definition**

> Layer 2 turns **qualified signals** into **the current reality of the enterprise** —
> including the parts of that reality that only exist **across** entities and **across** time.

**Name:** Context Intelligence Layer
**Package:** `genios_engine/context/`
**Input:** `QualifiedEnterpriseSignal` (from L1 v2)
**Output:** `BusinessSituationObject`
**Consumer:** Layer 3 (Domain Expertise) — and nothing else.

**The one-line doctrine**

> **L1 says what happened. L2 says what it means in relation to everything else.**

### The change that defines L2 v2

Layer 2 today is a well-built **describer**. Every derived value describes one thing:
this account, this thread, this person. Nothing compares account A to account B, groups
accounts into a cohort, or keeps more than the current value of any metric.

> **L2 v2 adds a stratum Globe never specified: the Analytic Stratum.**
> History, cohorts, comparison, trend.

This is the substrate every pattern the customer expects is made of. Without it,
"this cohort shows early churn signals" is not hard to compute — it is **unrepresentable**.

---

## 2. What L1 v2 changes about L2

| Change | Effect |
|---|---|
| Semantic extraction moves to L1 | `context/extract/` relocates. L2 loses the **extraction** call — and gains eight **judgment** calls (MAP A) |
| Input is now a typed `QualifiedEnterpriseSignal` | `signal_type`, `importance_bp`, verified evidence spans and conflicts all arrive pre-computed |
| `l2_extraction_results` → `l1_extraction_results` | the cache moves with the extractor |

**L2 v2 changes shape rather than getting lighter.** It stops doing high-volume extraction
(every message) and starts doing low-volume judgment (per situation) — see doc 11 for why
that inverts the cost profile.

---

## 3. The seven groups

| # | Group | Components | Status |
|---|---|---|---|
| L2.1 | Enterprise Context Graph (8 views) | 8 | 5 built · **Authority view missing** |
| L2.2 | Graph Engines | 8 | 6 built · version manager is a counter |
| L2.3 | Cross-Correlation Engine | 8 | 2 built · **3 missing** |
| **L2.4** | **Analytic Stratum** | **8** | 🆕 **ENTIRELY NEW — the core of v2** |
| L2.5 | Context Quality Engine | 8 | 4 built · **Missing Context Detection missing** |
| L2.6 | Situation Candidate Generator | 3 | anchor-based; **no pattern registry** |
| L2.7 | Business Situation Engine | 8 | **2 defects**: prioritization hardcoded to 5000, and **no stated-resolution path** |
| | **TOTAL** | **51** | |

---

## 4. MAP A — Where the LLM is used

> **An earlier draft of this document claimed L2 v2 had "zero required LLM sites."
> That was wrong, and the correction matters.** Deterministic code can only **check what
> is or is not there**. It cannot **construct** meaning. Half of Layer 2's job is
> construction.

### The line — drawn on output type, not on layer

> ## In L2 the LLM may judge a **RELATIONSHIP**, a **STATE**, or **frame a narrative**.
> ## It may never produce a **NUMBER**.

| Kind of work | LLM? | Why |
|---|---|---|
| *"Is this situation over?"* | ✅ | a rule can check `stage == closedwon`; it cannot read *"we signed, all done"* |
| *"Are these two things the same?"* | ✅ | judgment, in the ambiguous remainder only |
| *"What is this situation about?"* | ✅ | synthesis — a pattern match yields 5 conditions, not a story |
| *"What does this condition mean?"* | ✅ | *"come back when you have traction"* → a checkable predicate |
| Trend · percentile · cohort evaluation · anomaly · importance | ❌ **never** | see below |

### Why the analytic stratum stays deterministic — comparability, not purity

If a trend is computed by a model in March and again in September and the two disagree,
**you cannot tell whether the business changed or the model did.** A percentile produced
by judgment cannot be compared with last quarter's. Comparison requires a **stable
measuring instrument**; that is a structural requirement, not a doctrine.

**But the work *around* the arithmetic can be LLM-assisted:**

| Task | Owner |
|---|---|
| Which metrics are worth trending in this domain? | **LLM proposes** → human confirms |
| Write a cohort predicate from *"customers like Acme who churned"* | **LLM writes the predicate** → human approves → **deterministic engine evaluates it** |
| What does this trend *mean*? | ❌ not L2 — that is L3/L4 |

Cohort authoring by LLM **preserves** Law 3 (*declared, never clustered*): a human still
approves the predicate, and the predicate — not a model — decides membership.

### The nine sites

| ID | Site | Group | Deterministic gate first | Tier | Est. fires/day |
|---|---|---|---|---|---|
| **M-1** | Ambiguous entity linking | L2.2.4 | alias + domain cascade | T1 | 1–5 |
| **M-2** | Ambiguous edge typing | L2.2.1 | rule table | T1 | 2–10 |
| **M-3** | Cross-conversation matching | L2.3.2 | subject / participant / time | T1 | 3–15 |
| **M-4** | 🔴 **Resolution detection** | L2.7.7 | `terminal_by_fact` first | T2 | **10–30** |
| **M-5** | Condition parsing | L2.3.4 | date / count patterns | T2 | 1–5 |
| **M-6** | **Situation framing** | L2.7.2 | pattern conditions | T2 | **10–40** |
| **M-7** | **Timeline narrative** | L2.7.2 | chronological sort | T2 | 5–20 |
| **M-8** | **Clustering judgment** | L2.7.3 | shared-entity merge | T1 | 2–8 |
| **M-9** | **Cohort predicate authoring** | L2.4.4 | — | T3 | **on demand only** |

Situation naming folds into M-6. Volumes are estimates for an active small-team org and
must be measured — see doc 11.

### The discipline at every site

1. **Deterministic first.** The LLM sees only the ambiguous remainder.
2. **Typed output.** Never a `_bp` field. Never a visibility decision.
3. **Cached** on `hash(subject : member_set : prompt_v : schema_v : model)`.
4. **Budget-guarded**, and on exhaustion it **fails to the deterministic answer** — never
   silently skips.
5. **Span-constrained** where it makes claims: M-6 may only use facts already present in
   the situation's members.

### What survives from the earlier claim

**L2 still discovers patterns deterministically.** *"This account is in the bottom decile
of its cohort and has declined three months running"* needs no model — it is arithmetic
over the analytic stratum, reproducible and citable. The correction is that **describing,
resolving and framing** that finding does need one.

Both halves are true: the **measurement** is deterministic, the **meaning-construction**
is not.

---

## 5. MAP B — Where embeddings are used

**None.** Same decision as L1, same reasoning, and here it is load-bearing.

`context/identity.py:25` states it directly:

> *"No edit distance, no embeddings, no '0.87 similar'. Every one of those turns a
> [resolution into something that] cannot name the rule that resolved it."*

**Cohorts are DEFINED, not clustered.** A cohort produced by k-means is a cohort nobody
can explain, cannot be reproduced after a re-fit, and cannot be argued with. A cohort
defined as *"accounts with ARR between X and Y, onboarded in the last two quarters,
on plan P"* is explainable, stable, and a founder can correct it.

**When to revisit:** never for cohorting or identity. Possibly for a future free-text
retrieval surface — which belongs in its own component, labelled retrieval infrastructure.

---

## 6. MAP C — Where data is stored

| Store | Table | Owns | New? |
|---|---|---|---|
| Graph nodes | `graph_nodes` | the nouns | exists |
| Graph facts | `graph_facts` | current values, version-keyed, **overwritten by design** | exists |
| Graph edges | `graph_edges` | typed relationships | exists |
| Observations | `graph_observations` | what was noticed, by kind | exists |
| Identity | `source_identity_map`, `merge_proposals`, `merge_history` | entity resolution + audit | exists |
| Discrepancies | `discrepancies` | contradictions surfaced, not resolved | exists |
| **Metric history** | **`metric_history`** | **append-only per-node time series** | 🆕 **NEW** |
| **Cohorts** | **`cohort_definitions`, `cohort_membership`** | **declarative segments + who is in them** | 🆕 **NEW** |
| **Comparisons** | **`peer_baselines`** | **per-cohort percentile ladders** | 🆕 **NEW** |
| **Authority** | **`authority_rules`** | **approval thresholds as data** | 🆕 **NEW** |
| **Graph snapshots** | **`graph_snapshots`** | **point-in-time read** | 🆕 **NEW** |
| Situations | `situations`, `situation_members` | the output | exists |
| Read models | `context_read_models` | denormalized lenses for L3/L4 | exists |

### The two-table rule for metrics

`graph_facts` keeps the **current** value and continues to overwrite — that decision was
correct and stays. `metric_history` is a **separate, deliberately sampled** append-only
table beside it.

> Current value and history are different questions with different write patterns.
> Conflating them is why the answer to "is this declining?" does not exist today.

---

## 7. MAP D — Algorithms, rules and formulas

| ID | Algorithm | Unit | Kind | Doc |
|---|---|---|---|---|
| **BLG-01** | Anchor selection + correlation | L2.3.1 | algorithm | 03 |
| **BLG-02** | Entity resolution cascade | L2.2.4 | rule cascade | 02 |
| **BLG-03** | Per-edge freshness decay | L2.2.5 | formula | 02 |
| **BLG-04** | Point-in-time graph read | L2.2.7 | algorithm | 02 |
| **BLG-05** | **Dependency chain construction** | L2.3.8 | graph algorithm | 03 |
| **BLG-06** | **Dormant condition satisfaction** | L2.3.4 | algorithm | 03 |
| **BLG-07** | **Metric sampling policy** | L2.4.2 | decision table | 04 |
| **BLG-08** | **Trend computation** | L2.4.3 | formula | 04 |
| **BLG-09** | **Cohort membership evaluation** | L2.4.4 | predicate engine | 04 |
| **BLG-10** | **Percentile within cohort** | L2.4.5 | formula | 04 |
| **BLG-11** | **Peer baseline computation** | L2.4.6 | formula | 04 |
| **BLG-12** | **Metric correlation** | L2.4.7 | formula | 04 |
| **BLG-13** | **Anomaly vs own baseline** | L2.4.8 | formula | 04 |
| **BLG-14** | Confidence vector composition | L2.5.1 | formula | 05 |
| **BLG-15** | **Missing context detection** | L2.5.5 | rule set | 05 |
| **BLG-16** | **Subgraph pattern matching** | L2.6.1 | graph algorithm | 06 |
| **BLG-17** | Situation clustering | L2.7.3 | algorithm | 07 |
| **BLG-18** | **Situation importance composition** | L2.7.4 | **formula** | 07 |
| **BLG-19** | Situation lifecycle | L2.7.7 | state machine | 07 |

**How an algorithm gets built:** identical five-step procedure to Layer 1 — signature and
docstring first, test table before implementation, pure function, integer basis points,
wire last. See `01-Layer-1-Plan/00-Overview-and-Doctrine.md` §6.

---

## 8. The four laws of Layer 2

**1. L2 describes reality. It never recommends.**
Globe's hard rule: *never reasons.* L2 may say *"this account's engagement is in the
bottom decile of its cohort and declining."* It may not say *"reach out to them."* The
first is a fact about the world; the second is a decision, and decisions are Layer 4's.

**2. Every comparison names its population.**
A percentile without a stated cohort is a number nobody can check. Every comparative
value carries `cohort_id`, `population_size` and `computed_at`. A cohort with fewer than
**5 members** produces no percentile at all — it produces `insufficient_population`.

**3. Cohorts are declared, never clustered.**
A cohort is a predicate a human wrote and can correct. No k-means, no embeddings, no
"the model found these segments."

**4. Absence is a distinct state from zero.**
*"No support tickets"* and *"no source that could carry a support ticket"* are different
facts. `coverage_ready` from L1 v2 carries the difference, and L2.5.5 makes it usable.
A metric with no coverage is `unknown`, never `0`.

---

## 9. Document index

| Doc | Contents |
|---|---|
| `00-Overview-and-Doctrine.md` | this file |
| `01-Group-L2.1-Enterprise-Context-Graph.md` | 8 views, incl. the missing Authority view |
| `02-Group-L2.2-Graph-Engines.md` | 8 components, incl. point-in-time read |
| `03-Group-L2.3-Cross-Correlation.md` | 8 correlators, incl. the 3 missing |
| `04-Group-L2.4-Analytic-Stratum.md` | **8 components — the new core** |
| `05-Group-L2.5-Context-Quality.md` | 8 components, incl. Missing Context Detection |
| `06-Group-L2.6-Situation-Candidate-Generator.md` | 3 components, pattern registry |
| `07-Group-L2.7-Business-Situation-Engine.md` | 8 components, incl. the importance fix |
| `08-Contracts-BusinessSituationObject.md` | typed objects at the L2 seam |
| `09-Build-Order-and-Acceptance.md` | waves and gates |
| `10-CTO-Handoff-Note.md` | copy-paste brief for the coding agent |
| `11-Cost-Model-and-Budget-Guards.md` | **cost drivers, per-site budgets, fail-closed fallbacks** |
| `12-LLM-Edge-Cases.md` | **28 named failure cases across the 9 sites, with mitigations** |
| `13-Loops-and-Convergence.md` | **5 loops, bounded fixpoint, `coverage_epoch`, holiday-vs-broken-coverage** |
| `14-Worked-Example-End-to-End.md` | **one situation through every group, showing where the LLM fires** |
