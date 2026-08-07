# LearningObject Contract

Defines the immutable `learning.v2` proposal, evidence/independence lineage, source ACL and closed
target/state vocabulary. The reader retains explicit `learning.v1` compatibility for stored legacy
objects; new objects use v2.

Policy/time decisions are deliberately external to content identity and live in the append-only
per-run evaluation ledger, allowing safe Observed/Candidate reconsideration without object mutation.

**Primary authority:** `genios_engine/contracts/learning.py`

## Component modules

1. [Shape Evidence and Identity](01-Shape-Evidence-and-Identity.md)
2. [Immutability and Round Trip](02-Immutability-and-Round-Trip.md)
3. [Closed Targets and Expert Boundary](03-Closed-Targets-and-Expert-Boundary.md)
