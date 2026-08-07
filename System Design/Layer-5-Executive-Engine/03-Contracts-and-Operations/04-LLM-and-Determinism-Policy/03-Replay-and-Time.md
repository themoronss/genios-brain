# Replay and explicit time

Pure decisions accept evaluation time; they do not hide wall-clock reads. Canonical ordering and
integer calculations make the same input replayable.

Live revalidation is intentionally not replayed against old queue-time context: the audit stores
which current facts produced the later guard verdict.
