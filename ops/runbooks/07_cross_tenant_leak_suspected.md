# 07 — Cross-tenant data leak suspected

## Trigger
- Customer reports seeing another tenant's data
- Anomalous rows in a tenant's response that don't match their domain
- Security scan flag

## Diagnosis

**Treat as SEV-1 until ruled out.**

1. Reproduce with the exact request that triggered it. Capture full response.
2. Confirm `org_id` in the logged response vs. `org_id` in the auth principal.
3. Run T-17 RLS check from harness: `python scripts/run_harness.py` — must pass.
4. Manually check the RLS policy is applied:
   ```sql
   SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public' AND rowsecurity=false;
   ```
   Any table with `rowsecurity=false` that holds tenant data = suspect.
5. Check if any recent migration dropped an RLS policy.

## Mitigation
- If confirmed leak: **disable the compromised endpoint immediately** (FastAPI middleware that 503s the affected route; or scale workers to 0 for that queue).
- Rotate the victim tenant's API key.
- Do NOT delete the evidence — copy the logs to a safe place before doing anything else.
- Notify legal / affected customer per your DPA obligations (72h under GDPR).

## Follow-up
- Root cause: RLS policy missing, or a query using a superuser connection that bypasses RLS
- Every table holding tenant data: `ALTER TABLE x ENABLE ROW LEVEL SECURITY;` + `CREATE POLICY org_isolation ...`
- Add to harness T-17 a specific test for the failure mode you just hit
- Post-mortem and disclosure
