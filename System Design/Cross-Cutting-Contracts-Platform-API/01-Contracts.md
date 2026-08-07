← [Cross-Cutting — `contracts/` · `platform/` · `api/`](00-Overview.md) · [Folder map](README.md) · → [platform/ — the composition root](02-Platform.md)

---

# contracts/ — the boundary types

---

## §3 · `contracts/` — the boundary types

### 3.1 · Why they cannot live in either layer

`SourceEvent` is produced by Layer 1 and consumed by Layer 2. If it lived in `capture/`, Layer 2
would import Layer 1 — legal, but it would also mean **Layer 2 could reach into Layer 1's
internals**. If it lived in `context/`, Layer 1 would import Layer 2 — **illegal**.

So it lives in neither. **A contract is the only thing both sides may depend on.**

### 3.2 · The inventory

| File | Crosses | Detailed in |
|---|---|---|
| `source_event.py` | connectors → landing → L2 | [Layer 1](../Layer-1-Knowledge-Layer/00-Overview.md) |
| `gated_event.py` | L1 → L2 | [Layer 1](../Layer-1-Knowledge-Layer/00-Overview.md) |
| `prepared_content.py` | L1 → L2 (the persisted seam) | [Layer 1](../Layer-1-Knowledge-Layer/00-Overview.md) |
| `trace.py` · `parked.py` | L1 internals + the review queue | [Layer 1](../Layer-1-Knowledge-Layer/00-Overview.md) |
| `connection.py` | per-org source identity | [Layer 1](../Layer-1-Knowledge-Layer/00-Overview.md) |
| `events.py` | human + agent events | [Layer 1](../Layer-1-Knowledge-Layer/00-Overview.md) |
| `reasoning.py` | L3 → L4 → L5 (22 types) | [Layer 4 · 01](../Layer-4-Reasoning-Engine/_reference/Contracts-and-Dataflow.md) |
| `execution.py` | L5 → L5.2 (the Execution Object) | [Layer 5](../Layer-5-Executive-Engine/00-Overview.md) |
| `delivery.py` | L5.2's immutable `DeliveryObject`, stable `DeliveryResult`, lifecycle vocabulary and admission decisions | [Layer 5.2](../Layer-5.2-Delivery-Engine/00-Overview.md) |
| `validators.py` | shared field guards | below |

### 3.3 · `validators.py` — one definition of "valid"

```python
require_aware · require_bool · require_bp · require_enum · require_hash64
require_identifier · require_non_negative · require_ordinal · require_sorted_unique
require_text · freeze_mapping
```

Used by `execution.py` and `delivery.py` at construction. Three of them do real work:

- **`require_bp`** — 0–10,000, integer, **`bool` rejected**. The type system cannot express "basis
  points"; this function is the type.
- **`require_sorted_unique`** — a tuple that is sorted and deduplicated, *or the object refuses to
  exist*. Ordering that must be total cannot be left to the caller.
- **`freeze_mapping`** — `MappingProxyType` over a copy. **A frozen dataclass holding a mutable
  dict is not frozen.**

### 3.4 · The pattern every contract shares

| Property | Mechanism |
|---|---|
| immutable | `@dataclass(frozen=True, slots=True)` |
| content-addressed | `semantic_hash` / `stable_id` over `to_semantic_dict()` |
| validated at construction | `__post_init__` raising, never a separate `validate()` call |
| integer-only | floats rejected by `platform.canonical` |
| rehydratable | `from_semantic_dict()` + `verify_round_trip()` |

> An object that can be constructed invalid **will** be constructed invalid, somewhere, at 3am.

### 3.5 · The Layer 5 → 5.2 → 6 boundary

`ExecutionObject` is the only active input that can authorize a new outward delivery. Layer 5
owns the commitment and work owner; Layer 5.2 turns that frozen object into one deduplicated
`DeliveryObject`, then projects transport and engagement evidence as `DeliveryResult`. Layer 6
consumes that result's measured timestamps (`delivered`, `viewed`, `ignored`, `accepted`,
`executed`) instead of inferring engagement from a mutable transport status.

The v2 delivery contract includes execution lineage, audience/recipient, destination, channel,
format, five-class delivery priority, snapshotted daily attention budget, route ladder, retry
policy and stable lifecycle timestamps. These are deterministic fields; an LLM may rewrite
grounded copy, but cannot choose their values.

---
