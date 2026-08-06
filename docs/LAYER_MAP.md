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
| `executive/` | 5 | Executive Intelligence | — | Decision Briefs (brief.v1), verb taxonomy, four modes incl. **preventive** (distance-to-flip), summary ladder, executive memory, why-not receipts, the invention validator's canonical home. Deterministic only; answers what/why/urgency/evidence/what-if-nothing — **never who/when/channel** (that's deliver's). Surface: `/v1/executive/*`. |
| `deliver/` | 6 | Intelligence Distribution | L5 Delivery | Cards, routing/assignment, channels, digest, agent gateway. Who/when/where — never what/why. |
| `feedback/` | 7 | Learning Engine | L6 Feedback | Precision windows, nudges, mutes, MACV. Writes learned state DOWN as data (rule_mutes, lvl3_config) — never imported upward. |

Cross-cutting (outside the ordering): `contracts/` (boundary types; imports platform only),
`platform/` (config/db/crypto/wiring — the composition root), `api/` (transport surface).

**The rule that matters:** a lower layer never imports a higher one. Cross-layer needs are
met by *injection* (platform/wiring resolves and passes values down) or by *data* (a table
written above, read below — e.g. `rule_mutes`, `lvl3_config.rule_offsets`).
