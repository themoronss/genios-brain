# Input and selection context

The planner consumes the already selected `LearningBatch`: feedback, outcomes, enterprise events,
deliveries and input rejections frozen for one organization and evaluation time. It never queries
source tables itself.

The declared analysis order is:

1. Feedback Learning
2. Outcome Analysis
3. Pattern Learning
4. Preference Learning
5. Temporary Memory
6. Behavior Evolution
7. Adaptive Evolution
8. Recommendation Learning
9. Performance Optimization
10. Knowledge Evolution

Learning Validation is Atlas Unit 11 but is not an object-producing function in
`ALL_ANALYSIS_UNITS`. It evaluates each proposal as part of `lifecycle_path`, before governance or
publication. The tenant policy revision and evaluation time are therefore inputs to lifecycle
planning, not to the unit's immutable evidence identity.
