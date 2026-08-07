← [Layer 3 — Domain Expertise (`packs/`)](00-Overview.md) · [Folder map](README.md) · → [Pack Manifests — the Universal Brain](02-Pack-Manifests.md)

---

# The Four Brains

---

## The four brains, mapped to storage

| Brain | Lives in | Written by | Read by |
|---|---|---|---|
| **Universal** — expert baseline | `pack_registry.manifest` (immutable) | engineers, at build time | Layer 4 via `effective()` |
| **Organization** — this company's judgement | `tenant_packs.lvl2_config` + `pins`; plus Layer 1's canon (`internal_kind` rank 4) | admins | the merge |
| **Behavioral** — this person's style | `user_models` (voice · decision_policy · process_habits · priorities · relationships · red_lines) with `field_meta` recording `seeded \| learned` + confidence per field | seeded by the user, proposed by learning, **approved by the user** | Layers 5 and 6, for tone, channel and refusals |
| **Adaptive** — what actually worked | `lvl3_config.scoring_defaults.rule_offsets` + `rule_mutes` | Layer 7, through `write_lvl3_offset` only | the merge |

**The Behavioral brain never learns silently.** `user_model_proposals` holds a *proposed*
change with its `signal_count` and `rationale`, `pending` until a human approves or rejects
it. A persona is a statement about a person; the system may notice a pattern, but it may not
redefine someone without asking.

**The Adaptive brain writes DOWN, as data.** This is the architectural rule from the layer
map holding in practice: Layer 7 never imports Layer 3 or Layer 4 — it writes a row that the
merge reads. That is the only legal direction.

---
