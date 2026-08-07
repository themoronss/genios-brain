[← Folder map](README.md)

# Storage, API and scheduler

## Tables

| Table | Authority |
|---|---|
| `learning_policies` | tenant thresholds, review targets and TTL ceiling |
| `learning_runs` | one atomic organization claim per UTC week and its result |
| `learning_objects` | immutable payload hash + current lifecycle projection |
| `learning_transitions` | append-only state audit |
| `learned_brain_entries` | versioned Organization/Behavior/Adaptive state |
| `temporary_memories` | runtime context and authoritative expiry |
| `knowledge_suggestions` | pending/approved/rejected human review |
| `learning_metrics` | bounded-window metrics |

Every table is directly organization-scoped with `ON DELETE CASCADE`. The account-erasure test
discovers org-scoped tables from migrations and fails if any one lacks a schema-enforced path.

## Endpoints

| Method + path | Purpose |
|---|---|
| `GET /v1/learning/overview` | lifecycle counts, active brain counts, review/memory counts |
| `GET /v1/learning/objects` | filterable object and evidence history |
| `GET /v1/learning/brains` | active values or version history; never Expert |
| `GET /v1/learning/suggestions` | human knowledge-review queue |
| `GET /v1/learning/memories` | active TTL context or history |
| `GET /v1/learning/preview` | read-only exact plan under current policy |
| `POST /v1/learning/memories` | owner creates explicit leased context |
| `POST /v1/learning/objects/{id}/review` | owner approves/rejects a governed object |
| `POST /v1/learning/objects/{id}/rollback` | owner rolls back published dynamic state |
| `GET/PUT /v1/learning/policy` | inspect/replace enterprise governance controls |

Mutation uses the existing owner authority. Organization identity comes from credentials, never a
caller-supplied query parameter.

## Scheduler order

The maintenance heartbeat performs distribution, then exact-lineage calibration, then broader
Learning & Evolution, then graph maintenance. Each organization is isolated by an exception guard.
The heartbeat survives one tenant or one subsystem failing. A database claim—not process memory—
prevents a second evolution run in the same week.

## Verification

- `test_learning_atlas.py`: immutable contract, no Expert target, TTL, lifecycle, all units,
  outcome taxonomy, governance, schema and wiring.
- `test_learning_authority.py`: authoritative historical card lineage.
- `test_sql_references_real_tables.py`: every SQL table and inserted column exists in migrations.
- `test_account_erasure.py`: every org table cascades.
- `test_layer_topology.py`: lower packages cannot import learning upward.
