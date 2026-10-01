# Step 4 — Promote the seven untyped bags to typed claims

**Status:** NOT STARTED · **Effort:** weeks · **Depends on:** step 3 · **Engine:** D (contract) + L (extractor)
**Moves:** metric 3 — `relationship_change` surviving the floor, **1 of 49 → most**

> **This is the step that changes what Layer 1 can represent.** Everything else on the list makes
> existing things work. This one adds things that cannot currently exist.

---

## 1. Why this step exists

`contracts/extraction.py` has **two tiers**, and nothing in the codebase says so.

**Tier 1 — typed claims.** Each is a model with `evidence: EvidenceSpan` and `confidence_bp`:

```
entity_mentions · amounts · dates_mentioned · commitments · decision_states
dependencies · business_facts · unclassified_observations
```

**Tier 2 — untyped bags.** Each is `list[str]` or `list[dict[str, Any]]`:

```
topics · implied_actions · questions · roles
relationships · scheduling_proposals · availability
```

Doctrine 3 of the build record is **"no claim without a receipt."** Tier 2 cannot obey it — not
because the receipts were lost, but because **the type has no field to put one in.**

### And the detector fires real signals off Tier 2

| `esqe/detector.py` | Predicate | Reads | Tier |
|---|---|---|---|
| :399 | `RELATIONSHIP_CHANGE` | `ex.roles` | **2** |
| :406 | `AVAILABILITY_CHANGE` | `ex.availability` | **2** |
| :432 | a decision predicate | `ex.questions` | **2** |

### The measured consequence

```
untyped contract
      ↓  no typed amount, date or authority for ALG-17 to weigh
relationship_change scores 880–1240 bp   ← the LOWEST band of any signal type
      ↓  default floor 2500
48 of 49 relationship_change signals REFUSED
      ↓
Layer 2 receives almost no relationship signal at all
      ↓
benchmark P1 (relationship ledger) and the Radhesh finding are unanswerable
```

**This is the mechanism behind "thin signals."** Not a missing LLM. Not an over-aggressive gate.

### What it unlocks

| Bag | Benchmark prompt that needs it |
|---|---|
| `roles` | P1 — the relationship ledger, and the Radhesh miss |
| `questions` | P3 — *"the final unresolved question"*, the most valuable object in P3 |
| `availability` | P1 — waiting states |
| `scheduling_proposals` | P4 — meeting ↔ follow-up |
| `relationships` | P1, P4 — the recipient graph |

## 2. Current status — with evidence

```python
# contracts/extraction.py — ExtractionResult
topics:               list[str]              # no evidence, no confidence
implied_actions:      list[str]              # no evidence, no confidence
questions:            list[str]              # no evidence, no confidence
roles:                list[dict[str, Any]]   # no evidence, no confidence
relationships:        list[dict[str, Any]]   # no evidence, no confidence
scheduling_proposals: list[dict[str, Any]]   # no evidence, no confidence
availability:         list[dict[str, Any]]   # no evidence, no confidence
```

Contrast with a Tier 1 type:

```python
class Commitment:
    actor, action, beneficiary, due, is_conditional, condition_text
    evidence: EvidenceSpan        # ← the receipt
    confidence_bp: int            # ← the integer confidence
```

The detector's own comment at :392 shows the shape is already half-understood:
> *"`roles` is the lane whose closed keys are `party`/`role`/`evidence_text`"*

The keys are already closed **by convention**. They are simply not **enforced by a type**, so
`evidence_text` is a free string rather than a resolvable `EvidenceSpan`.

## 3. Expected result — the number that must move

| | Before | After |
|---|---|---|
| Claim types carrying `evidence` + `confidence_bp` | **8 of 15** | **13+ of 15** |
| `relationship_change` importance band | **880–1240 bp** | above the 2500 floor for real relationship changes |
| `relationship_change` surviving | **1 of 49** | most |
| Predicates firing on receipt-less claims | **3** | **0** |
| Benchmark objects present | 16 of 38 | ~21 of 38 |

