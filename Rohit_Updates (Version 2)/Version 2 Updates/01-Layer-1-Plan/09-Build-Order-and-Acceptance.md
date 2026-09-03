# Layer 1 v2 — Build Order and Acceptance Gates

> **Reverse engineering.** Units are built first, in isolation, fully tested. Components
> assemble from green units. Groups assemble from green components. Layer 1 is done when
> every group gate passes.
>
> **A parent is never built before its children are green.**

---

## The ten waves

| Wave | Builds | Depends on | Gate |
|---|---|---|---|
| **W0** | Contracts (doc 08) | — | G0 |
| **W1** | Pure validators: spans, dates, money, confidence | W0 | G1 |
| **W2** | S1: structural parser, thread reconstructor, chunking upgrade, attachment refetch, **structured mapper (L1.3.9)** | W0 | G2 |
| **W3** | **The typed sink**: vocabulary, schema gen, profiles, open lane, evidence binder | W0 | G3 |
| **W4** | **The extractor**: router, model router, injection guard, cache migration, extractor | W3, W2 | G4 |
| **W5** | **Claim group assembler (L1.5.0)** + conflict detector + authority weighter + entity canonicalizer | W1, W4 | G5 |
| **W6** | ESQE detection: detector, normalizer, classifier, source analyzer, relevance, domain | W4, W5 | G6 |
| **W7** | **Importance scoring** + org baseline + qualification floor | W6, W1 | G7 |
| **W8** | Lifecycle + publisher + signal store | W7 | G8 |
| **W9** | Connector fixes: backfill window, webhook parity, cadence/jitter, coverage wiring | independent | G9 |
| **W10** | Pilot activation + L2 cutover | all | G10 |

**W9 is independent** and may run in parallel from day one — it touches no contract and
unblocks the data L1 v2 needs to be worth running.

---

## Dependency graph

```
W0 contracts
 |
 +-- W1 pure validators ------+
 |                            |
 +-- W2 S1 deterministic -----+
 |                            |
 +-- W3 typed sink -----------+
                              |
                        W4 extractor
                              |
                        W5 conflict
                              |
                        W6 ESQE detect
                              |
                        W7 importance  <-- unlocks Layer 4
                              |
                        W8 publish
                              |
                        W10 pilot

W9 connectors ---- (independent, start immediately)
```

---

## Acceptance gates

Each gate is a **command with an expected result**. A wave is not done because the code
exists; it is done because the gate passes. **A skip is not a pass.**

### G0 — Contracts
```
pytest tests/contracts/test_l1_contracts.py -q
pytest tests/test_layer_topology.py -q
grep -rn "float" genios_engine/contracts/signal.py genios_engine/contracts/extraction.py
```
Expected: both suites pass with 0 skips; the grep finds no `float` type annotations.

### G1 — Pure validators
```
pytest tests/capture/validate -q
grep -rn "float(" genios_engine/capture/validate/
grep -rn "datetime.now\|date.today" genios_engine/capture/validate/
grep -rn "LLMClient\|anthropic" genios_engine/capture/validate/
```
Expected: suite passes, 0 skips; **all three greps return nothing.**

### G2 — S1 deterministic extraction
```
pytest tests/capture/structural tests/capture/documents tests/capture/structured -q
python scripts/l1_s1_report.py --org <pilot> --since 30d
```
Expected: 0 attachments stuck in `NEEDS_REFETCH` over 1h; 0 documents with empty text
and no `ocr_failed` marker; 0 structural-token offset round-trip failures.

**Plus the structured-lane assertions (L1.3.9):**
- a HubSpot deal fixture produces an `ExtractionResult` with **zero LLM calls**
- every mapped field carries `field_confidence == 10000` and `verified=True` evidence
- an identical (amount, date, authority) yields an identical `importance_bp` whether it
  came from a mapping or from the model

### G3 — The typed sink
```
pytest tests/capture/semantic -q
pytest tests/capture/semantic/test_import_graph.py -q
```
Expected: passes with 0 skips. The import-graph test must specifically assert:
- `capture/semantic/vocabulary.py` imports nothing from `packs/` or `context/extract/vocab.py`
- nothing under `packs/` or `reason/` imports `capture/semantic/open_lane.py`

### G4 — The extractor
```
pytest tests/capture/semantic/test_extractor.py -q
python scripts/extract_golden.py --set tests/golden/l1/
```
Expected on the 30-message golden corpus:

| Metric | Gate |
|---|---|
| expected commitments detected | >= 90% |
| emitted evidence spans that verify | >= 95% |
| **fabricated amounts** (Money not literally in source) | **0 — hard fail** |
| the doc-04 worked example | passes exactly as specified |
| cache hit on an unchanged re-run | 100%, zero LLM calls |

### G5 — Conflict detection
```
pytest tests/capture/validate/test_claim_group.py tests/capture/validate/test_conflict.py -q
```
Expected: the \$74K-signed vs \$84K-email fixture produces a `Conflict` with **both
claims retained**, `resolved_by_authority`, resolved to \$74K.

