# Part B · The 11 Learning Units

Each unit folder maps the Atlas pipeline
`Input → Validator → Retriever → Analyzer → Calculator → Evaluator → Builder → Publisher` to
current code. Units 1–10 build proposals; Unit 11 validates every proposal during lifecycle
planning and therefore does not emit a second LearningObject.

| # | Unit | Layer 6 core | Remaining integration outside the unit | Folder |
|---|---|---|---|---|
| 1 | Feedback Learning | Built | populate explicit canonical feedback | [01](01-Feedback-Learning/README.md) |
| 2 | Outcome Analysis | Built | populate grounded execution outcomes | [02](02-Outcome-Analysis/README.md) |
| 3 | Pattern Learning | Built baseline | richer sequence/correlation models are future extensions | [03](03-Pattern-Learning/README.md) |
| 4 | Preference Learning | Built | trusted structured preference capture | [04](04-Preference-Learning/README.md) |
| 5 | Temporary Memory | Built | lower-runtime memory consumption/cache is pending | [05](05-Temporary-Memory/README.md) |
| 6 | Behavior Evolution | Built | lower-layer Behavior Brain reader is pending | [06](06-Behavior-Evolution/README.md) |
| 7 | Adaptive Evolution | Built | lower-layer Adaptive Brain reader is pending | [07](07-Adaptive-Evolution/README.md) |
| 8 | Recommendation Learning | Built | recommendation selector consumption is pending | [08](08-Recommendation-Learning/README.md) |
| 9 | Performance Optimization | Built | broaden engagement/outcome coverage as sources mature | [09](09-Performance-Optimization/README.md) |
| 10 | Knowledge Evolution | Built suggestion path | human authoring/Git workflow remains deliberately external | [10](10-Knowledge-Evolution/README.md) |
| 11 | Learning Validation | Built | production threshold calibration is operational | [11](11-Learning-Validation/README.md) |

All units are deterministic over normalized facts. Measurement/pattern cohorts are separated by
source-derived ACL. Every user preference instead resolves exactly one subject, verifies that the
source ACL admits that subject and emits only `private + [subject]`; Behavior/Adaptive children
copy that cap unchanged. Canonical `wrong:bad_timing` is timing/neutral quality evidence, while
dashboard/extension snooze and dashboard requeue never enter the verdict cohort. Performance counts
only a `failed` delivery with no prior `delivered_at` as transport-negative, but uses every latest
durable lifecycle event for freshness. Source refs, independent refs and trace IDs are preserved;
neutral/open facts do not inflate confidence; and shared preflight can refuse incomplete lineage
before proposal payload persistence.
