# Layer 1 v2 — Overview and Doctrine

> **Read this first.** Every other document in `01-Layer-1-Plan/` assumes the
> vocabulary, the numbering and the four maps defined here.

---

## 1. What Layer 1 is

**Definition**

> Layer 1 turns **raw enterprise data** into **high-quality structured enterprise signals**.

**Name:** Hybrid Intelligence Extraction Layer
**Package:** `genios_engine/capture/`
**Output contract:** `QualifiedEnterpriseSignal` (QES)
**Consumer:** Layer 2 (Context Intelligence) — and nothing else.

**The one-line doctrine**

> **LLM understands the data. Deterministic systems make that understanding usable and trustworthy.**

### What changed from v1

| | v1 (Globe / current code) | v2 (this plan) |
|---|---|---|
| L1's job | route + filter | **understand + qualify** |
| LLM at L1 | 2 sites, both junk-filtering | **heavy — semantic extraction is the core** |
| Semantic extraction | lives at L2 | **moves to L1** |
| `importance_bp` | refused at L1 | **computed at L1, deterministically** |
| Signal taxonomy | none | **14 closed types** |
| Anti-hallucination | none | **evidence span validation, mandatory** |
| Conflicting facts | silently overwritten | **conflict detected and surfaced** |
| Unknown observations | discarded | **open lane — stored and reviewable** |

---

## 2. The four-stage spine

Every event that enters GeniOS passes these four stages in this order. No stage
may be skipped. Each stage has exactly one job.

```
                    RAW EVENT
                        |
   ==================== S1 ====================
   L1.3  DETERMINISTIC EXTRACTION
   "What is objectively present?"
   sender, recipient, timestamps, thread, IDs,
   URLs, numeric tokens, currency tokens, attachments
   NO interpretation.  NO LLM.
                        |
   ==================== S2 ====================
   L1.4  SEMANTIC EXTRACTION            <-- LLM HEAVY
   "What does this actually say / mean?"
   intent, entities, commitments, decision state,
   dependencies, implied actions, topics, stance,
   evidence spans, unclassified observations
   The model DESCRIBES. It never SCORES.
                        |
   ==================== S3 ====================
   L1.5  VALIDATION AND NORMALIZATION
   "Is that understanding true and usable?"
   span validation (anti-hallucination), date/currency
   normalization, canonicalization, CONFLICT DETECTION,
   confidence composition
   NO LLM.
                        |
   ==================== S4 ====================
   L1.6  QUALIFICATION (ESQE)
   "Does it matter, what kind of thing is it,
    and how big is it?"
   signal detection, classification, domain mapping,
   importance scoring, tenant floor, lifecycle
   NO LLM except ambiguous business-relevance.
                        |
             QualifiedEnterpriseSignal --> L2
```

### The stage law

| Stage | May use LLM? | May produce a number? | May drop an event? |
|---|---|---|---|
| S1 Deterministic Extraction | **NO** | yes (counts, offsets) | no |
| S2 Semantic Extraction | **YES — heavy** | **NO** (except its own field confidence) | no |
| S3 Validation | **NO** | yes | no (may flag) |
| S4 Qualification | only for ambiguous relevance | **yes — all scoring lives here** | **yes, with payload retained** |

**Why the model may not score:** a score is consumed by ranking, and ranking must be
reproducible byte-for-byte across machines and across replays. A model's number is
neither. This is the only hard prohibition on the LLM at L1 — everything else it may do.

### The structured bypass — S2 is SKIPPED for already-typed sources

Not every event is unstructured. A HubSpot deal, a Stripe subscription, a calendar event
and a client-database row **arrive already typed**. Running a language model over them is
pure waste and a hallucination risk: the model would be asked to "extract" an amount that
is already sitting in a typed field.

```
RAW
 |
 +-- unstructured (email, chat, transcript, document, CRM note)
 |        S1 -> S2 (LLM) -> S3 -> S4 -> QES
 |
 +-- structured (hubspot deal, stripe subscription, gcal event, db row)
          S1 -> [L1.3.9 Structured Mapper] -> S3 -> S4 -> QES
                        S2 IS SKIPPED
```

The structured lane produces the **same** `ExtractionResult` shape, populated from a
registered field mapping instead of from a model. From that point on S3 and S4 cannot
tell the difference, and must not try to.

