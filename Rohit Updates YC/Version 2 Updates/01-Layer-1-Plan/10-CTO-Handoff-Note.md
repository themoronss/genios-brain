# CTO Handoff — Layer 1 v2

> **How to use this document.** Section A is for you. Section B is a copy-paste block
> for the coding agent — paste it whole, then paste the wave prompt you want built.
> Every wave prompt lives in the group document named in the build order.

---

# SECTION A — For the CTO

## What we are changing and why

Layer 1 today **routes** events. It does not **qualify** them. Its own output contract
says so — `contracts/gated_event.py` records that the object *"was missing its
qualifying half."*

Concretely, of the 48 components Layer 1 is supposed to have, 19 are built, 10 are
partial, 3 moved to L2, and **16 are missing**. The gateway component — ESQE — is 2 of 10.

Three consequences you are feeling right now:

**1. Ranking does not work anywhere in the product.**
L1 stamps no `importance_bp`, so L4 has nothing intrinsic to score. It falls back to
`priority_override`, which replaces the formula outright. The code says it plainly at
`reason/decision_maker.py:243`: *"the formula has never once decided anything."* Ranking
collapses to ~30 constants authored in situation YAML, so **two different tenants
receive identical rankings.** This is a Layer 1 hole, and Wave W7 closes it.

**2. Details are lost, and not at the model.**
The extraction call is already rich. The loss happens after it: content truncated at
8000 chars, a 34-value observation vocabulary, and — the real ceiling — that vocabulary
is derived from *what the rules already consult*. The extractor is only permitted to
look for patterns somebody already wrote a rule for. That is circular, and it is why
nothing new is ever discovered. Wave W3 breaks the circle and adds an open lane.

**3. There is no defense against a confident wrong number.**
No evidence-span validation, so a hallucinated quote is indistinguishable from a real
one. No conflict detection, so when a signed PDF says \$74K and an email says \$84K,
whichever arrived last wins silently. Waves W1 and W5 fix both.

## The philosophy change

> **v1:** L1 = mostly deterministic, selective LLM.
> **v2:** L1 = **Hybrid Intelligence Extraction Layer.** LLMs are used heavily for
> semantic understanding of unstructured data; deterministic systems handle objective
> extraction, normalization, validation, deduplication, permissions and integrity.

LLM budget by layer: **L1 heavy · L2 light · L3 zero at runtime · L4 ambiguity only ·
L5 prose only.**

The one hard prohibition: **the model may describe, it may never score.** A score is
consumed by ranking, and ranking must be byte-identical across machines and replays.

## Cost — read this before you worry about it

Going heavy on LLM at L1 does **not** multiply your bill, because the extraction cache
already exists (`l2_extraction_results`, keyed on content + prompt version + schema
version + model + vocab fingerprint). It is being relocated, not invented.

**The model runs once per document version, ever.** That is what makes both an 18-month
backfill window and an Opus tier on contracts affordable. Controls retained: tier
routing sends ~70% of traffic to Haiku, the rules-first junk gate still runs before any
extraction, batching stays, and the daily USD circuit breaker stays.

## What you are agreeing to

| Decision | Rationale |
|---|---|
| `importance_bp` computed at L1, deterministically | it is intrinsic ("how big is this thing"); `priority_bp` stays at L4 ("what to do first"). Both are currently missing, which is why neither computes |
| Semantic extraction moves L2 -> L1 | L1 is where unstructured data arrives; L2 should do graph resolution only |
| No embeddings in L1 v2 | a cosine score is not a business conclusion and cannot name the rule that produced it. Revisit when a real retrieval surface exists |
| Extraction vocabulary decoupled from rule vocabulary | otherwise discovery is impossible by construction |
| Open lane for unnamed observations | the only mechanism by which the system can find a pattern nobody anticipated |
| Backfill window 60d -> 540d, per connection | 60 days makes every precedent-based claim impossible; the cache makes 540 affordable |
| Per-tenant activation table, never a global flag | `use_domain_compiler=False` is set in no environment and has left 152 capabilities dark for weeks |

## Sequencing

