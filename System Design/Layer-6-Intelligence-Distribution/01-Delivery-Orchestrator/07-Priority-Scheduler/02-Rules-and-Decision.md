# Rules and decision

Only due, claimable rows participate. Deferrals move eligibility without consuming attempts; transport failures use bounded exponential backoff.

The decision path is deterministic and emits a reason that can be stored and explained. A model is
not an alternate policy engine.
