← [The Delivery Gate](04-The-Delivery-Gate.md) · [Folder map](README.md) · → [Transport and the Outbox](06-Transport-and-Outbox.md)

---

# The Thirteen Reason Codes

---

## The thirteen reason codes

> Every blocked delivery names itself. **"Why wasn't I told?" is asked far more often, and far
> more angrily, than "why *was* I told?"** — so the answer is in the row, not in a log.

| Unit | Reason code | Verdict |
|---|---|---|
| `policy` | `org_delivery_disabled` | suppress |
| `policy` | `org_delivery_held` | **defer** *(the only one policy issues)* |
| `policy` | `channel_inactive` | suppress |
| `policy` | `below_channel_min_band` | suppress |
| `policy` | `recipient_inactive` | suppress |
| `policy` | `recipient_opted_out` | suppress |
| `policy` | `permitted` | send |
| `timing` | `quiet_hours` | defer |
| `timing` | `recipient_busy` | defer |
| `timing` | `burst_limit` | defer |
| `timing` | `channel_not_intrusive` | send |
| `timing` | `override_band_<band>` | send — **the break-glass** |
| `timing` | `within_attention_window` | send |
| `timing` | `quiet_window_unsatisfiable` | send *(defensive; unreachable via the contract)* |

**`suppressed` is a third status, not a flavour of `cancelled`:**

> `cancelled` already meant one specific thing: **the subject stopped being live** before the
> send — a closed commitment, a revoked decision. **A person who turned this channel off is a
> different fact with a different fix.** Three outcomes, three statuses, because an operator
> seeing `suppressed` should look at preferences, not at Slack's status page.

---
