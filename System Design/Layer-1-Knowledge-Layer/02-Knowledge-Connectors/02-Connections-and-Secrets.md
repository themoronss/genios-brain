# Connections and Secrets

*Layer 1 · Knowledge Layer · sub-layer 2 — `genios_engine/contracts/connection.py`, `capture/connections/store.py`, `migrations/0002_l1_tables.sql`*

> Where does one startup's identity for one tool live, and what happens to the password inside it?

| | |
|---|---|
| **Files** | [contracts/connection.py](../../../genios_engine/contracts/connection.py) · 25 lines · [connections/store.py](../../../genios_engine/capture/connections/store.py) · 135 lines · [platform/crypto.py](../../../genios_engine/platform/crypto.py) · 24 lines |
| **Table** | `connections` — [0002_l1_tables.sql](../../../migrations/0002_l1_tables.sql), 13 columns, one index |
| **Owns** | per-org, per-source identity · source-specific config · connection status |
| **Sealed fields** | `db_url`, `token`, `password`, `api_key`, `secret` |
| **Cipher** | Fernet (`cryptography`), key = `GENIOS_CRYPTO_KEY` |
| **Marker** | the literal prefix `enc:` |
| **Implementations** | `InMemoryConnectionStore`, `PostgresConnectionStore` |
| **Endpoints** | `POST /api/connections`, `GET /api/connections`, `POST /api/connections/{id}/{action}` |
| **Test** | [tests/test_connections.py](../../../tests/test_connections.py) |

---

## 1 · The `Connection` contract

Twenty-five lines, of which six are the docstring that explains the multi-tenancy model:

```python
class Connection(BaseModel):
    """One connected source for ONE org (tenant). This is the per-startup identity —
    it lives in the DB, not in .env. 30 startups = 30 rows. The Composio API key is
    global (GeniOS's); composio_user_id is this org's label inside Composio (blank for
    non-Composio sources like a client DB). `config` holds source-specific settings
    (e.g. a client DB's db_url / table / watermark) — stored in the capture_scope jsonb."""

    connection_id: str = Field(default_factory=lambda: new_id("con"))
    org_id: str                                  # the startup / tenant (ours)
    provider: str = "google"
    source_type: str = "gmail"
    composio_user_id: str = ""                   # Composio label; blank for DB/other sources
    config: dict[str, Any] = Field(default_factory=dict)   # source-specific (e.g. DB pull)
    status: str = "connected"                    # connected | paused | disconnected
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Why `composio_user_id` is a column and not an env var

**Because there is exactly one Composio API key for the whole engine, and thirty tenants behind it.** The split is stated in three places that all agree:

From [platform/config.py](../../../genios_engine/platform/config.py):

> composio (auth + data delivery) — API key is GLOBAL (GeniOS's, one).
> Per-org composio_user_id lives in the connections table, NOT here.

From the migration:

> One connected source per ORG (tenant). 30 startups = 30 rows. Per-org identity
> (composio_user_id) lives HERE, never in .env. The Composio API key is global.

From `PostgresConnectionStore`:

> Per-org connections in Supabase — the multi-tenant identity table. 30 startups
> = 30 rows; each carries its own composio_user_id (never in .env).

If per-org identity lived in `.env`, then onboarding a tenant would be a deploy, a tenant could not be paused without a restart, and the process would hold every tenant's identity in memory whether or not it was serving them. The consequence is visible in `make_connector_for`, which reads exactly one value from settings and one from the row:

```python
key, uid = s.composio_api_key, connection.composio_user_id
```

The test that pins this is deliberately unsubtle:

```python
def test_many_orgs_each_have_their_own_connection():
    store = InMemoryConnectionStore()
    # 30 startups, each its own org_id + composio_user_id — all in the store, not .env
    for i in range(30):
        store.add(Connection(org_id=f"org_{i}", composio_user_id=f"gmail_user_{i}"))
