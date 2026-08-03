# 02 — LLM quota / cost exhausted

## Trigger
- `TenantCostGuardrailExceeded` exceptions in Sentry
- Groq returning 429 `rate_limit_exceeded`
- `llm_usage.cost_usd` sum for an org hit `GENIOS_LLM_DAILY_CAP_USD` (default $50)

## Diagnosis
1. Which org: `SELECT org_id, SUM(cost_usd) FROM llm_usage WHERE called_at::date = CURRENT_DATE GROUP BY org_id ORDER BY 2 DESC LIMIT 10;`
2. Which purpose: add `, purpose` to the GROUP BY — find if one pipeline is burning tokens.
3. If Groq 429: check rate limit dashboard, current RPM usage.

## Mitigation
- If one org's guardrail is legitimate traffic: raise `GENIOS_LLM_DAILY_CAP_USD` for that tenant (future: per-tenant override; for now, env var affects all)
- If runaway loop: look for a contact being re-extracted repeatedly. Check `interactions.processed_version` for weird patterns.
- If Groq 429 global: flip problem `purpose` in ROUTES to Gemini temporarily (`purpose="extract_entities"` → Gemini has different quota).
- As last resort: stop the Celery `extract_pending` beat until quota resets.

## Follow-up
- If tenant legitimately exceeds cap, make cap per-plan-tier (product decision)
- Add Sentry alert on `TenantCostGuardrailExceeded` count > N/hour
- Investigate retry/loop bugs that caused token burn
