# CTO Handoff — Layer 3 v2

> Section A is for you. Section B is the copy-paste block for the coding agent.

---

# SECTION A — For the CTO

## What kind of layer this is

L1 was a **build** (16 missing components). L2 was a **missing stratum**. **L3 is an
unlock.** The compiler is 1:1 with the Globe spec — all nine components, snapshot
pinning, three-state predicates, an O(1) reverse index. The corpus is 1,389 files and
genuinely good. The brain machinery — versioned storage, a full promotion pipeline,
DB-level protection of the Expert brain — is *better* than Globe asked for.

And none of it reaches a customer, because of four operational facts:

1. **The switch is off everywhere.** `use_domain_compiler=False`, set in no environment.
2. **The weld starves L4.** Only step-bearing playbooks survive to the Decision Maker
   (alphabetically capped at 4). Heuristics (280), rules (46 — including
   `severity: blocking`), mental-models (61) and decision-frameworks (59) — **446
   artifacts, 63% of the knowledge — have no consumer at all.** The adapter's own
   docstring warns that flipping the switch without this work "would LOOK successful
   while producing generic output."
3. **Three of four brains are empty.** Readers, writers and governance all exist; no
   content pipeline produces proposals.
4. **The Admin corpus was authored as an "admin department"** (facilities, travel) while
   Globe's Admin is founder operating intelligence — so 21/57 capabilities are unrouted
   and Globe's two flagship surfaces (#13 Goal & Progress, #14 Opportunity — "the surface
   people remember") have no home.

One correction from the earlier audit: **"152 capabilities, 0 accepted" is stale.** All
153 carry `accepted_content_hash` today, the re-stamp mechanism is live, and
`validate.py` passes with 0 errors. The code comment lies; the corpus does not.

## Who decides brain updates — already answered, by built code

