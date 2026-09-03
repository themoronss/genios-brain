# CTO Handoff — Layer 2 v2

> Section A is for you. Section B is a copy-paste block for the coding agent.

---

# SECTION A — For the CTO

## What is different about Layer 2

Layer 1's problem was **absent components** — 16 of 48 missing, the gateway 2 of 10 built.

**Layer 2's problem is the opposite and, in a way, harder: the components are present and
correct, and they were specified to describe rather than compare.**

56% of Globe's 43 components are built. The graph is real. Identity resolution is genuinely
good — governed, reversible, auditable. The confidence machinery is a real vector and is
**better than the Globe spec**, which still models confidence as a scalar.

And none of it matters for the customer, because **every derived value describes one
thing**. This account. This thread. This person. Nothing compares account A to account B,
groups accounts into a cohort, or keeps more than the current value of any metric.

> That is not a missing component. It is a **missing stratum**.

## The three things this plan fixes

**1. One constant flattens ranking across the entire product.**

`situation_bso.py:39` — `DEFAULT_IMPORTANCE_BP = 5000`, stamped on **every**
`BusinessSituationObject` ever produced. The BSO contract requires `importance_bp`; L2 had
nothing to compute it from, so it satisfied the contract with a constant.

```
L1 refuses to stamp importance  ->  L2's contract requires it  ->  L2 hardcodes 5000
   ->  "193 of 223 signals scored an identical 50"
      ->  "the formula has never once decided anything"
         ->  two tenants get IDENTICAL rankings
```

**Layer 1's W7 is the supply side. Layer 2's X5 is the demand side. Neither works alone** —
L1 can compute importance perfectly and L2 will still stamp 5000 over it.

**2. A trend is unrepresentable — not hard, unrepresentable.**

`derived.py:108-109`: *"a derived value is a RECOMPUTE, not a new observation of
history."* I searched all 76 migrations; there is no per-node metric history table
anywhere. There is nowhere in the schema to put "engagement over six months". Every
"declining", "rising", "slower than usual" claim is structurally impossible.

**3. Correlation is joins, never comparison — and 3 of 8 are missing.**

`correlation.py` opens by refusing everything except *"do these belong to the same
thing?"* That is a faithful implementation of Globe — **and every one of Globe's eight
correlators is a join.** Not one computes a comparison across a population, which is what
"these leads look like your best customers" actually is.

Missing outright: **Dependency Correlation** (what makes a deadline more than a calendar),
**Cross Timeline** (the "condition you set 4 months ago is now met" surface), and **Cross
Organization** (a data-leak-class blocker, not just an intelligence one).

## The architectural claim worth arguing about

**L2 v2 discovers patterns without a language model.**

*"This account's engagement is in the bottom decile of its cohort and has declined three
months running"* is a discovered pattern. Nobody wrote a rule naming that account. It is
computed — deterministically, reproducibly, every input citable.

Layer 2 v2 has **zero required LLM sites** (semantic extraction moves to L1; one optional
cosmetic naming call remains).

This reframes the day-one finding that GeniOS has no synthesis cognition. Globe's doctrine
— *"if the output is a number, the LLM never produces it"* — is **not** the obstacle to
discovery it appears to be. It only becomes one when the comparative substrate is missing,
which is exactly the situation today. Build the substrate and deterministic pattern
discovery follows.

## Two deliberate refusals

**Cohorts are declared, never clustered.** A k-means cohort cannot be explained on a card,
changes on every re-fit, and a founder cannot correct it. A cohort defined as *"ARR
10k–50k, onboarded in the last 2 quarters, on Growth"* is explainable, stable and
correctable.

**Cross-tenant comparison is out of scope for v2.** It is the most tempting feature in
this plan and the most dangerous — it needs a k-anonymity floor, explicit opt-in, legal
review and a privacy contract. That is a product decision with a compliance surface, not
an engineering task to slip into a layer plan. Every baseline in v2 is within one tenant.

