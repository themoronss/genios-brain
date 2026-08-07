"""Layer 5 — the Executive Engine.

Layer 4 answers **what should happen**.  This layer answers **how we make it happen** — and
those are different jobs.  A conclusion is an opinion; a commitment is an opinion with an owner,
a deadline, a ladder and a clock attached. Until this layer existed, GeniOS produced
excellent recommendations and then stopped: it had no idea whether anything was ever done.

Two halves, one boundary.

**Decision intelligence** — briefs, the summary ladder, memory, preventive warnings, why-not
receipts.  What is happening, why it matters, how urgent, on what evidence, and what happens if
nothing is done.  Deterministic composition over already-stored truth.

**The executive engine** — interpret the decision, plan the actions, resolve the work owner,
author semantic communication intent, build the frozen ExecutionObject, validate it against live
state, track, remind, escalate, monitor, and hand the outcome to Layer 6 Learning.

**Layer 5 owns the commitment; Layer 5.2 owns delivery.** Layer 5 fixes the work owner, actions,
deadline, business priority and semantic audience/presentation intent. Layer 5.2 resolves the
current recipient, registered destination, concrete channel, format, timing and interruptibility
immediately before delivery. The concrete route fields retained for v1/v2 compatibility are frozen
audit/backwards-compatibility hints, not send authority. Rank 6 may import rank 5, rank 5 may never
import rank 6, and ``tests/test_layer_topology.py`` enforces it.

Three laws hold across every module here.

*No model decides anything.*  An LLM may improve the wording of a reminder.  It may never decide
whether to remind, who to escalate to, what the steps are, or how urgent something is.  Approval
boundaries and escalation ladders cannot be probabilistic.

*Nothing fires without re-validation.*  Every outbound moment — first delivery, each reminder,
each escalation rung — is re-checked against live state immediately before it happens
(``execution_guard``).  A nudge about something that already happened costs more trust than ten
missed ones ever could.

*The plan is immutable; only the row moves.*  Execution objects are frozen and content-addressed
over ``(org, decision, plan)``.  State, owner and counters live in a database row that points at
one.  That separation is what makes "why did this escalate on day 7?" answerable months later,
after the pack has been retuned twice.
"""
