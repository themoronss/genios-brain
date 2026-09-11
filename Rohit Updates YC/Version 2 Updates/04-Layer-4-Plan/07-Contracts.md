# L4 Contracts — additive extensions

> All additive, defaults everywhere; old-shaped objects still construct. Bump the
> `DecisionObject` schema version. Reuse `require_bp`, the L2 predicate grammar and L3's
> byte-identity citation validator — write nothing twice.

---

## G-01 · `ReasoningBundle` — `contracts/reasoning.py`
Full type in doc 05 §2. Validators V-1…V-7 (doc 05 §4). Structural rules:
`numbers_used` placeholders only in prose · `generation ∈ {llm:*, template_fallback}` ·
**V-3 action-id match is enforced in the constructor**, not by review.

## G-02 · `DecisionObject` additions
```python
    reasoning_bundle: ReasoningBundle | None = None
    confidence_vector: Mapping[str, int] = ...     # carried from the BSO (E2)
    components: Mapping[str, int]                  # now SIX keys, incl. 'importance'
    ranking_weights_version: str = ...
    formula_utility_bp: int                        # recorded beside the override, always
    do_nothing: Mapping[str, Any] = ...            # {cost_bp, horizon, statement, source}
    citations / constraints_applied                # from the L3 seam
```

## G-03 · `Finding` addition
```python
    value_bp: int | None = None      # the spec's missing magnitude field
    # unit_ref derives from reasoner_id — no new field, no new object
```

## G-04 · `ExternalCandidate` + `CritiqueVerdict`
```python
class ExternalCandidate(BaseModel):
    proposal_id: str; agent_id: str
    kind: str                        # closed enum: email_draft|sequence|task|crm_change
    draft: str; params: Mapping[str, Any]
    target_ref: str

class CritiqueVerdict(BaseModel):
    verdict: str                     # proceed | modify | hold
    advisory: bool = True            # ALWAYS True — GeniOS scores; the agent executes
    failing_checks: tuple[str, ...]
    winning_alternative: str | None
    utility_bp: int; confidence_bp: int
    rationale: str                   # R-3-narrated, evidence-bound
```
`advisory` cannot be constructed False — same enforcement pattern as L2's `is_causal`.

## G-05 · `BriefRanking`
```python
class BriefRanking(BaseModel):
    org_id: str; brief_date_key: str
    entries: tuple[BriefEntry, ...]  # {decision_id, rank, book_score_bp, rank_components}
```
Every entry carries `rank_components` — *"why #1 today"* is data, not narrative.

## G-06 · `ranking_weights` — six keys
```
importance 2500 · impact 2000 · urgency 2000 · success 1500 · effort 1000 · risk 1000
```
Validated to sum to 10000 at construction; carries a version string; **integer bp only**.

## G-07 · `l4_activation`
```sql
create table if not exists l4_activation (
    org_id  text not null,
    feature text not null,     -- 'roster_v2' | 'ranking_v2' | 'bundle' | 'critique' | 'brief'
    enabled_at timestamptz not null default now(),
    enabled_by text not null,
    primary key (org_id, feature)
);
```
Five independently-flippable features, **per tenant**. No global flags —
`use_domain_compiler = False` is the standing warning.

---

## REVERSE PROMPT — Wave Z0
```
TASK: L4 v2 contract extensions, additive only.
FILES: contracts/reasoning.py (ReasoningBundle, DecisionObject fields, Finding.value_bp,
ExternalCandidate, CritiqueVerdict, BriefRanking); new migration (l4_activation).
RULES:
- defaults on every new field; old shapes still construct (test the round-trip)
- advisory locked True at the constructor (mirror L2's is_causal enforcement)
- ranking_weights grows to six keys, validated to sum to 10000, with a version string
- V-3 (bundle.action_id == decision.action_id) enforced in the constructor
- reuse require_bp, the L2 predicate grammar and L3's citation byte-identity validator
- integer basis points only; no floats anywhere
ACCEPTANCE: pytest tests/contracts/test_l4_contracts.py -q -> 0 skips;
tests/test_layer_topology.py still green.
```
