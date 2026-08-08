[Overview](00-Overview.md) · [Domain Compiler](07-Domain-Compiler.md) · [Folder map](README.md)

# The Four Brains

The four brains describe provenance and authority, not four interchangeable dictionaries. They
remain distinct through compilation so Layer 4 can know whether a rule is universal expertise,
tenant policy, observed behavior, or learned adaptation.

| Brain | Meaning | Source of truth | Written by | Runtime role |
|---|---|---|---|---|
| Expert | What good domain practice says | Git-authored `Domain Expertise/` package | domain authors through review | baseline objects, situations, capabilities, rules, playbooks, heuristics, mental models, frameworks |
| Organization | What this organization knows and permits | versioned active `learned_brain_entries` plus governed organization configuration | authorized humans and governed discovery/publication | tenant facts, vocabulary, process, policy, constraints, approvals |
| Behavior | How actors actually operate | versioned active `learned_brain_entries` | governed observation/approval from Layer 6 | habits, interaction patterns, communication style; never permission authority |
| Adaptive | What has worked in this context | versioned active `learned_brain_entries` | governed outcome learning from Layer 6 | confidence calibration and preferences; never permission authority |

## Ownership

- The Authoring Engine changes only the Expert Brain.
- Layer 6 may publish versioned Organization, Behavior, and Adaptive entries.
- Layer 3 reads active entries and compiles a snapshot. It never learns or updates brains.
- Layer 4 reasons over the compiled package. It does not reinterpret brain ownership.
- Organization policy remains authoritative even when observed behavior or outcome learning
  suggests a different action.

## Two axes, not one precedence ladder

Preference precedence answers, "how should the permitted thing be done here?"

```text
Expert < Behavior < Organization < Adaptive
```

Permission precedence answers, "who is allowed to authorize or prohibit?"

```text
Adaptive < Behavior < Expert < Organization
```

These axes cannot be collapsed into a generic deep merge. A learned preference may refine a
ranking, but it cannot relax a tenant approval requirement. The compiler therefore carries four
separate arrays, resolves only matching explicit `conflict_key` values, and rejects permission-axis
categories from Behavior and Adaptive at ingress. Two claims at the same rank and conflict key are
an authoring/governance error, not a reason to invent a tie-break.

## Relevance and visibility

A runtime entry is eligible only when all of these hold:

1. its `org_id` equals the BSO tenant;
2. it is active and one immutable version is selected;
3. it explicitly selects a chosen capability, object, situation, BSO entity, or brain subject key;
4. its visibility permits every member of the package audience;
5. its brain is Organization, Behavior, or Adaptive;
6. its category respects that brain's authority.

Unrelated tenant memory is not loaded merely because it exists. Private evidence is not widened
into an organization-visible package. Every included entry carries its version, confidence,
learning id, trace, visibility, and content hash into the evidence receipts.

## Snapshot identity

The Expert Brain snapshot is derived from the selected Git-authored source documents. The runtime
snapshot is derived from the selected immutable DB entries. Their two ids are then combined into
`brain_snapshot_id`, which is part of the ExpertisePackage identity.

Consequently:

```text
same BSO + same Expert slice + same runtime entries = byte-identical ExpertisePackage
```

Changing one brain entry creates a new snapshot and package; historical packages remain unchanged.
