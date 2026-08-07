# Atlas Layer 6 gaps and production runbook

## Remaining gaps

- Controlled consumers/materializers for Organization, Behavior and Adaptive entries.
- Runtime-memory reader/cache with deterministic expiry and fallback; no Redis today.
- Trusted upstream structuring for free-text preference/memory feedback.
- Richer temporal, multi-entity and causal pattern learning.
- Human-owned Git/PR workflow for accepted knowledge suggestions.
- Live PostgreSQL migration, multi-replica claim and production-threshold proof.

## Deployment proof

1. Apply migration 0045.
2. Inspect `/v1/learning/preview` for one tenant before enabling the weekly run.
3. Verify the same UTC week can be claimed only once, including concurrent workers.
4. Confirm weak/noisy/conflicting evidence is held or rejected with reasons.
5. Confirm Organization and Knowledge targets require human review by default.
6. Create a bounded Runtime memory, then prove database-authoritative expiry.
7. Review, publish, supersede and rollback a safe test entry; inspect every transition.
8. Query code and database to confirm no Expert target/write path exists.
9. Keep generic lower-layer consumption disabled until its own contract/tests are shipped.
