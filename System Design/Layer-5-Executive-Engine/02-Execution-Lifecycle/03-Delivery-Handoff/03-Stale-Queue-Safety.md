# Stale queue safety

A reminder can wait through quiet hours or retry backoff while the business subject changes.
Immediately before send, the Executive guard is consulted again. Closed, revoked or reassigned
work is cancelled/rerouted instead of emitting stale copy.

This is the main race boundary between execution intent and transport.
