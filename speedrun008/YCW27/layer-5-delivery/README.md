# L5 · Delivery — `deliver/`

**36 files · 8,674 lines.** Milestone **M13**, 4 units.

> Who receives it, where, when, and in what form — **without adding a single fact**?

---

## What it owns

| Piece | Job |
|---|---|
| `pipeline.py` | the card-building pass, and the collapse measurement |
| `card_builder.py` `render.py` | the card itself |
| `card_source.py` | `classify` — SITUATION vs UNINTERPRETED |
| `outbox.py` | *every outbound human notification is a ROW, never a blocking call* |
| `executive_bridge.py` | the wire from L4 to a human |
| `router.py` `audience.py` `routing.py` | who sees it |
| `gate.py` `policy.py` `bands.py` `rate_limiter.py` | whether it may go |
| `digest.py` `scheduler.py` `timing.py` `timezone_infer.py` | when it goes |
| `act_pump.py` `actions.py` `agent_api.py` | the act lane and the agent gateway |

**The bridge points downward.** Executive may never import Delivery, so it writes its decision
down: an `execution_events` row of kind `execution.reminded` carries the routing plan, and Delivery
reads it. *"Until this module existed, Layer 5 could decide that somebody needed nudging, record
the decision, fire the escalation rung — and then nothing left the building. The reminder was a
row. This is the wire."*

**Division of labour:** L4 decides *whether to speak, to whom, through which channel, and what may
be said.* L5 **executes** that plan; it does not author it.

---

## The invention validator — what makes "no model invents a fact" enforceable

`executive/reminder.reminder_facts` returns *"the grounded fact corpus a reminder may be worded
from"*, and the validator **refuses any rendered sentence containing a number, name or date that is
not in it**. That function is literally the vocabulary of what a reminder is allowed to say.

⛔ But a sentence can be wrong without a new number — *"the vendor is blocking the launch"*, *"this
needs executive approval"*, *"finance caused the delay"*. That is what `M13.C1` widens, **without
weakening what is already there.**

## The cutover is measured before it is taken

`card_source.COMPARISON_KEYS` counts `cards_from_situation` / `cards_uninterpreted` /
`cards_from_signal` on **every** sweep. The new path is built beside the old one and both run for
one release.

⛔ **The recall guard: fewer cards must come from MERGING, never from DROPPING.** If every signal
must belong to a situation to be seen, a correlator gap becomes a silent disappearance.

---

## What changes — M13

### `M13.C1` Claim-level validation

| Unit | What |
|---|---|
| `U01` | the claim extractor — split rendered copy into claims, tag each fact / inference / hypothesis / recommendation |
| `U02` | the validator — claim type, evidence id, supporting span, permitted wording, visibility |

| Check | Rejects |
|---|---|
| claim type | a hypothesis worded as a fact |
| evidence ids | a material claim with no evidence |
| supporting span | a paraphrase warmer than the source |
| allowed wording | certainty the evidence does not carry |
| visibility | a card revealing restricted content to its reader |

### `M13.C2` Lanes on the card

| Unit | What |
|---|---|
| `U03` | the lane renders, and an investigation card carries **one precise ask** |
| `U04` | the scalar publication floor is replaced by lane routing, **recall guard held** |

⛔ `U03` is blocked on `M11.C2.U04` — a lane cannot render before L2 produces one.

## The failure this layer must design out

**Duplicates across paths.** The legacy signal path and the situation path must share one dedup
identity and **separate budgets** — otherwise a weak legacy card spends the budget a strong
situation card needed. Plus: card flattening (a rich result reduced to "follow up now"), and stale
fire (revalidate at send; if the situation resolved, drop it and record why).

## Read these first

`deliver/executive_bridge.py` · `deliver/card_source.py` · `executive/reminder.py`
