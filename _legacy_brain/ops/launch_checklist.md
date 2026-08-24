# Launch day — hourly checklist

Follow top-to-bottom. Check off each box before moving on. If a check fails,
**stop and escalate** — do not launch partial.

## -7 days: Freeze
- [ ] Merge freeze declared in team channel
- [ ] Only bug-fix PRs accepted until launch+3
- [ ] Full harness passes: `python scripts/run_harness.py`
- [ ] Full unit tests pass: `pytest tests/`
- [ ] Migration audit: every table holding tenant data has RLS + `org_isolation` policy
- [ ] Secret scan: `pip-audit --strict && (cd sdks/node && npm audit --audit-level=high)`

## -1 day: Dress rehearsal
- [ ] Deploy latest tag to staging; staging smoke-test green
- [ ] Run load tests against staging:
  - [ ] `k6 run pull_api.k6.js` — p95 < 400ms, 0 errors
  - [ ] `k6 run ingest.k6.js` — p95 ingest < 90s
  - [ ] Webhook harness (see `ops/load_tests/webhook.md`) — 0 dead letters
- [ ] Backup drill receipt in `ops/drill_log/` within the last 90 days
- [ ] Pen test report filed in `ops/audits/`, all high/critical findings remediated
- [ ] Legal sign-off letter in `ops/legal/signed/`
- [ ] Status page (when deferred item U unblocks) showing all components green
- [ ] On-call rotation for launch day + 72h confirmed
- [ ] Rollback plan reviewed: "if X breaks, do Y" for top 5 scenarios

## -1 hour: Pre-flight
- [ ] `SELECT NOW(); SELECT COUNT(*) FROM orgs;` — DB reachable, row count sane
- [ ] Redis reachable: `redis-cli PING` → PONG
- [ ] Celery workers healthy: `celery -A app.celery_app inspect ping`
- [ ] Beat scheduler running: check beat process uptime
- [ ] Sentry DSN receiving events (fire a synthetic error)
- [ ] All 3 LLM providers up (Groq, Gemini): run `python scripts/test_groq_connection.py`
- [ ] Cost guardrail sensible: confirm `GENIOS_LLM_DAILY_CAP_USD` matches plan tier

## T+0: Launch
- [ ] Deploy production tag (e.g. `v1.0.0`)
- [ ] Verify `GET /` returns `{"message": "GeniOS Brain running"}`
- [ ] Verify `GET /health` returns 200
- [ ] Watch Sentry for first 5 minutes — should be flat
- [ ] Announce in team channel + public

## T+1h
- [ ] Pull API p95 under load: check Sentry performance / custom metric
- [ ] Webhook success rate > 95% last hour
- [ ] No new Sentry issues of level ERROR
- [ ] Beta tenants' AAR: hit `GET /v1/admin/aar` for each

## T+4h
- [ ] Repeat T+1h checks
- [ ] Celery queue depth normal (no backlog)
- [ ] Redis memory under 60% of Upstash quota
- [ ] Supabase connection count < 80% of quota

## T+24h
- [ ] Repeat T+1h checks
- [ ] Calibration worker (if enabled) ran overnight without error
- [ ] Lifecycle hourly beat ran 24 times, nightly beat once
- [ ] Cost summary: `SELECT SUM(cost_usd) FROM llm_usage WHERE called_at::date = (NOW()-INTERVAL '1 day')::date` — within expected range
- [ ] No GDPR delete requests received (or, if received, acknowledged)

## T+72h (end of launch window)
- [ ] Review all Sentry issues; triage
- [ ] Review `delivery_attempts status='dead'` count (should be 0)
- [ ] Unfreeze non-critical PRs
- [ ] Post-mortem: what worked, what didn't, what to automate before next launch

---

## Emergency rollback

If a SEV-1 is detected in T+0 to T+24h:
1. Revert deploy to previous tag (App Platform: one click to previous deploy)
2. Announce in team channel + public
3. Open SEV-1 incident doc in `ops/incidents/`
4. Follow the matching runbook in `ops/runbooks/`
5. Do NOT attempt hot-fixes under stress — revert first, fix calmly
