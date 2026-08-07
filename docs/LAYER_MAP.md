# GeniOS Layer Map — the one translation table

Three specs number the layers three different ways. **Nobody says "L5" without a package
name attached.** The layer index lives in code at `genios_engine/LAYERS.py`; import
direction (same-or-lower only) is enforced by `tests/test_layer_topology.py`.

| Package (code) | Layer # | New vision name | Old dossier name | What it owns |
|---|---|---|---|---|
| `capture/` | 1 | Enterprise Sources | L1 Capture | Read + normalize reality. Connectors, envelope, dedup, preprocess, gate, triage, parked, payloads, traces. Zero reasoning. |
| `context/` | 2 | Context Intelligence | L2 Context graph | The live digital twin: entities, relationships, facts, observations, timeline, attention. The ONE extraction LLM call lives here. |
| `packs/` | 3 | Domain Expertise | L4 Domain packs | The four brains + capability content, shipped as data. Universal = pack manifests; Organization = org settings/knowledge; Behavioral = user_models; Adaptive = calibration + outcomes. |
| `reason/` | 4 | Reasoning Engine | L3 Reasoning | Deterministic cognition: rule eval, integer-bp scoring, baselines, derived signals, foresight. Zero model calls. |
| `executive/` | 5 | Executive Engine | — | **Two halves.** *Decision intelligence:* Decision Briefs (brief.v1), verb taxonomy, four modes incl. **preventive** (distance-to-flip), summary ladder, executive memory, why-not receipts, the invention validator's canonical home. *Executive engine:* the Execution Object (execution.v1) — interpret → plan actions → resolve owner → choose channel → validate → track → remind → escalate → monitor → emit outcome. **Owns who and where** (`assignment.py`, `communication.py`); deliver executes the plan it authors. No model decides anything. Surface: `/v1/executive/*`. |
| `deliver/` | 6 | Intelligence Distribution | Atlas L5.2 Delivery | Cards, delivery context/admission, deterministic destinations, Slack/Teams/signed webhook/pull surfaces, digest, outbox, retries/failover, results and analytics. *Executes* Layer 5's communication plan; never replaces its owner or commitment authority. |
| `feedback/` | 7 | Learning Engine | Atlas L6 Learning & Evolution | Eleven governed units over feedback, real execution outcomes, enterprise events and delivery results; versioned Organization/Behavior/Adaptive publishers, TTL memory, metrics, human-only knowledge suggestions, plus bounded rule calibration. Lower layers never import it. |

Cross-cutting (outside the ordering): `contracts/` (boundary types; imports platform only),
`platform/` (config/db/crypto/wiring — the composition root), `api/` (transport surface).

**The rule that matters:** a lower layer never imports a higher one. Cross-layer needs are
met by *injection* (platform/wiring resolves and passes values down) or by *data* (a table
written above, read below). Today Reasoning consumes `rule_mutes` and
`lvl3_config.rule_offsets`; the new versioned brain entries and Runtime memories are published but
do not yet have lower-layer consumers. Learning never edits the Expert Brain; knowledge evolution
stops at a human-review suggestion.

**Where the 5/6 line sits, and why it moved.** Owner and channel selection used to live in
`deliver/router.py`, which made Layer 6 the authority on who owns a recommendation. That was the
wrong home: deciding whether to interrupt somebody is part of the commitment, not part of its
transport. "Page this person now" and "let them find it in tomorrow's digest" are two different
promises about how much of their attention the work is worth, and that judgement belongs with
the layer that decided the work was worth doing. Layer 5 now authors the communication plan
(audience, seat, channel, interrupt, tone) and freezes it into the Execution Object; Layer 6
executes it — adapters, retries, budget, copy, the outbox. Deliver imports executive; executive
never imports deliver, and `executive/validate.py` documents the same downward-import pattern
for the render validators.