**This already exists in code** and must not be lost: `capture/structured/registry.py`
registers `hubspot.deal.v1`, `stripe.subscription.v1`, `gcal.event.v1` and
`postgres.customer_accounts.v1`; `gate/gate.py` S1.5 short-circuits on `is_structured`.
See L1.3.9 in doc 03.

**Why this matters for the customer bar:** billing and product-usage data — the sources
that make churn cohorts, LTV lookalikes and pricing analysis possible at all — are
*structured*. If the plan only described the unstructured path, the highest-value data
GeniOS will ever ingest would have had no route through Layer 1.

| Source class | Route | Confidence source | Authority rank |
|---|---|---|---|
| email / chat / transcript / document | S1 -> S2 -> S3 -> S4 | model field confidence | 1–3 |
| hubspot / stripe / gcal / client DB | S1 -> mapper -> S3 -> S4 | **10000 — a typed field is not a guess** | 4 |
| uploaded company canon | S1 -> S2 -> S3 -> S4 | model, then authority-boosted | 5 |
| signed / executed document | S1 -> S2 -> S3 -> S4 | model, then authority-boosted | 6 |

---

## 3. MAP A — Where the LLM is used

There are exactly **five** LLM call sites in Layer 1 v2. Any sixth is an
architectural bug and must be rejected in review.

| ID | Site | Group | Model tier | Mode | Purpose |
|---|---|---|---|---|---|
| **LLM-1** | Junk gate assist | L1.2 pre-filter | cheap (Haiku) | batched, ~12/call | drop spam/newsletters before they cost anything |
| **LLM-2** | **Semantic Extractor** | L1.4.3 | **tiered** (see below) | 1 call per document-version | the core: text -> typed meaning |
| **LLM-3** | Speech-to-Text | L1.3.4 | transcription model | always, per audio file | audio -> text (then LLM-2 runs on the text) |
| **LLM-4** | OCR fallback | L1.3.4 | vision model | fallback only | scanned doc -> text when Tesseract fails |
| **LLM-5** | Business relevance (ambiguous only) | L1.6.5 | cheap | <5% of events | rules handle the rest |

### LLM-2 model tiering (the cost lever)

The extractor does **not** use one model. `L1.4.10 Model Router` picks:

| Tier | Model | When | Est. share |
|---|---|---|---|
| **T1 cheap** | Haiku | short messages, low structural signal, chat lines | ~70% |
| **T2 standard** | Sonnet | normal email with entities/amounts/dates present | ~25% |
| **T3 deep** | Opus | contracts, legal docs, transcripts, anything above the value threshold | ~5% |

Routing inputs are **deterministic only**: content length, attachment presence,
currency-token count from L1.3.5, source type, thread depth. Never the model's own opinion.

### Where the LLM is FORBIDDEN at L1

`importance_bp` · `priority_bp` · any `_bp` field · visibility / audience ·
routing decisions · deduplication · date arithmetic · currency arithmetic ·
the qualification pass/fail decision · signal lifecycle transitions

---

## 4. MAP B — Where embeddings are used

**Decision: Layer 1 v2 ships NO embeddings.**

This is deliberate and reverses the Globe spec (which had Embedding Generation as an
always-on L1 site). Rationale, from the existing codebase
(`genios_engine/context/identity.py`): *"No edit distance, no embeddings, no
'0.87 similar'"* — because a similarity score is not a business conclusion, and an
entity resolved by cosine distance cannot name the rule that resolved it.

| Candidate use | Verdict | Instead |
|---|---|---|
| Entity resolution ("AWS" == "Amazon Web Services") | **NO** | deterministic alias + domain matching (L1.5.4) |
| Document retrieval for L2 | **DEFER** | not needed until a retrieval surface exists |
| Duplicate detection | **NO** | content hash (L1.3.7) |
| Semantic search for the founder | **DEFER to a later layer** | not an L1 concern |

**When to revisit:** the moment a genuine retrieval surface exists (an agent asking a
free-text question over the corpus). At that point embeddings belong in a dedicated
retrieval component, with pgvector, and explicitly labelled as *retrieval
infrastructure, never reasoning*. Not before. Building it earlier adds a store, a
migration and a cost centre that nothing reads.

---

## 5. MAP C — Where data is stored

