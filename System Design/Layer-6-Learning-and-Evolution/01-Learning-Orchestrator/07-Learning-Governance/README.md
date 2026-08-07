# Learning Governance

**Status:** Built

Enforces consent, retention, lineage and audience rules before a proposal value can be stored, then
decides whether an otherwise valid proposal may publish automatically, requires human review or
must be rejected.

| Boundary | Current truth |
|---|---|
| Input | `LearningObject`, immutable tenant policy revision and acting/viewing principal |
| Preflight | enablement, blocked target/subject, exact lineage, ACL audience, resolved user-subject visibility, explicit Runtime TTL |
| Governance | Runtime immediately temporary and never reviewed; configured/constrained durable targets reviewed; remaining targets promoted |
| Human control | scoped review/rollback APIs; owner authority for organization-wide change |
| Policy history | immutable snapshots in `learning_policy_revisions` |
| Lock authority | tenant root first; policy before LearningObject/memory/subject locks; erasure owns tenant `FOR UPDATE` |
| Output | reason-coded refusal, human-review, temporary or promoted decision |
| Authority | `feedback/governance.py`; policy API; migration `0047` |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
