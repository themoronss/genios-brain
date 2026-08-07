# Part E · Contracts and Operations

This part documents the implemented `learning.v2` contract and its PostgreSQL/API authority. The
baseline schema remains migration 0045; migration 0047 adds policy snapshots, ACL/trace lineage,
normalized inputs, rejection audit, run-policy-time-bound object evaluations and safe supersession
without rewriting 0045.

| Subpart | Purpose |
|---|---|
| [LearningObject Contract](01-LearningObject-Contract/README.md) | `learning.v2` immutable proposal, ACL and evidence lineage |
| [Persistence and Migration](02-Persistence-and-Migration/README.md) | 0045 baseline plus additive 0047 authority |
| [API Surface](03-API-Surface/README.md) | ACL reads, idempotent memory and scoped/owner commands |
| [Existing Calibration Loop](04-Existing-Calibration-Loop/README.md) | rule mutes and bounded offsets consumed by Reasoning |
| [Tests and Ratchets](05-Tests-and-Ratchets/README.md) | 50 canonical, 144 expanded cross-seam and 1,896 full-suite verification evidence |
| [LLM Policy](06-LLM-Policy/README.md) | bounded extraction only; no learned decision authority |
