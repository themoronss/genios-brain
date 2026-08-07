# Weekly claim and transaction

`learning_runs` claims one tenant/week and binds the immutable policy revision used. The main run
transaction includes the claim, trusted input load, sanitized input rejections, proposal preflight,
accepted proposal persistence or held-object re-evaluation, evaluation-ledger append, transitions,
publication and completion. Crash before commit leaves no half-published main run or detached
evaluation verdict.

The run has a unique
`(org_id, run_id, policy_key, policy_revision, evaluation_time)` identity. Each retained evaluation
references that exact tuple and the same-tenant LearningObject. The evaluation primary key
`(org_id, run_id, learning_id)` makes one decision row per object/run. A later week can re-evaluate
the same object only from Observed/Candidate; it uses the new run's policy/time while keeping
evidence identity fixed.

Retention expiry is intentionally a separate earlier transaction. A claimed main run that fails is
recorded in a separate sanitized failure update containing an error class, not source content.
Failed claims can be reclaimed with an incremented attempt count; completed claims remain
idempotent.

The transaction design and fake-SQL ratchets are implemented. Applying the ledger through 0045,
then Layer 5.2 migration 0046 and Layer 6 hardening 0047, plus exercising multi-replica claim,
advisory-lock publication, review/rollback races, tenant expiry and reset/delete contention on a
populated production-equivalent PostgreSQL database remain deployment integration proof.
