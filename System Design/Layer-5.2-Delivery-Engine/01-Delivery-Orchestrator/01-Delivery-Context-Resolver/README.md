# Delivery Context Resolver

**Status:** Active core; automatic reporting from every client is integration-dependent

Answers **“what is the recipient doing now, and which delivery constraints currently apply?”**
It combines tenant/seat/channel preferences, recent intrusive-delivery history and the newest
unexpired presence lease.

| Boundary | Current truth |
|---|---|
| Input | organization, resolved recipient, channel candidate and explicit evaluation time |
| Output | timezone, quiet window, channel policy, activity/surface/focus state, `busy_until` and burst facts |
| Runtime | `deliver/presence.py`, `deliver/gate.py`, delivery preference/presence APIs |
| Determinism | tenant-scoped rows + explicit time; no LLM judgement |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
