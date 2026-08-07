# Guard and progress projection

`next_state` lets the live guard lead. Terminal guard verdicts may close the commitment; progress
is considered only after `PROCEED`. Pending work with observed progress becomes running. Running
work with every step checked but no business proof becomes waiting, not completed.

A sweep may recognize work; it may not declare success on a person's behalf.
