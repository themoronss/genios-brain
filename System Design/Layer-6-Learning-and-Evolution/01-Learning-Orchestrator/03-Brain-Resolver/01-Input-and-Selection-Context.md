# Input and selection context

The resolver is encoded in typed unit builders. Its inputs are the unit, grounded subject/value,
source ACL and evidence—not a caller-provided table or free-form brain name.

| Unit | `LearningTarget` |
|---|---|
| Feedback Learning | Metrics |
| Outcome Analysis | Metrics |
| Pattern Learning | Organization |
| Preference Learning | Behavior for user scope; Organization for owner-authorized organization scope |
| Temporary Memory | Runtime |
| Behavior Evolution | Behavior |
| Adaptive Evolution | Adaptive |
| Recommendation Learning | Adaptive |
| Performance Optimization | Metrics |
| Knowledge Evolution | Knowledge Suggestion |
| Learning Validation | no object/destination; returns a verdict |

Subject namespaces (`feedback:`, `outcome:`, `pattern:`, `preference:`, `memory:`, `behavior:`,
`adaptive:`, `recommendation:`, `performance:`, `knowledge:review:`) prevent unrelated claims from
sharing a publication slot. Measurement, pattern, recommendation and knowledge cohort subjects
include an ACL-derived audience suffix. Preferences are instead actor/scope keyed and narrow all
contributing source ACLs.
