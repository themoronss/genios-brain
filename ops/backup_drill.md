# Backup restore drill

Supabase provides Point-in-Time Recovery (PITR) on paid plans. A drill proves we
can actually use it — untested backups are not backups.

## Cadence
Quarterly. First drill: after first public tenant onboarded (otherwise we're
restoring empty DBs, which proves nothing).

## Procedure

### 1. Pick a restore point
- Supabase dashboard → your project → Database → Backups
- Pick a random point 24h in the past
- Note the exact timestamp

### 2. Restore into a scratch project
- Create a NEW Supabase project (free tier is fine for the drill)
- Note its `DATABASE_URL`
- Use Supabase's "Restore to new project" flow pointing at the scratch project
  and the chosen timestamp

### 3. Validate
Run these against the scratch DB:

```sql
-- row counts for core tables
SELECT 'contacts'  AS t, COUNT(*) FROM contacts
UNION ALL SELECT 'interactions', COUNT(*) FROM interactions
UNION ALL SELECT 'contact_facts', COUNT(*) FROM contact_facts
UNION ALL SELECT 'recommendations', COUNT(*) FROM recommendations
UNION ALL SELECT 'llm_usage', COUNT(*) FROM llm_usage;

-- pick a known org and verify its data is intact
SELECT COUNT(*) FROM contacts WHERE org_id = '<known-tenant-id>';
SELECT COUNT(*) FROM interactions WHERE org_id = '<known-tenant-id>';
```

Expected: counts match what you saw in prod at the restore timestamp (± recent
writes in the last minute or two).

### 4. Prove the app boots against the restored DB
- Point a local `DATABASE_URL` at the scratch project
- Run: `cd genios-brain && source venv/bin/activate && python -c "from app.database import engine; from sqlalchemy import text; print(engine.connect().execute(text('SELECT COUNT(*) FROM orgs')).scalar())"`
- Start the API locally, hit `GET /` — should return `{"message": "GeniOS Brain running"}`

### 5. Tear down
- Delete the scratch Supabase project
- Commit a drill receipt to `ops/drill_log/YYYY-MM-DD.md`

## Receipt template

```md
# Backup drill YYYY-MM-DD

- Restore timestamp chosen: YYYY-MM-DDTHH:MM:SSZ
- Scratch project: <name>
- Restore duration: Xm
- Row counts at restore point vs. prod at same time:
  - contacts:       prod=X, restored=Y (diff = Z)
  - interactions:   ...
  - contact_facts:  ...
- App bootstrap test: passed / failed
- Notes:
  - <anything unexpected>

Status: PASS / FAIL
Signed: <engineer>
```

## If the drill fails

- Open a SEV-2 ticket — we have no working recovery path
- Escalate to Supabase support with the restore timestamp and error
- Do not close the drill incident until a successful restore is proven
