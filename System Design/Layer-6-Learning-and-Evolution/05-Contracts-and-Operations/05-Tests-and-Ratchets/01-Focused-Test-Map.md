# Focused test map

The verified canonical command covers 50 tests across `test_learning_atlas.py`,
`test_learning_authority.py` and `test_learning_hardening.py`: 14 Atlas, 3 authority and 33
hardening tests. The expanded Layer 6 cross-seam collection covers 144 tests.

The Atlas + authority tests cover immutable contracts, all ten analysis units plus validation,
governance paths, schema/API wiring, canonical calibration authority and no-Expert publication.
The hardening tests add fail-closed ACLs, `learning.v2`, clock-stable identity, actor-scoped
preference conflict, exact TTL preflight, disabled-consent behavior, tenant expiry, verified
rehydration, review-time revalidation, metrics rollback refusal, predecessor restoration,
ACL-material brain versioning, metric conflict behavior, held re-evaluation, feedback/performance
seams, tenant-root lock ordering, migration invariants and reset/erasure semantics.

Legacy calibration and broader cross-layer behavior participate in the expanded and full repository
suites; the final full suite records 1,896 passing tests.
