# Builder, Publisher and Output

The builder emits unit `knowledge_evolution`, target `knowledge_suggestion`, subject
`knowledge:review:<capability>:<play>:audience:<acl-hash>`, the grounded cohort, exact lineage and
`metadata.human_review_required=true` plus parent ID.

`apply_path` places valid objects in `human_review` and idempotently creates a pending
`knowledge_suggestions` row. Approve/reject requires visibility and current validation/governance.
Approval marks the suggestion approved and the object promoted, returns `published=false` and
`expert_brain_changed=false`; rejection records both decisions.

**External integration:** Harsh/the knowledge owner still needs the human authoring, versioning,
testing and PR workflow that acts on an approved suggestion. Automated Expert mutation is outside
this architecture by design, not unfinished publisher code.
