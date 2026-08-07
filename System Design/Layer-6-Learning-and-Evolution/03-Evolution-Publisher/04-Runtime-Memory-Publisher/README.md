# Runtime Memory Publisher

**Status:** Durable TTL publisher built; runtime consumer/cache pending

| Target | Durable store | Authority |
|---|---|---|
| `BrainTarget.RUNTIME` / `LearningTarget.RUNTIME` | `temporary_memories` | `feedback/store.py::publish` |

## Component modules

1. [Promotion and versioning](01-Promotion-and-Versioning.md)
2. [Consumption boundary and gaps](02-Consumption-Boundary-and-Gaps.md)
