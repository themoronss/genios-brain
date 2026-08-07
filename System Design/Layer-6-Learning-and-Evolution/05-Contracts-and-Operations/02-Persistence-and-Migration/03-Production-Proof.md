# Production proof

The implementation and local verification are complete for the repository boundary: 50 canonical
Layer 6 tests, 144 expanded cross-seam tests and 1,896 full-suite tests pass. Migration/source
ratchets cover the v2 projection, policy trigger, ACL sinks, tenant expiry, rejection/evaluation
audit, concurrency order and rollback lineage; the full run has one unrelated Starlette/httpx
deprecation warning.

The remaining work is integration proof, not missing deterministic unit logic:

1. Apply the normal ledger through 0045, Layer 5.2 migration 0046, then Layer 6 hardening 0047 in a
   production-equivalent PostgreSQL environment; validate existing-row backfills plus deferred/
   composite constraints with mixed-version workers quiesced.
2. Exercise real concurrent weekly claims/reclaims, advisory-locked publication, review versus
   policy update, repeated held-object re-evaluation, Candidate non-regression, terminal duplicate
   no-op, rollback versus republish, evaluation FK integrity and tenant expiry. On populated data,
   race reset/full deletion against weekly learning, expiry, policy update, direct memory,
   review/rollback and dashboard/intelligence feedback; prove blocking/rollback without deadlock,
   partial erasure or post-delete child resurrection.
3. Connect authorized upstream producers to `learning_event_inbox` and verify replay/collision,
   ACL, trace and retention behavior with real tenant data.
4. Wire versioned Organization/Behavior/Adaptive brain snapshots into their approved lower-layer
   consumers with explicit snapshot selection, fallback and rollback tests. Today the rows are
   durable and governed but generic brain consumption is not active.
5. Prove scheduler operations, alerting, retention jobs and optional Redis cache invalidation. The
   database remains authoritative; Redis is not required for correctness.

Local/fake-SQL lock-order ratchets prove query shape, not PostgreSQL's real row/advisory/FK wait
graph. Populated PostgreSQL erasure/contention rehearsal remains a deployment integration gate.
