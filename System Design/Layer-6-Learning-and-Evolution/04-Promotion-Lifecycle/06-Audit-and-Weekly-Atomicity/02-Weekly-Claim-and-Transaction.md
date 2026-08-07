# Weekly claim and transaction

`learning_runs` claims one tenant/week. The transaction includes expiry, claim, input load,
proposal persistence, transitions, publication and run completion. Crash before commit leaves no
half-published run; retry encounters the same claim law.

Live PostgreSQL multi-replica behavior is still part of deployment proof.
