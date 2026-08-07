← [Gaps and the map](05-Gaps.md) · [Folder map](README.md)

---

# The Atlas contract envelope — what the code actually carries

**Atlas revision:** v3.1, 8 August 2026 · **Scope:** all seven boundary objects

The Atlas now specifies a four-field **`ContractEnvelope`** that every boundary object must carry,
plus a typed lineage field per object and integer basis points for every score. Three of those
four fields already exist in the code and predate the Atlas text. One does not exist at all.

This page records which is which. It is deliberately blunt: the alignment tables in each layer
folder assert coverage, and coverage claims are only worth anything if the gaps next to them are
stated with the same confidence.

---

## §1 · The envelope, field by field

| Atlas field | Code truth | Verdict |
|---|---|---|
| `org_id` | `SourceEvent`, `GatedEvent`, `ExecutionObject`, `DeliveryObject`, `DeliveryResult`, `LearningObject` and every table. `on delete cascade` to `orgs (id)` | ✅ **complete** — and stronger than the Atlas, because it is enforced in the schema, not only in the type |
| `schema_version` | Present everywhere, but **two shapes**: `int` in Layer 1 (`SourceEvent` v4, `GatedEvent` v3) and `str` in Layers 5/5.2 (`execution.v2`, `delivery-object.v2`, `delivery-result.v2`) | ⚠️ **present, inconsistent** — see §3 |
| `visibility` | `contracts/visibility.py`, four ordered scopes, `narrowest()` and `can_view()`. Carried on `SourceEvent` → `GatedEvent` → `ExecutionObject`. Read by `deliver/orchestrator.py` from the stored execution | ⚠️ **partial** — see §2 |
| `trace_id` | **Does not exist.** `EventTrace` in `contracts/trace.py` is Layer 1 ingestion only (`org_id`, `event_id`, `dedup_key`, stage records). Lineage below Layer 1 is per-hop hashes, not one shared id | ❌ **absent** — see §4 |

---

## §2 · `visibility` stops at the execution

The rule the Atlas calls **Rule 10** — *a derived insight can never reach a wider audience than the
evidence it came from* — is enforced, but not by the outward object carrying the answer.

**What happens today.** `visibility` is stamped once at the source and new `execution.v2` objects
freeze the narrowest selected-evidence ACL. Layer 5.2 re-reads it **from the persisted,
hash-verified execution** at routing time. For a stored v1 object it re-derives the ACL in memory
from the immutable reasoning context; missing lineage fails closed. The audience check therefore
runs against real data and cannot be skipped.

**Where it differs from the Atlas.** `DeliveryObject` and `DeliveryResult` do not carry a
`visibility` field of their own. They carry `execution_id`, and the answer is one join away.

**Is that a bug?** No — it is a defensible normalisation, and arguably safer: a copied field can
drift from its source, a foreign key cannot. But it has one real consequence worth writing down:

> A consumer holding only a `DeliveryResult` cannot answer "who was allowed to see this?" without
> reading the execution. Layer 6 is such a consumer.

Today that is harmless, because Layer 6 aggregates outcomes rather than re-publishing content. It
stops being harmless the moment any consumer of `DeliveryResult` starts surfacing payload text.
**If that changes, denormalise `visibility` onto the delivery objects before shipping it, not
after.**

---

## §3 · `schema_version` has two shapes

Layer 1 uses a monotonic `int`. Layers 5 and 5.2 use a namespaced `str` (`execution.v2` for new
commitments; stored `execution.v1` objects remain hash-compatible).

Both are versioning. Neither is wrong. But a single generic reader — an audit tool, an export, a
replay harness — cannot treat the field uniformly, which is exactly the thing an envelope is
supposed to buy.

**Not worth a migration on its own.** Worth aligning on the string form the next time either
contract takes a breaking version bump, since that is a change the version field is already
signalling.

---

## §4 · There is no end-to-end `trace_id`

This is the one genuine gap, and it is the most useful item on this page.

