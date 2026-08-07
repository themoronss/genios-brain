[← Folder map](README.md)

# Dynamic brains and Evolution Publisher

`BrainTarget` is closed. Its values are Organization, Behavior, Adaptive, Runtime, Metrics and
Knowledge Suggestion. **Expert is not a value**, so an exhaustive publisher cannot accidentally
gain an Expert write branch.

| Publisher | Durable output | Semantics |
|---|---|---|
| Organization | `learned_brain_entries(brain='organization')` | organization-wide pattern/preference; human review by default |
| Behavior | `learned_brain_entries(brain='behavior')` | stable person behavior derived from repeated explicit evidence |
| Adaptive | `learned_brain_entries(brain='adaptive')` | current preference and recommendation efficacy |
| Runtime | `temporary_memories` | explicit leased context; PostgreSQL is authority |
| Metrics | `learning_metrics` | bounded-window effectiveness/performance facts |
| Knowledge Evolution | `knowledge_suggestions` | review artifact only; not an Expert publisher |

## Versioning and supersession

A published brain value is unique on `(org, brain, subject)` while active. Publishing a newer
version locks the old entry, ends it as `superseded`, increments the version, inserts the new value,
and moves the older LearningObject from Published to Superseded. History is never overwritten.

## Rollback

An owner may roll back a Published LearningObject. The active brain entry is ended with the actor,
reason and time represented in the transition ledger; the object moves to RolledBack. The system
does not silently reactivate an older version because old behavior may itself be stale.

## Knowledge review

Knowledge Evolution creates a `knowledge_suggestions` row at HumanReview. Rejection closes the
LearningObject. Approval records the human decision and moves the suggestion to Promoted, but
returns `expert_brain_changed: false`. Applying that suggestion to the Expert Brain remains a
separate, human-owned Git review workflow.

## Current consumption boundary

The publishers and read APIs are live, but a repository search shows no lower package currently
reads `learned_brain_entries` or `temporary_memories`. Therefore these generic Atlas outputs are
governed and durable, not yet operational inputs to Context, Reasoning, Executive or Delivery.

The existing narrow calibration path is different and already closed: reasoning reads active
`rule_mutes` plus bounded `tenant_packs.lvl3_config.rule_offsets` written by `calibrate.py`.
Integrating the new brains requires a typed, allowlisted materializer or read model per consuming
layer; a direct generic JSON read would bypass brain scope, policy lineage and expiry semantics.
