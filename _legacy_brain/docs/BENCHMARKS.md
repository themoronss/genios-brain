# GeniOS Benchmarks

Public methodology for [/v1/benchmarks/scorecard](../app/api/routes/benchmarks.py).

GeniOS is a **proactive context-intelligence API**, not a chatbot or code agent. Generic LLM benchmarks (SWE-bench, GAIA, LoCoMo) measure surfaces we don't have. Instead we publish four numbers that match what the product actually does.

## The four numbers

### 1. Acted Rate (AAR)
- **Definition:** `acted / (acted + dismissed + ignored)` over a 30-day window across all canary orgs.
- **Source:** `recommendations.outcome` column.
- **What it measures:** Of the proactive insights GeniOS surfaced, what fraction did users actually act on. Direct judgment-quality signal.
- **Min N:** 500 labelled outcomes.
- **Per-detector breakdown:** also shipped, suppressed when fewer than 3 distinct orgs (k-anonymity).

### 2. Context Latency (p50 / p95 / p99)
- **Definition:** End-to-end `/v1/context` response time across cold (`fresh`), warm (`redis`), and pre-computed (`precomputed`) paths, plus minimal-fallback (`minimal`).
- **Source:** `context_calls.latency_ms`.
- **SLA:** p95 < 400 ms (hard, enforced by [context.py](../app/api/routes/context.py) with background warm).
- **Min N:** 1,000 calls.

### 3. Faithfulness (proxy v1)
- **Current method:** `groundedness_proxy_v1` — fraction of bundle responses with both a non-null `relationship_stage` and non-zero `confidence` (i.e. not a degraded fallback).
- **Why proxy:** True faithfulness needs labelled `(entity → expected facts)` gold pairs. The fixture set ships in `benchmarks/fixtures/faithfulness_v1.jsonl`; until then the groundedness proxy is reported with the `method` field set explicitly.
- **Min N:** 1,000 calls.

### 4. Calibration ECE
- **Definition:** Sample-weighted Expected Calibration Error across orgs, computed nightly by [calibration.py](../app/brain/calibration.py) via Platt scaling.
- **Source:** `calibration_models.ece`.
- **Target:** ≤ 0.10 (gate threshold is 0.15 — we publish a tighter target).
- **Min N:** 100 outcomes total across orgs with ≥ 20 samples each.

## What we deliberately don't run

| Benchmark | Why we skip |
|---|---|
| SWE-bench | We are not a code agent. |
| GAIA | We are not a web-automation / file-parser agent. |
| LoCoMo / LongMemEval | Conversational long-term memory is not our product surface. Adapting them would mis-state what we measure. |
| MMLU / HellaSwag | Foundation-model evals — irrelevant to the brain layer above any model. |

## Anti-gaming

- **No PII:** scorecard never returns `org_id`, `contact_id`, emails, names, or recommendation titles.
- **k-anonymity:** per-detector rows suppressed when fewer than 3 distinct orgs contribute.
- **Min-N gating:** every metric returns `value: null` with `reason: "insufficient_data"` until threshold met.
- **Versioned:** scorecard ships with `version`, `build_sha`, `generated_at`, and an HMAC `signature`.
- **Public:** the endpoint is unauthenticated, Redis-cached 1 h, ETag-bearing.

## Reproducing

```bash
# Public scorecard (cached)
curl https://api.genios.ai/v1/benchmarks/scorecard

# Methodology
curl https://api.genios.ai/v1/benchmarks/methodology
```

To recompute locally against your own data:

```bash
cd genios-brain
psql $DATABASE_URL -f migrations/083_context_calls_latency.sql
uvicorn app.main:app --reload
curl localhost:8000/v1/benchmarks/scorecard | jq
```

## Roadmap

- **v1.1** — replace groundedness proxy with labelled fixture set (200 entity-fact pairs, hand-verified).
- **v1.2** — add **GeniOS-Bench** differentiator scores: cross-tool reasoning, proactive lead-time, learning-loop closure, stage-transition accuracy. 200 frozen fixtures in `benchmarks/fixtures/genios_bench_v1/`.
- **v1.3** — CI gate: regression > 5% on Tier-1, > 10% per-detector blocks merge. Per-release signed snapshots in `benchmarks/snapshots/`.
- **v1.4** — public reproducibility kit at `genios-bench-reproduce` with hashed fixtures and a one-line `genios-bench reproduce v1.0`.

## Why this approach

A 37 % gap between lab benchmark scores and real-world deployment is the industry norm. We publish numbers from production traffic, gated on minimum sample sizes, with the methodology open. If a number drops, the next 1 h cache cycle reflects it; we don't re-run only when we want to.
