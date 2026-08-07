# Authority and action races

Owner-only commands are enforced at the API and again in the store. Action completion rechecks the
current assignee and dependency state in the write path. Stale clients cannot bypass the state
machine by submitting an older view.

Reassignment is an event plus routing update; it does not produce a new execution identity.
