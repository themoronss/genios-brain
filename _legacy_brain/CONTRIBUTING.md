# Contributing

## Repository layout

This repo is the source of truth for the GeniOS brain (FastAPI + Celery)
**and** all client SDKs that talk to it. Keeping them together is intentional:
when the API contract changes, every distribution surface must change in the
same PR.

```
genios-brain/
├── app/                        FastAPI service (routes, ingestion, brain, tasks)
├── migrations/                 SQL migrations (numbered, additive-first)
├── tests/                      pytest suite + fixtures
├── sdks/
│   ├── python/                 Python SDK — publishes to PyPI as 'genios'
│   ├── node/                   Node SDK   — publishes to npm as '@genios/sdk'
│   └── mcp/                    MCP server — publishes to npm as '@genios/mcp'
├── docs/
│   ├── product/                PRODUCT_OVERVIEW, SPEC_V3
│   ├── architecture/           SYSTEM_DESIGN, INTELLIGENCE_BUILD_DECISIONS
│   ├── plans/                  build plans, upgrade plans
│   ├── status/                 phase completion + production readiness
│   └── analysis/               MVP analysis, cost analysis
├── PHASE_DEVIATIONS.md         plan-vs-reality (read before phase work)
├── ops/                        runbooks, load tests, legal, audits
├── deploy/                     deploy scripts
└── scripts/
    ├── audit/                  MVP audit harness (audit.py + probes + history)
    └── (rest)                  one-off + ops scripts (see scripts/README)
```

The dashboard (Next.js) lives in a sibling repo `genios-dashboard` because it
deploys on a different cadence.

## Where things go

| Adding... | Goes in |
|---|---|
| New API route | `app/api/routes/<resource>.py`, register in `app/main.py` |
| New Celery task | `app/tasks/<task>.py`, wrapper in `app/celery_app.py` |
| New integration | `app/ingestion/<tool>_connector.py` + `<tool>_bridge.py` |
| Schema change | New file in `migrations/` (additive — see rules below) |
| Public API change | Update route + Python SDK + Node SDK + MCP server in same PR |
| Planning / status doc | `docs/<category>/` |
| Operational doc | `ops/runbooks/` |

## Migration safety (enforced in CI)

Every schema change must be **additive** in the same PR as the code that reads the
new state. Destructive operations happen later, on their own.

### The four rules

1. **Additive in same PR**
   New columns / tables / indexes ship with the code that uses them.

2. **Destructive at least 14 days later**
   `DROP COLUMN`, `DROP TABLE`, `DROP INDEX` require:
   - The column/table to have been unreferenced in code for ≥ 14 days
   - A separate PR with `[approved-drop]` in the commit message

3. **Every migration has a `downgrade`**
   Include a commented-out rollback SQL block in the migration file:
   ```sql
   -- UPGRADE
   ALTER TABLE x ADD COLUMN y ...;

   -- DOWNGRADE (manually run if needed)
   -- ALTER TABLE x DROP COLUMN y;
   ```

4. **Long-running operations are non-blocking**
   - Indexes: `CREATE INDEX CONCURRENTLY`
   - Unique constraints: `CREATE UNIQUE INDEX CONCURRENTLY` then `ALTER TABLE ... ADD CONSTRAINT ... USING INDEX`
   - Backfills in batches (`UPDATE ... WHERE id IN (...) LIMIT 10000`)

### CI enforcement

`.github/workflows/migration_safety.yml` scans the diff. It fails the build when:
- A migration file contains `DROP COLUMN`, `DROP TABLE`, or `DROP INDEX`
- Commit message does NOT contain `[approved-drop]`

To approve an intentional drop:
```
git commit -m "drop unused column x [approved-drop]

Removed 14d ago from app/... (commit abc123). Verified zero readers."
```

### Backfill rules

- Large backfills (>100k rows) must run in batches with `LIMIT`
- Never `UPDATE table SET x = ...` without a `WHERE` clause
- Verify row counts before and after
- Test on a scratch Supabase project first

---

## Code rules

These match the `.claude/CLAUDE.md` conventions but repeated here for contributors:

- Files < 300 lines — split when growing past
- No lazy fixes. Identify root causes.
- No unrequested extras. Add what was asked, nothing more.
- No AI-slop UI (no generic purple gradients, no Inter everywhere).
- No auto-deploy from Claude. User handles all deployments.

---

## Commits

- Subject ≤ 70 chars
- Body: why, not what
- Reference issue / deviation-item when relevant (e.g. `fixes deferred item T`)
