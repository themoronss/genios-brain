# L4 Contracts — additive extensions

> All additive, defaults everywhere; old-shaped objects still construct. Bump the
> DecisionObject schema version. Reuse `require_bp` / the L2 predicate grammar / L3's
> citation byte-identity validator — write nothing twice.

## G-01 · ReasoningBundle — `contracts/reasoning.py`
The full type in doc 03 §3. Validators: V-1..V-7 (doc 03 §4). Key structural rules:
`numbers_used` placeholders only in prose · `generation` ∈ {llm:*, template_fallback} ·
V-3 action-id match is a **constructor-level** check, not a review nit.

## G-02 · DecisionObject additions
```python
    reasoning_bundle: ReasoningBundle | None = None
    confidence_vector: Mapping[str, int] = ...        # carried from the BSO, per E2
    ranking_weights_version: str = ...
    components: now includes "importance"             # 6-key ranking_weights
    do_nothing: Mapping[str, Any] = ...               # {cost_bp, horizon, statement, source}
    citations / constraints_applied                   # from L3 seam (already planned in Y0)
```

## G-03 · Finding additions (per-unit evidence emission — S1)
```python
    value_bp: int | None = None       # the spec's missing field
    # unit_ref derives from reasoner_id — no new field needed
```

## G-04 · ExternalCandidate + CritiqueVerdict (S4)
```python
class ExternalCandidate(BaseModel):
    proposal_id: str; agent_id: str
    kind: str                         # closed enum: email_draft | sequence | task | crm_change
    draft: str; params: Mapping[str, Any]
    target_ref: str                   # the situation/entity it addresses

class CritiqueVerdict(BaseModel):
    verdict: str                      # proceed | modify | hold
    advisory: bool = True             # ALWAYS True — GeniOS scores, the agent owns execution
    failing_checks: tuple[str, ...]   # rule ids
    winning_alternative: str | None
    utility_bp: int; confidence_bp: int
    rationale: str                    # R-3-narrated, evidence-bound
```
Validator: `advisory` cannot be set False — same pattern as L2's `is_causal`.

## G-05 · BriefRanking (S5)
```python
class BriefRanking(BaseModel):
    org_id: str; brief_date_key: str
    entries: tuple[BriefEntry, ...]   # {decision_id, rank, book_score_bp, rank_components}
```
Every entry carries `rank_components` — "why #1 today" is data.

## G-06 · `l4_activation`
```sql
create table if not exists l4_activation (
    org_id text not null, feature text not null,   -- 'roster_v2' | 'ranking_v2' |
                                                   -- 'bundle' | 'critique' | 'brief'
    enabled_at timestamptz not null default now(), enabled_by text not null,
    primary key (org_id, feature)
);
```
Five independently-flippable features, per tenant. **No global flags** — the standing
Version 2 rule.

## REVERSE PROMPT — Wave Z0
```
TASK: L4 v2 contract extensions, additive only.
FILES: contracts/reasoning.py (+ReasoningBundle, DecisionObject fields, Finding.value_bp,
ExternalCandidate, CritiqueVerdict, BriefRanking), new migration (l4_activation).
RULES: defaults on every new field; old shapes construct (test the round-trip);
advisory locked True (constructor-enforced, like L2's is_causal); ranking_weights grows
to 6 keys with re-normalized defaults + version string; V-3 (bundle action-id == decision
action-id) enforced in the ReasoningBundle/DecisionObject constructor; reuse require_bp,
the L2 predicate grammar, and L3's citation byte-identity check — do not duplicate any.
ACCEPTANCE: pytest tests/contracts/test_l4_contracts.py -q -> 0 skips;
tests/test_layer_topology.py still green.
```
