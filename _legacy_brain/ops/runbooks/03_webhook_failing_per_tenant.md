# 03 — Webhooks failing for one tenant

## Trigger
- Spike in `delivery_attempts.status='dead'` rows for one `org_id`
- Customer reports "I'm not getting notifications"
- `webhook_config.consecutive_failures` climbs

## Diagnosis
1. Scope the failure to a tenant: `SELECT org_id, COUNT(*) FROM delivery_attempts WHERE status='dead' AND attempted_at > NOW()-INTERVAL '1 hour' GROUP BY org_id ORDER BY 2 DESC;`
2. Get the failure pattern: `SELECT status_code, error, COUNT(*) FROM delivery_attempts WHERE org_id=:oid AND status IN ('failed','dead') AND attempted_at > NOW()-INTERVAL '24 hours' GROUP BY 1,2 ORDER BY 3 DESC;`
3. Try delivering manually: `curl -X POST <webhook_url> -H "X-Genios-Event: test" -H "Content-Type: application/json" -d '{"test":true}'` — confirm endpoint health from your side.
4. Check webhook URL in `webhook_config.url` — did it change?

## Mitigation
- If 401/403: tenant's endpoint needs a new secret → ask customer to regenerate via dashboard
- If DNS / connect refused: their endpoint is down; pause delivery until they fix (set `is_active=false` or raise retry ceiling)
- If 4xx with body errors: tenant's webhook parser broke on a field we added — check recent schema changes, consider a payload shim
- Retry stuck rows: `UPDATE delivery_attempts SET status='pending', next_attempt_at=NOW() WHERE status='dead' AND org_id=:oid AND attempted_at > NOW()-INTERVAL '2 hours';`

## Follow-up
- Add per-tenant dashboard row showing delivery success rate last 24h
- If many tenants hit the same 4xx → payload change is a breaking change; back it out or add versioning
- Consider auto-emailing tenant when `consecutive_failures > 10`
