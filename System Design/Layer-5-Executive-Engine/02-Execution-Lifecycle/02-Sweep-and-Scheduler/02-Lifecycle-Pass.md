# Lifecycle pass

The lifecycle pass loads due candidates, revalidates live truth, observes progress, proposes legal
state changes, decides reminders/escalations and collects terminal outcomes.

Due-time SQL is only candidate selection. Every external moment still passes the live guard after
claiming, so a stale queue cannot outrank current reality.
