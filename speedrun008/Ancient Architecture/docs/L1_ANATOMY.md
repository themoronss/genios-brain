# Layer 1 — what it is, how it is built, and everything inside it

> Read of `genios_engine/capture/` on branch `speedrun008` @ f905b65e, 2026-09-23.
> Counts below were **measured** from the tree today. Test counts are *collected*, not run —
> nothing here claims a suite is green.

---

## 0. The one-paragraph version

Layer 1 is the only layer that touches raw customer data. It turns a raw enterprise object
(an email, a HubSpot deal, a PDF, a calendar event, a screen capture, an uploaded file) into a
`QualifiedEnterpriseSignal` — a typed, evidence-carrying, deterministically-scored object that
Layer 2 can rank. It does this in four stages, and the split between them is the whole design:

```
raw object ─► S1 structural ─► S2 semantic ─► S3 validate ─► S4 ESQE ─► QES ─► Layer 2
              find, no model    LLM-2         pure, no I/O    scoring
```

* **S1** finds what is objectively there — money tokens, dates, thread direction — *without* a model.
* **S2** asks a model to understand prose and write into a **closed** schema. One call site.
* **S3** verifies every claim against the source characters it came from. Pure functions.
* **S4** decides which claims are signals, which kind, and how much each one matters — deterministically.

The package name carries no digit. The layer index lives in `genios_engine/LAYERS.py`
(`"capture": 1`), and `tests/test_layer_topology.py` enforces that a lower layer never imports a
higher one.

---

## 1. Size, measured today

| | |
|---|---|
| Python files in `capture/` | **138** |
| LOC in `capture/` | **42,311** |
| Subpackages | **18** + 13 root modules (3,308 LOC) |
| L1's own contracts | 6 files, **2,927 LOC** (`contracts/{evidence,units,extraction,conflict,signal,publication}.py`) |
| Test files under `tests/capture/` | **137** |
| Test functions collected | **2,286** |
| Source descriptors | **36**, of which **9** buildable, across **10 families** + `unclassified` |
| Signal taxonomy | **15** closed members (the docs still say 14 — see §9) |

### LOC by subpackage

| Package | Files | LOC | Stage |
|---|---:|---:|---|
| `esqe/` | 14 | 8,227 | S4 — qualification |
| `semantic/` | 13 | 7,839 | S2 — the extractor |
| `validate/` | 11 | 7,100 | S3 — verification |
| `connectors/` | 15 | 2,416 | ingestion |
| `structured/` | 8 | 2,355 | S1 — the typed bypass |
| `parked/` | 6 | 2,044 | S1 — refetch / recovery |
| `documents/` | 12 | 1,724 | S1 — document router |
| `acquire/` | 7 | 1,416 | ingestion — scheduling |
| `transcripts/` | 5 | 1,349 | P5 — meeting transcripts |
| `structural/` | 3 | 1,056 | S1 — tokens, threads |
| `screen/` | 4 | 869 | P2 — screen intelligence |
| `gate/` | 5 | 828 | the noise gate |
| `coverage/` | 5 | 724 | ingestion — coverage |
| `landing/` | 6 | 392 | dedup + the ledger |
| `preprocess/` | 5 | 287 | HTML strip, PII mask |
| `domain/` | 2 | 194 | domain hints |
| `connections/` | 2 | 140 | connection store |
| `triage/` | 2 | 43 | L2 drain lane |
| root modules | 13 | 3,308 | pipeline, stores, registry, intake |

---

## 2. The four doctrines

Every one of these is enforced by a test or a grep in a wave gate, because every one records a
failure that actually happened.

1. **The model may DESCRIBE, never SCORE.** Anything that orders a founder's morning is computed
   by deterministic code. `esqe/importance.py` has no LLM on its call path.
2. **Integer basis points. No floats. Anywhere.** Every score is `int` in `0..10000`; money is
   integer minor units + ISO code. `conf * 9 // 10`, never `conf * 0.9`.
3. **No claim without a receipt.** Every claim carries an `EvidenceSpan` — character offsets into
   the original source plus the quoted text. `verified=True` only after `validate/spans.py`
   resolves it. The extractor cannot stamp its own receipt (schema rule S-9 rejects it).
4. **No clocks inside logic.** Time arrives as `eval_time`. A function that reads the clock cannot
   be replayed, and replay is what makes every gate checkable. A tz-naive `eval_time` raises.

---

## 3. The seven groups

