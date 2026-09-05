# L1.7 — Knowledge Storage

**Group responsibility:** hold the evidence, the extractions and the signals so that
every claim can name its receipt and every decision can be replayed exactly.

**Group law:** *Nothing is a source of truth in a cache. Every derived claim can name
the row it came from.*

---

## Component map

| # | Component | Table | Wave | Status |
|---|---|---|---|---|
| L1.7.1 | Raw evidence store | `payload_store` / object storage | — | ✅ exists |
| L1.7.2 | Prepared content store | `prepared_content` | — | ✅ exists |
| L1.7.3 | **Extraction store** | `l1_extraction_results` | W4 | ↪️ migrate from L2 |
| L1.7.4 | **Signal store** | `qualified_signals` | W8 | 🆕 NEW |
| L1.7.5 | Coverage store | `source_coverage` | W9 | ⚠️ exists, unwired |

Plus two supporting tables introduced by other groups:
`signal_conflicts` (L1.5.5) and `unclassified_observations` (L1.4.5).

---

# L1.7.3 · Extraction store — the replay guarantee

**WHAT** — One permanent row per `(content, prompt_version, schema_version, model,
profile, vocab_fingerprint)`.

**WHY** — This single table is what makes a pipeline containing a language model
**auditable**. The model runs once. Every later stage — and every replay, months later —
reads the stored row. Re-running a March decision does not re-run March's model; it
reads March's extraction.

It is also what makes heavy L1 LLM **affordable**. A deep backfill extracts each
document once, ever. That is the economics that permits an 18-month history window
(L1.2.4-U1) and a T3 model on contracts (L1.4.10).

**Migration**
```sql
alter table l2_extraction_results rename to l1_extraction_results;
alter table l1_extraction_results add column if not exists profile_id text;
alter table l1_extraction_results add column if not exists tier text;
```

**Preserve the existing key discipline.** The current key already includes
`org_id : PROMPT_VERSION : EXTRACTION_SCHEMA_VERSION : model : vocab_fingerprint :
content`, and the code records why every component is there:

> *"the cache stores a parsed result, so a reader that now looks for `roles` would
> otherwise be served a cached payload that never had them — silently, and for exactly
> the messages that already matter most."*

A previous bug let 260 cached extractions survive a prompt fix and hide it completely —
the fix shipped, the numbers did not move, and the conclusion was that the fix had not
worked. **Do not regress this.** `profile_id` joins the key in v2 because the same text
under the `document` profile is a different extraction from the same text under `email`.

**Retention:** permanent. This table is not a cache in the disposable sense; it is the
provenance record. It may be pruned only alongside a tenant deletion cascade.

---

# L1.7.4 · Signal store — NEW

**WHAT** — One row per `QualifiedEnterpriseSignal`.

**WHY** — Today there is no qualified-signal store. `source_events` is a landing ledger:
it records that an object was ingested, not that a business signal was found in it. L2
therefore has no durable set of signals to read, re-read, or replay against.

DDL is in doc 06 (L1.6.10-U2). Key design points:

- `extraction_ref` is a **pointer** into `l1_extraction_results`, not a copy. The
  extraction lives once.
- `importance_components` is stored as JSONB alongside `importance_bp`. *"Why is this an
  8100?"* must be answerable from data, without recomputation.
- `importance_version` is stored so historical scores stay interpretable after a weight
  change.
- Indexed by `(org_id, state, importance_bp desc)` — this is the ranked read L2 and every
  downstream surface actually performs.

---

# L1.7.5 · Coverage store — wire it

`source_coverage` exists from migration `0002` and is written by nothing. See doc 01
(L1.1-U1) for the wiring task and its reverse prompt. It is listed here so the storage
map is complete.

---

## The four storage laws, enforced

| # | Law | How it is enforced |
|---|---|---|
| 1 | Nothing is a source of truth in a cache | no Layer 1 read path may depend on Redis; a flush test asserts correctness survives it |
| 2 | Every derived claim names its row | publication validator V-4: empty `evidence_refs` blocks emit |
| 3 | The extraction cache is permanent and hash-keyed | key includes every component that changes model instructions; test asserts a version bump misses |
| 4 | Drops keep their payload | qualification ledger row carries `payload_ref` + 90d retention |

## Retention and erasure

| Store | Retention | On tenant deletion |
|---|---|---|
| `payload_store` | tenant policy | hard delete |
| `prepared_content` | TTL, purgeable | cascade |
| `l1_extraction_results` | permanent | cascade |
| `qualified_signals` | permanent | cascade |
| `signal_conflicts` | permanent | cascade |
| `unclassified_observations` | rolling 180d unless promoted | cascade |
| `source_coverage` | recomputed each sweep | cascade |

**Every new table in this plan must be added to the existing
`0033_org_data_cascade.sql` pattern.** A table that survives a tenant deletion is a
compliance defect, and it is the kind that is only discovered during an audit.

**ACCEPTANCE**
```
pytest tests/capture/test_tenant_cascade.py -q
# create a tenant, ingest, qualify, delete the tenant
# assert ZERO rows remain in every table named in this document
```
