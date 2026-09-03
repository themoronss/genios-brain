# Gap Audit — Layer 2: Globe spec vs. built code

**Audited:** 2026-09-03 at commit `b4d4d15`
**Method:** all 43 Globe-specified L2 components checked against `genios_engine/context/`
(35 modules) and the graph migrations. Every claim carries a file:line citation.

---

## The headline

**Layer 2 is in far better structural shape than Layer 1.** The graph is real, identity
resolution is real, the situation engine is real, and the confidence machinery is
genuinely good.

**And it does not matter, because L2 computes nothing comparative.**

Every derived value describes **one thing**: this account, this thread, this person.
Nothing compares account A to account B. Nothing groups accounts into a cohort. Nothing
keeps more than the current value of any metric. The layer is a well-built **describer**
where the product needs a **comparer**.

> This is not a missing component. It is a **missing stratum**.

---

## Scoreboard

| Group | Spec'd | ✅ Built | ⚠️ Partial | ❌ Missing |
|---|---|---|---|---|
| L2.1 Enterprise Context Graph (8 views) | 8 | 5 | 2 | 1 |
| L2.2 Graph Engines | 8 | 6 | 2 | 0 |
| L2.3 Cross-Correlation Engine | 8 | 2 | 3 | 3 |
| L2.4 Context Quality Engine | 8 | 4 | 2 | 2 |
| L2.5 Situation Candidate Generator | 3 | 0 | 2 | 1 |
| L2.6 Business Situation Engine | 8 | 7 | 0 | **1 broken** |
| **TOTAL** | **43** | **24** | **11** | **8** |

**56% built — versus Layer 1's 40%.** The gap is concentrated in correlation (2/8) and
in one broken component that poisons everything downstream.

---

## The four findings

### 🔴 1. Every situation gets the same importance — a hardcoded 5000

`context/situation_bso.py:39` and `:235`:

```python
DEFAULT_IMPORTANCE_BP = 5000
...
importance_bp=DEFAULT_IMPORTANCE_BP,
```

The `BusinessSituationObject` contract **requires** `importance_bp`
(`contracts/domain_expertise.py:65`) — and L2 has nothing to compute it from, so it
stamps a constant on **every situation ever produced.**

This closes the loop on the Layer 1 audit and explains the day-one finding directly:

```
L1 stamps no importance_bp        (contracts/gated_event.py:28, deliberate)
  -> L2 must supply one anyway    (BSO contract requires it)
     -> L2 hardcodes 5000         (situation_bso.py:39)
        -> every situation is equally important
           -> "193 of 223 signals scored an identical 50"
              (reason/reasoners/priority.py:165-197)
                 -> priority_override replaces the formula
                    -> "the formula has never once decided anything"
                       (reason/decision_maker.py:243)
```

**One constant at L2 flattens ranking across the entire product.** L1 v2's ALG-17 is the
supply side; L2.7 consuming it is the demand side. Both are needed.

### 🔴 2. No metric history — every derived fact overwrites itself

`context/derived.py:108-109`, in the code's own words:

> *"a derived value is a **RECOMPUTE, not a new observation of history**: it overwrites
> its own deterministic version id rather than appending a row per drain."*

I searched all 76 migrations for a metric time-series table. The only `history`/`snapshot`
tables are `merge_history` (entity merges), `config_snapshots` and
`reasoning_context_snapshots` (both L4), and `learning_metrics` (L6). **There is no
per-node metric history anywhere in the system.**

**Consequence:** a trend is unrepresentable. Not hard to compute — *unrepresentable*.
There is no place in the schema to put "engagement over the last six months". Every
"declining", "rising", "slower than usual" claim the customer expects is structurally
impossible, regardless of how good the reasoning above it becomes.

The overwrite decision was correct for its stated reason (avoiding three rows per node
per drain forever). The fix is not to stop overwriting the current value — it is to add a
**separate, deliberately sampled** history table beside it.

### 🔴 3. Correlation is joins, never comparison — and 3 of 8 are missing

`context/correlation.py` opens with:

> *"This engine has exactly one job and refuses every other one. It does not prioritise,
> it does not score risk, it does not recommend. It answers one question: **Do these
> signals belong to the same thing?**"*

