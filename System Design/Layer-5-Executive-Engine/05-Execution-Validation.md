← [Escalation and the Execution Object Builder](04-Escalation-and-The-Builder.md) · [Folder map](README.md) · → [Reminders and Monitoring](06-Reminders-and-Monitoring.md)

---

# The Execution Validation Unit

---

## Unit 4 — Execution Validation ⭐ (`execution_guard.py`)

**This is the single most important thing in the layer.**

> The classic failure of any reminder engine is that it reminds you about something that
> already happened. The plan was correct when it was made; the world moved; nobody told the
> scheduler. You get nudged to chase a customer who replied yesterday — **and from that moment
> every future nudge is presumed wrong until proven otherwise. Trust is lost far faster than
> it is earned.**

So **every** outbound moment — first delivery, each reminder, each escalation rung —
re-validates against live state immediately before it happens.

#### Six verdicts, not a boolean

Five of them are refusals, and they mean genuinely different things — *collapsing them would
make the difference invisible in exactly the reports where it matters:*

| Verdict | Means |
|---|---|
| `COMPLETE` | the world already did it |
| `CANCEL` | it should never happen now — authority revoked, deal closed, human said no |
| `EXPIRE` | the window closed with nothing observed |
| `REROUTE` | valid work, wrong person — the rep left |
| `SUPPRESS` | live work must not speak now (for example an inactive owner before release) |
| `PROCEED` | proven still live and unmet |

`BLOCKED` is valid live work, so the guard returns `PROCEED`. The Reminder Unit suppresses
ordinary owner nudges for that state while still allowing the frozen escalation ladder to fire.

#### Checks are ordered by authority, not by cost

> A revoked decision outranks a satisfied outcome, which outranks a closed subject, which
> outranks a stale owner — because when several things are wrong at once, the operator needs to
> be told the **most fundamental** one.

#### The subtlety that makes it work

> **An observed event only counts if it happened *after* the commitment was created.**
>
> The event that *causes* a recommendation is usually the same kind as the event that would
> *prove* it resolved — an inbound reply both signals a stalled deal and proves the follow-up
> landed. Counting history would mark every commitment complete on day zero, **which is the
> most convincing possible way to look like it is working while doing nothing.**

The unit is **pure**: it takes a `ValidationInput` snapshot and returns a verdict. Gathering
the facts is SQL in `execution_store.py`. *Keeping the judgement separate is what lets the same
logic answer "why was this suppressed?" months later from stored inputs.*

---