```

### `config` — the escape hatch, and the one field name that shifts

`config` is the source-specific bag. It is empty for the Composio sources (their identity *is* `composio_user_id`) and required for the client database, where `make_connector_for` reads `cfg["db_url"]`, `cfg["table"]`, `cfg["identity_field"]` and `cfg.get("watermark_col", "updated_at")`.

**On the Python side the field is `config`; in Postgres the column is `capture_scope`.** `_UPSERT` binds `cast(:config as jsonb)` into `capture_scope`, and `_to_conn` reads `row.capture_scope` back into `config=`. Nothing else in the engine knows the column by its Python name, but a hand-written SQL query does need the DB name.

---

## 2 · The `connections` table

```sql
create table if not exists connections (
    connection_id       text primary key,
    org_id              text not null,
    provider            text not null default 'google',
    source_type         text not null default 'gmail',
    composio_user_id    text,                   -- this org's Gmail label in Composio
    ownership_type      text not null default 'workspace',
    external_account_id text,
    granted_scopes      text[] not null default '{}',
    status              text not null default 'connected',
    encrypted_secret_ref text,
    capture_scope       jsonb not null default '{}',
    expires_at          timestamptz,
    created_at          timestamptz not null default now()
);
create index if not exists connections_by_org on connections (org_id, status);
```

| Column | Written by the store? | Notes |
|---|---|---|
| `connection_id` | yes | `new_id("con")` → `con_` + 24 hex |
| `org_id` | yes | the tenant. Indexed with `status` — the shape `list_active` needs |
| `provider` | yes | defaults `'google'`; not used for dispatch (that is `source_type`) |
| `source_type` | yes | **the dispatch key** for `make_connector_for` |
| `composio_user_id` | yes | blank for non-Composio sources |
| `ownership_type` | **no** | always the default `'workspace'` |
| `external_account_id` | **no** | always `NULL` — see below |
| `granted_scopes` | **no** | always `'{}'` |
| `status` | yes | `connected` \| `paused` \| `disconnected` |
| `encrypted_secret_ref` | **no** | always `NULL`; secrets are sealed *inside* `capture_scope` instead |
| `capture_scope` | yes | `Connection.config`, sealed |
| `expires_at` | **no** | always `NULL` — no token-expiry tracking |
| `created_at` | yes | on insert; the upsert does **not** update it |

**Five of the thirteen columns are dead.** `_UPSERT` writes eight, `_COLS` selects eight, and the other five carry only their defaults. That is not purely cosmetic: [api/agent_mgmt_routes.py](../../../genios_engine/api/agent_mgmt_routes.py) reads `external_account_id` in raw SQL to label an org's connected accounts —

```sql
select connection_id, source_type, external_account_id
from connections where org_id=:o and status='connected'
```

— and falls back with `r.external_account_id or r.source_type`. Since nothing ever writes that column, the fallback is the only branch that runs, and every account is labelled with its source type rather than the actual mailbox.

`encrypted_secret_ref` documents the design that was *not* taken: rather than a reference into a separate secret store, secrets are sealed field-by-field inside `capture_scope`. §4.

### The upsert

```sql
on conflict (connection_id) do update set
  composio_user_id = excluded.composio_user_id,
  capture_scope = excluded.capture_scope, status = excluded.status
```

Three mutable columns. `org_id`, `provider` and `source_type` are immutable after insert — re-adding a `Connection` with the same `connection_id` but a different `source_type` silently keeps the original. `add()` is therefore both create and update.

---

## 3 · `ConnectionStore` — the protocol and its two implementations

```python
class ConnectionStore(Protocol):
    def add(self, c: Connection) -> None: ...
    def list_active(self, source_type: str | None = None) -> list[Connection]: ...
    def get(self, connection_id: str) -> Connection | None: ...
    def set_status(self, connection_id: str, status: str) -> None: ...