**The fixture must present the two claims as SEPARATE EVENTS** — an `email_message` and
its `email_attachment`, linked by `parent_object_id`. That is how the Gmail connector
actually emits them (`composio.py:383`). A fixture that puts both claims in one event
passes for the wrong reason and would hide the defect this gate exists to catch.

### G6 — ESQE detection
```
pytest tests/capture/esqe -q
```
Expected: the doc-04 worked example produces exactly
`{CONTRACT_RENEWAL, DECISION_PENDING, APPROVAL_REQUESTED}`.

### G7 — Importance scoring — **the Layer 4 unlock gate**
```
pytest tests/capture/esqe/test_importance.py -q
python scripts/importance_distribution.py --org <pilot> --since 30d
```
Expected:

| Metric | Gate | Why |
|---|---|---|
| distinct `importance_bp` values | > 50 | if it collapses to a handful, the formula is not deciding |
| p50 / p90 spread | p90 - p50 > 1500 | a flat distribution cannot rank |
| identical input replayed | byte-identical | reproducibility |
| every score has `importance_components` | 100% | explainability |

**This is the most important gate in the plan.** The current failure it fixes is
recorded in `reason/decision_maker.py:243` — *"the formula has never once decided
anything"* — and in `reason/reasoners/priority.py:165-197`, where 193 of 223 signals
previously carried an identical score. A distribution check is the only way to know the
fix actually took.

### G8 — Publication
```
pytest tests/capture/esqe/test_publisher.py -q
python scripts/l1_end_to_end.py --org <pilot> --since 30d
```
Expected: every metric in the doc-06 group acceptance table.

### G9 — Connectors
```
pytest tests/capture/connectors tests/capture/acquire -q
pytest tests/capture/test_webhook_parity.py -q
pytest tests/capture/coverage/test_coverage_wiring.py -q
```
Expected: webhook and poll produce identical rows for the same message; every swept
event carries a non-null `coverage_ready`.

### G10 — Pilot activation
```
python scripts/l1_shadow_diff.py --org <pilot> --days 7
```
Run L1 v2 **alongside** the existing L2 extraction for seven days on one real tenant.
Expected:

| Metric | Gate |
|---|---|
| events processed by both paths | 100% |
| signals L1 v2 found that v1 missed | reviewed, reported |
| signals v1 found that L1 v2 missed | **reviewed and explained — each one** |
| unverified span rate | < 5% |
| LLM cost per 1000 events | within 2x of v1 (the cache makes this achievable) |
| founder-visible regressions | 0 |

Only after G10 does the L2 extraction path get removed.

---

## The activation rule

**No global boolean flags.** Activation is a table:

```sql
create table if not exists l1_v2_activation (
    org_id      text primary key,
    enabled_at  timestamptz not null default now(),
    enabled_by  text not null,
    notes       text
);
```

**Why:** `platform/config.py:110` carries `use_domain_compiler: bool = False`. It is set
in no environment. 152 authored capabilities have therefore never influenced a single
customer-visible recommendation, and the flag reads as a cutover while behaving as a
dry run. Do not build a second one.

**Definition of done for any unit in this plan:**
> The unit is done when its acceptance command passes **against a real tenant with
> `l1_v2_activation` enabled**. "Built but not enabled" is not done.

---

## What must not regress

A checklist for every PR in this plan. These are all things the codebase currently gets
right and that a refactor could quietly break.

| # | Must not regress | Where it lives |
|---|---|---|
| 1 | Visibility stamped at source; gate parks `visibility_unknown` | `capture/visibility_rules.py`, `gate/gate.py` S0.6 |
| 2 | MUT-01 versionability check | `gate/rules.py` `content_integrity_rule` |
| 3 | Three distinct dedup jobs (content, message-id, delivery) stay distinct | `l1.content` / `l1.event` / `l5_2.mgmt` |
| 4 | 90-day payload retention on judged drops | `capture/pipeline.py:230-246` |
| 5 | Extraction cache key includes every instruction-changing component | `context/pipeline.py:463-475` |
| 6 | Prompt-injection defense | commit `54e8ca1` |
| 7 | Daily LLM spend circuit breaker | commit `7e17a6d` |
| 8 | Test suite cannot reach production | commits `ae63ef9`, `d860b8e` |
| 9 | Layer import direction | `tests/test_layer_topology.py` |
| 10 | Rules-first, then LLM, in the junk gate | commit `c373a9d` |

---

## Estimated sequencing

W0–W3 can proceed in parallel across two engineers (contracts + pure validators on one
track, S1 + typed sink on the other). W4 onward is a single critical path. W9 is fully
independent and should start on day one, because an 18-month backfill window and a
working HubSpot expansion change what L1 v2 has to work with.

**The one ordering that must not be violated:** W3 completes before W4 begins. The typed
sink exists before anything fills it. That ordering is the entire lesson of the 268
invented field names.