Ten waves, in `09-Build-Order-and-Acceptance.md`. Two tracks can run in parallel for
W0–W3. **W9 (connector fixes) is independent — start it on day one.** The single
ordering that must not be violated: **W3 before W4** — the typed sink exists before
anything fills it.

## The gate that tells you it worked

**G7.** After importance scoring ships, run:
```
python scripts/importance_distribution.py --org <pilot> --since 30d
```
If `importance_bp` has more than 50 distinct values and a p90-p50 spread above 1500, the
formula is deciding. If it collapses to a handful, it is not, and the wave is not done.

---

# SECTION B — Copy-paste to the coding agent

```
You are implementing Layer 1 v2 of GeniOS, the Hybrid Intelligence Extraction Layer.

=== READ THESE FIRST, IN THIS ORDER ===
  Rohit_Updates (Version 2)/Version 2 Updates/01-Layer-1-Plan/00-Overview-and-Doctrine.md
  Rohit_Updates (Version 2)/Version 2 Updates/01-Layer-1-Plan/09-Build-Order-and-Acceptance.md
  Rohit_Updates (Version 2)/Version 2 Updates/01-Layer-1-Plan/08-Contracts-QualifiedEnterpriseSignal.md
Then the group document for the wave you are building. Each contains a REVERSE PROMPT
block with the exact task.

=== WHAT LAYER 1 IS ===
L1 turns raw enterprise data into high-quality structured enterprise signals.
Package: genios_engine/capture/   Output: QualifiedEnterpriseSignal   Consumer: L2 only.

Four stages, in order, none skippable:
  S1 L1.3 Deterministic Extraction  - objective facts. NO LLM, NO interpretation.
  S2 L1.4 Semantic Extraction       - meaning. LLM HEAVY. Describes, never scores.
  S3 L1.5 Validation/Normalization  - truth + usability. NO LLM. Pure functions.
  S4 L1.6 Qualification (ESQE)      - type, relevance, importance. All scoring here.

=== THE FIVE LAWS (violating any one fails review) ===

1. THE MODEL MAY DESCRIBE, NEVER SCORE.
   No LLM output may become importance_bp, priority_bp, any _bp field, a visibility
   decision, a route, or a lifecycle transition. The ONLY number a model may emit is its
   own per-field confidence. Enforcement is structural: importance is not in the
   extraction schema at all, so even a successful prompt injection cannot raise it.

2. INTEGER BASIS POINTS ONLY.
   Every score is int in 0..10000, suffixed _bp. NO float crosses any function boundary
   anywhere in Layer 1. Money is integer minor units + ISO 4217 code. Use `x * 9 // 10`,
   never `x * 0.9`. CI greps for "float(" in capture/validate/, capture/esqe/,
   capture/structural/ and fails on a match.

3. EVERY CLAIM CARRIES A VERIFIED RECEIPT.
   Every assertion about the world carries an EvidenceSpan with a verbatim quote and
   character offsets. L1.5.1 verifies the quote literally appears in the source. A Money
   or a ResolvedDate whose span does not verify is DROPPED, not downgraded. Matching is
   exact or whitespace-normalized only — never fuzzy, never semantic, never embeddings.

4. NO HIDDEN CLOCK.
   Any unit needing "now" takes eval_time as an explicit parameter. No datetime.now(),
   no date.today(), anywhere in capture/validate/ or capture/esqe/. CI greps for it.
   Replaying a March event must resolve "next week" against March.

5. PER-TENANT ACTIVATION, NEVER A GLOBAL FLAG.
   Activation goes in table l1_v2_activation(org_id, enabled_at, enabled_by).
   Do NOT add a boolean to platform/config.py. That file already carries
   use_domain_compiler=False, set in no environment, which has left 152 authored
   capabilities dark. A unit is DONE when its acceptance command passes against a real
   tenant with activation enabled. "Built but not enabled" is not done.

=== BUILD ORDER — REVERSE ENGINEERING ===
Units first, in isolation, fully tested. Then components from green units. Then groups.
Never build a parent before its children are green.

W0 contracts -> W1 pure validators -> W2 S1 -> W3 typed sink -> W4 extractor
-> W5 conflict -> W6 ESQE detect -> W7 importance -> W8 publish -> W10 pilot
W9 connectors is INDEPENDENT — it may start immediately.

