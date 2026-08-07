# Terminality and illegal moves

Rejected, expired, superseded and rolled_back objects do not re-enter promotion. Published objects
may only be superseded or rolled back. Relearning requires a new immutable proposal with its own
evidence and identity.

No-op or illegal transitions are rejected and cannot be hidden as successful API commands.
