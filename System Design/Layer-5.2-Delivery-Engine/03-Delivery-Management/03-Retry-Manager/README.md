# Retry Manager

**Engine status:** Built. Live provider behavior and long-outage operations remain integration evidence.

The retry manager gives each due delivery a short database claim, atomically commits quota plus a
`started` physical-attempt fact before every adapter invocation, and applies bounded retry timing.
Admission holds never consume an attempt.

| Input | Output | Authority |
|---|---|---|
| due logical delivery and typed provider outcome | completed attempt, next due time or terminal transport result | `deliver/outbox.py` drain, reservation and finish logic |

## Retry policy

- Backoff ladder: 5 minutes, 30 minutes, 2 hours and 12 hours.
- A provider `Retry-After` may replace the delay only while a ladder slot remains; it cannot create an additional retry slot.
- `retryable_failure`, `terminal_failure`, `unknown` and `delivered` are distinct attempt outcomes.
- Stable provider key: `delivery_id:retry_generation:channel`.
- Definite route fallback or ordinary owner replay starts a new retry generation; ambiguous
  ACK-loss replay preserves the generation-level key so an idempotent receiver can recognize it.

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
