# Output, edge cases and gaps

**Output:** `SEND` with an explainable reason, or `DEFER` with a reason and strictly future
`not_before`. Deferral persists `gate_unit`, `gate_reason`, `defer_count` and lifecycle evidence.

**Edge cases and gaps**

- Missing configuration uses protective UTC 21:00–08:00 quiet hours; invalid writes are refused.
- Daylight-saving transitions are handled by searching local wall-clock openings and converting
  each candidate back to UTC.
- Expired presence cannot hold a row forever; a stale `busy_until` is ignored.
- A deferral that outlives execution authority is expired/cancelled before transport.
- Calendar-backed and universal device attention context are not implemented; active client
  presence is the available live signal.
