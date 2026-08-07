# Verification limit

The current post-hardening verification records **50/50 canonical Layer 6 tests**, **144/144
expanded Layer 6 cross-seam tests** and **1,896 full-suite tests passed**. That is executable
repository evidence for deterministic units, contracts, fake-SQL authority and integration
ratchets; it is not evidence that production infrastructure has already been exercised. The full
run has one unrelated Starlette/httpx deprecation warning and no failure.

Still required: apply the normal ledger through 0045, then 0046→0047 to production-equivalent
PostgreSQL, run real multi-connection race tests, validate existing-data backfills/constraints,
connect authorized inbox producers, prove scheduler/retention observability, and activate/test
versioned lower-layer brain-snapshot readers.
Until those checks exist, “published” proves a governed durable row, not downstream product effect.
