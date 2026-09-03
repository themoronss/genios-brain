# Gap Audit — Layer 1: Globe spec vs. built code

**Audited:** 2026-09-03, at merge commit `b4d4d15` (harsh/mvp merged into rohit-yc-brain)
**Method:** all 48 Globe-specified L1 components checked directly against
`genios_engine/capture/` (60 modules). Every claim below carries a file:line citation.

---

## Scoreboard

| Group | Spec'd | ✅ Built | ⚠️ Partial | ↪️ Moved to L2 | ❌ Missing |
|---|---|---|---|---|---|
| L1.1 Enterprise Sources | 16 | 6 | 3 | — | 7 |
| L1.2 Knowledge Connectors | 6 | 3 | 3 | — | 0 |
| L1.3a Content Pipeline | 8 | 4 | — | 2 | 2 |
| L1.3b Event Pipeline | 4 | 3 | — | 1 | 0 |
| **L1.4 ESQE — the gateway** | **10** | **2** | **3** | — | **5** |
| L1.5 Knowledge Storage | 4 | 1 | 1 | — | 2 |
| **TOTAL** | **48** | **19** | **10** | **3** | **16** |

**~40% built to spec. ESQE — the component Globe calls "the single gateway" — is 20% built.**

---

## The four structural failures

### ❌ 1. L1 does not qualify. It routes.

| | Globe spec | Code reality |
|---|---|---|
| L1 output | `QualifiedEnterpriseSignal` | `GatedEvent` |
| Carries | `signal_type`, `domain`, `entities[]`, `importance_bp`, `evidence_refs[]` | `route`, `structured_fields`, `domain_hints`, `triage_lane`, `recipients`, `visibility` |
| Answers | *"Something happened and it matters"* | *"Is this clean, and does it need extraction?"* |

The contract admits it — `contracts/gated_event.py:24`:

> *"The audit's RC-1 named this object as 'does not exist'; it existed under this name and
> **was missing its qualifying half**."*

**Downstream cost:** Globe's ESQE discards ~92% of noise *before it costs anything*. The
code's gate discards spam, then sends every survivor to L2 for an LLM extraction call.
The spend moved downstream — which is why daily LLM caps and circuit breakers became
necessary.

### ❌ 2. `importance_bp` does not exist — and this IS the ranking bug

Globe L1.4 Importance Scoring: *produces `importance_bp` from monetary value, deadline
proximity, actor authority, entity criticality.*

The code **deliberately refuses it** — `contracts/gated_event.py:28`:

> *"Still deliberately absent, by design not omission: `importance_bp` (importance is a
> REASONING output — L1 stamping it would be the priority/importance conflation the spec
> forbids)"*

The consequence chain:

```
L1 stamps no importance_bp
  -> L4 has no per-event importance to score on
     -> priority_override replaces the utility formula outright
        -> decision_maker.py:243: "the formula has never once decided anything"
           -> ranking = 30 authored constants in situation YAML
              -> two different tenants get IDENTICAL rankings
```

**The L4 ranking failure is an L1 hole.**

**Resolution adopted in v2:** build it at L1, keeping two distinct fields. `importance_bp`
(L1) answers *how big is this thing* — intrinsic, unchanged by what else is happening.
`priority_bp` (L4) answers *what should this person do first* — relative to their book.
The original objection guards against a real conflation; two fields answer it. Both are
currently missing, which is why neither computes.

### ❌ 3. No signal taxonomy exists

A grep of `capture/` for `signal_type`, `signal_detect`, `SIGNAL_TYPES` returns **zero
hits.** There is no Signal Detector and no Signal Classifier.

Globe calls Signal Detection *"the first gate in the entire system — a miss here is
unrecoverable downstream, no matter how good L4 is."* Absent. Nothing downstream can
branch on what kind of thing happened, which is why Globe's 15 Admin surfaces cannot be
built on this L1 — each keys off a signal type L1 never assigns.

`triage/triage.py` is **not** the classifier; its own comment says it is
*"PROCESSING ORDER only, not user priority."*

### ⚠️ 4. Rule 03's replay guarantee — **partially backed** (corrected)

An earlier pass of this audit reported the extraction cache as missing. **That was
wrong** — the grep searched for `model_ref` and the column is named `model_snapshot`.

The cache **exists and is well designed**: `l2_extraction_results`
(`migrations/0004_l2_context_graph.sql:181`), keyed on
`hash(org + PROMPT_VERSION + EXTRACTION_SCHEMA_VERSION + model + vocab_fingerprint + content)`
(`context/pipeline.py:463-475`).

The remaining gap is **location, not existence**: Globe places the Extraction store at
L1.5 and it lives at L2. v2 relocates it (Wave W4) rather than building one.

This matters more than a naming quibble: the cache is what makes heavy L1 LLM
affordable. The model runs once per document version, ever.

---

## Component detail

### L1.4 ESQE — the gateway (2/10)

