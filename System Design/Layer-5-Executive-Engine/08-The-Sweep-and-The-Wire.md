← [Execution Tracking and Feedback Collection](07-Lifecycle-and-Outcomes.md) · [Folder map](README.md) · → [Bugs, Runbook and Gaps](09-Bugs-Runbook-and-Gaps.md)

---

# The Sweep and the Delivery Bridge

---

## Layer 5.2 handoff (`deliver/executive_bridge.py`)

The one unit that lives in Layer 6. **Layer 5 cannot import Layer 6, so it cannot send
anything itself.** What it *can* do is write its decision down — and it does: the reminder
event carries the routing plan on the parent commitment and the **grounded fact corpus** in its
own `detail`. The bridge reads that and turns it into a message.

> Layer 5 decides **whether to speak, to whom, through which channel, and what may be said.**
> Layer 6 decides **how it looks and gets it there, with retries.**

Three properties make it safe to send:

1. **A commitment Layer 5 planned for the digest is not pushed.** *Respecting that is the whole
   reason Layer 5 was given the channel decision.*
2. **The bridge has no access to the graph and cannot look anything up**, so *"invents
   nothing" is **structural** rather than a matter of discipline.*
3. **The message is re-validated at send.** *A reminder can sit through a retry backoff while
   the customer replies, so a commitment that closed in that window is cancelled rather than
   delivered.*
4. **A widened escalation reaches its resolved target.** The event carries the rung's resolved
   seat, audience and interrupt flag; the outbox uses those values instead of falling back to
   the original owner.

`CREATED → PENDING` emits `execution.queued`. It does not claim delivery. Only a successful
Layer 5.2 adapter call stamps `executions.delivered_at` and emits
`execution.delivery_confirmed`.

**Exactly-once falls out of the synthetic key** `exec:<execution_id>:<event_id>` against the
existing `(org, card, channel)` unique index — the same trick the daily digest already uses.
**No new bookkeeping table**, and a crashed sweep that re-enqueues cannot double-send.

---

---

## The sweep (`sweep.py`) — what makes it a running system

**Pass 1 · `plan_commitments`** reads open signals that still prove out against
`reason/authority.py`'s predicate, builds an execution object for each, and writes it once.
Idempotent by construction.

**Pass 2 · `run_lifecycle`** — the part the layer exists for. The order **is** the design:

```text
validate → transition → observe → decide → speak
```

> **Validation comes first, always. Never "remind, then check."** The single most damaging
> thing a system like this can do is nudge somebody about work the world already finished, and
> the only structural defence is to make the guard **unskippable** — every path to a message
> goes through it.

> Nothing here is clever about batching or concurrency. Both passes take a limit, both are
> ordered deterministically, and both use guarded writes, so **two workers running the same
> sweep produce the same result as one — just faster.**

---
