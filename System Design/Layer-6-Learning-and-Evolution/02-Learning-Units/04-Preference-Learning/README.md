# 4 · Preference Learning

**Status:** Built

Proposes actor-scoped user preferences or owner-authorized organization preferences only from
explicit structured facts. Winner selection is deterministic, and competing values remain visible
as conflict evidence.

| Boundary | Value |
|---|---|
| Input | explicit FeedbackFacts with complete key/value/scope/category fields |
| User identity | actor-scoped subject; two users never share one preference cohort |
| User ACL | always private to one resolved subject; unresolved/excluded source ACL is rejected before persistence |
| Organization authority | frozen by authenticated feedback writer, not caller JSON |
| Winner | greatest support; canonical serialized value breaks an exact tie |
| Output | private subject-capped Behavior target for user scope; source-ACL Organization target for organization scope |
| Primary code | `feedback/units.py::preference_learning` |
| Integration requirement | UI/upstream structurer must emit the closed preference envelope; free text is not guessed here |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
