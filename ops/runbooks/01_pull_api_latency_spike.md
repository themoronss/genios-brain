# 01 — Pull API latency spike

## Trigger
- p95 on `POST /v1/context` > 400ms for > 5 min
- Users report slow agent responses
- Sentry shows `BUILD_FAILED` 504s

## Diagnosis
1. Check if `meta.degraded=true` is being returned — deadline guard firing means the
   builder is slow, not a crash.
2. Look at recent DB queries — `SELECT pid, query, now()-query_start AS age FROM pg_stat_activity WHERE state='active' ORDER BY age DESC LIMIT 10;`
3. Check Redis cache hit rate — `redis-cli INFO stats | grep keyspace_hits` vs misses.
   If cache miss rate jumped, something invalidated bulk of keys.
4. Check Groq / Gemini provider status pages.
5. Look at llm_usage for the last hour: `SELECT purpose, AVG(latency_ms), MAX(latency_ms) FROM llm_usage WHERE called_at > NOW() - INTERVAL '1 hour' GROUP BY purpose;`

## Mitigation
- If LLM latency → flip offending `purpose` to a faster model in `app/llm/client.py` ROUTES temporarily
- If DB queries → kill the slow query (`SELECT pg_cancel_backend(pid);`) and identify missing index
- If cache cold → pre-warm by calling Pull API for top 100 contacts per tenant
- Emergency: raise `GENIOS_PULL_DEADLINE_MS` to 800 temporarily to stop 504s (users get partial data but a response)

## Follow-up
- Add missing DB index in a new migration (additive; follow CONTRIBUTING.md)
- If provider flapping → add retry-with-fallback in `llm_client.call()`
- Post-mortem: log what changed in the 30 min before the spike (deploy? traffic? data backfill?)