```

Chosen by `make_connection_store()` in [wiring.py](../../../genios_engine/platform/wiring.py), on one condition:

> Per-org connections. Postgres if DATABASE_URL set (multi-tenant, survives
> restarts), else in-memory.

| | `InMemoryConnectionStore` | `PostgresConnectionStore` |
|---|---|---|
| storage | `dict[str, Connection]` | `connections` table via `get_engine` |
| `add` | overwrite by id | upsert on `connection_id` |
| `list_active` | filter `status == "connected"` | `where status='connected'` (+ optional `and source_type=:st`) |
| `set_status` | mutate in place, **no-op if absent** | `update ... where connection_id=:c` |
| **seals secrets** | **no** | **yes** |
| survives restart | no | yes |

Two consequences worth stating plainly:

- **`list_active` is not org-scoped.** It returns every connected row across every tenant, by design — that is what the cross-org sweep in `POST /api/ingest/all` needs (*"Full auto-sync sweep across EVERY active connection (all orgs)"*). Per-tenant endpoints filter afterwards: `GET /api/connections` does `... for c in _connections.list_active() if c.org_id == org_id`. **The filter is the caller's responsibility, and forgetting it leaks across tenants.**
- **The in-memory store does not seal.** Sealing lives in `PostgresConnectionStore.add`/`_to_conn`, not in the model. A dev run holds `db_url` in clear in process memory — acceptable, since sealing exists to protect *data at rest*, but it means a test against the in-memory store proves nothing about encryption.

`set_status` is what `POST /api/connections/{connection_id}/{action}` drives (pause/resume), and it is why `status` is one of the three mutable columns.

---

## 4 · Secret sealing

### The threat, exactly

From the top of [connections/store.py](../../../genios_engine/capture/connections/store.py):

> Secret fields inside a connection's config (client DB password, OAuth tokens) are ENCRYPTED at
> rest with the engine's Fernet key — a leaked connections table / backup no longer exposes every
> client's production DB password in clear. "enc:" prefix marks a sealed value; unsealed legacy
> values pass through and get sealed on the next write (backward-compatible).

The concrete exposure: a `postgres` connection's `config["db_url"]` is a full DSN —
`postgresql://readonly:S3cr3t@db.acme.internal:5432/prod` — which is a **live credential to a
customer's production database**, held by us. Without sealing, that string sat in clear inside
`capture_scope`, and therefore in every `pg_dump`, every Supabase point-in-time backup, every
`select * from connections` run by anyone with read access to the analytics replica, and every log
line that ever echoed a row.

Sealing closes *disclosure of the table*. It does not close a compromise of the running engine —
the process holds `GENIOS_CRYPTO_KEY` and must, because it has to open the DSN to connect. **The
security property is: `connections` at rest is worthless without a separately-held key.**

### The mechanism

```python
_SECRET_FIELDS = ("db_url", "token", "password", "api_key", "secret")


def _seal_config(config: dict) -> dict:
    key = get_settings().crypto_key
    if not key or not config:
        return config
    out = dict(config)
    for f in _SECRET_FIELDS:
        v = out.get(f)
        if isinstance(v, str) and v and not v.startswith("enc:"):
            out[f] = "enc:" + encrypt(v, key).decode("ascii")
    return out


def _open_config(config: dict) -> dict:
    key = get_settings().crypto_key
    if not key or not config:
        return config
    out = dict(config)
    for f in _SECRET_FIELDS:
        v = out.get(f)
        if isinstance(v, str) and v.startswith("enc:"):
            try:
                out[f] = decrypt(v[4:].encode("ascii"), key)
            except Exception:      # noqa: BLE001 — leave sealed rather than crash on a bad token
                pass
    return out
```

The cipher is Fernet, four lines in [platform/crypto.py](../../../genios_engine/platform/crypto.py) — the same primitive used for `raw_payloads.enc_content`:

```python
@lru_cache
def _fernet(key: str) -> Fernet:
    return Fernet(key.encode())

def encrypt(plaintext: str, key: str) -> bytes:
    """Encrypt raw payload content at rest. key = GENIOS_CRYPTO_KEY (Fernet)."""
    return _fernet(key).encrypt(plaintext.encode())
```

Fernet is AES-128-CBC with an HMAC-SHA256 tag and a random IV per call, base64url-encoded. Two properties follow: the ciphertext is authenticated (a tampered value fails to decrypt rather than decoding to garbage), and it is **non-deterministic** — sealing the same DSN twice produces different strings, so `capture_scope` values are not comparable and cannot be used to detect duplicate credentials.

### Five behaviours, and why each is chosen

| Behaviour | Code | Why |
|---|---|---|
| **Allowlist, not "everything"** | `_SECRET_FIELDS` is a fixed 5-tuple | `table`, `identity_field` and `watermark_col` must stay readable — they are validated as SQL identifiers and are useful in a support query. Sealing them would buy nothing and cost debuggability. |
| **`enc:` prefix as the marker** | `not v.startswith("enc:")` / `v.startswith("enc:")` | Self-describing: a human reading the row knows instantly whether it is sealed. No side table, no version column, no migration to backfill. |
| **Idempotent** | the same prefix check on write | `add()` is an upsert and the API pattern is read-modify-write (`get` → mutate → `add`). Without the check, a round trip would double-encrypt, and the second decrypt would return a string beginning `enc:` — a silent corruption that only appears when the connector tries to open it. |
| **Backward compatible** | `_open_config` only touches prefixed values | Rows written before sealing existed hold clear text. They pass through `_open_config` untouched and are sealed on the next `add()`. No migration was required, and no read path had to distinguish old rows from new. |
| **Fail-open on read** | `except Exception: pass` | A rotated or missing key, or a corrupted value, leaves the field as the literal `enc:gAAAA...` string instead of raising. The comment is explicit: *"leave sealed rather than crash on a bad token"*. |

