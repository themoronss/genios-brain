# Output, edge cases and gaps

**Output:** one `ValidationResult(state, reason_code)` consumed by lifecycle planning. Separate
reason codes preserve why a proposal is waiting or forbidden instead of collapsing all uncertainty
into a single score.

Important edge behavior:

- neutral/unproven outcomes may affect descriptive totals but never confidence support;
- feedback actions outside the positive/negative sets count as neutral/noise, not approval;
- conflicting preference values are retained as competing evidence and raise `conflict_bp`;
- identical sources and timestamps produce the same ID even if previewed or reviewed later; and
- review revalidates freshness and current consent before approving an old proposal.

**Remaining operational requirement:** threshold values need tenant/product calibration from real
production cohorts. Calibration may change a versioned policy revision; it must not bypass source,
ACL or independence invariants.
