# Layer 6 · Intelligence Distribution — the folder map

**This folder is the live truth of `genios_engine/deliver/`.** It is the source consulted before any action,
update or improvement to this layer. If a document and the code disagree, the document is wrong —
fix it in the same change that moved the code.

Start at **[00-Overview.md](00-Overview.md)** for the layer in one sitting. Use this page when you
already know what you are looking for.

---

## The one question this layer answers

> **May this reach them, now — and how does it look when it arrives?**

```mermaid
flowchart TD
    R["Layer-6-Intelligence-Distribution/"] --> A["01-Card-Production.md<br/><i>build · render · validate · persist</i>"]
    R --> B["02 · 03 · 04<br/><i>SEND / DEFER / SUPPRESS — policy, timing, the gate</i>"]
    R --> C["05-Reason-Codes.md<br/><i>every blocked delivery names itself</i>"]
    R --> D["06 · 07<br/><i>the outbox, Slack, digest, agent surfaces</i>"]
    R --> E["08-Bugs-Runbook-and-Gaps.md"]
```

---

## The documents

| # | Document | Answers |
|---|---|---|
| 00 | [Overview](00-Overview.md) | The two halves, the two forks, workflows, strategies |
| 01 | [Card Production](01-Card-Production.md) | Slots, the one model call, and the two gates that stand between it and a user |
| 02 | [The Admission Contract](02-The-Admission-Contract.md) | Why DEFER is not a failure, and why constraints compose rather than race |
| 03 | [Policy and Timing](03-Policy-and-Timing.md) | *May this travel at all?* versus *is this the moment?* |
| 04 | [The Delivery Gate](04-The-Delivery-Gate.md) | Why it runs at drain, and why before authority re-validation |
| 05 | [The Thirteen Reason Codes](05-Reason-Codes.md) | What each means and what an operator should do |
| 06 | [Transport and the Outbox](06-Transport-and-Outbox.md) | Claim, backoff, and the three outcomes |
| 07 | [Channels, Digest and Agents](07-Channels-Digest-and-Agents.md) | Slack, the 08:30 line, HMAC push, the claim-and-result surface |
| 08 | [Bugs, Runbook and Gaps](08-Bugs-Runbook-and-Gaps.md) | Six defects, the first night's numbers, and the unproven SQL |

---

## Where this layer sits

| | |
|---|---|
| **Package** | `genios_engine/deliver/` |
| **Layer number** | 6 — `genios_engine/LAYERS.py` |
| **Spec alias** | The architecture atlas calls this **Layer 5.2 · Delivery Engine**. The code numbers it 6, between `executive` and `feedback` |
| **Reads from** | authoritative signals (L4) · execution events (L5) |
| **Hands to** | cards on a surface · Slack messages · a daily digest · agent webhooks |
| **May import** | `executive/` (L5) and everything below |
| **LLM calls** | **One temp-0 call per card**, for copy only, behind two deterministic gates |

[← System Design index](../README.md)