**Fail-open is the one with a sharp edge, and it is worth being precise about the failure mode.** If the key rotates, `_open_config` returns `config["db_url"] == "enc:gAAAA..."`, and `make_connector_for` hands that to `ClientDatabaseConnector(database_url="enc:gAAAA...")`, where `get_engine` raises on an unparseable URL. The result is a per-connection sync failure logged by `_sync_connection` — *"L1 sync failed for org_id=… connection_id=…"* — rather than a `GET /api/connections` that 500s for the whole tenant. That is the correct trade for a listing endpoint, but the error message a reader gets is about a bad database URL, not about a key mismatch.

**No key means no sealing.** `if not key or not config: return config` — with `GENIOS_CRYPTO_KEY` unset, everything is stored in clear. `get_settings().crypto_key` defaults to `""`, so this is the dev default and, if the variable is ever dropped in production, the failure is silent: new writes go in clear and old sealed rows stop opening.

### Where sealing happens

```mermaid
flowchart LR
    API["POST /api/connections<br/>config with db_url in clear"] --> ADD["PostgresConnectionStore.add"]
    ADD --> SEAL["_seal_config<br/>db_url → enc:gAAAA..."]
    SEAL --> UPS["upsert into connections<br/>capture_scope jsonb"]
    UPS --> TBL[("connections<br/>at rest: sealed")]
    TBL --> SEL["list_active / get"]
    SEL --> TO["_to_conn"]
    TO --> OPEN["_open_config<br/>enc:... → db_url in clear"]
    OPEN --> CONN["Connection in memory"]
    CONN --> MK["make_connector_for<br/>cfg db_url"]
```

Exactly two call sites, and both are inside `PostgresConnectionStore`:

- `add()` → `"config": json.dumps(_seal_config(c.config), default=str)`
- `_to_conn()` → `config=_open_config(cfg or {})`, shared by `list_active` and `get`

A `Connection` object in memory always holds clear values. The sealed form exists only between `json.dumps` and `json.loads`.

---

## 5 · Worked example — a client database connection, round trip

**Step 1 — the tenant registers the source.**

```http
POST /api/connections
Authorization: Bearer <tenant JWT → org_id = org_7>

{
  "source_type": "postgres",
  "composio_user_id": "",
  "config": {
    "db_url": "postgresql://readonly:S3cr3t@db.acme.internal:5432/prod",
    "table": "public.customer_accounts",
    "identity_field": "account_id",
    "watermark_col": "updated_at"
  }
}
```

`add_connection` builds the model — `connection_id = "con_9f31c2a4d5e6b7889a0b1c2d"`, `provider = "google"` (the default, unused for a DB), `status = "connected"` — and calls `_connections.add(conn)`.

**Step 2 — sealing.** `_seal_config` walks `_SECRET_FIELDS`. Only `db_url` is present, is a non-empty `str`, and does not start with `enc:`, so it is replaced. `table`, `identity_field` and `watermark_col` are not in the tuple and pass through untouched.

**Step 3 — the row at rest.**

| Column | Value |
|---|---|
| `connection_id` | `con_9f31c2a4d5e6b7889a0b1c2d` |
| `org_id` | `org_7` |
| `provider` | `google` |
| `source_type` | `postgres` |
| `composio_user_id` | *(empty string)* |
| `status` | `connected` |
| `capture_scope` | `{"db_url": "enc:gAAAAABo9x...Qw==", "table": "public.customer_accounts", "identity_field": "account_id", "watermark_col": "updated_at"}` |
| `ownership_type` / `external_account_id` / `granted_scopes` / `encrypted_secret_ref` / `expires_at` | `workspace` / `NULL` / `{}` / `NULL` / `NULL` |

**A `pg_dump` taken now contains no credential.**

**Step 4 — a sync reads it back.** `POST /api/sync/{connection_id}` → `_connections.get("con_9f31...")` → `_to_conn` → `_open_config` strips `enc:`, decodes ASCII, and `decrypt` returns the DSN. The in-memory `Connection.config["db_url"]` is clear again.

**Step 5 — the connector is built.**