That is a faithful implementation of Globe — and Globe's own 8 correlators are all joins.
**Not one of them computes a comparison.** Against the founder's bar this is decisive:
"these 3 leads share traits with your highest-LTV customers" is a *comparison across a
population*, and the layer that owns cross-entity work has no primitive for it.

| Globe correlator | Status | Evidence |
|---|---|---|
| Cross Tool | ✅ | `correlate_event`, `choose_anchors` |
| Cross Conversation | ✅ | `thread_correlations` |
| Cross User | ⚠️ | `lift_people_to_their_companies` — a lift, not a role synthesis |
| Cross Resource | ⚠️ | `lift_companies_to_their_deals` — no contract↔spend link |
| Cross Domain | ⚠️ | `resolve_domain` exists; degraded-carry unverified |
| **Cross Timeline** | ❌ | no dormant-condition satisfaction — this is the "condition you set 4 months ago is now met" surface |
| **Cross Organization** | ❌ | no same-party-across-contexts resolution |
| **Dependency Correlation** | ❌ | grep for blocking-chain / prerequisite / circular-wait returns nothing |

**Dependency Correlation's absence is expensive.** Globe: *"A blocks B blocks C — what
makes deadlines more than a calendar."* Without it, Deadline Intelligence degrades to a
reminder app, which Globe itself names as the failure mode.

### 🔴 4. L2 cannot tell when something ENDED

`situations.py:278 decide_lifecycle` is good code — the fact/human distinction is correct
and well documented. But a situation has **only two ways to end**, and one of them is a
single field:

| Path | Trigger |
|---|---|
| `RESOLVED_BY_FACT` | **only** `normalize_stage(deal.stage) in {closedwon, closedlost}` (`situations.py:80`, `:417`) |
| `RESOLVED_BY_HUMAN` | someone clicks |

**One field. One source. Two values. There is no path for "somebody SAID it is done."**

| What happens | Today |
|---|---|
| HubSpot stage → closed-won | ✅ resolves |
| Someone clicks "handled" | ✅ resolves |
| *"All sorted, we signed yesterday"* | ❌ **bumps `last_seen_at` → looks MORE active** |
| A commitment fulfilled in an email | ❌ never detected |
| A decision made in a thread | ❌ never detected |

**A stated resolution makes the situation look more alive, not less.** That is a nagging
machine, and Globe names the consequence exactly: *"It told me about a contract I cancelled
last week"* — instant credibility loss.

**Why deterministic cannot close this.** A rule can check `stage == closedwon`. It cannot
read a paragraph and decide the thing is over. That is **construction of meaning**, not
checking — which is why the plan adds LLM site **M-4** here, gated behind
`terminal_by_fact` so a fact always beats a statement.

### 🟡 5. Three quality components missing, one of them the important one

| Globe component | Status |
|---|---|
| Confidence Calculation | ✅ **strong** — a real vector: `evidence_score`, `freshness_score`, `consistency_score`, `identity_score`, `coverage_score` (`situations.py:102-227`) |
| Freshness Evaluation | ✅ |
| Conflict Detection | ⚠️ `discrepancies` table exists |
| Noise Detection | ✅ |
| **Missing Context Detection** | ❌ **MISSING** |
| Evidence Aggregation | ⚠️ evidence flows, not a named component |
| Context Completeness | ⚠️ `support_situations` only |
| Context Validation | ❌ MISSING |

Globe calls Missing Context Detection *"the most underrated component in the layer —
absence is itself intelligence."* It is the correct trigger for degrading rather than
guessing, and it is absent.

---

## Component detail

### L2.1 — the 8 graph views (5/8)

Views are lenses over `graph_nodes` / `graph_facts` / `graph_edges`, per Globe's design
("eight views over one graph — not eight graphs"). Correct.

| View | Status | Note |
|---|---|---|
| Entity | ✅ | `graph_nodes`, typed |
| Relationship | ✅ | `graph_edges`, typed |
| Temporal | ⚠️ | `valid_from` / `last_reinforced` exist — but **no history**, see finding 2 |
| **Authority** | ❌ | **MISSING.** grep for approval thresholds returns nothing. Globe: *"`Arjun approves contracts > $50K` lives here as data, not as an `if` statement"* |
| Ownership | ✅ | `open_loops`, ball-in-court |
| Communication | ✅ | thread facts, contact frequency (`97aeb46`), account rollups (`d11f6e7`) |
| Resource | ⚠️ | money attaches, but `deal.value` is **deliberately not derived** (`derived.py:182`) |
| Knowledge | ✅ | `canon.py`, `document_register.py` |