| Store | Technology | Owns | Retention |
|---|---|---|---|
| **Raw evidence** | object storage / `payload_store` | the original bytes: email body, PDF, audio | tenant retention policy; erasable |
| **Prepared content** | `prepared_content` table | cleaned text + PII mask spans + offsets | TTL, purgeable |
| **Extraction cache** | `l1_extraction_results` (migrated from `l2_extraction_results`) | the S2 model output, keyed by content hash | permanent — this is what makes replay exact |
| **Landing ledger** | `source_events` | one row per ingested object + dedup key | permanent |
| **Signal store** | `qualified_signals` **(NEW)** | one row per QES + evidence refs | permanent |
| **Conflict store** | `signal_conflicts` **(NEW)** | detected disagreements, both sides retained | permanent |
| **Open lane** | `unclassified_observations` **(NEW)** | what the model noticed but could not name | rolling 180d, reviewable |
| **Coverage** | `source_coverage` (exists, unwired) | per-org capability coverage, for negative inference | recomputed each sweep |
| **Cursors** | `connector_cursors` | per-connection sync position | permanent |
| **Cost** | `llm_costs` | per-org token attribution | permanent |

### The storage law

1. **Nothing is a source of truth in a cache.** If Redis is flushed the system must
   still be correct, only slower.
2. **Every derived claim can name the row it came from.** A claim without an
   `evidence_ref` is not publishable.
3. **The extraction cache is permanent and hash-keyed.** The model runs once per
   `(content, prompt_version, schema_version, model, vocab_fingerprint)`. Every replay
   reads the stored extraction — never re-runs the model. This is what makes a
   non-deterministic pipeline auditable.
4. **Drops keep their payload.** A judged drop retains 90 days of content so
   *"why did GeniOS not see this?"* is answerable.

---

## 6. MAP D — Where algorithms, rules and formulas live

Anything that computes a number, applies a rule, or makes a deterministic decision is
listed here. Each must be **pure** (same input -> same output, no I/O), **unit-tested
in isolation**, and **have no LLM in its call path**.

| ID | Algorithm / rule / formula | Unit | Kind | Doc |
|---|---|---|---|---|
| **ALG-01** | Sentence-boundary chunking | L1.3.4 | algorithm | 03 |
| **ALG-02** | Content-hash dedup key | L1.3.7 | algorithm | 03 |
| **ALG-03** | Thread direction + turn index | L1.3.6 | algorithm | 03 |
| **ALG-04** | Structural token scan (URL/number/currency/date-string) | L1.3.5 | regex ruleset | 03 |
| **ALG-05** | Model tier routing | L1.4.10 | decision table | 04 |
| **ALG-06** | Extraction cache key | L1.4.9 | hash formula | 04 |
| **ALG-07** | Batch packing | L1.4.8 | bin-packing | 04 |
| **ALG-08** | **Evidence span validation** | L1.5.1 | algorithm | 05 |
| **ALG-09** | **Relative date resolution** | L1.5.2 | algorithm + certainty rules | 05 |
| **ALG-10** | **Currency normalization** | L1.5.3 | algorithm + locale rules | 05 |
| **ALG-11** | Entity canonicalization | L1.5.4 | rule cascade | 05 |
| **ALG-12** | **Conflict detection** | L1.5.5 | algorithm | 05 |
| **ALG-13** | **Confidence composition (Rule 11)** | L1.5.7 | formula | 05 |
| **ALG-14** | Authority weighting | L1.5.8 | lookup table | 05 |
| **ALG-15** | Signal detection predicates | L1.6.1 | rule set | 06 |
| **ALG-16** | Signal classification | L1.6.3 | decision table | 06 |
| **ALG-17** | **Importance scoring** | L1.6.7 | **formula** | 06 |
| **ALG-18** | Qualification floor | L1.6.8 | threshold rule | 06 |
| **ALG-19** | Signal lifecycle transitions | L1.6.9 | state machine | 06 |
| **ALG-20** | Coverage computation | L1.7.5 | algorithm | 07 |
| **ALG-21** | **Structured field mapping** | L1.3.9 | mapping registry | 03 |
| **ALG-22** | **Subject key derivation** | L1.5.0 | algorithm | 05 |
| **ALG-23** | **Claim group assembly** (thread + attachments) | L1.5.0 | algorithm | 05 |

### How an algorithm gets built (the standard procedure)

Every one of ALG-01..ALG-20 follows the same five steps. The coding agent must not
deviate.

