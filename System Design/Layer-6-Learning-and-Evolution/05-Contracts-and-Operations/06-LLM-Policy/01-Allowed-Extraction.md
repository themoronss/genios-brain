# Allowed extraction

A bounded model may be introduced to turn free-text feedback or enterprise text into a proposed
closed schema: for example, extracting a preference key/value/category, a correction, or a
structured event candidate. It may also summarize already-selected evidence for a human reviewer.

That output is untrusted input. Before it reaches a learning unit it must carry tenant, trace,
independence, source visibility and explicit schema/version provenance; validate against a closed
contract; and fail into the sanitized rejection ledger when malformed. The model may not widen
source visibility or assert owner authority. Explicit temporary memory must still come from an
authorized command with a bounded TTL.

No generic extractor is wired inside Layer 6 today. Adding one requires its own versioned contract,
grounded evaluation set, prompt/model provenance, replay tests, privacy review and failure-mode
monitoring. The deterministic pipeline remains correct without it.