Every runtime-brain write passes L6's promotion pipeline: OBSERVED → CANDIDATE →
VALIDATED (deterministic floors: `min_observations`, `min_distinct_days`,
`min_distinct_entities`) → GOVERNED → PROMOTED → PUBLISHED, versioned, rollback-able.
The Expert brain is human-PR-only, enforced by a **database check constraint**. A model
never decides a promotion; it only produces proposals that enter at OBSERVED. What is
missing is **input** — the two pipelines in doc 02 (N-3 policy-doc discovery, N-4
behavior distillation from L2.4's measurements) are the supply side.

## LLM posture

**Compile-time: zero** — same (situation, snapshot) must produce a byte-identical
package, or snapshot pinning means nothing. **Offline: five sites** (N-1 done, N-2
review assist, N-3 org discovery, N-4 behavior distillation, N-5 gap authoring), every
one of them proposing into human- or floor-gated pipelines. The L1/L2 law holds: the
model constructs meaning; deterministic systems decide when it becomes authoritative.

## The gate that tells you it worked

**J5:** on one pilot tenant within 7 days — **a card carrying a verbatim heuristic/rule
citation** (*"do X because urgency must belong to the buyer"*) and **a candidate
eliminated by a blocking corpus rule**, both structurally impossible today. Plus zero
generic "review the situation" plays — the fake-success detector.

## Sequencing

Y1 (weld) + Y2 (corpus) + Y4/N-3 (org discovery) are **three independent tracks from day
one**. Only ordering law: **Y1 before Y5** — never flip activation before the typed
consumers exist.

---

# SECTION B — Copy-paste to the coding agent

```
You are implementing Layer 3 v2 of GeniOS, the Domain Expertise layer.

=== READ FIRST, IN THIS ORDER ===
  Rohit_Updates (Version 2)/Version 2 Updates/05-Gap-Audit-L3-Spec-vs-Code.md
  .../Version 2 Updates/03-Layer-3-Plan/00-Overview-and-Doctrine.md
  .../Version 2 Updates/03-Layer-3-Plan/06-Build-Order-and-Acceptance.md
Then the group doc for your wave. Each carries a REVERSE PROMPT block.

=== WHAT LAYER 3 IS ===
L3 answers: how would an expert — and this specific company — read this situation?
It retrieves and binds knowledge. It NEVER decides.
Packages: genios_engine/packs/ + the Domain Expertise/ corpus.
In: BusinessSituationObject   Out: ExpertisePackage   Consumer: L4 only.

THIS IS AN UNLOCK, NOT A REBUILD. The compiler is built 1:1 with the spec and is good.
Most of your work is: typed consumers at the L3->L4 seam, corpus routing/authoring,
brain content pipelines, per-tenant activation.

=== THE FIVE LAWS ===
1. L3 NEVER DECIDES. No action selection anywhere in packs/.
2. THE COMPILE IS REPRODUCIBLE. Same situation + same brain_snapshot_id -> byte-identical
   package. Therefore ZERO LLM in the compile path. All five LLM sites (N-2..N-5) are
   offline and propose into gated pipelines; none writes a brain directly.
3. THE EXPERT BRAIN IS HUMAN TERRITORY. Enforced twice already: DB constraint
   (migrations/0045: brain in ('organization','behavior','adaptive')) and the publisher
   (expert_brain_changed always false). Never weaken either.
4. KNOWLEDGE DOESN'T COUNT UNTIL L4 CAN CONSUME IT, TYPED. 446 of 712 artifacts have no
   consumer today. Wave Y1 fixes that. NEVER flip activation before Y1 is green — the
   adapter's own docstring says why: "activation would LOOK successful while producing
   generic output."
5. ACTIVATION IS PER-TENANT, PER-DOMAIN via the l3_activation table. Do not add or read
   global flags. use_domain_compiler is being retired, not extended.

=== PRESERVE-HARD LIST (a PR touching these while doing something else is rejected) ===
- brain_resolver.py snapshot pinning
- capability_resolver.py admission-hash validation (content-minus-admission)
- context_adapter.py three-state predicates (UNKNOWN is never coerced)
- the generated registry (situation-capability-map.yaml) — regenerate via
  "Domain Expertise/_tools/index.py", NEVER hand-edit
- feedback/publisher.py version discipline (no_material_change, rollback-to-predecessor)
- learned_brain_entries one-active-per-subject unique index
- reason/adapters/expertise.py receipts — extend, never remove
- e1a0c47 package-churn suppression

=== TECHNICAL RULES ===
- Predicate grammars everywhere = the L2 cohort whitelisted operator tree. No eval().
- Citations are quoted BYTE-IDENTICAL from authored artifacts; a paraphrase is a
  validation error (hash-checked against the catalog).
- Numbers in any generated statement are TEMPLATED from validated values, never emitted
  by a model (same rule as L1 render and L2 framing).
- Every N-site output enters the L6 pipeline at OBSERVED, or stops at a human. No
  direct brain writes. No new governance — learning_policies + governance.py exist.
- Integer basis points; no float; explicit eval_time; hermetic tests; never touch a
  production database (commits ae63ef9, d860b8e).

=== BUILD ORDER ===
Y0 contracts -> Y1 typed consumers -> Y3 compiler inputs -> Y5 pilot
Y2 corpus (independent, corpus-only) and Y4 brains (N-3 independent; N-4 needs L2 X1-X4)
run in parallel. MANDATORY: Y1 before Y5.

=== YOUR FIRST TASK ===
Wave Y0. Reverse prompt at the end of
  03-Layer-3-Plan/05-Contracts-ExpertisePackage.md
Report:
  pytest tests/contracts/test_l3_contracts.py -q
  pytest tests/test_layer_topology.py -q
Do not start Y1 until both are green with zero skips.
```

---

## Wave → reverse-prompt index

| Wave | Location |
|---|---|
| Y0 | `05-Contracts-ExpertisePackage.md` (end) |
| Y1 | `03-Group-L3.3-Typed-Consumers.md` — CLG-06 prompt; CLG-07/08 specs |
| Y2 | `04-Group-L3.4-Admin-Corpus-V1.md` — U1–U5 |
| Y3 | `01-Group-L3.1-Domain-Compiler.md` — U1–U3 |
| Y4 | `02-Group-L3.2-Four-Brains.md` — N-3 prompt, N-4 spec; `04-…` U6–U7 |
| Y5 | `06-Build-Order-and-Acceptance.md` — J5 + retirement steps |
