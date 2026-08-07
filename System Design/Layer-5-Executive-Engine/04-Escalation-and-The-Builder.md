← [Owner Resolution and Communication Planning](03-Owner-and-Communication.md) · [Folder map](README.md) · → [The Execution Validation Unit](05-Execution-Validation.md)

---

# Escalation and the Execution Object Builder

---

## Unit 8 — Escalation (`escalation.py`)

> An escalation ladder is a promise made at planning time and kept later — which is why it is
> built once, **frozen into the execution object, and never recomputed.** If it were derived
> fresh each time the sweep ran, retuning the pack on a Tuesday would silently rewrite the
> history of every commitment made on Monday.

The shipped ladder:

| Day | Action | Audience | Interrupt |
|---|---|---|---|
| 1 | notify | owner | no |
| 3 | remind | owner | **yes** |
| 7 | escalate | manager | no |
| 14 | critical | executive | **yes** |

**Urgency compresses it, it does not replace it.**

```text
band_multiplier_bp:  critical 5,000  ·  high 7,500  ·  standard 10,000
critical ladder → 1 / 2 / 4 / 7 days
```

> The **shape** is preserved; only the tempo changes. That is the difference between an
> escalation *policy* and a timer.

**It stops at the decision's expiry.** A rung that would fire after Layer 4 stopped standing
behind the conclusion is **dropped at build time**, so the execution object is *provably*
incapable of escalating on lapsed authority — not merely unlikely to.

---

---

## Unit 4 — the Execution Object Builder (`execution.py`)

> The builder is **the last place that can refuse cheaply.** Once an execution object exists it
> will be stored, delivered, reminded on and escalated; a commitment that was already dead on
> arrival costs a person's attention every day it survives. So the builder refuses **by value,
> with a named code**, rather than emitting something the guard will have to kill a moment
> later.

The refusal counters (`planned.reasons`) are a histogram, not a log:

| Reason | Means | Do |
|---|---|---|
| `outcome_no_action` | Layer 4 looked and concluded nothing should happen | **nothing — this is health** |
| `built` | a commitment was created | nothing |
| `no_steps` | a play declares no step text | fix the pack; *GeniOS will not invent steps* |
| `window_closed` | `window_days` leaves no time to act | widen the play's window |
| `decision_expired` | the decision lapsed before the sweep saw it | shorten the sweep interval |
| `unreadable_expiry` | a stored decision has no parseable expiry | **escalate — this is a data defect** |

---
