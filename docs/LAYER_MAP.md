# GeniOS Layer Map — product identity and import order

The **product architecture has Layers 1, 2, 3, 4, 5, 5.2 and 6**. Layer 5.2 is Delivery; Layer 6
is Learning & Evolution. There is no product Layer 7.

`genios_engine/LAYERS.py` also assigns packages integer **import ranks** 1–7 so the topology test
can compare ordering. Rank 7 means “last package in the import DAG”; it does **not** create a
product Layer 7.

| Product layer | Package | Import rank | Canonical name | What it owns |
|---|---|---:|---|---|
| 1 | `capture/` | 1 | Knowledge Layer · Enterprise Sources | Read + normalize reality. Connectors, envelope, dedup, preprocess, gate, triage, parked, payloads, traces. Zero reasoning. |
| 2 | `context/` | 2 | Context Intelligence | The live digital twin: entities, relationships, facts, observations, timeline, attention. The one extraction LLM call lives here. |
| 3 | `packs/` | 3 | Domain Expertise | The four brains + capability content, shipped as data. |
| 4 | `reason/` | 4 | Reasoning Engine | Deterministic cognition: rule evaluation, integer-bp scoring, baselines, derived signals and foresight. |
| 5 | `executive/` | 5 | Executive Engine | Decision briefs plus the ExecutionObject: interpret, plan, own, validate, track, remind, escalate, monitor and emit outcome. |
| 5.2 | `deliver/` | 6 | Delivery Engine | Context-aware admission, destinations, adapters, outbox, retry/failover, DeliveryResult and analytics. |
| 6 | `feedback/` | 7 | Learning & Evolution | Eleven governed units, dynamic-brain publishers, TTL memory, metrics, knowledge suggestions and bounded calibration. |

Cross-cutting (outside the ordering): `contracts/` (boundary types; imports platform only),
`platform/` (config/db/crypto/wiring — the composition root), `api/` (transport surface).

**The rule that matters:** a lower import rank never imports a higher import rank. Cross-layer needs are
met by *injection* (platform/wiring resolves and passes values down) or by *data* (a table
written above, read below). Today Reasoning consumes `rule_mutes` and
`lvl3_config.rule_offsets`; the new versioned brain entries and Runtime memories are published but
do not yet have lower-layer consumers. Learning never edits the Expert Brain; knowledge evolution
stops at a human-review suggestion.

**Where the 5/5.2 line sits, and why it moved.** Owner and channel selection used to live in
`deliver/router.py`, which made Layer 5.2 the authority on who owns a recommendation. That was the
wrong home: deciding whether to interrupt somebody is part of the commitment, not part of its
transport. "Page this person now" and "let them find it in tomorrow's digest" are two different
promises about how much of their attention the work is worth, and that judgement belongs with
the layer that decided the work was worth doing. Layer 5 now authors the communication plan
(audience, seat, channel, interrupt, tone) and freezes it into the Execution Object; Layer 5.2
executes it — adapters, retries, budget, copy, the outbox. Deliver imports executive; executive
never imports deliver, and `executive/validate.py` documents the same downward-import pattern
for the render validators.
