# `core.impact` · Stage 6 — Evaluator

**Source:** `impact_unit.py:ImpactUnit.evaluate_meaning` (lines 306–362) and
`IMPACT_ADJUSTMENT_REASON` (line 57)
**Overridden by `ImpactUnit`:** **yes** — `evaluate_meaning` is `@abstractmethod`.

---

## 1 · What it is for

Two questions, in the code's own words:

> *"Is the stake material, and if so how far should it tilt the declared plays?"*

The first is a threshold comparison. The second is the only place in the unit where anything reaches
out and touches a decision candidate — and it is deliberately built so that the unit supplies a
**magnitude** and never a **choice**.

---

## 2 · What exists

### 2.1 · The constant

```python
#: Reason code carried by every adjustment and check this unit emits, so an auditor can ask "what
#: moved this play?" and get an answer that names the stake rather than the unit.
IMPACT_ADJUSTMENT_REASON = "impact_magnitude_at_stake"
```

Note what the name does *not* say: it is not `core_impact_adjustment`. An auditor reading a trace
row six months later gets a business reason — *the magnitude at stake moved this* — rather than a
module name they would then have to go and read.

### 2.2 · The method

```python
def evaluate_meaning(self, view, metrics, observations) -> Verdict:
    impact_bp = metrics.get("impact_bp")
    if impact_bp is None:
        return Verdict(matched=None, metrics=dict(metrics))

    threshold = _config_bp(view, "impact_threshold_bp", 5_000)
    material = impact_bp >= threshold
    evidence = tuple(sorted({item for observation in observations
                             for item in observation.evidence_ids}))
    findings = tuple(Finding(
        finding_id=f"impact.{observation.plugin_id}",
        kind="impact",
        matched=True,
        metrics=observation.metrics,
        evidence_ids=observation.evidence_ids,
        reason_codes=observation.reason_codes,
    ) for observation in observations)

    adjustments: list[CandidateAdjustment] = []
    checks: list[CandidateCheck] = []
    if material:
        authored = _mapping_config(view, "play_impact_bp")
        for play_id in sorted(str(key) for key in authored):
            delta = _delta_bp(authored[play_id], f"play_impact_bp.{play_id}")
            scaled = divide_half_up(delta * impact_bp, 10_000)
            if scaled == 0:
                continue                # a tilt that rounds away is noise in the audit trail
            adjustments.append(CandidateAdjustment(
                play_id=play_id, component="impact", delta_bp=scaled,
                reason_code=IMPACT_ADJUSTMENT_REASON, evidence_ids=evidence))
            checks.append(CandidateCheck(
                play_id=play_id, stage="cost_benefit", outcome=CheckOutcome.ADJUST,
                reason_code=IMPACT_ADJUSTMENT_REASON, evaluator_id=self.unit_id,
                evaluator_version=self.version,
                detail={"impact_bp": impact_bp, "delta_bp": scaled}))

    codes = {code for observation in observations for code in observation.reason_codes}
    codes.add("material_impact" if material else "immaterial_impact")
    return Verdict(matched=material, metrics=dict(metrics), findings=findings,
                   adjustments=tuple(adjustments), checks=tuple(checks),
                   reason_codes=tuple(sorted(codes)))
```

### 2.3 · Config keys

| Key | Type | Default | Read when |
|---|---|---|---|
| `impact_threshold_bp` | bp 0–10,000 | `5_000` | always, once `impact_bp` exists |
| `play_impact_bp` | mapping play_id → int −10,000..10,000 | `{}` | only when `material` is `True` |

`impact_threshold_bp` at 5,000bp says *"half the scale is where a stake becomes worth tilting a play
over."* It has never been fitted to data.

---

## 3 · `matched` — three values, three different statements

`core.impact` is the only unit in Category 2 that uses all three states of
`ReasonerResult.matched`.

