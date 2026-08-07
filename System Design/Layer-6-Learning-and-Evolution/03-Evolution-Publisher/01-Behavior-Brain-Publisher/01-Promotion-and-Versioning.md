# Promotion and versioning

Publishes one active version per tenant + brain + actor-scoped subject after validation and the
configured automatic/review path. An advisory transaction lock serializes the subject. Version is
`max(history)+1`, including after rollback; value, confidence and visibility are material state.

A newer row takes its version from maximum history, points to the actual prior active entry,
deactivates that entry and transitions its source LearningObject to `superseded`. A human rollback
deactivates the bad version and safely
restores its verified predecessor when current consent/ACL still allow that restoration.

Publication is invoked only after the legal validation/governance lifecycle. The publisher cannot
accept an arbitrary target or bypass transition audit.
