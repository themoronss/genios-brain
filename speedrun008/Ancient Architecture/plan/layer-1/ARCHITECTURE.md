# Layer 1 — Architecture

> **Read this first if you are new to Layer 1, or if you are reviewing it.**
> Branch `speedrun008` · 2026-09-23. Every claim is traceable to a file and line.
>
> Two columns run through this document: **TODAY** — what the code does right now, and
> **TARGET** — what it does after the fifteen steps in this folder. Nothing is written as done
> that is not done.

---

## 1. The contract, in one sentence

> **Layer 1 converts raw enterprise activity into qualified, evidence-backed, coverage-aware,
> lifecycle-managed signals — without making a single cross-signal business decision.**

It answers **"what happened, and can we prove it?"**
It does not answer "what does this mean for the company" (L2), "how would an expert read it" (L3),
or "what should be done" (L4).

### The one rule that defines the boundary

**L1 may never read company state to make a judgement.** The moment a capture unit reaches for the
graph to ask *"is this account strategic?"*, the two layers have merged and neither can be tested
alone. L1 judges a signal on **what is intrinsically in it**; L2 judges it **in context**.

---

## 2. Where the code lives

```
genios_engine/
  contracts/          the vocabulary — 6 files, 2,927 LOC, imports only stdlib + pydantic
  capture/            Layer 1 — 138 files, 42,311 LOC, 18 subpackages
  context/            Layer 2 — reads what L1 publishes
  platform/           wiring, activation, config — the composition root
  api/                the transport surface
```

The package name carries **no digit**. The layer index is data, in `genios_engine/LAYERS.py`
(`"capture": 1`), and `tests/test_layer_topology.py` enforces that a lower layer never imports a
higher one. That test is a build failure, not a review nit.

---

## 3. The stage model

```
                         ENTERPRISE SOURCES
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  ACQUIRE               │   connectors · cadence · backfill
                    │  get the bytes         │   never interprets meaning
                    └───────────┬────────────┘
                                ▼
                    ┌────────────────────────┐
                    │  S1  OBSERVE           │   land · dedup · preprocess · documents
                    │  what objectively is   │   structural tokens · threads · structured lane
                    │  NO MODEL              │
                    └───────────┬────────────┘
                                ▼
                    ┌────────────────────────┐
                    │  S2  INTERPRET         │   LLM-2, the one extraction call
                    │  what it represents    │   closed vocabulary · open lane · cache
                    │  MODEL PROPOSES        │
                    └───────────┬────────────┘
                                ▼
                    ┌────────────────────────┐
                    │  S3  VALIDATE          │   spans · dates · money · authority
                    │  what can be checked   │   confidence · conflict · canonicalisation
                    │  PURE — no I/O at all  │
                    └───────────┬────────────┘
                                ▼
                    ┌────────────────────────┐
                    │  S4  QUALIFY (ESQE)    │   detect · classify · relevance · domain
                    │  does it matter        │   source · importance · floor
                    │  NO MODEL SCORES       │
                    └───────────┬────────────┘
                                ▼
                         ┌──────────────┐
                         │ PUBLICATION  │   V-1 … V-7
                         │    GATE      │
                         └──────┬───────┘
              ┌─────────┬───────┴───────┬──────────┐
              ▼         ▼               ▼          ▼
            EMIT      PARK          REVIEW       REJECT
              │    mechanical      low conf.    not a signal
              │    blocker         high value       │
              ▼         └── drain ──┘               ▼
        ┌──────────────┐                     qualification_drops
        │  LIFECYCLE   │  active/superseded/          (kept, with
        │   ALG-19     │  expired/resolved             the reason)
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │   PUBLISH    │  → qualified_signals → LAYER 2
        └──────────────┘
```

**REVIEW is TARGET** (step 10). The other three outcomes exist today, and
`contracts/publication.py:82` states the enum is closed — *"a fourth outcome invented at a call
site would be an emit nobody reviewed"* — which is why REVIEW is a deliberate contract change.

---

## 4. The engine law — where models are allowed, and where they are not

Five engines. Every unit in Layer 1 declares one.