| `matched` | Condition | Statement |
|---|---|---|
| `None` | `impact_bp` absent — no dimension reported | **"I have no opinion."** Not "this is immaterial" |
| `False` | `impact_bp < impact_threshold_bp` | **"I measured the stake and it is below the bar."** A real, evidenced claim |
| `True` | `impact_bp >= impact_threshold_bp` | **"I measured the stake and it is material."** |

> *"`matched` is None when no dimension reported — the unit has no opinion, which is a different
> statement from 'this is immaterial' and must not be collapsed into False."*

The collapse would be invisible and expensive. Downstream, `validation_unit.py:_asserts_a_claim`
treats `matched is True` as a claim requiring evidence; `decision_maker.py` reads
`ReasonerResult.matched` when deciding what a run actually established. Reporting `False` for an
unmeasured stake would mean the system asserting *"we checked, and this deal is small"* about a deal
it never priced.

The early return also carries **no findings, no adjustments, no checks and no reason codes** — just
`metrics`, which at that point is `{"impact_signal_count": 0}`. Nothing is asserted, and the count
is left visible so a reader can see that the unit ran and found nothing measurable.

---

## 4 · Findings

One `Finding` per observation, always, whenever `impact_bp` exists:

| Field | Value |
|---|---|
| `finding_id` | `f"impact.{observation.plugin_id}"` — `impact.revenue_exposure`, `impact.account_importance`, `impact.strategic_linkage` |
| `kind` | `"impact"` — the same for all three |
| `matched` | **`True`, unconditionally** |
| `metrics` | the observation's metrics verbatim, including `exposure_value` and `linked_goal_count` |
| `evidence_ids` | the observation's citations — empty for the `relationship_footprint` fallback |
| `reason_codes` | the observation's codes |

Two things about that table are worth stopping on.

**Findings survive an immaterial verdict.** They are constructed *before* the `if material:` branch,
so a run with `matched=False` still emits three `matched=True` findings. This is the opposite of
`core.opportunity`, which suppresses findings below its threshold, and the two units make opposite
calls in the same category. The impact reading is defensible — the dimensions really were measured
and the readings really are true, independent of whether the total clears a bar — but it has a
downstream consequence: `validation_unit.py:_asserts_a_claim` returns `True` for
*"any finding that is not an explicit negative"*, so even an immaterial `core.impact` result counts
as a claim that must be grounded.

**`matched=True` on the finding means "this dimension reported", not "this dimension is large".**
A `revenue_exposure` finding with `strength_bp = 0` — the `deal.value = 1` case — is still
`matched=True`. The finding asserts the reading, not a judgement about it.

---

## 5 · Adjustments and checks — the play tilt

### 5.1 · Why the unit is allowed to touch a candidate at all

Everything about this block is arranged so that the unit contributes magnitude and nothing else.

```text
WHICH plays can be tilted   → whatever keys the capability author put in play_impact_bp
HOW FAR each may be tilted  → the author's delta, as a CEILING
HOW FAR it IS tilted        → the author's ceiling × the measured impact
WHO chooses the winner      → decision_maker.py, from the resulting utility
```

> *"Where large stakes should make a play more attractive, the tilt is authored in Layer 3 as
> `play_impact_bp: {play_id: delta}` and merely scaled here by the measured impact. The unit
> supplies the magnitude; the capability author supplies the judgement about which play the
> magnitude favours; the Decision Maker does the actual choosing. Hardcoding play names here would
> make this unit a decision authority by the back door."*

**No play id appears anywhere in `impact_unit.py`.** Every play id the unit ever names came out of
`view.config`.

### 5.2 · The scaling arithmetic

```text
scaled = divide_half_up(delta × impact_bp, 10_000)
```

> *"Adjustments are scaled by the measured impact, so the author's delta is the ceiling reached at a
> maximal stake rather than a flat bonus applied to anything that clears the threshold."*

The alternative — apply the full `delta` to anything above the threshold — would make a
5,001bp stake and a 10,000bp stake tilt a play identically, and would put a step discontinuity right
where the decision is most contested. Scaling makes the tilt continuous in the stake above the
threshold.