```python
return ClientDatabaseConnector(
    database_url=cfg["db_url"], table=cfg["table"],
    identity_field=cfg["identity_field"],
    watermark_col=cfg.get("watermark_col", "updated_at"), source=st)
```

`__init__` runs `_safe_ident` on all three identifiers — `public.customer_accounts` matches `_IDENT` (one dotted qualifier), `account_id` and `updated_at` match as bare identifiers — and `get_engine` opens the pool. `incremental_changes(since=<watermark>)` then issues:

```sql
select * from public.customer_accounts where updated_at > :since order by updated_at limit :lim
```

Each row becomes a `RawObject` with `object_type="public.customer_accounts"` and
`content_version=str(row["updated_at"])`, which `postgres.customer_accounts.v1` in the structured
registry maps to `product_account.plan` / `.status` / `.seats_used`.

**Step 6 — the tenant pauses the source.** `POST /api/connections/con_9f31.../pause` → `set_status(..., "paused")` → a single `update`. `capture_scope` is not rewritten, so the sealed value is untouched and no re-encryption happens. `list_active` stops returning the row, and the sweep skips it. The test for this is two lines:

```python
def test_paused_connection_excluded():
    store = InMemoryConnectionStore()
    c = Connection(org_id="o", composio_user_id="u", status="paused")
    store.add(c)
    assert store.list_active() == []
```

---

## 6 · Gaps

| Gap | Detail |
|---|---|
| **No key rotation path** | Nothing re-seals under a new key. Rotating `GENIOS_CRYPTO_KEY` orphans every sealed value; `_open_config` silently returns the ciphertext and the failure surfaces as a bad DSN. A re-seal script would be a `get`-then-`add` loop under both keys — it does not exist. |
| **Five dead columns** | `ownership_type`, `external_account_id`, `granted_scopes`, `encrypted_secret_ref`, `expires_at` are never written. `agent_mgmt_routes.py` reads `external_account_id` and always gets `NULL`. |
| **No OAuth token storage or refresh** | Composio holds the tokens; `expires_at` is unused and nothing detects an expired grant. A revoked grant appears as a provider error inside `run_sync`, logged per connection. |
| **`list_active` is global** | Every caller must filter by `org_id` itself. `GET /api/connections` does; a new caller that forgets would cross tenants. |
| **In-memory store does not seal** | Sealing is a `PostgresConnectionStore` behaviour, not a model invariant — no test can assert it without a database. |
| **`config` is unvalidated** | A `postgres` connection missing `db_url` is accepted by `POST /api/connections` and fails later with a `KeyError` inside `make_connector_for`. |
| **`_SECRET_FIELDS` is flat and top-level** | A secret nested one level down (`config["auth"]["password"]`) is not sealed. Today no source nests, but nothing enforces it. |
| **No audit of reads** | Opening a `db_url` is not recorded anywhere. |

---

## 7 · Map

| Thing | Where |
|---|---|
| `Connection` | [contracts/connection.py](../../../genios_engine/contracts/connection.py) |
| `ConnectionStore`, `InMemoryConnectionStore`, `PostgresConnectionStore` | [connections/store.py](../../../genios_engine/capture/connections/store.py) |
| `_SECRET_FIELDS`, `_seal_config`, `_open_config`, `_UPSERT`, `_COLS`, `_to_conn` | same file |
| `encrypt`, `decrypt`, `generate_key` | [platform/crypto.py](../../../genios_engine/platform/crypto.py) |
| `crypto_key`, `composio_api_key`, `use_real_db` | [platform/config.py](../../../genios_engine/platform/config.py) |
| `make_connection_store` | [platform/wiring.py](../../../genios_engine/platform/wiring.py) |
| `new_id("con")` | [platform/ids.py](../../../genios_engine/platform/ids.py) |
| `get_engine` (pool sizing, Supabase caps) | [platform/db.py](../../../genios_engine/platform/db.py) |
| `connections` table | [migrations/0002_l1_tables.sql](../../../migrations/0002_l1_tables.sql) |
| `AddConnection`, `add_connection`, `list_connections`, pause/resume | [api/routes.py](../../../genios_engine/api/routes.py) |
| `external_account_id` reader | [api/agent_mgmt_routes.py](../../../genios_engine/api/agent_mgmt_routes.py) |
| tests | [tests/test_connections.py](../../../tests/test_connections.py) |

---

*Prev: [The Connector Contract](01-The-Connector-Contract.md) · Next: [The Connector Factory](03-The-Connector-Factory.md)*