| | Engine | Used when | Never for |
|---|---|---|---|
| **D** | deterministic | the answer is in the bytes — headers, offsets, ids, arithmetic | anything needing meaning |
| **R** | rules / ontology | a closed business vocabulary decides it, written down in advance | open-ended language |
| **M** | small model | bounded classification over a closed set, high volume | anything producing a quote or a span |
| **L** | LLM | ambiguity, implicit meaning, cross-sentence composition | any number that orders anything |
| **J** | JEV *(not wired)* | choosing how much intelligence to spend on this item | replacing any engine above |

### The pattern every intelligent operation follows

```
   RAW EVIDENCE
        │
        ▼
   INFERENCE          M or L — proposes a structured HYPOTHESIS
        │
        ▼
   VALIDATION         D or R — schema · closed vocabulary · ontology · span resolution
        │
        ▼
   COMMITMENT         D only — the score, the state transition, the publication
```

**Model proposes. Deterministic system validates and commits.** Three laws follow:

1. **Nothing a model proposes is a fact until validation resolves it against source characters.**
   `validate/spans.py` ALG-08 *corrects* the model's offsets rather than trusting them, and forces
   `verified=False` on failure. Schema rule S-9 rejects an extraction that stamps its own
   `verified=True` — **the extractor cannot write its own receipt.**
2. **No model output becomes a number that orders anything.** A model's confidence changes with
   its version; `importance_bp` must replay byte-identical. Confidence may **route** (decide
   whether to look harder) and may be **stored** as provenance. It may not **rank**.
3. **`unknown` is a valid output and is never manufactured to satisfy a schema.**
   `contracts/intent.py` already enforces this: every enum carries `unknown`, and a missing intent
   means *"do not filter on this"* rather than a guess.

### The five model call sites

| | Site | Where | Status |
|---|---|---|---|
| LLM-1 | junk gate | `gate/relevance.py` | live |
| LLM-2 | semantic extractor | `semantic/extractor.py` | live — **the one call the group exists to make** |
| LLM-3 | speech-to-text | `documents/transcript.py` | seam built, **no provider** |
| LLM-4 | OCR fallback | `documents/` | live when OCR is on |
| LLM-5 | ambiguous business relevance | `esqe/relevance.py` | live, **rules-first**, bounded by budget |

**A sixth is an architectural bug.** `tests/test_every_llm_call_site_is_metered.py` holds a closed
register and fails in **both** directions — a new site that is not registered, and a registered
site that disappeared.

---

## 5. The doors — every way an event enters

Exactly four call `capture_event`:

| Door | Code | Carries |
|---|---|---|
| Poll / sweep | `acquire/sync_runner.py:270` | scheduled connector syncs |
| Push / webhook | `connectors/push_ingest.py:123` | Composio trigger deliveries |
| Manual intake | `intake.py:54` | human notes, agent outcomes, uploads |
| API | `api/routes.py:1545` | direct ingest |

And after any door has captured its events, **one** finalizer runs — `esqe/finalize.py`, in a
fixed order:

```
conflicts  →  qualify  →  lifecycle  →  publish
```

It exists because that sequence grew a line at a time inside `api/routes.py` and **the upload door
never called it**: a founder's hand-uploaded signed contract was captured, extracted, scored, and
then its signals fell on the floor. Nothing errored; `qualified_signals` simply had no row.

> **The rule this encodes, and it applies to every future unit:**
> *A unit is done when a **real request path** reaches it and a test drives **that path**.*
> A test that constructs the collaborator itself proves the unit, not the wiring.

An AST audit of all 119 modules on 2026-09-23 found **0 genuinely dead modules**. The code is
wired. What is not wired is the **data** — see §8.

---

## 6. `capture_event` — the runtime spine

`capture/pipeline.py`, 1,704 LOC. One raw object in, one `CaptureResult` out.
Terminal outcomes: **duplicate** (landing), **dropped** / **parked** (gate), **emitted**.

