# Organization Brain Publisher

**Status:** Publisher built; lower-layer consumer pending

| Target | Durable store | Authority |
|---|---|---|
| `BrainTarget.ORGANIZATION` / `LearningTarget.ORGANIZATION` | `learned_brain_entries` | `feedback/store.py::_publish_brain` |

## Component modules

1. [Promotion and versioning](01-Promotion-and-Versioning.md)
2. [Consumption boundary and gaps](02-Consumption-Boundary-and-Gaps.md)