The plan's own numbering. 7 groups · 49 components · 65 written unit specs (of 100 promised) ·
23 algorithms · 12 contracts · 5 LLM call sites.

| Group | Name | Code | Components |
|---|---|---|---|
| **L1.1** | Enterprise Sources | `source_registry.py`, `source_families.py`, `coverage/`, `source_waitlist.py` | source taxonomy (16 categories, not buildable components) |
| **L1.2** | Knowledge Connectors | `connectors/`, `acquire/`, `connections/` | 6 |
| **L1.3** | Deterministic Extraction (S1) | `structural/`, `documents/`, `structured/`, `parked/`, `landing/`, `preprocess/` | 9 |
| **L1.4** | Semantic Extraction (S2) | `semantic/` | 10 |
| **L1.5** | Validation & Normalization (S3) | `validate/` | 9 |
| **L1.6** | ESQE — Qualification (S4) | `esqe/` | 10 |
| **L1.7** | Knowledge Storage | `payload_store.py`, `prepared_store.py`, `esqe/signal_store.py`, `coverage/store.py` | 5 |

---

## 4. Group by group — components and their units

### L1.2 · Knowledge Connectors — *get the bytes, honestly*

| Component | Units | Code | State |
|---|---|---|---|
| L1.2.1 Connector Manager | 3 | `connectors/dispatch.py`, `base.py` | reuse as-is |
| L1.2.2 Authentication | 3 | `connectors/composio*.py` | reuse as-is |
| L1.2.3 Permission Manager | 3 | `visibility_rules.py` | **strong — do not touch** |
| L1.2.4 Incremental Sync | 3 | `connectors/backfill.py`, `acquire/sync_runner.py` | fixed: backfill window 60 → 540 days, per connection |
| L1.2.5 Webhook Listener | 3 | `connectors/push_ingest.py`, `composio_push.py` | fixed: push used to drop attachments and `mailbox_owner` — same mail landed 3 rows by poll, 1 by push |
| L1.2.6 Polling Scheduler | 3 | `acquire/{cadence,jitter,catchup,scheduler}.py` | fixed: per-source cadence, **deterministic** jitter (org+connection, not entropy), catch-up windows |

Connectors present: `gmail` (via Composio), `calendar`, `drive`, `notion`, `hubspot`, `linear`,
`database`/`postgres`, plus `fake` for tests.

### L1.3 · Deterministic Extraction (S1) — *what a model must never be asked to find*

| Component | ALG | Units | Code |
|---|---|---|---|
| L1.3.1 Event Normalizer | — | 1 | `landing/normalize.py` |
| L1.3.2 Metadata Extraction | — | 2 | `landing/` |
| L1.3.3 Content Normalizer | — | 2 | `preprocess/{preprocess,text,pii,quoted}.py` |
| L1.3.4 Document Router | ALG-01 | 4 | `documents/` — U1 native, U2 OCR, U3 speech (descoped), U4 chunking, U5 page map |
| **L1.3.5 Structural Parser** | ALG-04 | 3 | `structural/tokens.py` — U1 `scan()` (11 token types), U2 `router_counts()`, U3 tenant identifier regexes |
| L1.3.6 Thread Reconstructor | ALG-03 | 2 | `structural/threads.py` — U1 `reconstruct_thread()` (direction, turn index, `ball_in_court`), U2 `assemble_chain()` |
| L1.3.7 Deduplication | ALG-02 | 2 | `landing/repository.py`, `landing/reread.py` |
| L1.3.8 Attachment Resolver | — | 2 | `parked/{refetch,refetch_policy,recapture,drain}.py` |
| **L1.3.9 Structured Mapper** | ALG-21 | 3 | `structured/{registry,mapper,lane,targets,apply,product_usage,coverage}.py` |

**The S1 invariant:** `source[tok.start:tok.end] == tok.text` for every token — a property test,
not a handful of examples.

**The find-vs-interpret line:** `$84K` leaves `tokens.scan` as a `currency_token` with a raw string
and two offsets, *and nothing else*. Turning it into `Money(8_400_000, "USD")` is ALG-10's job and
happens later in `validate/money.py` — so the model's claim and the source's literal stay two
comparable objects rather than one number nobody can audit.

**The structured bypass** is the cheapest path in the layer: a mapped HubSpot deal skips the model
entirely, lands `field_confidence == 10000, verified=True`, and runs even when the semantic lane is
not configured (proven with an LLM client that *raises* if called).

