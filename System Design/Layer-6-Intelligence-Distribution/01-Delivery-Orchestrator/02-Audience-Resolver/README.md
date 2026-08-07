# Audience Resolver

**Status:** Upstream-owned

Preserves the resolved owner/audience chosen by Layer 5 and prevents Delivery from becoming a second assignment authority.

| Boundary | Current truth |
|---|---|
| Input | ExecutionObject communication plan or another authenticated candidate with explicit recipient |
| Output | the same authorized audience plus eligible registered destinations |
| Authority | Layer 5 `executive/assignment.py` and the frozen communication plan |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