| `impact_bp` | `delta = 2,000` | `delta = 400` |
|---|---|---|
| 5,000 (the bar) | 1,000 | 20 |
| 6,000 | 1,200 | 240 → *see below* |
| 8,050 (Northwind) | 1,610 | 322 |
| 10,000 (saturated) | 2,000 | 400 |

*(the 6,000 / 400 cell is `divide_half_up(400 × 6,000, 10,000) = 240`.)*

Half-up division on the full product, once — never on a per-term intermediate.

### 5.3 · Every tilt is mirrored by a check

```python
checks.append(CandidateCheck(
    play_id=play_id, stage="cost_benefit", outcome=CheckOutcome.ADJUST,
    reason_code=IMPACT_ADJUSTMENT_REASON, evaluator_id=self.unit_id,
    evaluator_version=self.version,
    detail={"impact_bp": impact_bp, "delta_bp": scaled}))
```

> *"Each adjustment is mirrored by a `cost_benefit` check so the tilt shows up in the audit trail
> next to the score it moved, instead of appearing as an unexplained component delta."*

The adjustment changes a number; the check explains it. Without the check, an auditor reading
`DecisionCandidate.score_components["impact"] = 6,610` where the play declared 5,000 would see a
1,610bp delta with no row anywhere saying who moved it or why. `detail` carries both halves of the
arithmetic — the measured `impact_bp` and the resulting `delta_bp` — so the multiplication is
re-derivable from the trace alone.

`"cost_benefit"` is a member of `guards.py:CHECK_STAGES`, and `"impact"` is a member of
`guards.py:CANDIDATE_COMPONENTS`. Both are closed sets re-validated at the orchestrator boundary by
`validate_candidate_effects`; an unknown component or stage is a deployment fault, never a silent
no-op. `validate_candidate_effects` also rejects an adjustment naming a play the capability never
declared — so an author who mistypes a key in `play_impact_bp` gets a `FAILED` result, not a lost
tilt.

`CheckOutcome.ADJUST` is not `PASS`, `WARN` or `ELIMINATE`. `decision_maker.py:evaluate_candidates`
eliminates only on `CheckOutcome.ELIMINATE`, so an impact check can never remove a candidate. The
unit's entire influence is a bounded, signed nudge to one score component.

### 5.4 · Two determinism details

**`sorted(str(key) for key in authored)`** — iteration over authored config is alphabetical by play
id, so the adjustment and check tuples are byte-stable regardless of how the manifest dict was
written. Their order reaches `ReasonerResult.semantic_hash`.

**`evidence` is computed once, from all observations, and attached to every adjustment.** Not
per-play: the stake that justifies the tilt is the blended one, and the blended one stands on every
dimension's citations. `decision_maker.py:aggregate_evidence` unions
`adjustment.evidence_ids` into the decision's evidence set, so a tilt carries its provenance into
the decision object even though it is not a finding.

### 5.5 · The rounds-to-zero guard

```python
if scaled == 0:
    continue                # a tilt that rounds away is noise in the audit trail
```

An adjustment of `delta_bp = 0` would be a real row in the trace, a real `CandidateCheck`, and a
real change of exactly nothing.

**At the default threshold this guard is unreachable.** The smallest positive product is
`delta = 1 × impact_bp = 5,000 = 5,000`, and `divide_half_up(5,000, 10,000) = 1`. It becomes
reachable the moment a capability lowers `impact_threshold_bp`:

```text
config  impact_threshold_bp = 1,000 · play_impact_bp = {"executive_escalation": 1}
facts   deal.value = 60,000, reference 200,000  →  impact_bp = 3,000

3,000 >= 1,000 → material
scaled = divide_half_up(1 × 3,000, 10,000) = (3,000 + 5,000) // 10,000 = 0
→ dropped

result  matched True · impact_bp 3,000 · adjustments () · checks ()
```

Verified against the live unit. Note the asymmetry this creates: the result says `matched=True` and
carries `material_impact`, but tilts nothing. A downstream reader who inferred "material implies an
adjustment" would be wrong.

