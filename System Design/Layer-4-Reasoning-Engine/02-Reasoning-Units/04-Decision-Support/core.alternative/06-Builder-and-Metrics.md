# 06 · Builder and Metrics — `core.alternative`

**Stages 7–8 of eight.** Stage 7 is the base class implementation, unchanged. Stage 8 is a class
attribute plus a guard the framework applies between stages 6 and 7.

---

## 1 · What it is for

Stage 7 assembles the one object shape every unit in the layer returns, so that seventeen units
produce one thing a reviewer, a store, a verifier and a replayer can each handle without knowing
which unit made it. Stage 8 is the declaration that says what this unit is allowed to publish — and
the guard that refuses anything else *before* the object exists.

---

## 2 · What exists

### 2.1 · Stage 8 · the guard, which runs first

Despite the numbering, the `publishes` check sits **between** the Evaluator and the Builder
(`unit.py:256-262`):

```python
undeclared = sorted(set(verdict.metrics) - set(self.publishes)) if self.publishes else []
if undeclared:
    raise ValueError(f"{self.unit_id} published undeclared metrics: {', '.join(undeclared)}")
return self.build(view, verdict, observations)
```

Placing it before `build` means the failure reads *"this unit is misdeclared"* rather than *"this
result contains something surprising"*. `core.alternative` declares a non-empty tuple, so it is not
in the framework's escape hatch for units with an empty `publishes`.

```python
# alternative_unit.py:304-305
publishes = ("declared_count", "viable_count", "distinct_count", "duplicate_count",
             "option_count", "has_alternative", "do_nothing_baseline_bp")
```

`calculate` returns exactly those seven names, so `undeclared` is always empty and the guard has
never fired in this unit's history. It exists for the eighth metric someone adds tomorrow.

### 2.2 · Stage 7 · the Builder, unchanged

`AlternativeUnit` does **not** override `build`. One unit in the roster does (`core.confidence`);
this is not it. The inherited implementation is `unit.py:223-241`:

```python
def build(self, view: UnitView, verdict: Verdict,
          observations: Sequence[Observation]) -> ReasonerResult:
    evidence = set(view.evidence_ids)
    for observation in observations:
        evidence.update(observation.evidence_ids)
    return ReasonerResult(
        reasoner_id=self.unit_id,
        reasoner_version=self.version,
        status=ResultStatus.COMPLETED,
        matched=verdict.matched,
        metrics={name: clamp_bp(value) if name.endswith("_bp") else value
                 for name, value in verdict.metrics.items()},
        findings=verdict.findings,
        adjustments=verdict.adjustments,
        checks=verdict.checks,
        evidence_ids=tuple(sorted(evidence)),
        reason_codes=verdict.reason_codes,
    )
```

Four things it does for this unit:

| What | Effect here |
|---|---|
| Stamps identity and status | `reasoner_id = "core.alternative"`, `reasoner_version = "1.0.0"`, `status = COMPLETED` |
| Clamps `_bp` metrics | Touches exactly one of seven: `do_nothing_baseline_bp`. The six counts pass through untouched, which is correct — `declared_count = 12` must not become `10,000`-adjacent nonsense |
| Unions evidence | `view.evidence_ids` (empty) ∪ every observation's `evidence_ids` (all empty) = `()` |
| Carries the Verdict's tuples straight through | `adjustments = ()` and `checks = ()`, because the Evaluator never assigned them |

The clamp is redundant for this unit but not harmless to remove: `do_nothing_baseline_bp` already
passed through `clamp_bp` inside `DoNothingBaselinePlugin`, and `_prior_bp` clamped its input too.
Three clamps on one value is the framework being defensive at a boundary it does not control.

---

## 3 · What the `ReasonerResult` carries

Taking the canonical five-play run, re-derived live:

```text
ReasonerResult(
  reasoner_id       = "core.alternative"
  reasoner_version  = "1.0.0"
  status            = ResultStatus.COMPLETED
  matched           = True

  metrics = {
    "declared_count":          5,
    "viable_count":            4,
    "distinct_count":          3,
    "duplicate_count":         1,
    "option_count":            4,
    "has_alternative":         1,
    "do_nothing_baseline_bp":  7500,
  }

  findings = (
    Finding("alternative.viability:accept_partial_scope",  "alternative", True,
            {viable 1, expected_value_bp 3000, elimination_count 0}, (), ("option_available",)),
    Finding("alternative.viability:auto_send_reminder",    "alternative", False,
            {viable 0, expected_value_bp 4200, elimination_count 1}, (),
            ("option_eliminated_upstream", "read_only_policy")),
    Finding("alternative.viability:escalate_to_sponsor",   "alternative", True,  ...),
    Finding("alternative.viability:reply_to_buyer",        "alternative", True,  ...),
    Finding("alternative.viability:reply_to_buyer_v2",     "alternative", True,  ...),
    Finding("alternative.signature:reply_to_buyer",        "alternative", False,
            {group 3, group_size 2}, (), ("plays_share_one_move",)),
    Finding("alternative.signature:reply_to_buyer_v2",     "alternative", False, ...),
    Finding("alternative.do_nothing",                      "alternative", True,
            {do_nothing_baseline_bp 7500, signal_count 3}, (),
            ("exposure_compounds", "headroom_lapses", "inaction_has_a_price", "momentum_decays")),
    Finding("alternative.option_set",                      "alternative", True,
            all seven metrics, (), all eleven reason codes),
  )

  adjustments  = ()
  checks       = ()
  evidence_ids = ()
  missing_fields = ()
  reason_codes = ("exposure_compounds", "false_choice_in_roster", "genuine_choice_available",
                  "headroom_lapses", "inaction_has_a_price", "momentum_decays",
                  "option_available", "option_eliminated_upstream", "play_is_a_distinct_move",
                  "plays_share_one_move", "read_only_policy")

  semantic_hash = 7e7066301ed10826b1ca372df03bee4a212d7ddf5e9dee615176b8dde4021182
)
```

