← [The Policy and Timing Units](03-Policy-and-Timing.md) · [Folder map](README.md) · → [The Thirteen Reason Codes](05-Reason-Codes.md)

---

# The Delivery Gate

---

## The Gate — `gate.py`

`policy.py` and `timing.py` **neither know the other exists, and neither can read a database.**
The gate is what makes them a system: it resolves their inputs from live tenant state, folds
their verdicts, and hands `outbox.py` one decision with a reason code attached.

#### Why the gate runs *before* authority re-validation

> Both can stop a delivery, and **the gate is local, cheap and takes no locks**, while the
> authority check holds `for share` locks on the graph **across an outbound HTTP call**. Holding
> those to discover the recipient is asleep would be **paying the expensive question to answer
> the cheap one.**
>
> A message deferred past its card's expiry is not lost work either — the authority check runs
> when the deferral opens and cancels it there, so **staleness stays owned by the one predicate
> that already owns it.**

#### Preferences resolve **field-by-field**, never row-by-row

Rows are keyed `(org_id, seat_id, channel)` with `'*'` as the wildcard, at four specificities:

```text
(org, seat, 'slack')  →  this person, this channel     "no Slack pushes, keep email"
(org, seat, '*'    )  →  this person, everywhere       their timezone, their quiet hours
(org, '*',  'slack')  →  everyone, this channel        "Slack is escalations only"
(org, '*',  '*'    )  →  the tenant default            set by an admin
```

Each **column** independently walks from most specific to least and takes the first non-null
opinion.

> Picking a winning **row** would mean a person who sets only their timezone thereby **discards
> their tenant's quiet hours.**

A seat beats an org-wide channel rule, *because the seat is a statement about a human and the
channel is a statement about a pipe.*

**`'*'` is a sentinel rather than `NULL`** because **NULLs never compare equal inside a primary
key**, which would let two org-wide default rows coexist and make resolution depend on physical
row order.

#### Bad configuration: degrade in the engine, refuse at the door

Two responses to the same predicate, and the asymmetry is deliberate:

| Path | Behaviour | Why |
|---|---|---|
| `build_context` (the drain) | **degrades** — every unusable value falls back to the **protective** default (a broken timezone becomes **UTC quiet hours**, not *no* quiet hours), and the reason travels into the audit row | *a tenant who types `Amercia/New_York` must never stop **another** tenant's mail draining* |
| `PUT /delivery/preferences` | **refuses** — writes, re-resolves inside the same transaction, and **rolls back** if the result would degrade | the form field cannot afford to lie |

> **The consequence is the one that matters: a setting that survives a PUT is a setting that
> will actually take effect.**

---
