# GeniOS Engine

Fresh, modular backend for the GeniOS intelligence layers. Built **layer-by-layer, tested per stage**, with **per-event traceability** so you can always see what filtered where, how much, and how correctly.

**Design source of truth:** `../docs/rebuild/` — [00-global](../docs/rebuild/00-global.html), [01-layer1](../docs/rebuild/01-layer1.html), [02-layer2](../docs/rebuild/02-layer2.html).

## Setup / Run (fresh clone)

```bash
# 1. Python 3.11 virtualenv
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt        # or requirements-lock.txt for an exact pin

# 2. Config — copy the example and fill secrets (never commit .env)
cp .env.example .env      # then set GENIOS_DATABASE_URL, GENIOS_ANTHROPIC_API_KEY, GENIOS_CRYPTO_KEY, ...

# 3. Apply DB migrations (idempotent) to your Supabase/Postgres
.venv/bin/python -m genios_engine.platform.migrate

# 4. Run the API (http://localhost:8000)
.venv/bin/uvicorn genios_engine.main:app --port 8000 --reload

# tests
.venv/bin/python -m pytest -q
```

**Env vars** (all `GENIOS_` prefixed, read from `.env` — see `genios_engine/platform/config.py`): `DATABASE_URL` (Supabase session-pooler), `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL`, `CRYPTO_KEY` (Fernet), `COMPOSIO_API_KEY`, `JWT_SECRET`, `REDIS_URL` (optional cache), `INTERNAL_TOKEN` (cron endpoints), `COMPOSIO_WEBHOOK_SECRET`, `CORS_ORIGINS`.

## Status — L1 Capture complete (dev), 33 tests green

Runs on fake + in-memory by default; fill `.env` to switch to real Composio + Supabase (no code change). Coverage vs the L1 design doc:

| L1 doc heading | Code | State |
|---|---|---|
| Pipeline / kya karta | `capture/pipeline.py` | ✅ |
| Connectors + SDK | `capture/connectors/` (base · composio · fake) | ✅ |
| OAuth / connection plane | Composio auth + `connections` table | ✅ (auth via Composio) |
| Acquisition (backfill/incremental) | `capture/acquire/sync_runner.py` | ✅ |
| Durable landing · source_event | `contracts/source_event.py` + `landing/` | ✅ |
| Preprocess + PII + offset map | `capture/preprocess/` | ✅ |
| Documents + OCR (Tesseract iface) | `capture/documents/` | ✅ |
| Gate S0–S2 + filter rules (N/W) | `capture/gate/` | ✅ |
| Structured short-circuit + mapping registry | `capture/structured/` | ✅ (data-driven) |
| Client DB source | structured registry (postgres mapping) | ✅ |
| Deterministic pre-classify (domain hints) | `capture/domain/hints.py` | ✅ (LLM is L2) |
| Triage P0–P3 | `capture/triage/` | ✅ |
| gated_event contract | `contracts/gated_event.py` | ✅ |
| Human + agent events | `contracts/events.py` + endpoints | ✅ |
| L1 tables | `migrations/0001` + `0002` | ✅ |
| L1 APIs | `api/routes.py` | ✅ |
| Coverage / readiness | `capture/coverage/` | ✅ |
| Failure/recovery | idempotent dedup, park-not-drop, on-conflict | ◑ poison-quarantine/retries TODO |
| gate_logs persistence to DB | trace built; DB write | ◑ wired next |
| Real integration (Composio+Supabase) | `wiring` + `pg_repository` + `migrate` | ✅ env-driven |

**Then:** fill `.env` → migrate → `/ingest/gmail` on real Gmail. After that, L2.

## Structure

```
genios_engine/
  platform/     config, ids   (+ db, audit, idempotency, outbox — added as needed)
  contracts/    source_event, trace          ← the testable seams / debug core
  capture/  (L1)
    connectors/ base (SourceConnector), composio (behind interface), fake (dev/tests)
    landing/    normalize (raw→source_event), repository (in-memory; Postgres later)
    pipeline.py the spine, fully traced
  api/          routes (health, dev/ingest-sample)
migrations/     0001_initial.sql (Supabase)
tests/          golden tests per stage
```

## Run

```bash
cd genios-engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

uvicorn genios_engine.main:app --reload
#  GET  /health
#  POST /dev/ingest-sample   → fake Gmail event through the landing spine, returns the trace
#                              (call twice: second is dropped as duplicate)

pytest
```

Dev runs with **no live DB or Composio** — in-memory repos and a fake Gmail connector. Set `GENIOS_DATABASE_URL` (Supabase) and apply `migrations/` when wiring real storage.

## Principles

- **Composio behind the `SourceConnector` interface** — auth + data delivery only; our contract, gate, graph, and acquisition orchestration stay ours; swappable for native.
- **Traceability first-class** — every stage records `pass/drop/park + reason_code` per event (`event_trace`), so debugging is a query, not a guess.
- **Fresh DB** (Supabase/Postgres); in-memory repos default so dev/tests run instantly.
- **No LLM in L1** — deterministic gate + triage; the single relevance+extraction call lives in L2.
