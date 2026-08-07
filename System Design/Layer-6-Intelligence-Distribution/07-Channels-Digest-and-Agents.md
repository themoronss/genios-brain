← [Transport and the Outbox](06-Transport-and-Outbox.md) · [Folder map](README.md) · → [Bugs, Runbook and Gaps](08-Bugs-Runbook-and-Gaps.md)

---

# Channels, Digest and Agent Delivery

---

## The other exits

| Exit | Module | Note |
|---|---|---|
| **Slack** | `channels/slack.py` behind `channels/base.py` | one adapter today |
| **Daily digest** | `digest.py` | *one line*: `"N cards waiting · top: <headline>"`. **Not a card, consumes no budget, outside the 2-notification cap.** Computed **on demand** — no periodic task |
| **Agent push** | `push.py` | HMAC-SHA256 signed (`X-Genios-Signature`). The body **is** the `/v1/signals` poll projection, *so push and poll are interchangeable*. Carries **no execution request** |
| **Agent API** | `agent_api.py` | the metered read-and-claim surface. A 15-minute claim lock, **first writer wins visibly** (409 on double claim), a `failed` result re-surfaces to the human. *Execution stays on the customer's side* |
| **Executive bridge** | `executive_bridge.py` | Layer 5's commitments → real messages |

#### `executive_bridge.py` — the wire, and why it runs this way round

> Layer 5 may never import Layer 6, so it cannot enqueue anything itself. What it *can* do is
> **write down its decision**, and it does: an `execution_events` row of kind
> `execution.reminded` carries the routing plan on the parent commitment and the **grounded fact
> corpus** in its own `detail`. Layer 6 reads that and turns it into a message.

> **Nothing new is ever said.** The message is assembled only from values Layer 5 put in the
> fact corpus. The bridge has **no access to the graph and no way to look anything up**, which
> makes the invention guarantee **structural rather than a matter of discipline.**

**Exactly once by construction:** the synthetic `card_id` embeds the event id, so the existing
`(org, card, channel)` unique index absorbs a re-enqueue.

---
