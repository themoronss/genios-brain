# Output, edge cases and gaps

**Output:** an ordered list of immutable `LearningObject` proposals. Every proposal names exactly
one unit and target and contains content-addressed evidence, timing, visibility, trace and lineage.

Important edge behavior:

- one source cohort can intentionally produce both a measurement and a derived brain proposal;
  their unit, target and subject namespaces keep identities distinct;
- no-input units emit nothing rather than zero/unknown pseudo-learning;
- Unit 11 emits a validation result, not an eleventh `LearningObject`; and
- input rejections are persisted for audit but never passed to analytical units as evidence.

**Change rule:** adding, removing or reordering a unit changes the architectural plan and requires
an explicit contract/test/document update. It is not a runtime prompt decision.