| # | Step | Module | Note |
|---|---|---|---|
| 1 | land | `landing/` | dedup + the audit ledger. Not landed ⇒ duplicate, stop |
| 2 | route detect | `structured/registry` | a mapping *or* an `enterprise_system` family ⇒ structured route |
| 3 | preprocess | `preprocess/` | HTML stripped here; **subject is part of the prose** and masked with the body; PII masked, offsets kept |
| 4 | gate | `gate/gate.py` | S0 scope → S1 hard rules + whitelist → S1.5 structured short-circuit |
| 5 | persist the decision | `repo.add(...)` | decision-first ledger — route, lane, hints written **with** the decision |
| 6 | triage | `triage/` | the L2 **drain order**, P1/P2/P3 |
| 7 | stash payload | `payload_store`, `prepared_store` | tiered TTL — see §7 |
| 8 | structured lane | `structured/lane.py` | typed fields → `ExtractionResult`, **no model** |
| 9 | semantic lane | `semantic/` | LLM-2. Refuses the structured route on the same flag the gate used |
| 10 | conflict | `validate/conflict.py` | after extraction, before emit. **Never fails a capture** |
| 11 | ESQE | `esqe/` | after conflict. **Always runs** — pure and unbilled |
| 12 | coverage verdict | `coverage/` | against the domain this event was hinted into |
| 13 | emit | `_build_gated_event` | `GatedEvent` → Layer 2 |

### The bundle discipline

`capture_event` takes 17 parameters, so each optional subsystem arrives as **one** frozen
dataclass: `SemanticLane`, `StructuredLane`, `ConflictLane`, `EsqeStage`. `None` means *not wired*
and the pipeline behaves exactly as it did before that subsystem existed — which is what makes a
strangler-fig activation safe to land ahead of any tenant.

**The one exception:** `EsqeStage` — `None` does **not** turn S4 off, because it is pure and
unbilled. Gating it behind a flag would mean an activated tenant could still be *routing* events
instead of *qualifying* them.

---

## 7. Storage — and the retention argument

| Store | Table | Holds |
|---|---|---|
| Raw evidence | encrypted payloads | the raw object, tiered TTL |
| Prepared content | `prepared_content` | PII-masked text **+ the offset map** |
| Extraction | `l1_extraction_results` | content-addressed, the expensive artifact, stored once |
| Signals | `qualified_signals` | **the L1 → L2 boundary** |
| Drops | `qualification_drops` | every refusal, with its components and a payload ref |
| Conflicts | `signal_conflicts` | both claims retained |
| Lifecycle | `signal_lifecycle` | ALG-19's rows |
| Coverage | `source_coverage` | which channels are connected |

**Retention is tiered by decision, and each tier is an argument:**

* **emitted** — short TTL. It reached Layer 2; the seam has what it needs.
* **parked** — long TTL. A park is a human-review queue; parked once stored no payload, so
  `/recover` was a no-op black hole.
* **judged drop** — 90 days. A model's verdict is the one kind of deletion we might be wrong
  about, and 657 dropped events with zero payloads once made *"did we lose anything real?"*
  permanently unanswerable.
* **deterministic drop** — nothing. **L1 stays a filter, not a warehouse.**

---

## 8. How things are wired — and the one place they are not

### Code wiring: clean

119 modules, 0 dead. Three have no static importer and all three are accounted for:
`coverage/audit` (a gate ratchet, test-driven by design), `documents/fake` (a dev engine),
`screen/fingerprint` (wired via `importlib` at `pipeline.py:657`).

### Data wiring: this is the defect

Eight values are computed correctly every sweep and then **dropped on the floor**:

| Computed by | Value | Ends up |
|---|---|---|
| `structural/threads.py` ALG-03 | `ball_in_court`, `turn_index`, `thread_depth` | on the **trace**, not the signal |
| `pipeline._envelope_direction` | `direction` | `prepared_content` only |
| `esqe/normalize.py` ALG-22 | `subject_key` | the **drop ledger**, not the published signal |
| `esqe/*` | `domain_hints`, `confidence_vector`, `occurred_at`, `expires_at`, `secondary_types`, `internal_kind`, `extraction_ref` | written to `qualified_signals`, **never selected** |

```
L1 produces      26 ExtractionResult fields + 29 QES fields
L1 persists      28 columns
L2 reads          9 columns        ← context/situation_bso.py:516
```

And `context/runner.py:249` resolves `extraction_ref` through `array_agg(...)[1]` — **only the
loudest signal per event** gets an extraction behind it.

> **L1 does the work and drops it between itself and Layer 2.** That sentence is the architecture's
> single biggest defect, and step 3 closes it.

### The second defect: the contract has two tiers

`contracts/extraction.py` has **8 typed claim lists**, each carrying `evidence: EvidenceSpan` and
`confidence_bp`, and **7 untyped bags** typed as `list[str]` or `list[dict[str, Any]]`:

```
topics · implied_actions · questions · roles · relationships
scheduling_proposals · availability
```

