# Policy validation

Policy updates bound counts, days, basis-point thresholds and TTL; normalize target/prefix sets;
support blocked targets and constrained-visibility review; and keep Knowledge Suggestion as a
non-negotiable human-review target. The configured maximum TTL cannot be below the current 168-hour
default lease.

The owner update locks the current policy, performs a revision compare-and-swap and increments its
revision. Migration 0047's trigger freezes the complete new snapshot in
`learning_policy_revisions`; immutable revision rows cannot be updated. Runs and accepted objects
retain the revision that governed them, while review revalidates against current policy.

Invalid target/state/value combinations return explicit errors; the API cannot invent a publisher.