### L1.4 · Semantic Extraction (S2) — *the one place a model runs*

Group law: **the model DESCRIBES. It never SCORES, never ROUTES, never DECIDES VISIBILITY.**

| Component | Units | File | What it is |
|---|---|---|---|
| L1.4.1 Content-Type Router | 2 | `router.py` | which reading task is this |
| L1.4.2 Extraction Profile Registry | 3 | `profiles.py` | 5 profiles, one prompt per kind of content, versioned as data |
| **L1.4.3 Semantic Extractor** | 4 | `extractor.py` (1,938 LOC) | **LLM-2** — the call itself |
| L1.4.4 Extraction Schema | 2 | `vocabulary.py` (U1 closed vocabularies), `schema_gen.py` (U2 schema from the type) |
| **L1.4.5 Open Lane** | 3 | `open_lane.py`, `sink_guard.py` | `UnclassifiedObservation` — what the closed vocabulary could not name |
| L1.4.6 Evidence Binder | 2 | `evidence_binder.py` | span attachment, mask→original offset alignment |
| L1.4.7 Prompt Injection Guard | 2 | `injection.py` | content fencing; a payload containing the fence is escaped |
| L1.4.8 Batch Planner + Cost Governor | 3 | `batch.py` | what the drain is about to spend, *before* it spends it |
| L1.4.9 Extraction Cache | 2 | `cache.py` | keyed on content + schema version + profile + prompt version |
| L1.4.10 Model Router | 2 | `model_router.py` | ALG-05 — tier chosen on **deterministic inputs only**; demotion visible as `tier_demoted` |

**Wave 3 built the sink before Wave 4 filled it.** Not stylistic: a free-form extractor once
invented 268 distinct field names in one org — 192 used exactly once — while rules reading
`deal.status` were dead because the model had written `status`.

### L1.5 · Validation (S3) — *turn what a model said into what can be checked*

No float, no clock, no LLM, no DB — anywhere in this package.

| Component | ALG | File | What it does |
|---|---|---|---|
| L1.5.0 Claim Group Assembler | ALG-22/23 | `claim_group.py` | groups claims about one subject across a thread and its attachments |
| **L1.5.1 Evidence Span Validator** | ALG-08 | `spans.py` | grades exact / whitespace-normalised / relocated / fuzzy / unverified, and **corrects** the model's offsets rather than trusting them |
| **L1.5.2 Date/Time Normalizer** | ALG-09 | `dates.py` | "next Friday" is a *range with a certainty*, not a point |
| **L1.5.3 Currency Normalizer** | ALG-10 | `money.py` | `$84K` and `$84,000` → the same object; integer path throughout |
| L1.5.4 Entity Canonicalizer | ALG-11 | `canonical.py` | "AWS" = "Amazon Web Services", deterministic aliases, no embeddings. A *hint* — L2 stays authoritative on identity |
| **L1.5.5 Conflict Detector** | ALG-12 | `conflict.py`, `conflict_store.py` | the $74K signed PDF vs the $84K email — **both claims retained**, with a resolution and a reason |
| L1.5.6 Schema Validator | — | `schema.py` | S-1…S-9 shape and vocabulary rules, stage-scoped |
| **L1.5.7 Confidence Composer** | ALG-13 | `confidence.py` | **Rule 11** — composed confidence may never exceed the weakest source unless independent evidence is *named* |
| L1.5.8 Authority Weighter | ALG-14 | `authority.py` | a signed contract outranks an email outranks a chat aside. A table, not a chain of ifs |

**Rule 11, in one measurement.** Before the fix a weak Slack message waived the ceiling entirely:

```
prior 2000 · signed.pdf 9000 · slack 100
before:  composed 9002    (the slack line bought an 8,900 bp lift it never earned)
after:   composed 1882    = corroborate(100, 9000) — the sanctioned bound, exactly
```

### L1.6 · ESQE — Enterprise Signal Qualification (S4)

Group law, one sentence: **all scoring lives here, and none of it is done by a model.**