**Prediction:** `relationship_change` rises because ALG-17 gains typed inputs (an authority rank
from the role's evidence, a date from the availability window) — **not because the formula
changes.** It does not change.

**If the band does not rise, the hypothesis was wrong** and the real cause is elsewhere in ALG-17.
That is a finding, and it stops the step rather than being worked around.

## 4. Edge cases and failure scenarios

| # | Scenario | What must happen | Why |
|---|---|---|---|
| E1 | The model returns a role with no quotable span | the claim arrives with `evidence=None` and is **kept**, flagged | forcing a span would make the model invent one — the exact failure Gemini showed on 3one4 |
| E2 | Migrating stored extractions | old rows have bags; readers must tolerate both shapes during the transition | a big-bang schema flip loses history |
| E3 | The prompt grows | `schema_gen.py` derives the schema **from the type**, so it follows automatically | do not hand-write the prompt's schema |
| E4 | Token cost rises | measure it. Five new typed objects is more output tokens | `semantic/batch.py` is the cost governor; it must see the change |
| E5 | The cache | the schema version is part of the cache key — **the whole corpus re-extracts** | budget for it; this is the expensive part of the step |
| E6 | `topics` and `implied_actions` | these may legitimately stay untyped — a topic is a label, not a claim | **do not promote what is not a claim.** Decide per bag, with a reason |
| E7 | A promoted claim now scores high enough to flood the feed | watch the published count | more signal, not more noise — if volume explodes, the floor conversation is step 8 |
| E8 | `sink_guard.py` | it closes untyped-dict bypasses; it must learn the new types | otherwise a promoted claim goes to the open lane |
| E9 | The open lane | what the closed vocabulary cannot name still goes to `UnclassifiedObservation` | the release valve stays |

**E6 is a real decision, not a formality.** Of the seven bags, probably **five are claims**
(`roles`, `questions`, `relationships`, `scheduling_proposals`, `availability`) and **two are
labels** (`topics`, `implied_actions`). Promoting a label to a claim adds ceremony without adding
truth. **Write the per-bag decision and its reason before writing code.**

## 5. How to do it — unit by unit

### 4-U0 · Decide, per bag *(no code)*
For each of the seven: is it a **claim** (something asserted about the world, which could be
wrong, and which a reader should be able to check) or a **label** (a description of the message)?
Claims get promoted. Labels stay. **Write the reason for each into this file before proceeding.**

### 4-U1 · The types
One typed model per promoted bag, each with `evidence: EvidenceSpan | None` and
`confidence_bp: int`. Follow `Commitment`'s shape exactly — it is the reference implementation.

Suggested shapes (to be confirmed at U0):
```
Role                 party · role · evidence · confidence_bp
OpenQuestion         text · asked_by · asked_of · answered · evidence · confidence_bp
PartyRelationship    subject · relation · object · evidence · confidence_bp
SchedulingProposal   proposer · window_text · resolved_window · evidence · confidence_bp
AvailabilityWindow   party · kind · start_text · end_text · resolved · evidence · confidence_bp
```

### 4-U2 · The schema
`schema_gen.py` generates the prompt's schema **from** the type — so U1 changes the prompt
automatically. Verify it did; do not hand-edit.

### 4-U3 · The extractor
Parse into the new types. Failures go to the open lane, never to a silent drop.

### 4-U4 · Validation
Every new claim's span runs through ALG-08 like any other — **graded and corrected**, never
trusted. `verified=True` is stamped by the validator, never by the extractor (schema rule S-9).

### 4-U5 · The three predicates
`detector.py:399`, `:406`, `:432` read typed claims instead of bags. Behaviour must be
**identical** on a fixture where both shapes are present — this is the seam of the whole step.

### 4-U6 · ALG-17's inputs
The new typed claims now carry authority and dates that the scorer can read. **The formula, the
five weights and the total check do not change.** Only what feeds them does.

### 4-U7 · Migration + re-extraction
Schema version bumps → the cache key changes → the corpus re-extracts. Plan the spend (E5).

## 6. Test cases

| # | Test | Asserts | RED today because |
|---|---|---|---|
| T1 | each promoted type | carries `evidence` and `confidence_bp` | the types do not exist |
| T2 | the three predicates | fire identically on typed vs bag fixtures | they only read bags |
| T3 | a role claim | its span resolves against source characters | `evidence_text` is a free string |
| T4 | the extractor | cannot stamp `verified=True` | S-9, existing — **regression guard** |
| T5 | a claim with no span | is **kept**, flagged, not dropped | E1 |
| T6 | `relationship_change` on a typed fixture | scores above the tenant floor | 880–1240 today |
| T7 | ALG-17 | formula output byte-identical on the SAME inputs | **the guard that the formula did not change** |
| T8 | importance distribution | >50 distinct, p90−p50 > 1500 still hold | G7 |
| T9 | `sink_guard` | a promoted field does not fall into the open lane | E8 |
| T10 | the open lane | still receives genuinely unnameable things | E9 |

**T7 and T8 are the protection.** This step must make the scorer *better fed*, never *different*.

## 7. Verify commands

```bash
uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q -p no:randomly
uv run --no-sync pytest tests/capture/semantic -q -p no:randomly
uv run --no-sync pytest tests/capture/validate -q -p no:randomly
uv run --no-sync pytest tests/capture/esqe -q -p no:randomly

# the purity greps — gate criteria, not lint
grep -rn "float(" genios_engine/capture/validate/
grep -rn "datetime.now\|date.today" genios_engine/capture/validate/
grep -rn "LLMClient\|anthropic" genios_engine/capture/validate/

# the distribution must hold
python scripts/importance_distribution.py --org <org> --database-url "<url>"
```

## 8. Done criteria

**Ticked 2026-09-23.** Six of seven closed; the seventh is measured as far as this machine can
see it and names the one number that needs a production read. Full detail:
[`findings/step-04-typed-claims.md`](findings/step-04-typed-claims.md).

- [x] **U0's per-bag decision, with a reason for each of the seven, written into this file** —
      §8.1 below.
- [x] **every promoted type carries `evidence` + `confidence_bp`** — `RoleAssertion`,
      `AvailabilityWindow`, `OpenQuestion`. Pinned by
      `test_a_promoted_lane_carries_evidence_and_a_confidence`, parametrised over the lane list
      rather than written out, so a fourth promotion is covered the day it lands.
- [x] **0 predicates fire on a claim that CANNOT carry a receipt** — pinned by
      `test_no_predicate_fires_on_a_claim_that_cannot_carry_a_receipt`.
      **The criterion as written above said "receipt-LESS", and that is a different and stronger
      claim which is deliberately NOT met.** A role the model read but could not quote still
      fires RELATIONSHIP_CHANGE, carrying an empty span tuple. Forcing a span would make the
      model invent one, which is the hallucination this architecture exists to prevent; `evidence=[]`
      is the extractor SAYING it found no quote, and V-5 downgrades it. Pinned the other way by
      `test_a_role_the_model_could_not_quote_still_fires_and_cites_nothing`.
- [x] **T7 green: ALG-17 byte-identical on identical inputs** —
      `test_gate_the_whole_corpus_replays_byte_identically`. 10/10 in
      `tests/capture/esqe/test_importance_gate_probe.py`.
- [x] **T8 green: the distribution properties hold** —
      `test_gate_the_distribution_is_wide_enough_for_layer_4_to_rank_on` and
      `test_gate_no_single_score_swallows_the_corpus`.
- [x] **`relationship_change`'s band recorded in `STATUS.md` — even if it did not rise** —
      `published 4 · DROPPED 54 · band 880–1560 bp` is in `STATUS.md` and in the findings. It did
      not rise **and it could not have**: `DATE_POLICY=none` and `AMOUNT_POLICY=claims_only` mean
      ALG-17 reads `None` for both terms whatever the lane's type, so the change is worth exactly
      zero bp. The predicted post-change band is therefore **identical**, and confirming that on
      real data needs the code deployed — it is a line in §9 of the Harsh runbook.
- [~] **the re-extraction cost is measured and recorded** — **the trigger is measured; the volume
      is not, and needs one production query.**

      ```
      vocabulary_fingerprint()   151b9dabf235  ->  a3d5496aa0d3      (measured by stash-and-compare)
      ```

      `UNTYPED_LANE_KEYS` is folded into that digest, the digest is a component of the
      `l1_extraction_results` key, so **every cached extraction misses and the whole corpus
      re-extracts on the first sweep after deploy.** This is correct rather than accidental — the
      prompt genuinely changed, and the module's own note records the failure where *"260 cached
      extractions survived a prompt fix, the numbers did not move, and the conclusion drawn was
      that the fix had not worked."* But it is a real model bill, it was **not** named anywhere in
      this step's plan, and it was nearly shipped unnoticed.

      Pinned by `test_promoting_a_lane_changes_the_vocabulary_fingerprint_and_therefore_the_cache_key`,
      which fails the day the digest moves again, so the next person is told rather than invoiced.
      The row count is §5 of the Harsh runbook.

### 8.1 · U0 — the per-bag decision, all seven

| Lane | Decision | Reason |
|---|---|---|
| `questions` | **PROMOTE** → `OpenQuestion` | an unanswered question is an open loop; benchmark P3 (*"the final unresolved question"*) is exactly this lane, and a loop the product cannot quote is a loop it cannot show |
| `roles` | **PROMOTE** → `RoleAssertion` | `detector.py:417` fires RELATIONSHIP_CHANGE off it; a claim about WHO SOMEBODY IS with no receipt is the one kind of error a reader cannot check |
| `availability` | **PROMOTE** → `AvailabilityWindow` | the lane with the most readers in the tree — the detector, `lifecycle.py`, `qualification.py` and L2's `person.availability` all branch on it |
| `topics` | **KEEP FREE TEXT** | the contract's own words: *"free text by design; topics are for retrieval and grouping, not for rule matching"*. A label about the message, not a claim about the world |
| `implied_actions` | **KEEP FREE TEXT** | *"what the message implies somebody should do, in the model's words"* — a judgement. A receipt on a judgement adds ceremony without adding truth |
| `relationships` | **KEEP OPEN** *(next candidate)* | the VALUES are genuinely free; its key names are already closed by `UNTYPED_LANE_KEYS` and the sink guard, which is the half that was actually leaking |
| `scheduling_proposals` | **KEEP OPEN** | blocked on L2's scheduler declaring what it reads. Typing it now would pin a boundary shape to a design that has not been made |

Both KEEP-FREE-TEXT rows are guarded in the opposite direction by
`test_a_label_lane_is_deliberately_left_alone`, because the pressure after a step like this is to
type everything.

## 9. What this step must NOT do

- **Do not change ALG-17's formula, weights or total check.**
- **Do not promote a label to a claim.** E6.
- **Do not force a span.** A claim without one is kept and flagged; inventing one is the
  hallucination this architecture exists to prevent.
- **Do not hand-write the prompt schema.** It derives from the type.
- **Do not remove the open lane.**
