# Layer 1 v2 — Build Record

> **Created:** 2026-09-05 · **Status:** Active

**Purpose:** the execution record for building Layer 1 v2 (Hybrid Intelligence Extraction) into
`genios_engine/capture/` — the wave/gate order, the verified component counts, what is reused
versus built new, the four sequencing defects found reviewing the spec against this codebase, and
the database hazards that must be handled before any wave lands.

**Specification of record:** `Rohit_Updates (Version 2)/Version 2 Updates/01-Layer-1-Plan/`
(docs 00–10) plus `02-Gap-Audit-L1-Spec-vs-Code.md` and `03-Plan-Crosscheck-and-Corrections.md`.
That set is the *design*. This file is the *build*: what is scheduled, what was found wrong with
the schedule, and what must not be forgotten at the database layer. Where the two disagree, the
corrections in §4 below win, and the source doc should be amended to match.

**The one-line doctrine:** *the LLM understands the data; deterministic systems make that
understanding usable and trustworthy.* Semantic extraction moves from L2 to L1; scoring
(`importance_bp`) becomes deterministic and lives at L1; nothing the model produces reaches Layer 2
without a verified evidence span.

---

## 1. The ten waves and their gates

Reverse-engineered order: units are built and tested in isolation, components assemble from green
units, groups from green components. **A parent is never built before its children are green.**

| Wave | Builds | Depends on | Gate | Gate passes when |
|---|---|---|---|---|
| **W0** | Contracts (doc 08) — C-01…C-12 | — | **G0** | `tests/contracts/test_l1_contracts.py` and `tests/test_layer_topology.py` pass with **0 skips**; `grep -rn "float" genios_engine/contracts/signal.py genios_engine/contracts/extraction.py` finds no float annotation |
| **W1** | Pure validators: spans, dates, money, confidence | W0 | **G1** | `tests/capture/validate` green, 0 skips; **all three greps empty** — no `float(`, no `datetime.now`/`date.today`, no `LLMClient`/`anthropic` under `capture/validate/` |
| **W2** | S1: structural parser, thread reconstructor, chunking upgrade, attachment refetch, **structured mapper (L1.3.9)** | W0 | **G2** | 0 attachments stuck in `NEEDS_REFETCH` past 1h; 0 documents with empty text and no `ocr_failed`; 0 structural-token offset round-trip failures; a HubSpot deal fixture yields an `ExtractionResult` with **zero LLM calls** and `field_confidence == 10000`, `verified=True` |
| **W3** | **The typed sink**: vocabulary, schema gen, profiles, open lane, evidence binder | W0 | **G3** | `tests/capture/semantic` green, 0 skips; the import-graph test asserts `capture/semantic/vocabulary.py` imports nothing from `packs/` or `context/extract/vocab.py`, and that nothing under `packs/`/`reason/` imports `capture/semantic/open_lane.py` |
| **W4** | **The extractor**: content-type router, model router, injection guard, cache migration, extractor | W3, W2 | **G4** | on the 30-message golden corpus: ≥90% expected commitments detected, ≥95% emitted spans verify, **0 fabricated amounts (hard fail)**, the doc-04 worked example passes exactly, and an unchanged re-run is a 100% cache hit with zero LLM calls |
| **W5** | **Claim group assembler (L1.5.0)** + conflict detector | W1, W4 | **G5** | the \$74K-signed vs \$84K-email fixture — presented as **two events** (`email_message` + `email_attachment` linked by `parent_object_id`, as `composio.py:383` actually emits them) — produces a `Conflict` with **both claims retained**, `resolved_by_authority`, resolved to \$74K |
| **W6** | ESQE detection: detector, normalizer, classifier, source analyzer, relevance, domain | W4, W5 | **G6** | `tests/capture/esqe` green; the doc-04 worked example produces exactly `{CONTRACT_RENEWAL, DECISION_PENDING, APPROVAL_REQUESTED}` |
| **W7** | **Importance scoring** + org baseline + qualification floor | W6, W1 | **G7 — the Layer 4 unlock** | >50 distinct `importance_bp` values on 30d of a real tenant; `p90 − p50 > 1500`; identical input replays byte-identical; 100% of scores carry `importance_components`; **plus the structured/model parity assertion moved here from G2** (§4.1) |
| **W8** | Lifecycle + publisher + signal store | W7 | **G8** | `tests/capture/esqe/test_publisher.py` green and every metric in the doc-06 group acceptance table met end to end |
| **W9** | Connector fixes: backfill window, webhook parity, cadence/jitter, coverage wiring | independent | **G9** | webhook and poll produce **identical rows** for the same message; every swept event carries a non-null `coverage_ready` |
| **W10** | Pilot activation + L2 cutover | all | **G10** | 7 days shadow on one real tenant: 100% of events processed by both paths, every signal v1 found and L1 v2 missed **reviewed and explained individually**, unverified span rate <5%, LLM cost/1000 events within 2× of v1, **0 founder-visible regressions** |

