← [The Admission Contract](02-The-Admission-Contract.md) · [Folder map](README.md) · → [The Delivery Gate](04-The-Delivery-Gate.md)

---

# The Policy and Timing Units

---

## The Policy Unit — *may this travel at all?*

> A tenant on a compliance hold, a channel somebody disconnected, a person who turned Slack
> pushes off — **none of those are matters of timing, and none of them get better in an hour.**
> Keeping the two questions in separate units is what stops *"you opted out"* from being
> expressed as a deferral that quietly retries forever.

**Verdicts here are almost always terminal.** Policy answers `SEND` or `SUPPRESS`. It has
exactly **one** deferral — an org-wide hold **with a stated end** — *because a hold does have a
clock, and pretending otherwise would throw away work that becomes legitimate on Monday.*

---

---

## The Timing Unit — *is this the moment?*

> Every other unit in this layer asks whether a message is **correct**. This one asks whether
> the **moment** is. It is the only unit here that can make GeniOS look thoughtless while being
> completely right: **a churn alert that is accurate, owned, well-worded and delivered at 03:14
> is still a reason to turn notifications off — and once they are off none of the accuracy
> matters.**

#### The one rule underneath all the others

> **Deferral is not suppression.** Nothing in this module ever decides that a person should not
> be told something. That judgement was made upstairs, by a layer with the context to make it.
> This unit only ever **moves the moment** — and where it cannot find a humane one it says so
> with a reason code rather than quietly dropping the message.

`evaluate_timing` returning `SUPPRESS` is **impossible**, and a test sweeps *every reachable
combination of profile, state, band, interrupt flag and hour across eight days* to prove it.

#### The break-glass, and the confidence floor it inherits for free

```text
band ≥ override_band  AND  interrupt
```

The second half is doing more work than it looks:

> `executive/communication.py` only sets `interrupt` when the reasoner's confidence clears its
> floor — **a critical-*scoring* conclusion it is 40% sure of comes through with
> `interrupt=False`.** So a low-confidence crisis **cannot** wake anybody, and the timing unit
> gets that property **without knowing what a confidence interval is.**

One dial, upstairs. And because there is **no band above `critical`**, raising `override_band`
to `critical` is how a tenant says *"never wake me"*.

#### Three timing constraints

| Constraint | Verdict | Note |
|---|---|---|
| **quiet hours** in the recipient's own timezone | `defer` until the window opens | DST-correct — proven against spring-forward, fall-back and +05:30 |
| **burst limit** (per hour) | `defer` | distinct from the daily budget — *seven cards are a reasonable day and an unreasonable minute* |
| **recipient busy** | `defer` | `AttentionState.busy_until` from an owner-authenticated, short-lived `delivery_presence` lease; automatic calendar/client publishing remains open |

---
