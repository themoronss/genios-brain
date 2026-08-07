← [Reminders and Monitoring](06-Reminders-and-Monitoring.md) · [Folder map](README.md) · → [The Sweep and the Delivery Bridge](08-The-Sweep-and-The-Wire.md)

---

# Execution Tracking and Feedback Collection

---

## Unit 8 — Execution Tracking (`lifecycle.py`)

Two rules make the history worth trusting.

**Every move is proved legal against one table** — `ALLOWED_TRANSITIONS` in the contract, read
by this module, the SQL guard and the tests alike.

**Every move carries a cause** — not a timestamp and a new value, but a **cause code, an actor
and a detail**:

> *"cancelled"* answers nothing. *"cancelled · authority_revoked · the pack was rolled back"*
> answers everything, and it is the difference between an incident that takes an afternoon and
> one that takes ten minutes.

**Terminal states are terminal.** `COMPLETED`, `CANCELLED` and `EXPIRED` go only to `ARCHIVED`.

> If the world changes again, that is a **new** decision producing a **new** commitment.
> Reopening would silently rewrite the outcome Layer 7 already learned from.

The owner-only transition API makes `RUNNING`, `WAITING` and `BLOCKED` reachable while work is
open. A resumed expired outcome requires a new Layer 4 decision and therefore a new commitment.

---

---

## Unit 9 — Feedback Collection (`collect.py`)

> The original learner used only card judgments, which measured whether a recommendation
> **looked** right at the moment it arrived. Atlas Layer 6 now also consumes these durable
> execution outcomes, so it can measure whether acting on the recommendation **worked** and how
> much reminder/escalation attention it cost. A card everybody clicks and nobody ever completes
> is no longer counted as a triumph.

#### The label taxonomy — the deliberate output

| Label | Means |
|---|---|
| `succeeded` | the world produced the declared evidence. **The only positive label** |
| `completed_unproven` | every step ticked, nothing observed |
| `expired_untouched` / `expired_in_progress` | ran out of time, with or without progress |
| `cancelled_by_human` / `by_world` / `by_system` | dismissed / deal closed / incident |

> **`completed_unproven` is kept separate on purpose. A play people are happy to finish and
> that never produces its outcome is the most expensive failure mode a recommendation system
> has**, and merging it into "succeeded" would hide it permanently.

Counting terminal states would flatten four genuinely different endings into "not completed" —
and *the distinction between "we ran out of time" and "the deal closed while we were drafting"
is the entire difference between "shorten the window" and "this play was fine, the world moved
on".*

Each row also carries `reminders_sent` and `escalations_fired` — **the cost in human
attention.** *A play that succeeds once per four reminders and one escalation is not obviously
better than one that fails quietly.*

**Direction of travel matters.** Layer 5 **emits**; Layer 7 **reads**. Nothing here imports
`feedback` — *a lower layer importing a higher one is exactly what the topology ratchet exists
to prevent, and it would invert the dependency in the one place where the consumer should be
free to change its mind about what it wants to learn.*

---