**W9 is independent and starts on day one.** It touches no contract, and an 18-month backfill
window plus the HubSpot expansion changes what L1 v2 has to work with.

**The one ordering that must not be violated: W3 completes before W4 begins.** The sink exists
before anything fills it. That is the whole lesson of `context/extract/vocab.py` — *268 distinct
field names invented in one org, 192 used exactly once*, while rules read `deal.status` and the
extractor, never told the name, wrote `status`.

### Activation is a table, not a flag

`platform/config.py:110` carries `use_domain_compiler: bool = False`, set in **no environment** —
152 authored capabilities have never influenced one customer-visible recommendation. L1 v2 must not
add a second such switch. Activation is per tenant in `l1_v2_activation (org_id, enabled_at,
enabled_by, notes)`, and **"built but not enabled" is not done**: a unit is done when its acceptance
command passes against a real tenant with that row present.

---

## 2. Verified counts

| Count | Value | How it is arrived at |
|---|---|---|
| Groups | **7** | L1.1 sources, L1.2 connectors, L1.3 deterministic, L1.4 semantic, L1.5 validation, L1.6 ESQE, L1.7 storage |
| Components | **49** | 6 + 9 + 10 + 9 + 10 + 5 across L1.2…L1.7. (L1.1's 16 entries are *source categories*, not buildable components — the crosscheck's P-07 arrives at "65 components" by adding them, which double-counts the 16 sources against the six component maps — and collides with the 65 that is the *unit* count.) |
| Unit specs written | **65** | `-U` unit specs actually present in docs 01–07 — counted by `scripts/unit_ledger.py`, not by hand |
| Units promised | **100** | the sum of the "Units" column across the six component maps: 18 + 21 + 25 + 18 + 18 (L1.7 declares none) |
| Units missing a spec | **37** | promised minus written. The ledger names every one; see the breakdown below |
| Contracts | **12** | C-01…C-12 in doc 08, `EvidenceSpan` … `QualifiedEnterpriseSignal` |
| Algorithms | **23** | ALG-01…ALG-23 in MAP D, every one pure, integer-only, no LLM in its call path |
| LLM call sites | **5** | LLM-1 junk gate, LLM-2 semantic extractor (tiered Haiku/Sonnet/Opus), LLM-3 speech-to-text, LLM-4 OCR fallback, LLM-5 ambiguous business relevance. **A sixth is an architectural bug.** |

These are not hand counts. `scripts/unit_ledger.py` parses each group doc's component map and its
unit headings and subtracts the two, per group, naming the missing ids:

```
$ python -m scripts.unit_ledger
LAYER GROUP     COMPNTS   PROMISD   WRITTEN     GAP   ACCEPT
      L1.1            0         —         2       —        2
      L1.2            6        18         9       9        3  !
      L1.3            9        21        13       8        6  !
      L1.4           10        25        15      10       13  !
      L1.5            9        18        13       5        7  !
      L1.6           10        18        13       5        9  !
      L1.7            5         —         0       —        0
L1    TOTAL          49       100        65      37       40
```

**Where the 37 sit, and what that means for scheduling.** The gap is not spread evenly — it
clusters in the components the plan marks "exists":

| Group | Missing | Character |
|---|---|---|
| L1.2 | 9 — **all of** L1.2.1/2.2/2.3 | the three components marked ✅ reuse. Their units were never written because nothing is being built; the risk is a refactor with no spec to regress against |
| L1.3 | 8 — L1.3.1, L1.3.2, L1.3.3, L1.3.7 units + L1.3.6-U2 | same shape: existing, unspecified |
| L1.4 | 10 — L1.4.8 (all 3), L1.4.3-U3/U4, L1.4.9-U2, L1.4.10-U2, L1.4.1-U2, L1.4.2-U3, L1.4.7-U2 | **the real hole.** Batch Planner + Cost Governor has three promised units and zero specs, and it is the component that bounds LLM spend in the wave that turns the LLM on |
| L1.5 | 5 — L1.5.4 (both), L1.5.6-U1, L1.5.7-U2, L1.5.3-U2 | exactly the components §4.3 finds contradictory wave assignments for |
| L1.6 | 5 — L1.6.1-U2, L1.6.3-U2, L1.6.5-U2, L1.6.8-U2, L1.6.9-U2 | second units of new components; each has a first unit that defines the shape |

