[← Folder map](README.md)

# The 11 Learning Units

Every analysis unit receives the same normalized `LearningBatch`, calculates with integer counts
and basis points, builds immutable LearningObjects, and names its target. Unit 11 then evaluates
every object. No unit publishes directly.

| # | Unit | Live input and calculation | Output |
|---|---|---|---|
| 1 | Feedback Learning | Explicit latest card verdicts; accepted/executed vs rejected/wrong; timing and neutral remain separate | Metrics object |
| 2 | Outcome Analysis | `execution_outcomes`; success/failure/unproven, progress, time, reminders and escalations | Outcome metrics |
| 3 | Pattern Learning | Repetition of normalized graph `subject + kind` across distinct days | Organization pattern candidate |
| 4 | Preference Learning | Only explicit structured preference facts; grouped by scope/key/value | Behavior or Organization candidate |
| 5 | Temporary Memory | Explicit memory directive plus mandatory future expiry | Runtime object with TTL |
| 6 | Behavior Evolution | Stable behavior categories: communication, decisions, meetings, execution, relationships | Behavior Brain candidate |
| 7 | Adaptive Evolution | Current priority, notification, execution and runtime personalization categories | Adaptive Brain candidate |
| 8 | Recommendation Learning | Per-capability/play outcome effectiveness and attention cost | Adaptive recommendation efficacy |
| 9 | Performance Optimization | Delivery terminal rate, attempts, deferrals and latency; open/suppressed is not failure | Learning metrics |
| 10 | Knowledge Evolution | At least 8 labeled outcomes with sustained success below 40% | Human-review play suggestion only |
| 11 | Learning Validation | Repetition, distinct days, confidence, noise, conflict, freshness, business value and TTL | Hold, reject or validated decision |

## Outcome taxonomy

| Class | Labels | Meaning |
|---|---|---|
| Positive | `succeeded` | Declared outcome evidence was observed |
| Negative | `expired_untouched`, `expired_in_progress`, `cancelled_by_human` | The recommendation did not reach its intended result |
| Neutral/unproven | `completed_unproven`, `cancelled_by_world`, `cancelled_by_system` | Do not fabricate a success/failure label |

`completed_unproven` is a first-class count in the published cohort. It can reveal that a play's
declared success evidence is missing without punishing the play as though it failed.

## Determinism

All operational calculations are plain integer arithmetic. The Atlas-permitted LLM seam may one
day structure free-text feedback before a `FeedbackFact` is constructed; it cannot validate a
pattern, assign confidence, promote learning, score a recommendation or update a brain.
