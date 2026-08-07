# Closed targets and Expert boundary

`BrainTarget` contains exactly the four Atlas brains: Organization, Behavior, Adaptive and Runtime.
`LearningTarget` is the publication vocabulary and adds Metrics plus Knowledge Suggestion. Keeping
telemetry/review artifacts out of the brain enum prevents them from masquerading as mutable brain
state. Knowledge unit objects are contractually restricted to Knowledge Suggestion.

`Expert` is absent from both enums and publisher dispatch. Suggestion approval records a governed
human handoff; it never changes an Expert pack or repository code. This is a structural
prohibition, not a role convention.
