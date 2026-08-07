# Output, edge cases and gaps

**Output:** `SEND` or `DEFER` with reason and next eligible time.

**Edge cases / honest gap:** This unit never converts a timing hold into terminal suppression and never spends a retry attempt. Missing/bad timezone uses the protective fallback.
