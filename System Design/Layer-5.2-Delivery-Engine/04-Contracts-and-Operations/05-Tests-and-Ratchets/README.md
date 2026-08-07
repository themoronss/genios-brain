# Tests and Ratchets

Captures the automated evidence that keeps Delivery Engine contracts, routing, lifecycle, API authority and Layer 6 handoff from drifting. It also states where the suite uses fakes or source-level assertions and therefore cannot be treated as deployment proof.

**Primary authority:** delivery-focused tests, topology/schema ratchets

## Verified working-tree snapshot — 2026-08-08

| Collection | Result |
|---|---|
| Full repository suite | 1,861 passed, 1 third-party deprecation warning |
| Delivery/agent/executive-bridge focused files | 217 passed, same warning |
| Selected topology/schema/auth ratchets | 59 passed |

The warning is Starlette's `TestClient` compatibility notice for the installed `httpx`; it is not
a Delivery Engine assertion failure.

## Component modules

1. [Focused Test Map](01-Focused-Test-Map.md)
2. [Architecture and Schema Ratchets](02-Architecture-and-Schema-Ratchets.md)
3. [Verification Limit](03-Verification-Limit.md)
