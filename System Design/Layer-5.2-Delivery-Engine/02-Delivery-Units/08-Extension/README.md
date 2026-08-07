# 8 · Extension Delivery

**Status:** Engine-ready; extension pull/presence route active; client not included

Provides an `extension` pull channel and short-lived presence seam for browser, email-editor and
CRM overlays.

| Boundary | Current truth |
|---|---|
| Runtime | `channels/surface.py`, presence and inbox APIs |
| Active route | authenticated `extension` pull surface |
| Result | durable availability plus explicit extension lifecycle receipts |
| Business outcome | never inferred from transport alone |
| Integration | installed browser/CRM/email extension and permission lifecycle |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
