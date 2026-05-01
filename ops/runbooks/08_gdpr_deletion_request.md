# 08 — GDPR deletion request

## Trigger
- Customer emails asking for deletion of their or a subject's data
- Legal forwards a right-to-erasure request
- 72h SLA clock starts on receipt

## Diagnosis
1. Identify the principal: which tenant (`org_id`), which subject (`contact_id`)?
2. If the request is about a subject on a tenant's graph, route it to the tenant — data controllers handle erasure for their data. We're processor.
3. If the request is about the tenant themselves (account wipe), proceed as ours to execute.

## Mitigation

**Always dry-run first.** The script supports it.

```bash
cd genios-brain
python scripts/gdpr_delete.py --org <uuid> --entity <uuid>   # dry-run, prints counts
python scripts/gdpr_delete.py --org <uuid> --entity <uuid> --execute   # actual delete
```

Or via the admin API:
```bash
curl -X POST https://api.genios.ai/v1/admin/delete \
  -H "Authorization: Bearer <admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "<contact_uuid>", "dry_run": false}'
```

What the cascade removes:
- `contact_facts`, `interactions`, `commitments`
- `insights`, `recommendations`, `delivery_attempts`, `context_outcomes`
- `contacts` (the row itself)
- Any matching Redis cache keys (best-effort pattern scan)

What's retained:
- Anonymized `activity_log` entry (counts only, no PII) — proves action was taken
- `llm_usage` rows (aggregate cost accounting; no PII beyond org_id + trace_id)

## Follow-up
- Email confirmation to requester with what was deleted (counts)
- Record the erasure in your legal tracker (outside this repo)
- If the same subject re-enters via a new sync, they'll be re-created — explain this to the controller; they must exclude the subject from their source
- After deletion, if you find stale references to the deleted row elsewhere, fix the missing cascade in next migration
