# Authorization and errors

Tenant identity comes from authenticated context, not arbitrary payload fields. Owner-only
operational commands use explicit role checks; execution-owner checks are repeated at the store
boundary.

Invalid state, authority, dependency and missing-resource conditions remain distinct errors rather
than generic success/no-op responses.