Doctrine 3 is *"no claim without a receipt."* **Tier 2 cannot obey it — the type has no field to
put one in.** And `esqe/detector.py` fires three real signal types off them (`:399` `roles`,
`:406` `availability`, `:432` `questions`).

The measured consequence: `relationship_change` has **no typed amount, date or authority for
ALG-17 to weigh**, so it scores **880–1240 bp** — the lowest band of any type — and **48 of 49 die
at the 2,500 floor.** Step 4 closes this.

---

## 9. The contracts that cross each boundary

| | Contract | File | Crosses |
|---|---|---|---|
| C-01 | `EvidenceSpan` | `contracts/evidence.py` | everywhere — the receipt |
| C-02/03 | `Money`, `ResolvedDate` | `contracts/units.py` | integer minor units; a date that knows it is a **range** |
| C-04…C-09 | `EntityMention`, `Commitment`, `DecisionState`, `Dependency`, `UnclassifiedObservation`, `ExtractionResult` | `contracts/extraction.py` | S2 → S3 → S4 |
| C-10 | `Conflict` | `contracts/conflict.py` | **both sides retained, always** |
| C-11 | `SignalType` | `contracts/signal.py` | **15 closed members** (16 after step 2) |
| C-12 | `QualifiedEnterpriseSignal` | `contracts/signal.py` | **L1 → L2** |
| V-1…V-7 | the publication gate | `contracts/publication.py` | emit / park / reject |

### The publication gate, and why the outcomes differ

| Rule | Checks | On failure |
|---|---|---|
| V-1 | envelope complete, `visibility is not None` | **park** — recoverable, not a defect in the claim |
| V-2 | `signal_type` in the closed enum | reject |
| V-3 | `0 ≤ importance_bp ≤ 10000` | reject |
| V-4 | `evidence_refs` non-empty | reject — *a claim with no receipt is a guess* |
| V-5 | every span `verified` | **downgrade confidence and emit**, flagged |
| V-6 | `confidence_bp ≤ min(sources)` unless independent evidence is named | reject (Rule 11) |
| V-7 | no float in the serialized object | reject |

**V-5 downgrading rather than rejecting is load-bearing.** An unverified commitment is still an
open loop worth surfacing, at reduced confidence. The **stored** row must carry the downgraded
value — publishing the input instead silently re-inflates it, and there is a test for exactly that.

---

## 10. The invariants — what a reviewer should check first

| # | Invariant | Enforced by |
|---|---|---|
| 1 | A lower layer never imports a higher one | `tests/test_layer_topology.py` |
| 2 | Integer basis points; **no float crosses a boundary** | V-7 + three purity greps |
| 3 | No claim without a receipt | ALG-08 + V-4 + schema S-9 |
| 4 | No clock inside logic — time arrives as `eval_time`, and a naive one **raises** | grep over `capture/validate/` |
| 5 | No model on a scoring path | grep + `importance.py` mutation test |
| 6 | Structural tokens round-trip: `source[tok.start:tok.end] == tok.text` | a property test, not examples |
| 7 | Rule 11: composed confidence never exceeds the weakest source unless independent evidence is **named** | `validate/confidence.py` |
| 8 | Domain mapping **tags, never filters** — uncovered domains degrade | doctrine (test in step 6) |
| 9 | Every model call site files an `llm_costs` row | `tests/test_every_llm_call_site_is_metered.py` |
| 10 | Activation is a **table**, never a global boolean | `l1_semantic_activation` |
| 11 | A drop is logged, never silently discarded | `qualification_drops` |
| 12 | Every sweep replays byte-identical on identical input | G7 |

### The measured proof that invariant 5 matters

`importance.py` was mutation-checked: replacing the formula with `return 5000` collapses the
distribution to 1 distinct value and turns **16 tests red**. Before ALG-17 existed,
`context/situation_bso.py` stamped a constant and **193 of 223 signals carried an identical
score — with a green test suite the entire time.**

That is why G7 is a **distribution** gate, not an example gate: >50 distinct values,
p90 − p50 > 1500, 100% carrying components, byte-identical on replay.

---

## 11. What Layer 1 must never do