`ReasonerResult.__post_init__` re-validates on the way in: every `_bp`-suffixed metric must be an
integer in 0–10,000, and `evidence_ids`, `missing_fields` and `reason_codes` are deduplicated and
sorted. `Finding.__post_init__` applies the same `_bp` rule to finding metrics — which is why
`expected_value_bp` and `do_nothing_baseline_bp` inside findings are also constrained to the scale.

### 3.1 · The empty tuples, and why each is empty

| Field | Value | Reason |
|---|---|---|
| `adjustments` | `()` | *"No adjustment, no check, no candidate ever leaves this unit… Saying which of the three to take is synthesis, and GeniOS has exactly one synthesis authority."* Pinned by `test_the_unit_never_touches_a_candidate` |
| `checks` | `()` | same. This unit **reads** checks; it emits none |
| `evidence_ids` | `()` | no `required_fields`, so `view.evidence_ids` is empty; no plugin attaches evidence to an observation. See §5 |
| `missing_fields` | `()` | only populated on an `INSUFFICIENT_CONTEXT` result |

---

## 4 · The published metrics in full

| Metric | Range | Meaning | What it is **not** |
|---|---|---|---|
| `declared_count` | 1–n | How many plays the capability's manifest declares | not how many are usable |
| `viable_count` | 0–`declared_count` | How many survived both viability screens | not how many distinct things they are |
| `distinct_count` | 0–`viable_count` | How many genuinely different **moves** the survivors amount to | not a ranking, and not a recommendation to take any of them |
| `duplicate_count` | 0–`viable_count − 1` | Viable plays folded into a move another viable play already covers | not a count of duplicates in the manifest — an eliminated duplicate does not count |
| `option_count` | **1**–n | `distinct_count + 1`. The moves plus the null option | never 0; the null option never leaves the table |
| `has_alternative` | 0 or 1 | 1 only when two or more distinct moves survive | not *"we recommend acting"*. `matched` mirrors it exactly |
| `do_nothing_baseline_bp` | 0–10,000 | The price of standing still. `7,500bp` means 0.75 | **not trustworthy as a zero** — `0` may mean *unmeasured*. Read `do_nothing_cost_unknown` alongside it |

None of the seven is a reserved shared metric. `test_the_unit_never_publishes_a_reserved_shared_metric`
asserts `published.isdisjoint({"confidence_bp", "urgency_bp", "priority_override_bp"})`, and further
asserts `set(result.metrics) <= published` on a run where `core.confidence` published
`confidence_bp = 9,000` and `core.temporal` published `urgency_bp = 8,000` in `prior` — proving the
unit does not forward what it read.

The roster-wide invariant `test_no_unit_publishes_a_metric_another_unit_owns` guarantees these seven
names are owned by `core.alternative` alone. That matters most for `do_nothing_baseline_bp`, whose
input `do_nothing_cost_bp` is owned by `core.cost` — two similar names, two different owners, and the
distinction is deliberate: `core.cost` prices inaction as a **cost ledger** entry, `core.alternative`
reports it as a **member of the option set**.

---

## 5 · Evidence attachment — the empty tuple

`build` computes:

```python
evidence = set(view.evidence_ids)                 # () — no required_fields declared
for observation in observations:
    evidence.update(observation.evidence_ids)     # () — no plugin attaches any
```

so `result.evidence_ids == ()` on every shipped run, and every `Finding` carries `evidence_ids = ()`
too.

**Is that wrong?** Partly. The unit's claims are about the *manifest* — which plays exist, what their
steps say, what they are worth in expectation — and the manifest is not evidence in the
`EvidenceRef` sense; it is versioned capability content already hashed into the request id. There is
nothing in `context.evidence` that grounds *"these two plays are the same move"*.

But the baseline claim is different. `do_nothing_baseline_bp = 7,500` is a statement about the
world, derived from numbers that other units cited real evidence for — and `core.alternative` cites
none of it. The plugin could forward the source units' `evidence_ids`; it does not.

**The consequence, and why it has not bitten.** `validation_unit.py:_asserts_a_claim` counts a result
as a claim when `matched is True` **or** any finding is not explicitly negative:

