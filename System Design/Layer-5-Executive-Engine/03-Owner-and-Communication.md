← [Decision Interpretation and Execution Planning](02-Interpretation-and-Planning.md) · [Folder map](README.md) · → [Escalation and the Execution Object Builder](04-Escalation-and-The-Builder.md)

---

# Owner Resolution and Communication Planning

---

## Owner resolution (`assignment.py`)

Three ordered rules, moved down from `deliver/router.py` **unchanged in behaviour**:

```text
rule 1  the entity's declared owner (deal / relationship / node attribute) → that seat
rule 2  otherwise the triggering commitment's actor, if it maps to an active seat
rule 3  otherwise nobody — the admin queue, visible as `unrouted`, NEVER a silent drop
```

> **Rule 3 matters more than it looks.** An unroutable commitment still exists, is still
> tracked, still escalates and still shows up in coverage reporting. The alternative —
> dropping it — is how a system quietly stops mentioning **the accounts nobody owns, which are
> precisely the accounts most likely to be lost.**

**Pure core, injected directory.** The logic takes a `SeatDirectory`, not a database handle,
so all of it is testable without Postgres. `PgSeatDirectory` is the only part that touches SQL.

**No load balancing, on purpose.** No round-robin, no "assign to whoever is least busy". *Those
would make the same commitment land on different people on different days, and an owner who
cannot predict what reaches them stops trusting the queue.*

---

---

## Unit 3 — Communication Planning (`communication.py`)

> **Interruption is a budget, not a feature.** Every channel is ordered by how much of a
> person's attention it spends, and a commitment has to earn its way up that order with score,
> not with enthusiasm. **A system that pages on everything is indistinguishable from a system
> nobody reads.**

Behaviourally this reproduces exactly what Layer 6 used to do — high and critical to the org's
chat channel, everything else to the digest, unrouted work on the card surface — with three
differences: the choice is **recorded**, **explained by a reason code**, and **frozen into the
execution object** rather than recomputed inside a queue drain.

`may_interrupt(band, confidence_bp, cfg)` sets `interrupt` **only** when the reasoner's
confidence clears the pack's `interrupt_min_confidence_bp` floor. A critical-*scoring*
conclusion the engine is 40% sure of comes through with `interrupt=False`. *This single
property is what Layer 6's break-glass later inherits for free.*

Pure: the org's available channels are **passed in**, never queried here.

---