## Sequencing — the good news

**X0 through X4 — the entire analytic stratum — can be built while Layer 1 is still in
progress.** They read the existing graph. This is the largest piece of parallel work
available in Version 2 and it should start immediately. X7 (authority view, point-in-time
read, dependency chains) is a second independent track.

Only **X5** genuinely blocks on Layer 1 (W7), and it is the gate that proves the whole
thing worked.

## The gate that tells you it worked

**H5**, and it must be read together with Layer 1's **G7**:

```
python scripts/situation_importance_distribution.py --org <pilot> --since 30d
```
More than 50 distinct `importance_bp` values, p90−p50 above 1500, under 5% still at
exactly 5000.

**Passing G7 while failing H5 changes nothing for the customer.** The constant would still
flatten everything downstream.

---

# SECTION B — Copy-paste to the coding agent

```
You are implementing Layer 2 v2 of GeniOS, the Context Intelligence Layer.

=== READ FIRST, IN THIS ORDER ===
  Rohit_Updates (Version 2)/Version 2 Updates/04-Gap-Audit-L2-Spec-vs-Code.md
  .../Version 2 Updates/02-Layer-2-Plan/00-Overview-and-Doctrine.md
  .../Version 2 Updates/02-Layer-2-Plan/09-Build-Order-and-Acceptance.md
  .../Version 2 Updates/02-Layer-2-Plan/08-Contracts-BusinessSituationObject.md
Then the group doc for the wave you are building. Each has a REVERSE PROMPT block.

=== WHAT LAYER 2 IS ===
L2 turns qualified signals into the current reality of the enterprise — INCLUDING the
parts of that reality that only exist ACROSS entities and ACROSS time.
Package: genios_engine/context/   In: QualifiedEnterpriseSignal   Out: BusinessSituationObject

L1 says what happened. L2 says what it means in relation to everything else.

=== THE FOUR LAWS ===

1. L2 DESCRIBES REALITY. IT NEVER RECOMMENDS.
   L2 may say "this account's engagement is in the bottom decile of its cohort and
   declining." It may NOT say "reach out to them." The first is a fact; the second is a
   decision, and decisions are Layer 4's.

2. EVERY COMPARISON NAMES ITS POPULATION.
   A percentile without a stated cohort is a number nobody can check. Every comparative
   value carries cohort_id, population_size and computed_at. A cohort with fewer than 5
   members produces NO percentile — it produces insufficient_population. Enforced by
   contract validator, not by convention.

3. COHORTS ARE DECLARED, NEVER CLUSTERED.
   No k-means, no embeddings, no "the model found these segments." A cohort is a
   predicate a human wrote and can correct. If you are importing sklearn, stop.

4. ABSENCE IS A DISTINCT STATE FROM ZERO.
   "No support tickets" and "no source that could carry a support ticket" are different
   facts. coverage_ready (from L1 v2) carries the difference. A metric with no coverage
   is unknown, NEVER 0. Reading a coverage gap as a decline is a false churn signal and
   it is the worst output this layer can produce.

=== TECHNICAL RULES ===

- INTEGER BASIS POINTS ONLY. No float anywhere. No numpy, no statistics module, no
  sklearn. Integer least squares, integer nearest-rank percentile, integer MAD.
  CI greps for "float(", "import numpy", "import statistics", "sklearn" under
  genios_engine/context/analytic/ and fails on a match.
- NEVER INTERPOLATE A GAP. A missing period is known=False and is excluded from any fit.
  An interpolated value is a fabricated observation that would flow into a card.
- NO HIDDEN CLOCK. eval_time is an explicit parameter everywhere.
- PER-TENANT ACTIVATION via l2_v2_activation. Do NOT add a boolean to platform/config.py.
  That file already carries use_domain_compiler=False, set in no environment, which has
  left 152 capabilities dark. Do not build a second one.
- ZERO LLM in genios_engine/context/analytic/. CI greps for it.

=== THE TWO-TABLE RULE (most likely thing to get wrong) ===
graph_facts keeps the CURRENT value and CONTINUES TO OVERWRITE. That is correct and stays.
metric_history is a SEPARATE, deliberately sampled, append-only table beside it.

Do NOT "fix" derived.py by making it append. That would grow the table by three rows per
node per drain forever and make every "latest" read sift duplicates — the exact failure
the current design deliberately avoids (see derived.py:105-118).
Two tables. Two questions. "What is true now?" and "What was true then?"

=== BUILD ORDER ===
X0 contracts -> X1 history+sampler -> X2 trend+cohort -> X3 comparator+baseline
-> X4 correlator+anomaly -> X5 IMPORTANCE -> X6 patterns+absence -> X8 pilot
X7 (authority, point-in-time, dependency chains) is an INDEPENDENT second track.

X0-X4 need NOTHING from Layer 1 — they read the existing graph. Start them immediately,
in parallel with L1 work. Only X5 blocks on L1 W7.

=== DO NOT REGRESS (all currently correct) ===
1. identity.py:25 — "No edit distance, no embeddings, no '0.87 similar'." An entity
   resolved by cosine distance cannot name the rule that resolved it.
2. Governed entity merges: merge_proposals, merge_history, reversibility.
3. The confidence VECTOR at situations.py:102-227. Globe's own blocker list names scalar
   confidence as a defect; L2 already fixed it. Never collapse it for convenience.
4. The tenant node is deliberately EXCLUDED from ANCHOR_PRIORITY in correlation.py.
   Without that exclusion one node swallows every conversation in the org into one
   situation.
5. correlation.py refuses to prioritise, score risk or recommend. Keep that refusal.
6. graph_facts keeps overwriting. See the two-table rule above.
7. tests/test_layer_topology.py stays green.
8. Tests never reach a production database (commits ae63ef9, d860b8e).

=== NEVER ===
- Never cluster to form a cohort.
- Never interpolate a missing metric period.
- Never return a percentile without cohort_id and population_size.
- Never compute a percentile on a population under 5, or a correlation on n under 20.
- Never let MetricCorrelation.is_causal be True. The field exists to make the absence of
  a causal claim explicit in the data.
- Never treat coverage_ready=None as absence. It is UNKNOWABLE.
- Never draw a negative inference from an UNKNOWABLE fact.
- Never add a global feature flag.
- Never synthesize an importance spread when L1 is not yet supplying real importance —
  log L1_IMPORTANCE_NOT_ACTIVE and keep the base. A fake distribution is worse than a
  flat one because it looks like it works.

=== YOUR FIRST TASK ===
Build Wave X0. The reverse prompt is at the end of
  02-Layer-2-Plan/08-Contracts-BusinessSituationObject.md
Report back with:
  pytest tests/contracts/test_l2_contracts.py -q
  pytest tests/test_layer_topology.py -q
Do not start X1 until both are green with zero skips.
```

---

## Quick reference — where each wave's prompt lives

| Wave | Reverse prompt |
|---|---|
| X0 | `08-Contracts-BusinessSituationObject.md` (end) |
| X1 | `04-Group-L2.4-Analytic-Stratum.md` — L2.4.1, L2.4.2 |
| X2 | `04-Group-L2.4-...` — L2.4.3 (trend), L2.4.4 (cohort) |
| X3 | `04-Group-L2.4-...` — L2.4.5, L2.4.6 |
| X4 | `04-Group-L2.4-...` — L2.4.7, L2.4.8 |
| **X5** | `07-Group-L2.7-Business-Situation-Engine.md` — **L2.7.4** |
| X6 | `06-Group-L2.6-...` (patterns), `05-Group-L2.5-...` (L2.5.5 absence) |
| X7 | `01-Group-L2.1-...` (authority), `02-Group-L2.2-...` (point-in-time), `03-Group-L2.3-...` (dependency) |
