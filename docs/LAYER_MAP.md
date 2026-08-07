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
| 5.2 | `deliver/` | 6 | Delivery Engine | `ExecutionObject`-only materialization; current audience/recipient, destination, channel, format, timing, policy, priority scheduling, lifecycle, retry/recovery, `DeliveryResult` and analytics. |
| 6 | `feedback/` | 7 | Learning & Evolution | Exact outcome/feedback/event lineage → eleven deterministic units → immutable `learning.v2` → versioned governance/lifecycle → Organization, Behavior, Adaptive, Runtime, metrics and human-only knowledge suggestions; also owns bounded calibration. |

Cross-cutting (outside the ordering): `contracts/` (boundary types; imports platform only),
`platform/` (config/db/crypto/wiring — the composition root), `api/` (transport surface).

**The rule that matters:** a lower import rank never imports a higher import rank. Cross-layer needs are
met by *injection* (platform/wiring resolves and passes values down) or by *data* (a table
written above, read below). Today Reasoning consumes `rule_mutes` and
`lvl3_config.rule_offsets`; the new versioned Organization, Behavior and Adaptive entries plus
Runtime memories are governed and published but do not yet have typed lower-layer consumers.
Metrics is not a brain. Learning never edits the Expert Brain; knowledge evolution stops at a
human-review suggestion. Layer 6 uses PostgreSQL as source of truth, carries source visibility and
trace through every sink, and treats any future Redis/LLM integration as non-authoritative.

**Where the 5/5.2 line sits.** Layer 5 owns the business commitment: the work owner, ordered
actions, deadline, completion evidence, business priority and the semantic audience/presentation
intent frozen in the `ExecutionObject`. Layer 5.2 owns attention and transport at delivery time:
it resolves the **current** audience and recipient, registered destination, concrete channel,
format, timing, interruptibility, hard policy, delivery priority, retries and lifecycle. The
concrete `channel_id`, `channel_class` and `interrupt` fields retained for v1/v2 compatibility are
backwards-compatible audit hints, not send authority; new `execution.v2` objects also carry the
narrowest inherited source visibility. The Layer 5.2 orchestrator deliberately ignores concrete
route hints and enforces that visibility against the live recipient/destination.

This split prevents both ownership drift and stale routing. Reassigning who must do the work is a
Layer 5 lifecycle operation; routing a still-live commitment to the owner's current manager or
active surface is Layer 5.2. New outward rows are materialized only from a persisted,
hash-verified `ExecutionObject`; cards remain a read model and cannot independently authorize a
notification. `deliver/` may import `executive/`; `executive/` never imports `deliver/`.
