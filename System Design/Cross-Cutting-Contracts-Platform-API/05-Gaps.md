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
| 7 | **Layer 5.2 provider/deployment proof is external** | Migration `0046`, multi-worker contention and real Slack/Teams/webhook ACK-loss behavior need a staging PostgreSQL/provider run; email, APNs/FCM and exact Slack/Teams user targeting require chosen providers/OAuth/client integrations |
| 8 | **No end-to-end `trace_id`** | Atlas v3.1 specifies one identifier minted at Layer 1 and carried to Layer 6. Lineage exists hop by hop (`event_id`, `decision_hash`, `reasoning_run_id`, `context_snapshot_id`, `execution_id`, `evidence_refs`) so the chain is *traversable*, but it is not *queryable* in one predicate. Detail and the cheap fix: [06-Atlas-Envelope-Alignment.md §4](06-Atlas-Envelope-Alignment.md) |
| 9 | **`visibility` is not on the delivery objects** | It is stamped at the source, reaches `ExecutionObject`, and Layer 5.2 re-reads it from the persisted execution — so Rule 10 *is* enforced. But `DeliveryObject`/`DeliveryResult` carry only `execution_id`, so a consumer holding a result alone cannot answer "who could see this?" without a join. Harmless while Layer 6 only aggregates; denormalise **before** any consumer surfaces payload text. [§2](06-Atlas-Envelope-Alignment.md) |
| 10 | **`schema_version` has two shapes** | `int` in Layer 1, namespaced `str` in Layers 5/5.2. Both version correctly; neither is wrong; a generic reader cannot treat them uniformly. Align on the string form at the next breaking bump of either contract, not before. [§3](06-Atlas-Envelope-Alignment.md) |

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
| `GENIOS_CRYPTO_KEY` | Fernet key for payloads, connection secrets and Layer 5.2 channel/agent credentials |
| `GENIOS_REDIS_URL` | empty → `NullCache` |
| `GENIOS_SCHEDULER_ENABLED` · `GENIOS_SYNC_INTERVAL_HOURS` | heavy sync/maintenance heartbeat |
| `GENIOS_DELIVERY_INTERVAL_SECONDS` | minute-scale Layer 5.2 heartbeat |
| `GENIOS_PUBLIC_APP_URL` | HTTPS product origin used in delivery links |
| `GENIOS_L1_WORKERS` · `GENIOS_L2_WORKERS` | concurrency, capped by the 15-connection budget |
| `GENIOS_ENABLE_OCR` · `GENIOS_ENABLE_L1_RELEVANCE` | optional L1 stages |
| `GENIOS_LOG_LEVEL` | logging |

### 9.3 Tests

`test_layer_topology.py` (**the ratchet**) · `test_no_missing_module_deps.py` (the import ratchet)
· `test_sql_references_real_tables.py` · `test_identity_parity.py` · `test_account_erasure.py` ·
`test_source_registry.py` · `test_delivery_control_plane.py` (ExecutionObject-only routing,
lifecycle, priority, isolation, provider outcomes and migration ratchets)

### 9.4 Scorecard against §1

| Required | Status |
|---|---|
| Boundary types usable by both sides | ✅ `contracts/` imports only `platform` |
| Real vs dev is configuration, never code | ✅ 17 factories, lazy imports, one switch file |
| Transport contains no business logic | ⚠️ mostly — two copies of pack data, and the heartbeat lives here for want of a better home |
| The topology rule is enforced | ✅ a build failure, not a convention |
| One definition of identity | ✅ `platform/identity.py` |
| Migrations immutable and ordered | ✅ checksummed ledger, crash-on-fail at boot |
