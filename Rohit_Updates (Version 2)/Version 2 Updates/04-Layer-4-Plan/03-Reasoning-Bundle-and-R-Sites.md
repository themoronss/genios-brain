# The Reasoning Bundle and the R-Sites — Layer 4's voice

> **The centerpiece of L4 v2.** The founder's requirement, verbatim: *"user ke saamne
> detail jaana chahiye"* — a heading, then the scenario, then what should happen and
> why. Without the reasoning narrative, nothing downstream can polish what does not
> exist.

---

## 1. The gap, precisely

The Theory chat sets the bar for a card body (founder-bottleneck example):

```
WHY THIS MATTERS   6 workflows depend exclusively on you. $230K pipeline...
ROOT CAUSE         Your approval is required for all four workflow categories.
RECOMMENDATION     Delegate operational approvals below $10K to Maya.
EXPECTED EFFECT    ~11 founder interruptions/week potentially eliminated.
```

Today's mechanism (`intelligence.py:263-328`): **one sentence**, validator rejects
directive verbs, numbers, and any ≥4-char word absent from the grounding JSON. The bar
is structurally unreachable. The engine decides well enough to be trusted and is
forbidden from explaining itself well enough to be valued.

## 2. The design law

> **The decision is fixed first. The bundle describes it. The bundle can never amend it.**

Everything the bundle says must trace to material the deterministic run already
produced: unit Findings, evidence refs, L3 citations, computed numbers. The model
supplies **language and arrangement — never facts, never numbers, never the verdict.**

---

## 3. The Reasoning Bundle — typed contract

```python
@dataclass(frozen=True)
class ReasoningBundle:
    headline: str                    # <= 90 chars, the card heading
    situation_summary: str           # what the scenario IS — from L2's M-6 framing,
                                     # carried through, not re-invented
    why_it_matters: str              # implication — impact/risk/urgency evidence, narrated
    root_cause: str                  # the evidence chain as a story
                                     # ("approval required in all four categories, and
                                     #  three of them route only to you")
    recommendation_rationale: str    # why THIS action — citing L3 knowledge verbatim
                                     # ("...because urgency must belong to the buyer")
    expected_effect: str             # from do_nothing_cost_bp + foresight — R-4 framed
    alternatives_narrative: str      # what lost and why — from alternatives_rejected
    citations: tuple[CitationRef, ...]     # L3 artifacts quoted byte-identically
    evidence_refs: tuple[str, ...]         # every claim's receipts
    numbers_used: Mapping[str, int]        # every number in the prose, as data —
                                           # the render substitutes from HERE
    generation: str                  # "llm:<model_snapshot>" | "template_fallback"
    bundle_hash: str                 # cached on (decision_id, inputs hash)
```

**`numbers_used` is the enforcement mechanism for "numbers templated, never generated":**
the prose contains placeholders (`{amount}`, `{days_left}`, `{interruptions_saved}`);
substitution is deterministic at render. A number appearing in prose without a
placeholder fails validation.

## 4. Validation gauntlet (deterministic, after R-2 and before publish)

