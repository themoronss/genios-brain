← [Transport and the Outbox](06-Transport-and-Outbox.md) · [Folder map](README.md) · → [Bugs, Runbook and Gaps](08-Bugs-Runbook-and-Gaps.md)

---

# Channels, Digest and Agent Delivery

---

## The other exits

| Exit | Module | Note |
|---|---|---|
| **Slack** | `channels/slack.py` behind `channels/base.py` | Slack incoming webhook; retains the original dedicated settings routes |
| **Teams** | `channels/teams.py` | Teams Incoming Webhook or anonymous Workflow trigger, using an Adaptive Card and validated Microsoft endpoint host |
| **Signed customer webhook** | `channels/webhook.py` | public HTTPS endpoint, canonical JSON and `X-Genios-Signature: sha256=...`; production still needs network egress controls |
| **Pull surfaces** | `channels/surface.py`, `results.py` | `in_app`, `dashboard`, `api`, `application`, `extension`, and `mobile`; delivered means available through the authenticated inbox, not device push |
| **Daily digest** | `digest.py` | *one line*: `"N cards waiting · top: <headline>"`. **Not a card, consumes no budget, outside the 2-notification cap.** Computed **on demand** — no periodic task |
| **Agent push** | `push.py` | HMAC-SHA256 signed (`X-Genios-Signature`). The body **is** the `/v1/signals` poll projection, *so push and poll are interchangeable*. Carries **no execution request** |
| **Agent API** | `agent_api.py` | the metered read-and-claim surface. A 15-minute claim lock, **first writer wins visibly** (409 on double claim), a `failed` result re-surfaces to the human. *Execution stays on the customer's side* |
| **Executive bridge** | `executive_bridge.py` | Layer 5's commitments → real messages |

#### Card routing and recovery

`destination.py` orders every active registered destination deterministically. High/critical
cards go to the primary destination first. A later destination is enqueued only after the
previous adapter exhausts its bounded retry ladder and becomes `failed_terminal`.

> Failover is transport recovery, never a policy escape. A suppressed, deferred, opted-out or
> authority-revoked delivery is not moved to another channel. Layer 5 commitment reminders also
> keep their exact frozen channel plan; changing that plan here would cross the authority line.

#### Typed results and observability

`DeliveryObject` and `DeliveryResult` expose the Atlas boundary without adding another mutable
table. `results.py` projects the outbox ledger for `/delivery/results` and `/delivery/inbox`;
`analytics.py` derives counted status, channel, attempt, deferral, failure and latency metrics
from the same rows.

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
