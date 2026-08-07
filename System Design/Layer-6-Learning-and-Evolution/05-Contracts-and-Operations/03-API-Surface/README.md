# API Surface

Exposes ACL-filtered transparency, scoped review/rollback and owner-only retention, organization
and policy commands. Authenticated tenant identity always comes from `AuthCtx`.

**Primary authority:** `genios_engine/api/learning_routes.py`

## Component modules

1. [Read Endpoints](01-Read-Endpoints.md)
2. [Owner Commands](02-Owner-Commands.md)
3. [Policy Validation](03-Policy-Validation.md)