MANDATORY ORDERING: W3 completes before W4 starts. Reason, from
genios_engine/context/extract/vocab.py: a previous free-form extractor "invented 268
distinct field names in one org, 192 of them used exactly once." The typed sink exists
before anything fills it.

=== HOW TO BUILD ANY ALGORITHM (ALG-01..ALG-20) ===
1. Write the signature and docstring first. State the formula in prose. Name what it
   deliberately does NOT do.
2. Write the test table BEFORE the implementation: (input, expected, why) rows covering
   every edge case in that unit's FAILURE MODES section.
3. Implement as a PURE function. No DB, no network, no clock, no LLM.
4. Integer basis points. No floats.
5. Wire it last. The pure function is green before any caller exists.

=== TESTING RULES ===
- Every wave has an acceptance command in doc 09. A SKIP IS NOT A PASS.
- Tests must be hermetic: no network, no LLM, no production database. See commits
  ae63ef9 and d860b8e — the suite previously opened transactions against a paying tenant.
- Golden corpus for extraction: 30 hand-labelled real messages across all 5 profiles.
  Hard fail on any fabricated amount (a Money not literally present in the source).

=== DO NOT REGRESS THESE (they are currently correct) ===
1.  Visibility stamped at source; gate PARKS visibility_unknown rather than guessing
    (capture/visibility_rules.py, gate/gate.py S0.6)
2.  MUT-01 versionability check (gate/rules.py content_integrity_rule)
3.  Three distinct dedup jobs stay distinct (l1.content / l1.event / l5_2.mgmt)
4.  90-day payload retention on judged drops (capture/pipeline.py:230-246)
5.  Extraction cache key includes every instruction-changing component
    (context/pipeline.py:463-475 — a past bug let 260 cached extractions survive a
    prompt fix and hide it entirely)
6.  Prompt-injection defense (commit 54e8ca1)
7.  Daily LLM spend circuit breaker (commit 7e17a6d)
8.  Rules-first, then LLM, in the junk gate (commit c373a9d)
9.  Layer import direction (tests/test_layer_topology.py)
10. The envelope on the extraction prompt — direction + parties. Without it an outbound
    offer reads as an inbound request. This bug already happened once.

=== NEVER DO THESE ===
- Never let the model emit importance_bp or any _bp except its own field confidence.
- Never add a global boolean cutover flag.
- Never use embeddings, edit distance, or fuzzy similarity in L1 v2.
- Never derive the extraction vocabulary from rule vocabularies (that is the circle that
  makes discovery impossible).
- Never delete the losing claim in a Conflict — both sides are always retained.
- Never default an ambiguous currency to USD, or guess a locale date order. Return
  UNKNOWN or None.
- Never delete the L2 extraction path before gate G10 passes.
- Never run tests against a production database.

=== YOUR FIRST TASK ===
Build Wave W0. The reverse prompt is at the end of
  01-Layer-1-Plan/08-Contracts-QualifiedEnterpriseSignal.md
Report back with the output of:
  pytest tests/contracts/test_l1_contracts.py -q
  pytest tests/test_layer_topology.py -q
Do not start W1 until both are green with zero skips.
```

---

## Quick reference — where each wave's prompt lives

| Wave | Reverse prompt location |
|---|---|
| W0 | `08-Contracts-QualifiedEnterpriseSignal.md` (end) |
| W1 | `05-Group-L1.5-...md` — units L1.5.1, L1.5.2, L1.5.3 |
| W2 | `03-Group-L1.3-...md` — unit L1.3.5 |
| W3 | `04-Group-L1.4-...md` — "REVERSE PROMPT — Wave W3" |
| W4 | `04-Group-L1.4-...md` — "REVERSE PROMPT — Wave W4" |
| W5 | `05-Group-L1.5-...md` — unit L1.5.5 |
| W6 | `06-Group-L1.6-...md` — units L1.6.1, L1.6.3 |
| W7 | `06-Group-L1.6-...md` — unit L1.6.7 |
| W8 | `06-Group-L1.6-...md` — units L1.6.9, L1.6.10 |
| W9 | `02-Group-L1.2-...md` (L1.2.4) and `01-Group-L1.1-...md` (coverage) |