**What exists.** Lineage is real and, hop by hop, richer than the Atlas asks for:

| Hop | Field(s) in code |
|---|---|
| Raw → gated | `event_id`, `dedup_key`, `EventTrace.records[]` |
| Reasoning → execution | `decision_hash`, `reasoning_run_id`, `candidate_id` |
| Context pinning | `context_snapshot_id`, `config_snapshot_id`, `capability_version`, `capability_snapshot_id` |
| Execution → delivery | `execution_id` on `DeliveryObject` and `DeliveryResult` |
| Delivery → learning | `evidence_refs` on `LearningObject` |

**What does not exist.** A single identifier minted at ingestion and carried unchanged to Layer 6.

**Why the difference matters.** The chain is *traversable* — given a `DeliveryResult` you can walk
back to the originating event by following four joins. It is not *queryable* — you cannot select
every artifact belonging to one causal thread in a single predicate. The Atlas's T.1 trace reads
as one query; in the code it is a graph walk that a person has to know how to perform.

**The cheap version of the fix**, if it is ever wanted: mint `trace_id` in Layer 1 alongside
`event_id`, carry it as an opaque string through the existing envelope-bearing types, and index
it. No existing lineage field is replaced — `trace_id` answers *"what else belongs to this
thread?"* while the hashes keep answering *"is this exactly the thing I think it is?"*. Those are
different questions and both are worth keeping.

Until then: **the Atlas specifies `trace_id`; the engine does not implement it.** Any document that
implies otherwise is wrong.

---

## §5 · The rest of Atlas v3.1, already true

These arrived in the Atlas as fixes and were already how the code worked. They are listed so
nobody re-implements something that exists.

| Atlas v3.1 concept | Code truth | Verdict |
|---|---|---|
| Integer basis points, `_bp` suffix | `priority_bp`, `confidence_bp`, `impact_bp`, `success_probability_bp`, `noise_bp`, `conflict_bp`, `freshness_bp`, `business_value_bp` | ✅ the Atlas was corrected *to match the code*, not the reverse |
| `audience_intent` is semantic, never a route | `AudienceClass` on actions and the communication plan; `channel_id`/`channel_class`/`interrupt` retained as v1/v2 compatibility hints the orchestrator deliberately does not read | ✅ complete — see [LAYER_MAP.md](../../docs/LAYER_MAP.md) |
| `brain_snapshot_id` pins the compile | `capability_snapshot_id` + `config_snapshot_id`; `packs/snapshot.py` | ✅ complete, different name |
| Gate returns `SEND` / `DEFER` / `SUPPRESS`, most restrictive wins | `contracts/delivery.py`; `combine` is an intersection; `DEFER` does not consume a retry attempt | ✅ complete |
| Transactional outbox, at-least-once, idempotent | `deliver/outbox.py`; logical dedupe key with a unique row; migration `0046` | ✅ complete |
| `Cancelled` / `Expired` / `Failed` / `Suppressed` are distinct endings | `DeliveryResultStatus` carries all four plus `deferrals` as its own counter | ✅ complete — the code distinguished them before the Atlas did |
| Reasoning trace persisted and replayable | Migration `0026`; append-only, context payloads TTL'd while hashes survive | ✅ complete — the Atlas previously claimed the opposite |
| No Expert Brain write path | No Expert publisher; `contracts/learning.py` has no `expert` target | ✅ complete |

---

## §6 · What to do with this page

1. When a layer's `Atlas-Alignment.md` claims envelope coverage, it links here rather than
   restating it. One copy, one place to correct.
2. §2 and §4 are **open gaps**, mirrored in [05-Gaps.md](05-Gaps.md). Close them there when they
   close here.
3. If a future Atlas revision changes the envelope again, this page is the first file to update —
   before any layer folder, because every layer folder depends on it.

---

[← Gaps and the map](05-Gaps.md) · [Folder map](README.md) · [System Design index](../README.md)
