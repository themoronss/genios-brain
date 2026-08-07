← [contracts/ — the boundary types](01-Contracts.md) · [Folder map](README.md) · → [api/ — the transport surface](03-API-and-The-Heartbeat.md)

---

# platform/ — the composition root

---

## §4 · `platform/` — the composition root

### 4.1 · `config.py` — real vs dev is a `.env` line

```python
class Settings(BaseSettings):
    """Typed settings from env (GENIOS_* prefix) / .env file.

    Empty DATABASE_URL  → in-memory repos (dev).
    Empty COMPOSIO keys → fake connector (dev).
    Fill .env to switch either to real, with no code change."""
```

Derived predicates — `use_real_db`, `use_real_composio`, `use_real_llm` — are the *only* thing the
rest of the codebase branches on. **No module asks "is this production?"**

### 4.2 · `wiring.py` — the switch, in one file

Every `make_*` factory follows one shape:

```python
def make_X():
    s = get_settings()
    if s.use_real_db:
        from ... import PostgresX
        return PostgresX(s.database_url)
    from ... import InMemoryX
    return InMemoryX()
```

Seventeen of them: repo · connection store · cursor store · parked store · payload store ·
prepared store · trace repo · document job store · agent registry · human/agent event stores ·
LLM client · graph store · card store · pack registry · relevance classifier · connector factory.

Two properties fall out:

- **Imports are lazy, inside the branch.** A dev run never imports `psycopg`; a test never imports
  `composio`. *The dependency graph is a function of configuration.*
- **This is the only file that knows both halves.** A layer receives a `SourceEventRepository`; it
  never learns whether that is Postgres or a dict.

`IMPLEMENTED_SOURCE_TYPES`, `DIRECT_SOURCE_TYPES` and `COMPOSIO_SOURCE_TYPES` are exported **as
data** so a test can compare the dispatch against the source registry
([Layer 1 §3](../Layer-1-Knowledge-Layer/00-Overview.md)).

### 4.3 · `db.py` — one engine, and a hard connection budget

```python
@lru_cache
def get_engine(database_url: str) -> Engine
```

Two production facts encoded here:

- **URI normalisation** — `postgres://` and `postgresql://` both become `postgresql+psycopg://`.
  *Supabase hands out one shape and SQLAlchemy wants another.*
- **The connection budget:**

> Supabase's **session** pooler caps this project at **15 concurrent client connections** (FATAL
> `EMAXCONNSESSION` beyond that). Every app connection holds one slot, so **the whole engine must
> stay comfortably under 15** — the old `pool_size=12 + overflow=8 = 20` blew past it.

That single cap is why `GENIOS_L1_WORKERS` and `GENIOS_L2_WORKERS` both default to **3**
([Layer 1 §3 P4](../Layer-1-Knowledge-Layer/00-Overview.md), [Layer 2 §3.9](../Layer-2-Context-Intelligence/00-Overview.md)).
**Three limits, one root cause, documented in all three places.**

`pool_pre_ping` survives Supabase idle-connection drops.

### 4.4 · `crypto.py` — 20 lines, two call sites

Fernet symmetric encryption, `lru_cache`d per key. Used for **raw payload content at rest**
(Layer 1's 30-day store) and **secret fields inside a connection config** (`db_url`, `token`,
`password`, `api_key`, `secret`).

### 4.5 · `identity.py` — ONE definition, imported downward

> Identity is the substrate of cross-intelligence: **the same human arriving via gmail (sender),
> calendar (attendee), CRM (contact) and a typed note must converge on ONE node**, or every
> cross-tool rule reasons about strangers.
>
> That only holds if every writer computes the **same** canonical key — **and it didn't:** the
> structured lane lowercased only, while the extraction pipeline also stripped `+tags`, so
> `priya+cal@x.com` (calendar) and `priya@x.com` (email) became **two people.**

| Function | Produces |
|---|---|
| `norm_email` | lowercase, `+tag` stripped — **the person key** |
| `domain_root` | `acme.io` → `acme` |
| `company_slug` | strips legal-form tokens (`inc`, `llc`, `ltd`, `pvt`, `limited`, …), punctuation and case |
| `person_name_key` | a comparison key for an observed name — **never an anchor** |

> Deterministic, no fuzz: **exact key equality is the ONLY auto-merge.** Name similarity is a
> candidate finder, never a merge authority.

The fuzziness lives in **derivation**, never in **comparison** — the same rule Layer 2's entity
resolution obeys ([Layer 2 §3.2](../Layer-2-Context-Intelligence/00-Overview.md)), and it is enforceable
precisely because there is one implementation.

### 4.6 · `canonical.py` — determinism for everyone

Lives here rather than in `reason/` because it is a **generic determinism utility with no
reasoning in it**, and `contracts/` needs it too — and `contracts/` may import nothing above
`platform`. Detailed in
[Layer 4 · 01](../Layer-4-Reasoning-Engine/_reference/Contracts-and-Dataflow.md).

### 4.7 · `migrate.py` — a checksummed, immutable ledger

```sql
create table if not exists schema_migrations (
    filename text primary key,
    checksum text not null,
    ...
)
```

> Before this existed, **every `*.sql` re-ran on every invocation**, so correctness silently
> depended on **every statement being idempotent forever** — and one non-idempotent statement
> **aborted every later statement in its file** (one transaction per file).

Two rules follow, stated in every runbook in this folder:

- **Migrations are immutable.** Editing an applied file changes its checksum and **the runner
  refuses, by design.**
- **Ship the next number, never edit in place.**

The app migrates at boot and **crashes loudly** if a migration fails. *A silent partial migration
is how a column goes missing and a feature reads `None` forever.*

### 4.8 · `auth.py` — two credential families, one server-side answer

> **BOTH resolve `org_id` server-side.** Stdlib-only — no PyJWT, no passlib, no bcrypt.

| Credential | For | Dependency |
|---|---|---|
| Bearer session token | dashboard users | `get_current_org` |
| API key | agents and integrations | `get_current_org` |
| `x-internal-token` | cross-org cron | `require_internal` |
| owner check | destructive settings | `require_owner` |

**`org_id` is never taken from the request body or a path parameter.** Layer 1's `/ingest/all` is
internal-only *so a tenant cannot trigger a cross-org run or learn which orgs exist.*

### 4.9 · `cache.py` — an accelerator, never a dependency

```python
class NullCache:
    """Used when Redis is unconfigured. Every op is a safe no-op / miss."""
```

Four rules, stated in the module:

1. **No `REDIS_URL` → `NullCache`** — tests and local runs never break.
2. **Fail-open** — any Redis error degrades to a miss, never breaks a request.
3. **Cache only — never a queue broker** (the Upstash quota law).
4. **Keys are org-scoped by construction** (`okey` / `l2key`) — *this is the fix for the
   cross-tenant L2 extraction-cache leak.*

### 4.10 · `logging.py` — because there was none

> The engine had **ZERO** application logging (one stray `print`), so **every background failure
> was invisible.** This gives an on-call a real log stream.

### 4.11 · `audit.py` — append-only, and never fatal

> `record()` is a side effect — **it NEVER raises into the caller: a failed audit write must not
> break the action it's auditing.**

**Refs and counts only, no content.** An audit trail that stored payloads would become a second
copy of the data Layer 1 works so hard to TTL.

### 4.12 · `scheduler.py` — one thread, no broker

Detailed in [Layer 1 §3 P14](../Layer-1-Knowledge-Layer/00-Overview.md). *A plain thread plus the database,
honouring the no-periodic-broker rule.*

---