| Component | ALG | File | What it does |
|---|---|---|---|
| L1.6.1 Signal Detector | ALG-15 | `detector.py` | deterministic predicate table over validated claims — *is there a signal, and which kinds* |
| L1.6.2 Signal Normalizer | — | `normalize.py` | one canonical shape whichever predicate fired |
| L1.6.3 Signal Classifier | ALG-16 | `classifier.py` | constant precedence over the closed taxonomy — *which kind is primary* |
| L1.6.4 Source Analyzer | — | `source_analyzer.py` | provenance and actor authority — *who said it, does that make it weigh more* |
| L1.6.5 Business Relevance | — | `relevance.py` | **LLM-5** — rules first, model only for the ambiguous remainder, batched at the page seam |
| L1.6.6 Domain Mapping | — | `domain.py`, `domain/hints.py` | domain tagging, never-filter rule enforced |
| **L1.6.7 Importance Scoring** | **ALG-17** | `importance.py` (1,184 LOC) | **the formula** — five weighted integer terms × an evidence-authority multiplier |
| L1.6.7-U2 Org Baseline | — | `baseline_reader.py` | the org's own priced history, so the formula is normalised per tenant |
| L1.6.8 Qualification Engine | ALG-18 | `qualification.py` | **the floor** — below it, dropped *with a ledger row* carrying components and a payload ref |
| L1.6.9 Signal Lifecycle | ALG-19 | `lifecycle.py` | active / superseded / expired / resolved, as an explicit transition table |
| L1.6.10 Signal Publisher | — | `publisher.py`, `finalize.py` | V-1…V-7 over what qualified → `qualified_signals`. The L1→L2 boundary |

**ALG-17's five terms:** monetary exposure against the org's own p50 · deadline proximity · actor
authority · entity criticality · signal-type nudge. Weights are injectable (`ImportanceWeights`,
must sum to 10000 — that check is a gate on arithmetic, since `/10000` is only a weighted mean
while it holds).

**Why this component is the point of the whole layer.** Before it, `context/situation_bso.py`
stamped a constant and `reason/decision_maker.py` recorded that *"the formula has never once
decided anything"* — 193 of 223 signals carried an identical score, **with a green suite the whole
time**. So G7 is a *distribution* check, not an example check: >50 distinct values, p90−p50 > 1500,
100% carrying components, byte-identical on replay. Mutation-checked — replacing the formula with
`return 5000` collapses it to 1 distinct value and turns 16 tests red.

### L1.7 · Knowledge Storage

| Component | Table / store | File |
|---|---|---|
| L1.7.1 Raw evidence store | encrypted payloads, TTL'd | `payload_store.py` |
| L1.7.2 Prepared content store | `prepared_content` + offset map | `prepared_store.py` |
| L1.7.3 Extraction store | `l1_extraction_results` (migrated from L2) | `semantic/cache.py` |
| L1.7.4 Signal store | `qualified_signals` | `esqe/signal_store.py` |
| L1.7.5 Coverage store | `source_coverage` | `coverage/store.py` |

Retention is tiered by decision: emitted keeps a short TTL, **parked keeps a long one** (a park is
a human-review queue — parked used to store no payload, so `/recover` was a no-op black hole), and
a **judged** drop keeps 90 days (a model's verdict is the one deletion we might be wrong about; 657
dropped events with zero payloads once made "did we lose anything real?" permanently unanswerable).
A deterministic drop still stores nothing — L1 stays a filter, not a warehouse.

---

## 5. The runtime spine — `capture_event()` step by step

`capture/pipeline.py` (1,704 LOC). One raw object in, one `CaptureResult` out. Terminal outcomes:
**duplicate** (landing), **dropped** / **parked** (gate), or **emitted** (`GatedEvent` → L2).

| # | Step | Code | Notes |
|---|---|---|---|
| 1 | **land** | `land_raw_object` → `landing/` | dedup + the audit ledger. Not landed ⇒ `duplicate`, stop |
| 2 | **route detect** | `structured/registry.has_mapping` | a registry mapping *or* an `enterprise_system` family ⇒ structured route |
| 3 | **preprocess** | `preprocess/` | HTML stripped **here** (heavy at ingestion); subject is part of the prose and masked *with* the body; PII masked, offsets kept |
| 4 | **gate** | `gate/gate.py` | S0 scope → S1 hard rules + whitelist → S1.5 structured short-circuit → route. Every stage records pass/drop/park/short_circuit with a reason code |
| 5 | **persist the decision** | `repo.add(...)` | decision-first ledger: route, lane, domain hints, linkage hints, all written *with* the decision so L2 and replays read instead of recompute |
| 6 | **triage** | `triage/triage.py` | the L2 **drain order** (P1/P2/P3). An availability notice is forced to P3 — an auto-reply storm must never preempt a customer |
| 7 | **stash payload** | `payload_store`, `prepared_store` | per the retention rules in §4 |
| 8 | **structured lane** | `structured/lane.py` | typed fields → `ExtractionResult`, **no model**. A mapping is the only condition |
| 9 | **semantic lane** | `run_semantic_lane` → `semantic/` | LLM-2. Refuses the structured route on the same flag the gate short-circuited on, so the bypass stays free |
| 10 | **conflict** | `validate/conflict.py` | after extraction (nothing to compare before), before emit (so the trace carries it). Never fails a capture |
| 11 | **ESQE** | `run_esqe_stage` → `esqe/` | after conflict (INFORMATION_CONFLICT is one of the predicates), before emit. **Always runs** — it is pure and unbilled |
| 12 | **coverage verdict** | `coverage/` | assessed against the domain *this* event was hinted into |
| 13 | **emit** | `_build_gated_event` | `GatedEvent` → Layer 2 |

