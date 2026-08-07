# Part 3 · Contracts and Operations

| Subpart | Authority |
|---|---|
| [Execution Object Contract](01-Execution-Object-Contract/README.md) | `contracts/execution.py` |
| [Persistence and Migration](02-Persistence-and-Migration/README.md) | `execution_store.py`, migration 0041 |
| [API Surface](03-API-Surface/README.md) | `api/executive_routes.py` |
| [LLM and Determinism Policy](04-LLM-and-Determinism-Policy/README.md) | validation/rendering boundary |
| [Tests and Ratchets](05-Tests-and-Ratchets/README.md) | focused tests + topology/schema checks |

These are not extra Executive Units. They are the boundary and operational machinery that lets the
units run without duplicating authority.
