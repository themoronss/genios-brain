# Output, edge cases and gaps

**Output:** an auditable final state plus target-specific artifact. Run counters report inserted,
re-evaluated, unchanged, published, held, rejected and preflight-rejected objects separately. Each
actual evaluation records its final sink-level state/reason; a skipped later-state duplicate has no
fabricated evaluation row.

Important edge behavior:

- preflight refusal is recorded without retaining the proposed value;
- a metrics uniqueness conflict becomes `rejected / metric_identity_conflict`, never a false
  publication count;
- metrics and suggestions cannot use dynamic-brain rollback;
- organization review/rollback requires owner authority in addition to a review scope;
- an old reviewed proposal cannot replace a newer active subject value; and
- concurrent publication/review uses row/advisory locks and compare-and-set transitions.

**Remaining integration requirement:** approved learned-brain entries must be consumed through
explicit lower-layer read contracts before they can affect reasoning/execution. Publication is
durable and transparent, but it does not silently wire itself into every consumer.
