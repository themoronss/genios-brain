# Output, edge cases and gaps

**Output:** a grounded delivery context containing timezone, quiet window, channel policy, busy/activity/current-surface state and burst facts.

**Edge cases / honest gap:** A malformed timezone degrades to a protective default in the engine but is rejected on preference write. Stale leases disappear automatically. Automatic trusted publishing from every real client is not built.
