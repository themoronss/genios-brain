# Inputs and context

Layer 5 provides integer business priority in basis points. Layer 5.2 maps it once to:

- `critical` at 8,500–10,000;
- `high` at 7,000–8,499;
- `medium` at 4,000–6,999;
- `low` at 2,000–3,999; and
- `background` below 2,000.

The scheduler also reads `next_attempt_at`, creation time, transport/lifecycle state, claim lease,
route retry generation and an explicit evaluation time. Only queued/deferred lifecycle rows whose
transport is due, or whose in-flight claim expired, are eligible.
