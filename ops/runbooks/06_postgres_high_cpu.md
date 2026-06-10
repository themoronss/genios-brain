# 06 — Postgres high CPU

## Trigger
- Supabase dashboard shows CPU > 80% sustained
- Query latency climbing across multiple endpoints
- Pull API 504s alongside slow ingest

## Diagnosis
1. Top offenders: `SELECT query, calls, total_exec_time FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;` (requires `pg_stat_statements` extension)
2. Running-now queries: `SELECT pid, state, wait_event, now()-query_start AS age, left(query, 120) FROM pg_stat_activity WHERE state != 'idle' ORDER BY age DESC LIMIT 10;`
3. Locks: `SELECT l.locktype, l.mode, l.granted, a.query FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE NOT granted;`
4. Index usage: `SELECT relname, idx_scan, seq_scan FROM pg_stat_user_tables ORDER BY seq_scan DESC LIMIT 10;` — high `seq_scan` + low `idx_scan` on big tables = missing index.

## Mitigation
- Kill runaway query: `SELECT pg_cancel_backend(pid);` (soft); `pg_terminate_backend(pid)` (hard)
- If it's a nightly refresh or backfill looping: pause the Celery task
- Scale Supabase instance size if persistent (one click in dashboard, ~30s downtime)
- Vacuum a hot table blocking autovacuum: `VACUUM (ANALYZE, VERBOSE) table_name;`

## Follow-up
- Add the missing index in a new migration (concurrently, per CONTRIBUTING.md)
- Partition hot tables if > 10M rows (`interactions`, `contact_facts`, `llm_usage`)
- Enable `pg_stat_statements` in Supabase if not already (auto-reset needs cron)
