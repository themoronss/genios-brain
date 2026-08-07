[← Atlas alignment](09-Atlas-Layer-5.2-Alignment.md) · [Folder map](README.md)

# DeliveryObject and DeliveryResult

Atlas defines a typed input and output for Layer 5.2. The implementation keeps those contracts
without introducing a second mutable delivery store: `delivery_outbox` is both queue and durable
attempt ledger, while `results.py` projects a row into immutable public objects.

## DeliveryObject

`DeliveryObject` contains only materialized delivery intent:

| Field | Authority |
|---|---|
| `delivery_id`, `org_id`, `subject_id` | outbox identity and tenant scope |
| `recipient` | Layer 5/card ownership decision; Layer 5.2 never invents it |
| `channel`, `channel_class` | concrete adapter plus interruption physics |
| `band`, `interrupt` | upstream priority and break-glass eligibility |
| `payload` | already-grounded render; timing/policy units cannot read it |
| `retry_minutes` | adapter registry's bounded transport ladder |
| `created_at`, schema version | audit and stable contract version |

It is deep-frozen. Retry steps must be positive, unique and ordered. Unknown band/channel-class
values fail closed during projection rather than silently entering the gate.

## DeliveryResult

Private outbox implementation states are reduced to a stable lifecycle:

```text
queued · deferred · delivered · suppressed · cancelled · failed
```

`failed_terminal` becomes public `failed`; gate-specific private fields become `reason_code`; the
result carries attempts, deferrals, delivery time and measured transport facts such as latency.
It never adds a recommendation score or business interpretation.

## Why one ledger matters

A separate DeliveryObject/DeliveryResult table would require two writes for every attempt and
could disagree about status after a crash. Projection gives callers typed stability while keeping
claim, retry, gate and adapter success on the same transactional row.

## Read paths

- `GET /api/org/{org}/delivery/results` returns typed results, optionally filtered by channel.
- `GET /api/org/{org}/delivery/results/{id}` returns both object and result for one tenant-owned row.
- `GET /api/org/{org}/delivery/inbox` uses the same projection for pull surfaces.
- Atlas Layer 6 Learning reads the durable row window and builds deterministic `DeliveryFact`s.

Tests cover projection, private-state mapping, deferral counts, retry policy and latency calculation.
