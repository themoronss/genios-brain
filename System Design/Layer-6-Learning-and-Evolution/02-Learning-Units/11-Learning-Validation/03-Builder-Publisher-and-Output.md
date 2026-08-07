# Builder, Publisher and Output

Unit 11 has no LearningObject builder and no publisher. It returns
`ValidationResult(state, reason_code)` and `lifecycle_path` converts that verdict into the legal
transition prefix.

Only a Validated verdict proceeds to separate governance, which chooses temporary, human review,
promoted or rejected. This preserves the architectural separation:

- evidence quality cannot grant enterprise permission;
- consent/ACL cannot turn weak evidence into a valid claim; and
- publication occurs only after both decisions and only through the target-specific shared
  publisher.

Preflight rejection is audited without storing the proposed value. Ordinary validation transitions
remain attached to the immutable object for full explainability.
