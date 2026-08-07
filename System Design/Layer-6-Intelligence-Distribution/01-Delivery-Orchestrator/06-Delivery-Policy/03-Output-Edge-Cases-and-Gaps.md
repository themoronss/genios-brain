# Output, edge cases and gaps

**Output:** `SEND` or terminal `SUPPRESS` with a stable reason code.

**Edge cases / honest gap:** Policy and timing compose; their order cannot accidentally make the system louder. Configuration write APIs reject values that would silently degrade.