Also from the ledger: **only 40 of 65 written L1 units carry an `**ACCEPTANCE**` block**, and L1.7's
five components declare no unit column at all. A wave gate cannot be met by units that never said
what "met" means, so writing the missing HOW/ACCEPTANCE for a wave's units belongs *inside* that
wave, before its code — starting with L1.4.8 before W4.

---

## 3. Reuse versus build — all 49 components

The plan is **not** a rewrite. 16 of 49 components already exist and are either kept untouched or
relocated; the shape of the work is 14 fixes and 19 new builds on top of a working capture layer.

| Disposition | Count | Components |
|---|---|---|
| **Reuse as-is** | **13** | L1.2.1 Connector Manager · L1.2.2 Authentication · L1.2.3 Permission Manager (**strong — do not touch**) · L1.3.1 Event Normalizer · L1.3.2 Metadata Extraction · L1.3.3 Content Normalizer · L1.3.7 Deduplication · L1.3.9 Structured Mapper (exists in `capture/structured/registry.py`; the plan formalises it, the mappings stand) · L1.4.7 Prompt Injection Guard (port) · L1.4.8 Batch Planner + Cost Governor (port) · L1.6.6 Domain Mapping (`domain/hints.py`) · L1.7.1 Raw evidence store · L1.7.2 Prepared content store |
| **Move layer** | **3** | L1.4.3 Semantic Extractor (L2 → L1) · L1.4.9 Extraction Cache (L2 → L1) · L1.7.3 Extraction store (`l2_extraction_results` → `l1_extraction_results`) |
| **Fix existing** | **14** | L1.2.4 Incremental Sync (**broken promise**: `sync_runner.py:270-299` documents "FULL history", routes to `newer_than:60d`) · L1.2.5 Webhook Listener (bypasses gate/prepared/parked stores, `routes.py:1549`) · L1.2.6 Polling Scheduler (one global 6h cadence, no per-source rate, no jitter) · L1.3.4 Document Router (3 gaps) · L1.3.6 Thread Reconstructor · L1.3.8 Attachment Resolver (parks `NEEDS_REFETCH`, **nothing refetches**) · L1.4.4 Extraction Schema (widen) · L1.5.4 Entity Canonicalizer · L1.5.6 Schema Validator · L1.5.7 Confidence Composer · L1.5.8 Authority Weighter · L1.6.4 Source Analyzer (`internal_knowledge.py:113` covers `internal_kind` only) · L1.6.8 Qualification Engine (no importance floor — impossible without L1.6.7) · L1.7.5 Coverage store (`source_coverage` written by nothing, read only by the deletion cascade) |
| **Build new** | **19** | L1.3.5 Structural Parser · L1.4.1 Content-Type Router · L1.4.2 Extraction Profile Registry · L1.4.5 Open Lane · L1.4.6 Evidence Binder · L1.4.10 Model Router · L1.5.0 Claim Group Assembler · L1.5.1 Evidence Span Validator · L1.5.2 Date/Time Normalizer · L1.5.3 Currency Normalizer · L1.5.5 Conflict Detector · L1.6.1 Signal Detector · L1.6.2 Signal Normalizer · L1.6.3 Signal Classifier · L1.6.5 Business Relevance (today's `gate/relevance.py` is a *junk* gate — a different job) · L1.6.7 Importance Scoring · L1.6.9 Signal Lifecycle Manager · L1.6.10 Signal Publisher (rewrite: emits QES, not `GatedEvent`) · L1.7.4 Signal store |
| **Contracts** | **12** | C-01…C-12, built first in W0. Integer basis points throughout (`*_bp`, 0..10000); money is integer minor units + ISO code; no float crosses a boundary |

---

## 4. Four sequencing corrections found in review

These are defects in the **build order**, not in the design. Each would have surfaced as a wave
that cannot finish, mid-flight, after its code was written.

### 4.1 G2 asserts `importance_bp`, which W7 builds — move that assertion to G7

Doc 09's G2 (wave **W2**) requires that *"an identical (amount, date, authority) yields an identical
`importance_bp` whether it came from a mapping or from the model."* But `importance_bp` is produced
by L1.6.7 Importance Scoring, built in **W7** — five waves later — and the model-sourced half of the
comparison needs the extractor, built in W4.

**Correction:** G2 keeps the two assertions it can actually make in W2 — zero LLM calls on a
structured fixture, and `field_confidence == 10000` with `verified=True` evidence. The
structured-versus-model parity assertion **moves to G7**, where both inputs exist. Leaving it in G2
means W2 cannot pass on its own terms and the gate gets waived, which is how a gate stops meaning
anything.

### 4.2 L1.5.8 Authority Weighter must move into W1

Doc 09 places the authority weighter in **W5**. But authority rank is an input to things built
earlier: L1.3.9's structured lane stamps **authority rank 4** in W2, and the L1.5.7 Confidence
Composer (W1) composes over it. ALG-14 is a pure lookup table with no dependency beyond the
contracts — the cheapest unit in the group.

**Correction:** build L1.5.8 in **W1** with the rest of the pure validators. A lookup table sitting
in W5 is a W2 blocker wearing a late wave's number.

### 4.3 L1.5.4 and L1.5.8 have contradictory wave assignments

The doc 05 component map assigns **L1.5.4 → W2** and **L1.5.8 → W2**. Doc 09's wave table lists both
the entity canonicalizer and the authority weighter under **W5**. Two files, two answers, and a
coding agent handed the unit id has no way to choose.

**Correction:** authoritative assignment is **L1.5.8 → W1** (per §4.2) and **L1.5.4 → W2** (it is a
rule cascade over deterministic S1 output and does not need the extractor). Doc 09's W5 line should
be amended to read *"Claim group assembler (L1.5.0) + conflict detector"* only. Until doc 09 is
amended, **this file is the tie-breaker.**

### 4.4 L1.3.4-U3 speech-to-text is blocked on an unscheduled connector — descope it

L1.3.4-U3 (LLM-3, audio → diarized text) is marked *"MISSING ENTIRELY"*, and the L1.1 connector
priority list runs P0 HubSpot expansion, P1 Stripe billing, P2 product usage, P3 support desk, P4
Slack. **No audio or meeting-recorder source appears anywhere in it.** The unit would be built,
gated, and then have nothing to run on — and the crosscheck's P-04 already made exactly this correction for
the `transcript` extraction profile, whose golden-corpus coverage was cut for the same reason.

**Correction:** L1.3.4-U3 is **descoped to synthetic fixtures** — the code path and its unit tests
exist so the `transcript` profile has a producer, but it is explicitly **not part of any wave gate**
and joins the gates the day a recorder connector is scheduled. Consistency matters here: the
`transcript` profile and its producer must be in or out together, and they are out.

---

## 5. Database hazards

### 5.1 The `l2_extraction_results` → `l1_extraction_results` rename breaks tenant erasure

L1.7.3 relocates the extraction cache. The table name is referenced in **15 places across 11 files**
today:

```
$ grep -rn "l2_extraction_results" genios_engine/ migrations/ scripts/ docs/ tests/ | grep -v __pycache__ | wc -l
15
$ ... | cut -d: -f1 | sort -u | wc -l
11
```

| File:line | What it does | What breaks on a rename |
|---|---|---|
| **`genios_engine/api/account_routes.py:326`** | membership in `_ORG_SCOPED_TABLES` | **tenant erasure silently stops deleting the cache.** The reset endpoint iterates a hand-written list; a renamed table just is not in it. This is the one that matters — every other reference fails loudly |
| `genios_engine/context/graph_store.py:365,376` | cache read + write | the L2 cache path breaks at runtime |
| `genios_engine/context/runner.py:157` | uncached-event query | the drain re-extracts everything |
| `genios_engine/api/routes.py:1209` | the same query on the API path | as above |
| `migrations/0004_l2_context_graph.sql:181,191` | table + index definition | the rename migration must carry both |
| `migrations/0033_org_data_cascade.sql:53` | `l2_extraction_results_org_cascade_fk` | the cascade constraint must be renamed with the table or account deletion loses its schema-enforced path |
| `scripts/rebuild_graph.py:13,48,115` · `scripts/e2e_verify.py:43` · `scripts/gmail_l1.py:20` · `scripts/verify_ingest.py:32` | maintenance scripts | fail at run time, on production, with a partially applied wipe |
| `docs/plans/IMPLEMENTATION_PROGRAM.md:237` | prose | stale reference |

*(The review that commissioned this build recorded "15 refs across 9 files". The reference count
matches; the file count does not — the census above is the one to work from.)*

**Do the rename as `alter table … rename to …` plus a constraint rename in one migration, and update
`_ORG_SCOPED_TABLES` in the same commit.** A create-and-copy loses the permanence guarantee that
makes replay exact.

### 5.2 Four new tables need erasure entries

L1 v2 introduces `qualified_signals` (L1.7.4), `signal_conflicts` (L1.5.5),
`unclassified_observations` (L1.4.5) and `l1_v2_activation` (the activation ledger). Every one is
org-scoped and holds tenant content.

Two separate obligations, and only one of them is enforced by a test:

1. **`org_id` FK with `ON DELETE CASCADE` to `orgs(id)`** — enforced.
   `tests/test_account_erasure.py::test_every_org_scoped_table_has_a_proven_account_delete_cascade`
   replays every migration in order and fails the moment an org-scoped table lacks a live cascade. A
   new table without one cannot merge.
2. **An entry in `account_routes._ORG_SCOPED_TABLES`** — **not enforced by anything.** That list
   drives the *graph reset* path (wipe learned state, keep the account), which is a different
   operation from account deletion. A new table omitted from it survives a reset and reappears as
   ghost signals against a graph that no longer contains their subjects.

Migration numbering continues from `0077_card_builder_version.sql`. Deletion order in
`_ORG_SCOPED_TABLES` is load-bearing where FKs chain (see the Layer 4 block already in that list) —
`signal_conflicts` and `unclassified_observations` must be deleted before `qualified_signals` if
they reference it.

### 5.3 No maintenance script may resolve its own database (closed 2026-09-05)

`scripts/rebuild_graph.py:107` resolved its engine from `get_settings().database_url`, and
`platform/config.py` loads `.env` — so on a developer machine that expression is the **production**
Supabase URL, feeding a script that backs up, wipes and replays eight projection tables. The five
gate scripts this plan adds (`l1_s1_report`, `extract_golden`, `importance_distribution`,
`l1_end_to_end`, `l1_shadow_diff`) would each have inherited that default.

**Closed by `scripts/_db.py`:** a target must be named (`--database-url` or
`GENIOS_TARGET_DATABASE_URL`), there is no settings fallback, a Supabase host additionally requires
`GENIOS_ALLOW_PROD_WRITE=1`, and the resolved target is printed with credentials redacted before
anything runs. `tests/test_scripts_db_guard.py` holds it — the offender ledger is an exact-equality
set, so a new gate script cannot join it silently.

**Still to migrate:** `rebuild_graph.py` (the one name in the ledger). Also unmigrated, by a
different route — they resolve through `make_graph_store()` or read `GENIOS_DATABASE_URL`
directly, which is the same production default wearing a different spelling:
`corpus_route_probe.py`, `e2e_verify.py`, `finish_l2.py`, `gmail_l1.py`, `graph_quality_probe.py`,
`pause_notion_email.py`, `probe_readonly.py`, `regmail_sync.py`, `restore_reingest.py`,
`verify_ingest.py`, `card_audit.py`, `pause_org.py`, `runtime_receipts.py`, `wipe_org_data.py`.

---

## 6. What must not regress

Every PR in this plan is checked against these. All are things the codebase currently gets right and
a refactor could quietly break.

| # | Must not regress | Where it lives |
|---|---|---|
| 1 | Visibility stamped at source; gate parks `visibility_unknown` | `capture/visibility_rules.py`, `gate/gate.py` S0.6 |
| 2 | MUT-01 versionability check | `gate/rules.py` `content_integrity_rule` |
| 3 | Three distinct dedup jobs (content, message-id, delivery) stay distinct | `l1.content` / `l1.event` / `l5_2.mgmt` |
| 4 | 90-day payload retention on judged drops | `capture/pipeline.py:230-246` |
| 5 | Extraction cache key includes every instruction-changing component | `context/pipeline.py:463-475` |
| 6 | Prompt-injection defense | commit `54e8ca1` |
| 7 | Daily LLM spend circuit breaker | commit `7e17a6d` |
| 8 | Test suite cannot reach production | commits `ae63ef9`, `d860b8e`; now `tests/test_scripts_db_guard.py` for scripts too |
| 9 | Layer import direction | `tests/test_layer_topology.py` |
| 10 | Rules-first, then LLM, in the junk gate | commit `c373a9d` |

---

## 7. Status

| Wave | State |
|---|---|
| W0 contracts | **in progress** — 12 contract objects, integer basis points, no float anywhere |
| W1–W8 | not started |
| W9 connectors | not started (independent; should start immediately) |
| W10 pilot | not started; blocked on G0–G9 |
| DB safety guard (§5.3) | **done** — `scripts/_db.py` + `tests/test_scripts_db_guard.py` |
| Doc 09 amendments (§4) | **not applied to the source plan** — this file is the tie-breaker until they are |
| Missing unit specs (37) | open — write each wave's missing HOW/ACCEPTANCE inside that wave, **L1.4.8 before W4**. `python -m scripts.unit_ledger --check` is the ratchet |
