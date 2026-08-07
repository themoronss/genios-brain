# Rules and decision

Preference fields resolve from most-specific seat+channel through tenant defaults. Presence is accepted only when tenant/seat match and its lease has not expired.

The decision path is deterministic and emits a reason that can be stored and explained. A model is
not an alternate policy engine.
