# Store responsibilities

The store loads policy/batch, claims weekly runs, persists immutable objects, applies guarded
transitions, publishes dynamic targets, queues knowledge review, expires memory and completes the
run.

Pure learning units do not write SQL or choose transaction boundaries.
