# Planning pass

`executive/sweep.py::plan_commitments` selects authoritative decisions, builds execution objects and
persists only valid new commitments. Content identity plus the partial database uniqueness rule
prevent repeated sweeps from creating a second open commitment for the same decision.

A build refusal is recorded/explained; it is not converted into a partially valid execution.
