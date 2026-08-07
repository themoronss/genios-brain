# State Machine

Defines the legal lifecycle around an immutable `learning.v2` LearningObject. Preflight refusal is
deliberately outside this state graph: forbidden payloads are not inserted into `learning_objects`
and receive only a sanitized rejection record.

The weekly scheduler may revisit an identical stored object only in Observed/Candidate. That is a
new policy/time evaluation of the same immutable evidence, not a new state graph or object rewrite;
Candidate never regresses and later lifecycle states never reopen.

## Component modules

1. [States and Paths](01-States-and-Paths.md)
2. [Terminality and Illegal Moves](02-Terminality-and-Illegal-Moves.md)

**Primary authority:** `genios_engine/contracts/learning.py`,
`genios_engine/feedback/governance.py` and `genios_engine/feedback/store.py`.
