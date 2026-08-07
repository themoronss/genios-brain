# States and transitions

`ExecutionState` contains `created`, `pending`, `running`, `waiting`, `blocked`,
`completed`, `cancelled`, `expired` and `archived`. `ALLOWED_TRANSITIONS` lives in
`contracts/execution.py`; `lifecycle.py::transition` and tests use that single definition.

No-op and illegal moves raise `LifecycleError`. Completed, cancelled and expired commitments can
only be archived; reopening would rewrite an outcome already exposed to learning.
