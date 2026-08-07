← [The Topology Ratchet](04-The-Topology-Ratchet.md) · [Folder map](README.md)

---

# Gaps and the Map

---

## §8 · Gaps

| # | Gap | Detail |
|---|---|---|
| 1 | **`api/routes.py` carries the heartbeat and ~60 endpoints** | `run_maintenance_sweep` is the system's most important function and it lives in a transport module because there is no better home. A `platform/orchestration.py` would be one |
| 2 | **Two copies of pack data live in `api/`** | `_MATURITY`/`_DISPLAY` and `_DEAL_REASON_CODES` |
| 3 | **No admin role check** | Writes take `require_owner`, the strongest boundary available. `org_seats.role` exists; *a shared admin dependency belongs in `platform/auth.py` when one is written, not invented inside a settings router* |
| 4 | **The connection budget is a comment, not a check** | Nothing asserts that `L1_WORKERS + L2_WORKERS + pool_size + overflow < 15`. Three env vars can be raised independently until Supabase starts refusing connections |
| 5 | **The scheduler is single-instance by convention** | Multi-instance is *safe* (dedup + guarded writes) but wasteful, and the only control is an env var somebody has to remember |
| 6 | **CI has no database** | The single largest verification gap in the entire repo, and the first item of every runbook in this folder |

---

---

## §9 · The map

### 9.1 Files

| Package | Files |
|---|---|
| `contracts/` | `source_event`, `gated_event`, `prepared_content`, `trace`, `parked`, `connection`, `events`, `reasoning`, `execution`, `delivery`, `validators` |
| `platform/` | `config`, `wiring`, `db`, `crypto`, `cache`, `canonical`, `identity`, `ids`, `logging`, `auth`, `audit`, `migrate`, `scheduler` |
| `api/` | `main` + 19 route modules |

### 9.2 The env surface

| Variable | Effect |
|---|---|
| `GENIOS_DATABASE_URL` | empty → **in-memory everything** |
| `GENIOS_COMPOSIO_API_KEY` | empty → **fake connector** |
| `GENIOS_ANTHROPIC_API_KEY` | empty → **no LLM; L2 skips extraction** |
| `GENIOS_CRYPTO_KEY` | Fernet key for payloads + connection secrets |
| `GENIOS_REDIS_URL` | empty → `NullCache` |
| `GENIOS_SCHEDULER_ENABLED` · `GENIOS_SYNC_INTERVAL_HOURS` | the heartbeat |
| `GENIOS_L1_WORKERS` · `GENIOS_L2_WORKERS` | concurrency, capped by the 15-connection budget |
| `GENIOS_ENABLE_OCR` · `GENIOS_ENABLE_L1_RELEVANCE` | optional L1 stages |
| `GENIOS_LOG_LEVEL` | logging |

### 9.3 Tests

`test_layer_topology.py` (**the ratchet**) · `test_no_missing_module_deps.py` (the import ratchet)
· `test_sql_references_real_tables.py` · `test_identity_parity.py` · `test_account_erasure.py` ·
`test_source_registry.py`

### 9.4 Scorecard against §1

| Required | Status |
|---|---|
| Boundary types usable by both sides | ✅ `contracts/` imports only `platform` |
| Real vs dev is configuration, never code | ✅ 17 factories, lazy imports, one switch file |
| Transport contains no business logic | ⚠️ mostly — two copies of pack data, and the heartbeat lives here for want of a better home |
| The topology rule is enforced | ✅ a build failure, not a convention |
| One definition of identity | ✅ `platform/identity.py` |
| Migrations immutable and ordered | ✅ checksummed ledger, crash-on-fail at boot |