Negative deltas round toward zero the same way, because `divide_half_up` mirrors the positive
branch: `divide_half_up(-3,000, 10,000) = -((3,000 + 5,000) // 10,000) = 0`.

---

## 6 · Reason codes

```python
codes = {code for observation in observations for code in observation.reason_codes}
codes.add("material_impact" if material else "immaterial_impact")
return Verdict(..., reason_codes=tuple(sorted(codes)))
```

The union of every dimension's codes, plus **exactly one** verdict code. A set, then sorted — so
`linked_to_strategic_initiative` appearing twice collapses to one, and the tuple is byte-stable.

| Code | Emitted by | Means |
|---|---|---|
| `revenue_at_stake` | `revenue_exposure` | a positive deal value was read |
| `named_account_tier` | `account_importance` | an explicit tier classification was priced |
| `relationship_footprint` | `account_importance` | the coverage proxy stood in for a tier |
| `linked_to_capability_goal` | `strategic_linkage` | tagged to the capability's own goal |
| `linked_to_strategic_initiative` | `strategic_linkage` | tagged to a priced initiative |
| `material_impact` | the Evaluator | `impact_bp >= impact_threshold_bp` |
| `immaterial_impact` | the Evaluator | `impact_bp < impact_threshold_bp` |

The `matched=None` path emits **none of these** — not even a code saying the unit found nothing.
`impact_signal_count = 0` is the only trace, and it is a metric rather than a reason code.

---

## 7 · Worked examples

### 7.1 · Material, one authored play — Northwind

```text
metrics       impact_bp 8,050
config        impact_threshold_bp default 5,000
              play_impact_bp {"executive_escalation": 2000}

8,050 >= 5,000 → material True
evidence      = ("ev_init", "ev_tier", "ev_value")      # union of all three observations
findings      = impact.account_importance · impact.revenue_exposure · impact.strategic_linkage
                (plugin_id order, all matched=True)

play loop, sorted(["executive_escalation"])
  delta  = 2,000                                        # passes _delta_bp
  scaled = divide_half_up(2,000 × 8,050, 10,000)
         = (16,100,000 + 5,000) // 10,000 = 1,610

  CandidateAdjustment(play_id="executive_escalation", component="impact",
                      delta_bp=1610, reason_code="impact_magnitude_at_stake",
                      evidence_ids=("ev_init", "ev_tier", "ev_value"))
  CandidateCheck(play_id="executive_escalation", stage="cost_benefit",
                 outcome=ADJUST, reason_code="impact_magnitude_at_stake",
                 evaluator_id="core.impact", evaluator_version="1.0.0",
                 detail={"impact_bp": 8050, "delta_bp": 1610})

reason_codes = ("linked_to_strategic_initiative", "material_impact",
                "named_account_tier", "revenue_at_stake")
```

The play declared `impact_bp = 5,000`, so `synthesize_candidates` computes
`components["impact"] = clamp_bp(5,000 + 1,610) = 6,610`. At the default
`ranking_weights["impact"] = 35`, that contributes `6,610 × 35 = 231,350` to the utility numerator,
which `score_candidate` divides by 100 at the end. The tilt's marginal effect on the final utility
is `1,610 × 35 / 100` = **≈564bp** — the single half-up rounding happens once, on the whole sum.

Pinned by `test_a_material_stake_tilts_only_the_plays_the_capability_authored`,
`test_every_tilt_is_mirrored_by_an_auditable_check`, and the Northwind end-to-end test.

### 7.2 · Barely material — the ceiling scales down

```text
facts   deal.value 120,000, reference 200,000  →  revenue 6,000 → impact_bp 6,000
config  play_impact_bp {"executive_escalation": 2000}

6,000 >= 5,000 → material
scaled = divide_half_up(2,000 × 6,000, 10,000) = 1,200

adjustments = [("executive_escalation", "impact", 1200)]
```

Pinned by `test_the_authored_delta_is_a_ceiling_scaled_by_the_measured_stake` — *"A barely-material
deal must not get the same push as a company-defining one."* The same authored 2,000bp ceiling
produced 1,610 at Northwind and 1,200 here.