| # | Component | Status | Evidence |
|---|---|---|---|
| 1 | Signal Detector | ❌ MISSING | zero grep hits in `capture/` |
| 2 | Signal Normalizer | ❌ MISSING | nothing to normalize |
| 3 | Signal Classifier | ❌ MISSING | no closed taxonomy |
| 4 | Source Analyzer | ⚠️ PARTIAL | `internal_knowledge.py:113` `authority_rank_for()` covers `internal_kind` only |
| 5 | Business Relevance | ⚠️ SUBSTITUTED | `gate/relevance.py` is a *junk* gate ("is this spam?"), a different job |
| 6 | Domain Mapping | ✅ BUILT | `domain/hints.py` |
| 7 | Importance Scoring | ❌ REFUSED | deliberate, documented |
| 8 | Qualification Engine | ⚠️ PARTIAL | drop/park works; **no importance floor** — impossible without #7 |
| 9 | Signal Lifecycle Mgr | ❌ MISSING | `prepared_store` TTL is content expiry, not signal lifecycle |
| 10 | Signal Publisher | ✅ BUILT | emits `GatedEvent`, not a QES |

### L1.3a Content Pipeline (4/8)

| Component | Status | Evidence |
|---|---|---|
| OCR | ✅ BUILT | `documents/tesseract.py` — but `enable_ocr=False` |
| Speech to Text | ❌ MISSING | no audio path anywhere |
| Content Normalizer | ✅ BUILT | `preprocess/text.py` |
| Chunking | ✅ BUILT | `documents/chunking.py` — sentence-aware, **not section-aware** |
| Entity Extraction | ↪️ MOVED | now `context/extract/` |
| Relationship Extraction | ↪️ MOVED | now `context/extract/` |
| Embedding Generation | ❌ MISSING | no pgvector. `context/identity.py:25` deliberately rejects it |
| Deduplication | ✅ BUILT | content hash |

### Connectors, events, storage

| Component | Status | Note |
|---|---|---|
| Permission Manager | ✅ **STRONG** | visibility stamped at source; gate **parks** `visibility_unknown` |
| Metadata Extraction | ✅ **STRONG** | recipients captured at the last moment they exist |
| Connector Manager / Authentication | ✅ BUILT | |
| Event Normalizer / both dedup jobs | ✅ BUILT | correctly distinct |
| Incremental Sync | ⚠️ **BROKEN PROMISE** | `sync_runner.py:270-299` documents "FULL history"; routes to `newer_than:60d` |
| Webhook Listener | ⚠️ PARTIAL | HMAC verify ✅; bypasses gate, prepared-store, parked-store (`routes.py:1549`) |
| Polling Scheduler | ⚠️ PARTIAL | one global 6h cadence (`config.py:88`); no per-source rate, no jitter |
| Raw evidence store | ✅ BUILT | 90d retention on judged drops |
| Extraction store | ⚠️ WRONG LAYER | exists at L2 |
| Vector index | ❌ MISSING | none — and v2 keeps it that way, deliberately |
| Signal store | ⚠️ PARTIAL | `source_events` is a landing ledger, not a signal store |

---

## Where the code is BETTER than the spec

Fair credit — three places the implementation is ahead of Globe:

1. **6 buildable connectors vs Globe V1's 2.** Ahead of scope.
2. **MUT-01 versionability check** (`gate/rules.py`). Refuses to ingest a mutable object
   with no version, which would otherwise freeze at first-seen state forever. Not in Globe.
3. **Judged-drop payload retention + re-adjudication drain.** Globe says "log and drop";
   the code keeps 90 days of payload so a wrong drop is recoverable. A better answer to
   *"why didn't GeniOS see this?"*

And on Globe's own L1 failure-mode table: both **safety** failures (webhook redelivery,
visibility too wide) are properly guarded. The two **intelligence** failures (missed
commitment, currency mis-parse) cannot occur at L1 — because those components do not exist.

---

## Silent losses found

Things computed or persisted and then thrown away:

| # | What | Evidence |
|---|---|---|
| 1 | `coverage_ready` | `coverage_fn` passed by no production caller; `coverage/model.py` computes the answer and discards it |
| 2 | `source_coverage` table | migration `0002`; written by nothing, read only by the deletion cascade |
| 3 | `linkage_hints` | persisted on `GatedEvent`, no reader |
| 4 | `route` column | persisted, unread |
| 5 | Prepared-content offset map / masked spans | no downstream reader — v2's evidence binder becomes that reader |
| 6 | Attachment stubs | park as `NEEDS_REFETCH`; **no code path ever refetches** |
| 7 | Gmail fast-path drops | keep only the list snippet; attachments never fetched |

Items 1, 5 and 6 are addressed directly in the v2 plan; 3 and 4 are absorbed into the QES.

---

## Correction log

| Date | Claim | Correction |
|---|---|---|
| 2026-09-03 | "No extraction cache table exists — Rule 03's replay guarantee is unbacked" | **Wrong.** `l2_extraction_results` exists at `migrations/0004:181` with a correct hash key. The grep searched `model_ref`; the column is `model_snapshot`. The real gap is location (L2, not L1.5), not existence. |