**The Authority view's absence has a specific downstream cost:** L4's Policy and
Constraint units both need approval thresholds as data. Without the view they cannot fire.

### L2.2 — Graph Engines (6/8)

| Component | Status |
|---|---|
| Graph Builder / Updater / Validator | ✅ `pipeline.py`, `derived.py`, `guard.py` |
| Graph Deduplicator | ✅ **strong** — `identity.py`, `merge.py`, `merge_proposals`, audit trail |
| Freshness Manager | ⚠️ freshness scored; per-edge half-life decay not implemented |
| Lifecycle Manager | ✅ `meeting_lifecycle.py` + situation lifecycle |
| **Version Manager** | ⚠️ **a counter, not a reader.** `graph_store.py:69-72` increments an integer. There is **no `as_of` / point-in-time query**, so *"what did GeniOS know when it decided that?"* — the question Globe says every enterprise security review asks — **is not answerable** |
| Consistency Checker | ✅ `discrepancies` |

### L2.5 — Candidate Generator (0/3)

Globe specifies subgraph **pattern matching**: *"graph patterns, not text patterns"*,
with a pattern registry per surface. The code instead derives situation type from an
**anchor node type**: `situations.py:83 situation_type(anchor_type, domain)`.

Anchor-based detection cannot express *"contract renewal + auto-renewal + high value +
short cancellation window + active migration discussion + no scheduled decision"* — the
six-condition pattern that is Globe's own worked example. **No pattern registry exists.**

---

## Where the code is BETTER than the spec

1. **The confidence vector is real and better than Globe's scalar.** `situations.py`
   computes evidence, freshness, consistency, identity and coverage as separate scores.
   Globe's own open-blocker list names scalar confidence as a defect; L2 already fixed it.
2. **Identity resolution has an audit trail.** `merge_proposals` + `merge_history` +
   `discrepancies` means an entity merge is reviewable and reversible. Globe asks for
   entity resolution; the code delivers governed entity resolution.
3. **`deal.value` is deliberately not derived** (`derived.py:182-184`): *"a wrong one
   would flow straight into prioritisation."* That restraint is correct — and it becomes
   safe to lift once L1 v2 supplies validated `Money` with evidence.
4. **The anchor-priority design** deliberately excludes the tenant node from correlation,
   so one org node cannot swallow every conversation into a single situation. A subtle
   failure mode, correctly pre-empted.

---

## What L1 v2 changes about L2

L1 v2 moves semantic extraction **out** of L2. That has three consequences the L2 plan
must absorb:

| Change | Effect on L2 |
|---|---|
| `extract/` moves to L1 | L2's only LLM site disappears. L2 v2 is near-zero LLM |
| Input becomes `QualifiedEnterpriseSignal` | typed `signal_type`, real `importance_bp`, verified evidence spans, conflicts — all arrive pre-computed |
| `l2_extraction_results` → `l1_extraction_results` | the cache moves with the extractor |

**L2 v2 gets lighter and smarter at the same time.** Freed of extraction, it can spend
its budget on the thing only it can do: **computing across entities and across time.**

---

## Correction log

| Date | Claim | Correction |
|---|---|---|
| 2026-09-03 | *"Layer 2 v2 has zero required LLM sites"* | **Wrong.** Deterministic code can only check what is or is not there; it cannot construct meaning. Resolution detection, situation framing, timeline narrative, clustering judgment, conversation matching and condition parsing are all construction. The plan now carries **9 LLM sites**. The *measurement* in the analytic stratum stays deterministic — for comparability, not purity. |
| 2026-09-03 | the audit listed 4 findings | **A fifth was missing:** the lifecycle gap above. It is arguably the one a customer notices first. |

---

## Verdict

Layer 1's problem was **absent components**. Layer 2's problem is different and, in a
way, harder: **the components are present and correct, and they were specified to
describe rather than compare.**

Fixing L2 is not mostly filling gaps in Globe's 43. It is adding a **stratum Globe never
specified** — metric history, cohorts, comparison, trend — plus the 8 genuinely missing
components. That stratum is the substrate every "pattern" the customer expects is made of.