| ❌ | Belongs to |
|---|---|
| Decide what the company should do | L4 |
| Recommend an action | L4 |
| Resolve strategic priority | L4 |
| Choose an owner or a channel | L5 |
| Build the enterprise situation | L2 |
| Resolve entity **identity** (L1 preserves the keys; L2 decides they are the same person) | L2 |
| Judge **situational** relevance — "is this account strategic?" | L2 |
| Evaluate whether a condition is satisfied by company state | L2 |
| Apply domain expertise | L3 |

### The progression, with one example carried through

```
L1   Keshav sent a message on 8 Jul. Meeting coordination.
     No subsequent outbound detected. Coverage over the window: 100%.
      ↓
L2   The interaction is unresolved and sits with Rohit. 77 days.
      ↓
L3   In a fundraising relationship, unanswered coordination beyond N days
     is a relationship-risk pattern.
      ↓
L4   A follow-up is warranted.
      ↓
L5   Draft it; Rohit approves and it sends.
```

Every step in that chain is a different layer, and **L1's line contains no judgement at all** —
only what was observed and how completely it was searched.

---

## 12. TODAY versus TARGET

| Capability | TODAY | TARGET | Step |
|---|---|---|---|
| Document reading | 159 attachments unread | 0, or an explained remainder | 1 |
| Delivery failures | **deleted at the gate by design** | `DELIVERY_FAILURE`, joined to the sent message | 2 |
| Seam | 9 of 28 columns cross | 24+, and per-signal extraction | 3 |
| Claim types with receipts | 8 of 15 | 13+ of 15 | 4 |
| Coverage denominator | none | claimed · fetched · exhausted, per sync | 5 |
| Domain mapping | 4 regexes, **8%** recognition | multi-label, ontology-validated | 6 |
| Intent | inside a mega-prompt | its own contract and confidence | 7 |
| Importance | every score < 4,700 / 10,000 | ceiling published, floor relative | 8 |
| Claim directness | hearsay weighs as first-hand | a separate axis feeding Rule 11 | 9 |
| Gate outcomes | EMIT / PARK / REJECT | + **REVIEW**, with a drain | 10 |
| Benchmark objects | **16 of 38** | 30+ | 11 |
| Commitment state | none | OPEN/FULFILLED/BROKEN/**UNKNOWN**, coverage-gated | 12 |
| Cross-source keys | recipients as one tuple | to/cc/bcc, attendees, meeting kind | 13 |
| Temporal vocabulary | 2 world instants | 6, + reply pairs | 14 |
| Coverage on the signal | `coverage_ready` bool | window + completeness + `unknown` | 15 |

**Nothing in the TARGET column renames a module, changes ALG-17's formula, or lets a model write a
ranking number.**

---

## 13. How to verify this architecture holds

```bash
# import direction — a build failure, not a review nit
uv run --no-sync pytest tests/test_layer_topology.py -q

# the purity greps — gate criteria. All three must return NOTHING.
grep -rn "float(" genios_engine/capture/validate/
grep -rn "datetime.now\|date.today" genios_engine/capture/validate/
grep -rn "LLMClient\|anthropic" genios_engine/capture/validate/

# every model call site is metered — fails in both directions
uv run --no-sync pytest tests/test_every_llm_call_site_is_metered.py -q

# the seam actually carries what L1 published
uv run --no-sync pytest tests/test_l2_reads_what_l1_publishes.py tests/test_l1_seam_activation.py -q

# the scoring distribution — not an example check
python scripts/importance_distribution.py --org <org> --database-url "<url>"

# the whole funnel, on real data — the measurement every step compares against
python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"

# the spec ratchet — the promised-vs-written unit gap may only shrink
python -m scripts.unit_ledger --check
```

**The seam tests are Postgres-only** (`pytest.mark.pg`). Without `GENIOS_TEST_DATABASE_URL` they
skip, and **a skipped test is not a pass**.

---

## 14. Where to go next

| You want | Read |
|---|---|
| The live build state | `../STATUS.md` |
| The eleven-plus-four steps | `00-OVERVIEW.md`, then `step-NN-*.md` |
| What exists, package by package | `../../docs/L1_ANATOMY.md` |
| The eight ESQE groups in detail | `../../docs/L1_GROUP_PLAN.md` |
| Every item's engine (D/R/M/L/J) | `../../docs/L1_BUILD_SPEC.md` |
| The benchmark as a conformance suite | `../../docs/L1_P1_P5_AUDIT.md` |
| The component ledger and the loop | `../../docs/L1_MASTER_LEDGER.md` |
