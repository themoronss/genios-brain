# Destination Router

**Status:** Built

Selects a stable primary and ordered fallbacks from tenant-registered destinations supported by known adapters.

| Boundary | Current truth |
|---|---|
| Input | authorized recipient, channel intent and registered destination records |
| Output | a primary `Destination` plus bounded fallback sequence |
| Authority | `deliver/destination.py`, `deliver/channels/` |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