| # | Check | On failure |
|---|---|---|
| V-1 | every named fact resolves to a Finding or EvidenceRef of THIS run | drop the sentence; below coverage threshold → template fallback |
| V-2 | no bare numbers in prose — placeholders only | reject |
| V-3 | the recommendation described == the decision's action (id-match, not string-match) | **hard reject — the bundle may not amend the decision** |
| V-4 | citations byte-identical to authored artifacts (L3's E-01 validator reused) | reject citation |
| V-5 | no visibility widening — bundle input is pre-filtered by `narrowest()` | structural (input-side) |
| V-6 | expected_effect uses only computed values (`do_nothing_cost_bp`, foresight) with their hypothesis status carried | reject |
| V-7 | length budgets per field (headline 90, others 500 chars) | truncate at sentence boundary |

**Fallback is a real path:** every field has a deterministic template rendering from the
same inputs. A plain card beats a wrong card; `generation: template_fallback` is
recorded so quality is measurable.

## 5. The R-sites in operation

### R-2 · Bundle narrative (the main call, T2)

```
INPUT   (visibility-filtered): decision + components + unit Findings + eliminations +
        L3 citations + M-6 situation framing + computed numbers (as placeholders)
PROMPT  six blocks, same discipline as L1's extractor: ROLE (you describe a decision
        already made; you never alter it) · SAFETY · SCHEMA (the bundle shape) ·
        MATERIAL (the findings, labeled) · EVIDENCE (every claim cites) ·
        PLACEHOLDERS (numbers by name only)
OUTPUT  ReasoningBundle JSON → the gauntlet → publish or fallback
CACHE   (decision_id, material_hash) — a re-render of an unchanged decision is free
```

### R-1 · Ambiguity interpreter (gated, evidence-producing)

The Theory-chat case, kept exactly: *"considering moving workloads"* →
`{classification: proposal, confidence_bp: 7200, quote, offsets}` → **enters the run as
an EvidenceRef** (span-validated, independence-grouped `llm_interpretation`), consumed by
units like any other evidence. Gate: only when a unit declares an input AMBIGUOUS and
the orchestrator's LLM Decision Policy admits it. Recorded non-authoritative in the trace.

### R-3 · Alternatives narration (T1, on expand)

From `alternatives_rejected` (which already carries the eliminating check and utilities):
*"Annual renewal lost on flexibility: the migration discussion is live, and the corpus
rule 'never lock a term during an active platform decision' eliminated it."* Same
gauntlet, V-3 checks it names only actually-rejected candidates.

### R-4 · Expected-effect framing (T1, with R-2)

Numbers from `do_nothing_cost_bp` + foresight; hypothesis-status carried (*"based on
your last 90 days"* only when L7-tuned; otherwise the estimate framing). One sentence,
placeholder-substituted.

### R-5 · Low-confidence consult — reconciled position

**DEFER-to-human remains the default** (the code's stated design: *"it never invents the
missing fact"* — stricter than Globe, and right). R-5 exists only as a targeted
interpretive question over ALREADY-HELD evidence (*"do these three messages constitute a
commitment?"*), under intelligence.py's full validation discipline, recorded
non-authoritative. It may sharpen evidence; it may never fill a missing fact. The spec
deviation (Globe cases 1–2) is hereby reconciled **in the spec's direction of more
caution, documented rather than silent.**

---

## 6. Cost

| Site | Fires | Cache | Est. volume/day |
|---|---|---|---|
| R-2 | per **published** decision (post-floor, post-budget — the existing suppressions are the volume control) | by material hash | 10–40 |
| R-3 | on card expand | by decision | 3–10 |
| R-4 | with R-2 | shared | — |
| R-1 | declared-ambiguous inputs only | by claim hash | 1–5 |
| R-5 | rare, gated | — | 0–2 |

Same shape as L2: low volume, per-situation, cache-dominant. Budget guards and
fail-to-template inherited from doc 11 of the L2 plan.

---

## 7. Acceptance — **K4, the voice gate**

```
pytest tests/reason/test_reasoning_bundle.py -q
python scripts/bundle_quality_report.py --org <pilot> --days 7
```

| Metric | Gate |
|---|---|
| published decisions carrying a full bundle | 100% (fallback counted separately) |
| bundle contradicting its decision (V-3) | **0 — hard fail** |
| bare numbers in prose | **0** |
| unsupported facts per bundle (V-1 drops) | < 5% of sentences |
| **a pilot card showing WHY / ROOT CAUSE / RECOMMENDATION / EXPECTED EFFECT with an L3 citation** | **>= 1 — the founder-bar moment** |
| template-fallback rate | < 15% and falling |
| golden set: 25 decisions hand-checked | every claim traceable |
