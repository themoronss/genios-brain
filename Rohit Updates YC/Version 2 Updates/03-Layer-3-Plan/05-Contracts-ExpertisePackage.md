# L3 Contracts — ExpertisePackage extensions

> Like L2's contract, **the L3 boundary object already exists and is good**
> (`contracts/domain_expertise.py:302` — frozen, validated, `brain_snapshot_id`
> mandatory, "structured expertise only; no recommendation or decision"). This document
> specifies **additive** extensions only, with a schema-version bump.

---

## E-01 · ExpertisePackage — additions

```python
    # --- typed-consumer outputs (doc 03) ---
    compiled_constraints: tuple[Mapping[str, Any], ...] = ()
        # CLG-06 output: {rule_id, severity, predicate_tree, source_ref}
    citations: tuple[Mapping[str, Any], ...] = ()
        # CLG-08: {artifact_id, artifact_class, statement (verbatim), source_ref}
    framing_blocks: tuple[Mapping[str, Any], ...] = ()
        # mental-models / decision-frameworks as render/explanation input material

    # --- consumption receipts (extend existing metadata discipline) ---
    weld_receipt: Mapping[str, Any] = field(default_factory=dict)
        # rules_compiled/fired/unevaluable, citations_attached/truncated,
        # plays_selected/over_cap, per class — "what did the corpus contribute HERE"

    # --- L2 v2 passthrough ---
    pattern_id: str | None = None
    matched_conditions: tuple[Mapping[str, Any], ...] = ()
```

### Validators added

| # | Rule | Enforces |
|---|---|---|
| V-1 | every `citation.statement` is byte-identical to the artifact's authored text (hash check against the catalog) | citations are quoted, never paraphrased |
| V-2 | every `compiled_constraint` carries `severity in {blocking, warning}` and a parseable predicate tree | CLG-06 discipline |
| V-3 | `weld_receipt` present whenever `expert_rules` is non-empty | consumption is always accounted for |
| V-4 | additions are optional-with-defaults; an old-shaped package still constructs | additive migration |
| V-5 | no float anywhere (reuse `require_bp`) | standing law |

## E-02 · DecisionObject — consumption side (L4 contract, small additive change)

```python
    citations: tuple[Mapping[str, Any], ...] = ()          # carried through from the package
    constraints_applied: tuple[Mapping[str, Any], ...] = () # which compiled rules fired,
                                                            # incl. eliminations by rule id
```
`alternatives_rejected` already exists on the decision projection — eliminations by a
blocking rule land there with the rule id, so E5's "why not X?" is answerable.

## E-03 · `l3_activation`

```sql
create table if not exists l3_activation (
    org_id      text not null,
    domain      text not null,               -- 'admin' first
    enabled_at  timestamptz not null default now(),
    enabled_by  text not null,
    notes       text,
    primary key (org_id, domain)
);
```
The compiler's live pass consults this table — per tenant, per domain — **instead of**
`use_domain_compiler`. The global flag is retired after the first pilot passes J5
(kept read-only for one release as a kill switch, then deleted).

---

## REVERSE PROMPT — Wave Y0

```
TASK: Extend the L3 contracts, additively.

FILES:
  genios_engine/contracts/domain_expertise.py  -> ExpertisePackage additions (E-01)
  genios_engine/contracts/reasoning.py         -> DecisionObject additions (E-02)
  new migration                                -> l3_activation (E-03)

RULES:
1. ADDITIVE ONLY. Every new field has a default; an old-shaped package/decision still
   constructs. Bump EXPERTISE_PACKAGE_VERSION. Test the old-shape round-trip.
2. Citation statements are validated byte-identical against the authored artifact
   (hash from the ExpertBrainCatalog). A paraphrased citation is a validation error.
3. compiled_constraints predicates use the SAME whitelisted operator grammar as L2
   cohorts. No new grammar.
4. l3_activation is per (org_id, domain). Do NOT touch use_domain_compiler in this wave.
5. reuse require_bp / require_identifier from contracts/validators.py.

ACCEPTANCE:
  pytest tests/contracts/test_l3_contracts.py -q   -> pass, 0 skips
  pytest tests/test_layer_topology.py -q           -> still green
```
