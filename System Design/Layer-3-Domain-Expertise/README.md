# Layer 3 · Domain Expertise

Layer 3 answers one question:

> Given this already-qualified business situation, what is the smallest relevant, reproducible
> expertise package that Layer 4 may reason over?

The canonical implementation is the deterministic Domain Compiler in
`genios_engine/packs/compiler/`. It combines the authored Expert Brain in `Domain Expertise/`
with tenant-scoped Organization, Behavior, and Adaptive brain entries. It does not query the
Context Graph and it does not make recommendations, decisions, or LLM calls.

```text
BusinessSituationObject + SituationContextSlice  Layer 2 output
        |
        v
Domain Compiler / Orchestrator          Layer 3
        |---- Expert Brain              Git-authored, versioned YAML
        `---- Runtime Brains             Organization + Behavior + Adaptive, DB
        |
        v
ExpertisePackage                        immutable, content-addressed
        |
        v
Layer 4 Reasoning
```

## Read in this order

| Document | Purpose |
|---|---|
| [00 · Overview](00-Overview.md) | Boundary, invariants, lifecycle, and current implementation |
| [01 · The Four Brains](01-The-Four-Brains.md) | Ownership, persistence, authority, and precedence |
| [07 · Domain Compiler](07-Domain-Compiler.md) | The eight units, failure semantics, determinism, and production operation |
| [06 · Gaps](06-Gaps.md) | Honest remaining activation and corpus gaps |

The following documents describe the earlier pack/effective-config runtime that still exists for
compatibility while the new boundary is activated end to end:

- [02 · Pack Manifests](02-Pack-Manifests.md)
- [03 · Merge Engine](03-The-Merge-Engine.md)
- [04 · Pack Registry](04-The-Pack-Registry.md)
- [05 · Native Capabilities](05-Native-Capabilities.md)

## Current code map

| Concern | Location |
|---|---|
| Authoring source | `Domain Expertise/` |
| Boundary contracts | `genios_engine/contracts/domain_expertise.py` |
| Catalog and compiler | `genios_engine/packs/compiler/` |
| Production composition | `genios_engine/packs/domain_wiring.py` |
| Package persistence | `migrations/0048_l3_domain_compiler.sql` |
| Contract/compiler tests | `tests/test_domain_expertise_compiler.py` |

Layer 3 may import `contracts/` and platform utilities. Layer 6 may publish versioned runtime-brain
rows, but it never imports Layer 3 or edits the Expert Brain. Layer 3 only reads the pinned snapshot.

[System Design index](../README.md)
