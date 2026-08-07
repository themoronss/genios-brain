# Store responsibilities

`execution_store.py` is the SQL authority for insert/load, due selection, guarded transitions,
action completion, reminder/escalation recording, coordination projection and outcome persistence.

Pure units do not issue ad-hoc SQL. This keeps state-machine and tenant-scope checks concentrated
at the concurrency boundary.