**Everything L1 computes is persisted at the seam** — the decision on the `source_events` row, the
PII-masked prepared text plus offset map in `prepared_content` — so L2 reads the seam instead of
re-deriving it, and evidence traces back to exact source characters.

### The bundle discipline

`capture_event` takes 17 parameters, so each optional subsystem arrives as **one** frozen dataclass:
`SemanticLane`, `StructuredLane`, `ConflictLane`, `EsqeStage`. `None` means *not wired* and the
pipeline behaves exactly as it did before that subsystem existed — which is what makes a
strangler-fig activation safe to land ahead of any tenant. The one exception is `EsqeStage`: `None`
does **not** turn S4 off, because it is pure and unbilled.

---

## 6. The doors — every way an event enters Layer 1

Exactly four call `capture_event`:

| Door | Code | What comes through |
|---|---|---|
| **Poll / sweep** | `acquire/sync_runner.py:270` | scheduled connector syncs |
| **Push / webhook** | `connectors/push_ingest.py:123` | Composio trigger deliveries |
| **Manual intake** | `intake.py:54` | human notes/edits, agent outcome events, uploads |
| **API** | `api/routes.py:1545` | direct ingest path |

And after a door has captured its events, **one** finalizer runs — `esqe/finalize.py`, in a fixed
order: `conflicts → qualify → lifecycle → publish`. It exists because that sequence grew a line at
a time inside `api/routes.py` and the **upload door never called it** — a founder's hand-uploaded
signed contract was captured, extracted, scored, and then its signals fell on the floor. Nothing
errored; `qualified_signals` simply had no row. Called now by `routes.py`, `upload_routes.py` and
`platform/screen_promoter.py`.

---

## 7. Sources — the taxonomy

**10 families** (declared, never derived) + `unclassified`: `internal`, `external`, `human_input`,
`ai_generated`, `enterprise_system`, `communication`, `knowledge`, `operational`, `live_event`,
`intelligence`.

**36 source descriptors**, of which **9 are buildable** today: `gmail`, `gcal`, `notion`, `gdrive`,
`hubspot`, `postgres`, `database`, `mysql`, `linear`.

One descriptor per source is the single source of truth for: family · coverage capability ·
buildability · object types · **mutability**. That last field is load-bearing — an email never
changes so its id is a safe dedup key, but a deal, a meeting and a DB row all do, and the id alone
freezes them at first-seen state. Mutable sources must name a `version_field` (`updatedAt`,
`modifiedTime`, `updated`) or the module refuses to import.

---

## 8. The L1 → L2 boundary

**`QualifiedEnterpriseSignal`** (C-12, `contracts/signal.py`), written to `qualified_signals`.

**15 closed signal types:** `COMMITMENT_MADE`, `COMMITMENT_DUE`, `DEADLINE_STATED`,
`DECISION_PENDING`, `DECISION_MADE`, `APPROVAL_REQUESTED`, `CONTRACT_RENEWAL`,
`FINANCIAL_OBLIGATION`, `RISK_FLAGGED`, `OPPORTUNITY_SIGNAL`, `RELATIONSHIP_CHANGE`,
`INFORMATION_CONFLICT`, `ESCALATION`, `ANOMALY`, `AVAILABILITY_CHANGE`.

**The publication gate** (V-1…V-7, `contracts/publication.py`) — note that the outcomes differ on
purpose:

| Rule | Checks | On failure |
|---|---|---|
| V-1 | envelope complete, `visibility is not None` | **park** — recoverable, not a defect in the claim |
| V-2 | `signal_type` in the closed enum | reject |
| V-3 | `0 ≤ importance_bp ≤ 10000` | reject |
| V-4 | `evidence_refs` non-empty | reject — *a claim with no receipt is a guess* |
| V-5 | every span `verified` | **downgrade confidence and emit**, flagged |
| V-6 | `confidence_bp ≤ min(source confidences)` unless independent evidence named | reject (Rule 11) |
| V-7 | no float in the serialized object | reject |

V-5 downgrading rather than rejecting is deliberate: an unverified commitment is still an open loop
worth surfacing, at reduced confidence. The **stored** row must carry the downgraded value.

---

## 9. What the code has that the build record does not

`docs/plans/L1_V2_BUILD_RECORD.md` was written 2026-09-06. Since then:

| Added | Code | Notes |
|---|---|---|
| **P2 · Screen intelligence** | `screen/{render,fingerprint,relevance}.py` (869 LOC) | what a seat's desktop app read on screen; enters via `/v1/sessions` + `platform/screen_promoter.py`, not a connector |
| **P5 · Meeting transcripts** | `transcripts/{parse,speakers,link,ingest}.py` (1,349 LOC) | export → ordered turns → speakers against a closed candidate set → linked to the calendar meeting, ingested as private parts |
| **The one finalizer** | `esqe/finalize.py` | §6 |
| **Manual intake door** | `intake.py` | the one door for notes, agent outcomes, uploads |
| **Internal knowledge** | `internal_knowledge.py` | what the company *deliberately* asserts about itself — enters at authority rank 4, above system-of-record |
| **The journey answer** | `journey.py` | *"why did I never see X?"*, answerable about one event |
| **Unread / reread** | `landing/{unread,reread}.py` | mail captured while a tenant's L1 was off, read again once on; a re-read must not re-land attachments |
| **Source waitlist** | `source_waitlist.py` | a source a tenant wants but cannot connect, recorded instead of a lying UI tile |
| **AVAILABILITY_CHANGE** | `contracts/signal.py` | a **15th** signal type. The record and `esqe/__init__.py` both still say "closed 14-member taxonomy" — stale prose, not a code defect |

---

## 10. What is open

| Item | State |
|---|---|
| **G10 — pilot activation** | the only open gate per the record. Needs a real tenant and 7 days of shadow running, not more code |
| **Activation is a table, not a flag** | per tenant in `l1_semantic_activation`. The record's rule: *"built but not enabled is not done."* Tenants have shipped with no row — 1,665 events landed, 14 facts came out |
| **Golden corpus (G4)** | **8 messages, not the 30** the spec asks for. Passes every threshold on those 8; should not be reported as complete |
| **Speech-to-text (L1.3.4-U3)** | descoped. The router seam exists against synthetic fixtures; no provider wired |
| **35–37 unwritten unit specs** | component maps promise 100 units; 65 have spec blocks. `scripts/unit_ledger.py --check` is the ratchet — the gap may only shrink |
| **Org holiday calendar** | `add_business_days` takes an injected calendar; nothing in L1 reads a per-org holiday list, so weekends-only is live behaviour |
| **ALG traceability** | 19 of 23 algorithm ids appear in `capture/`. **ALG-02** (dedup key), **ALG-06** (cache key), **ALG-07** (batch packing) and **ALG-20** (coverage computation) appear nowhere in code or engineering docs — all four are implemented, but only in the "reuse as-is" components whose code never got tagged. A traceability gap, not a build gap |

---

## 11. Where to verify any of this

```bash
# the translation table between the three layer vocabularies
docs/LAYER_MAP.md · genios_engine/LAYERS.py

# the schedule (waves, gates, sequencing corrections) and the result
docs/plans/L1_V2_BUILD.md · docs/plans/L1_V2_BUILD_RECORD.md

# the design of record — 11 docs, one per group
"Rohit Updates YC/Version 2 Updates/01-Layer-1-Plan/"

# the spec ratchet
python -m scripts.unit_ledger

# the purity greps — gate criteria, not lint
grep -rn "float(" genios_engine/capture/validate/
grep -rn "datetime.now\|date.today" genios_engine/capture/validate/
grep -rn "LLMClient\|anthropic" genios_engine/capture/validate/

# import direction
uv run --no-sync pytest tests/test_layer_topology.py -q
```
