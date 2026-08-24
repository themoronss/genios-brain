# Load tests (Phase 6.1)

Three scenarios from the plan. Two tools — pick by what's installed.

## Prereqs
- `GENIOS_BASE_URL` — e.g. `https://api.staging.genios.ai`
- `GENIOS_API_KEY` — an API key for a fixture tenant (NOT prod)
- `ENTITY_NAME` — a contact name that exists in the fixture tenant

Use a staging tenant with synthetic data. Never load-test prod.

## Install
- `k6`: https://k6.io/docs/get-started/installation/ (or `brew install k6`)
- `hey`: `go install github.com/rakyll/hey@latest`

## Scenarios

### Pull API — 500 req/s for 15 min (target p95 < 400ms)
```bash
# k6
k6 run -e URL=$GENIOS_BASE_URL -e KEY=$GENIOS_API_KEY -e ENTITY="$ENTITY_NAME" pull_api.k6.js

# hey (simpler, less granular)
./pull_api.hey.sh
```

### Ingestion — 10K signals/min burst × 5 min
```bash
k6 run -e URL=$GENIOS_BASE_URL -e KEY=$GENIOS_API_KEY ingest.k6.js
```

### Webhook delivery — 1000 concurrent outbound
Tests the brain's webhook sender (requires pointing webhook_config at a
controlled receiver). See `webhook.md` for the harness setup.

## Success criteria

- Pull: p95 < 400ms, p99 < 800ms, 0 errors
- Ingest: 95th percentile per-signal extract < 90s, 0 errors
- Webhook: ≤ 5% retries, 0 dead letters in 5-minute window