### 7.3 · Immaterial — the size is reported, the contest is not entered

```text
facts   deal.value 20,000, reference 200,000  →  revenue 1,000 → impact_bp 1,000
config  play_impact_bp {"executive_escalation": 2000}

1,000 < 5,000 → material False
play_impact_bp is NEVER READ                # the whole block is inside `if material:`

result  matched False
        impact_bp 1,000 · revenue_exposure_bp 1,000 · impact_signal_count 1
        adjustments () · checks ()
        findings  impact.revenue_exposure, matched=True
        reason_codes ("immaterial_impact", "revenue_at_stake")
```

Pinned by `test_an_immaterial_stake_tilts_nothing` — *"Below the declared threshold the unit reports
the size and stays out of the contest."* Note that `_delta_bp` is never called here, so a **malformed**
`play_impact_bp` entry passes unnoticed on an immaterial run and raises on the next material one.

### 7.4 · No opinion

```text
metrics       {"impact_signal_count": 0}
impact_bp     None → early return

Verdict(matched=None, metrics={"impact_signal_count": 0})
        findings () · adjustments () · checks () · reason_codes ()
```

`impact_threshold_bp` is not read on this path either — an entirely malformed threshold is invisible
to a run that measured nothing.

### 7.5 · A negative tilt

```text
facts   deal.value 200,000, reference 200,000 → impact_bp 10,000
config  play_impact_bp {"executive_escalation": -2000}

scaled = divide_half_up(-2,000 × 10,000, 10,000) = -2,000
adjustment  delta_bp = -2,000
check       detail = {"impact_bp": 10000, "delta_bp": -2000}
```

Verified. *"An adjustment delta may be negative — a large stake can also make a cheap play look
worse."* A play whose value is that it is quick and low-touch legitimately becomes *less* attractive
when the stake is enormous. `CandidateAdjustment.__post_init__` permits −10,000..10,000, and
`synthesize_candidates` clamps the resulting component into 0..10,000.

### 7.6 · A malformed authored delta is loud

```text
config  play_impact_bp {"executive_escalation": 40000}
facts   deal.value 200,000, reference 200,000 → impact_bp 10,000 → material

_delta_bp(40000, "play_impact_bp.executive_escalation")
  → ValueError: play_impact_bp.executive_escalation must be an integer between -10000 and 10000
  → orchestrator records ResultStatus.FAILED
```

Pinned by `test_a_malformed_authored_delta_is_a_loud_capability_fault` — *"Silently coercing bad
tuning would let a broken manifest reprice plays undetected."*

---

## 8 · Edge cases

| Situation | Behaviour |
|---|---|
| `impact_bp` exactly equals `impact_threshold_bp` | material — the comparison is `>=` |
| `impact_threshold_bp = 0` | every run with any reading is material, including `impact_bp = 0` |
| `impact_threshold_bp = 10_000` | only a fully saturated stake tilts anything |
| `play_impact_bp` empty or absent | material verdict, `matched=True`, **zero** adjustments and checks. Legal and common — the shipped `deal_cooling_v2` is the only capability that authors any |
| `play_impact_bp` names a play the capability never declared | `guards.py:validate_candidate_effects` raises at the orchestrator boundary → `FAILED` |
| `play_impact_bp` key is not a string | `sorted(str(key) for key in authored)` stringifies it, then `authored[play_id]` — a `KeyError` if the string form is not the original key. Only reachable with a non-string key, which `contracts/reasoning.py:_freeze` already coerces to `str` at manifest construction |
| Two plays authored | two adjustments and two checks, in sorted play-id order |
| `play_impact_bp` value is `True` | `_delta_bp` rejects `bool` → `FAILED` |
| Observations present but all with empty `evidence_ids` | `evidence` is `()`; adjustments carry no citations, and the whole result is an ungrounded claim to `core.validation` |

---

| ← | → |
|---|---|
| [04 · Calculator](04-Calculator.md) | [06 · Builder and Metrics](06-Builder-and-Metrics.md) |