```python
if result.matched is True:
    return True
return any(finding.matched is not False for finding in result.findings)
```

`core.alternative` satisfies that on almost every run — its viability findings are `matched=True` for
every survivor. With `evidence_ids == ()` it would be counted as an **ungrounded claim** and emit
`claim_without_evidence` naming `core.alternative`, dragging down `evidence_sufficiency_bp`.

It does not happen today for one reason only: `deal_cooling_v2.py` declares `core.validation` with
dependencies `("core.risk", "core.opportunity", "core.impact", "core.confidence")`, and
`core.alternative` is not among them, so `core.validation` never inspects it. Add the edge — which a
future capability author reasonably might — and `core.alternative` becomes the run's largest
ungrounded claimant.

The only lever available today is declaring a `required_field` on the spec, which attaches that
field's evidence to the result at the cost of an `INSUFFICIENT_CONTEXT` failure mode. See
[02 · Retriever](02-Retriever.md) §3.3.

---

## 6 · Who consumes these metrics

**Nothing, by name.** A grep across `genios_engine/` for `has_alternative`, `option_count`,
`distinct_count`, `duplicate_count`, `declared_count`, `viable_count` and `do_nothing_baseline_bp`
returns hits only inside `alternative_unit.py` itself and its test file.

| Candidate consumer | Reads these metrics? | What it does instead |
|---|---|---|
| `reason/decision_maker.py` | **no** | Ranks on `impact`, `success`, `urgency`, `effort`, `risk`; reads `confidence_bp` from the confidence authority and `urgency_bp` / `priority_override_bp` from the priority authority |
| `core.validation` | **no** — not a declared dependency in the shipped capability | would inspect the result generically for contradictions and evidence, not by metric name |
| `core.recommendation` | **no** | declares `("core.validation", "core.dependency")` |
| `executive/brief.py` | **no** | `CapabilityManifest.do_nothing_consequence` is a **string authored in Layer 3**, unrelated to `do_nothing_baseline_bp` |
| `deliver/` | **no** | |
| `reason/authority.py` | **no** | the SQL predicate re-proves scoring inputs, none of which come from here |

What *does* consume the output is the audit surface. Every metric, finding and reason code lands in
the persisted `ReasonerResult` and therefore in `ReasoningTrace`, re-derived independently by
`reason/store.py` and re-provable through `reason/replay.py`. The unit's `semantic_hash` is part of
the run's content addressing, so a change to any of the seven numbers is detectable.

**So the honest summary is:** `core.alternative` currently has **zero mechanical effect** on any
decision. Its entire product is explanation — the option set a human is shown, and the record of how
it was screened. That is defensible for a shadow-mode candidate whose whole purpose is to prove
itself before anything depends on it, and it is also why the defects in
[README §6](README.md#6--known-defects-and-compromises) have never been felt.

It also means one thing worth stating for whoever wires the native delivery adapter: **the two
numbers most likely to be surfaced to a human — `option_count` and `do_nothing_baseline_bp` — are the
two with the known honesty problem.** `option_count` is safe; `do_nothing_baseline_bp` must be read
together with `do_nothing_cost_unknown`, and a card that renders the number alone will tell a person
that waiting is free when nobody measured it.

---

## 7 · Edge cases

| Situation | Result |
|---|---|
| A metric name not in `publishes` reaches the `Verdict` | `ValueError: core.alternative published undeclared metrics: <names>` between stages 6 and 7 → orchestrator records `ResultStatus.FAILED` |
| A `_bp` metric above 10,000 in the `Verdict` | clamped silently by `build` to 10,000; cannot occur here, the value is already clamped twice |
| A **float** `_bp` metric in the `Verdict` | truncated silently by `clamp_bp`'s `int()`, not rejected — the framework-wide gap in [Part 2 §3.7](../../README.md#37--verdict-is-unvalidated-and-one-float-path-survives). Cannot occur here: every value originates from an `Observation`, whose `__post_init__` rejects non-integers |
| A float in a **non**-`_bp` metric | loudly rejected one layer later by `platform/canonical.py:canonicalize` |
| The unit returns `ResultStatus.SKIPPED` | impossible — `build` hardcodes `COMPLETED`. Were it possible, the orchestrator would overwrite it with `FAILED` carrying `reasoner_returned_skipped`: a unit may not decide it is irrelevant |
| A finding cites an evidence id not in the snapshot | `guards.py:validate_evidence_references` raises at the orchestrator boundary. Cannot occur here — nothing is cited |
| The same run evaluated twice | byte-identical `semantic_hash`. Pinned by `test_the_same_situation_reasons_identically_twice`, which asserts metrics, reason codes **and** hash |
| Plays authored in a different order | identical metrics. Pinned by `test_the_option_count_does_not_depend_on_the_order_plays_were_authored` |
| The unit satisfies the `Reasoner` protocol | pinned by `test_the_unit_satisfies_the_reasoner_protocol` — `isinstance(AlternativeUnit(), Reasoner)` |

---

| ← | → |
|---|---|
| [05 · Evaluator](05-Evaluator.md) | [README](README.md) |
