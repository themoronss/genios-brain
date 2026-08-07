# Learning Selector

**Status:** Built

Loads one bounded, tenant-scoped, as-of-time batch from durable Layer 2, Layer 5, Layer 5.2 and
explicit Layer 6 input seams. It verifies the immutable execution envelope wherever a fact claims
Layer 5/5.2 lineage and fails closed when ACL or lineage cannot be proven.

| Boundary | Current truth |
|---|---|
| Input | `org_id`, timezone-aware evaluation time and a 28-day default source window |
| Durable sources | latest card feedback revision, execution outcome, graph observation/source refs, structured learning event and delivery lifecycle |
| Security | source visibility is inherited and narrowed; absent/invalid ACL becomes private-empty and incomplete, never organization-visible |
| Lineage | exact ExecutionObject identity/hash, trace IDs, source refs and independence groups |
| Output | canonical `LearningBatch` facts plus sanitized `InputRejection` records |
| Authority | `feedback/store.py::load_batch` |

The selector does not parse raw prose, infer missing facts, or query mutable live state after the
batch has been frozen. A malformed optional preference is rejected without discarding an otherwise
valid explicit feedback verdict. User preference construction subsequently caps the selected source
ACL to a private resolved-subject ACL; it never turns a company-visible card into a company-visible
personal preference.

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
