# Audience Resolver

**Status:** Active

Answers **“who should receive this delivery now?”** Layer 5’s work owner remains unchanged, but
Layer 5.2 resolves the final attention recipient from the requested audience class, current seat
directory and active agent registry.

| Boundary | Current truth |
|---|---|
| Input | execution work-owner seed, audience intent, optional reminder target, current seats and scoped agents |
| Output | `AudienceResolution(audience, recipient, reason_code)` |
| Runtime | `deliver/audience.py`, `deliver/orchestrator.py` |
| Non-goal | reassigning the execution or changing its action ownership |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
