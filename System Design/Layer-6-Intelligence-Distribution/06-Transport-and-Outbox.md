← [The Thirteen Reason Codes](05-Reason-Codes.md) · [Folder map](README.md) · → [Channels, Digest and Agent Delivery](07-Channels-Digest-and-Agents.md)

---

# Transport and the Outbox

---

## Transport — `outbox.py`

```mermaid
flowchart TD
    A["ENQUEUE<br/>fast · idempotent<br/>deduped by (org, card, channel)"] --> A2["**materialise** the delivery object:<br/>recipient · band · channel_class · interrupt"]
    A2 --> B["queued row"]
    B --> C["DRAIN: claim<br/>FOR UPDATE SKIP LOCKED"]
    C --> D["**gate.py** — local, lock-free"]
    D -- SUPPRESS --> E["status = suppressed<br/>+ gate_unit + gate_reason"]
    D -- DEFER --> F["next_attempt_at = not_before<br/>defer_count += 1<br/>**attempts UNTOUCHED**"]
    D -- SEND --> G["**authority re-validation**<br/>for share locks"]
    G -- "no longer live" --> H["status = cancelled"]
    G -- live --> I["adapter POST"]
    I -- ok --> J["status = delivered<br/>+ the ADMITTING verdict recorded"]
    I -- error --> K["backoff 5 → 30 → 120 → 720 min<br/>then failed_terminal"]
    J --> L["card_events row"]
    E --> L
    H --> L
    K --> L
```

**Dispatch policy** mirrors the card pipeline's push law without touching it: `HIGH` and
`CRITICAL` notify; `STANDARD` stays a dashboard rotation. The daily digest goes once per org per
UTC day **under a synthetic card id** — same dedup machinery, zero special cases.

---