1. **Write the signature and the docstring first.** The docstring states the formula
   or rule in prose, names its inputs, and names what it deliberately does NOT do.
2. **Write the test table before the implementation.** A table of
   `(input, expected_output, why)` rows — including every edge case named in the
   Failure Modes section of that unit's spec.
3. **Implement as a pure function.** No database, no network, no clock, no LLM. If the
   algorithm needs "now", it takes `eval_time` as an explicit parameter.
4. **All numbers are integer basis points** (`0..10000`) with a `_bp` suffix. No floats
   cross a function boundary. Money is integer minor units plus an ISO currency code.
5. **Wire it last.** The pure function is complete and green before any caller exists.

---

## 7. The numbering scheme

```
L1              layer
L1.4            group
L1.4.3          component
L1.4.3-U2       unit  (the smallest buildable, testable thing)
```

Every ticket, commit and PR references the **unit** id. A commit that says
"fix extraction" is a commit nobody can route.

---

## 8. The unit spec template

Every unit in documents 01-07 is specified with exactly these fields. If a field
says `n/a` that is an answer; a blank is a defect in the plan.

| Field | Meaning |
|---|---|
| **WHAT** | one sentence: what this unit does |
| **WHY** | what breaks, concretely, if it does not exist |
| **WHERE** | the file path it lives in |
| **WHEN** | build wave + what must be green before it starts |
| **HOW** | the algorithm, rule set or formula — concretely enough to implement |
| **LLM** | yes/no. If yes: which site id, which tier, and why a rule cannot do it |
| **EMBEDDINGS** | yes/no + why |
| **STORAGE** | table and columns, or `pure — no I/O` |
| **INPUT** | typed |
| **OUTPUT** | typed |
| **FAILURE MODES** | what goes wrong and what the unit does about it |
| **ACCEPTANCE** | the exact command that proves it works, and the expected result |
| **REVERSE PROMPT** | a copy-paste block for the coding agent |

---

## 9. Two standing warnings

### 9.1 Do not repeat the `use_domain_compiler` mistake

`genios_engine/platform/config.py:110` carries `use_domain_compiler: bool = False`. It
is set in **no environment**, and has been off since it was written — so 152 authored
capabilities have never influenced a single customer-visible recommendation.

Therefore, in Layer 1 v2:

- **No global boolean cutover flags.** Activation is per-tenant, in a table, with an
  owner and a date.
- **"Built but not enabled" is not done.** A unit is done when it is enabled for at
  least one real tenant and its acceptance command passes against that tenant.
- **Every wave has an acceptance gate** that must pass before the next wave begins.

### 9.2 The typed sink is built before the extractor

The codebase already ran the alternative experiment. From
`genios_engine/context/extract/vocab.py`:

> *"the model, given three examples and an ellipsis for `field`, invented **268
> distinct field names in one org, 192 of them used exactly once**."*

And the other half of the same failure:

> *"Rules read `deal.status` while the extractor, never told the name, wrote `status` —
> so the rule was **dead on arrival**."*

**The lesson is not "use less LLM." The lesson is that extraction is worth exactly as
much as the consumer's ability to read it.** Therefore build wave W3 (Extraction
Schema + Open Lane + Evidence Binder) completes **before** wave W4 (the extractor)
begins. The sink exists first; then it is filled.

---

## 10. Document index

| Doc | Contents |
|---|---|
| `00-Overview-and-Doctrine.md` | this file |
| `01-Group-L1.1-Enterprise-Sources.md` | 16 source categories, connector priority |
| `02-Group-L1.2-Knowledge-Connectors.md` | 6 components — ingestion control plane |
| `03-Group-L1.3-Deterministic-Extraction.md` | 8 components — stage S1 |
| `04-Group-L1.4-Semantic-Extraction-Engine.md` | 10 components — stage S2, the new core |
| `05-Group-L1.5-Validation-and-Normalization.md` | 8 components — stage S3, trust |
| `06-Group-L1.6-ESQE-Qualification.md` | 10 components — stage S4, the gateway |
| `07-Group-L1.7-Knowledge-Storage.md` | 5 components — stores and migrations |
| `08-Contracts-QualifiedEnterpriseSignal.md` | every typed object crossing the L1 seam |
| `09-Build-Order-and-Acceptance.md` | 10 waves, dependencies, acceptance gates |
| `10-CTO-Handoff-Note.md` | copy-paste brief for the coding agent |
