# `core.tradeoff` · Stage 7 — Builder · Stage 8 — Metrics

**Source:** `genios_engine/reason/reasoners/tradeoff_unit.py:TradeoffUnit.publishes` (line 188)
**Framework:** `unit.py:ReasoningUnit.build` (lines 223–241, **not overridden**) and the guard in
`unit.py:ReasoningUnit.evaluate` (lines 256–261)

---

## 1 · What it is for

Stage 7 assembles the one object shape every unit in the roster returns. Stage 8 is not code at all —
it is a class attribute, `publishes`, plus a guard that refuses any metric name not on it.

Together they answer *what does this unit hand the rest of the system, and who is allowed to be
surprised by it?* For `core.tradeoff` the honest answer to the second half is: nobody, because nobody
reads it yet. See §5.

---

## 2 · What exists

### 2.1 · `build()` — not overridden

One of seventeen roster units overrides `build` (`core.confidence`, to route around the publishes
guard). `TradeoffUnit` does not. The base implementation runs unchanged:

```python
def build(self, view: UnitView, verdict: Verdict,
          observations: Sequence[Observation]) -> ReasonerResult:
    """Assemble the one object shape every unit returns."""
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

**Why it is not overridden:** the base does everything this unit needs, and nothing this unit needs
to prevent. Three of its behaviours are worth naming for this unit specifically:

| Base behaviour | Effect on `core.tradeoff` |
|---|---|
| Clamps every `_bp`-suffixed metric | `tension_bp` and `margin_bp` are already in `0..10000` by construction — `_weigh` clamps them and the maximum reachable value is exactly 10,000. The clamp never binds |
| Leaves non-`_bp` metrics alone | `axis_count` and `contested_count` pass through as plain integers, which is correct: they are counts, not basis points |
| Unions `view.evidence_ids` with every observation's `evidence_ids` | Both sides of the union are empty on every shipped run. See §4 |
| Copies `verdict.adjustments` and `verdict.checks` verbatim | Both are always `()`, because the `Verdict` never populates them |

`status` is hard-coded to `COMPLETED`. A unit cannot decide it is irrelevant — if it returned
`SKIPPED`, `orchestrator.py` would overwrite the result with a `FAILED` carrying
`reasoner_returned_skipped`, because skipping is a scheduling decision and scheduling belongs to
Part 1.

### 2.2 · The `publishes` declaration

```python
publishes = ("tension_bp", "margin_bp", "axis_count", "contested_count")
```

| Metric | Type | Range | Meaning |
|---|---|---|---|
| `tension_bp` | integer basis points | 0–10,000 | How hard the **sharpest single argument** in this situation is. `10,000bp` means 1.00 — two maximal pressures, dead level. `0` means the leading axis was a free move, or nothing was measurable |
| `margin_bp` | integer basis points | 0–10,000 | How decisively that same argument was won. `0` is a dead heat; `10,000` is one side at maximum against the other at zero. Read it **only** alongside `tension_bp` — a large margin with a small tension is a settled question, and a small margin with a small tension is two weak pressures |
| `axis_count` | plain integer | 0–3 with the current plugin set | How many comparisons had both sides published. The disambiguator between *nothing was contested* and *nothing was measurable* |
| `contested_count` | plain integer | 0–`axis_count` | How many of those cleared `tension_threshold_bp`. `contested_count == axis_count` on a multi-axis run means everything is pulling against everything |

`axis_count` and `contested_count` deliberately carry no `_bp` suffix, so `build` does not clamp them
and `ReasonerResult.__post_init__` does not range-check them. Correct — they are cardinalities, and
clamping a count to 10,000 would be meaningless.

### 2.3 · The guard

```python
undeclared = sorted(set(verdict.metrics) - set(self.publishes)) if self.publishes else []
if undeclared:
    raise ValueError(f"{self.unit_id} published undeclared metrics: {', '.join(undeclared)}")
```

It sits between stage 6 and stage 7 — not inside `build` — so a misdeclared unit fails *before* a
well-formed `ReasonerResult` exists. The failure reads as "this unit is misdeclared" rather than
"this result contains something surprising".

For this unit the guard is load-bearing in one specific direction. The `Verdict` carries exactly the
Calculator's four names, so the guard never fires today. It exists to catch the change that would
matter: a fourth plugin, or a well-meaning edit promoting `leading_bp` and `trailing_bp` to unit
level, would raise

```text
ValueError: core.tradeoff published undeclared metrics: leading_bp, trailing_bp
```

on the first test run — and, more importantly, any attempt to publish `confidence_bp` or `urgency_bp`
would fail the same way. This unit reads both. `test_the_unit_never_republishes_a_reserved_shared_metric`
pins the declaration and the emitted set:

```python
published = set(TradeoffUnit().publishes)
assert published.isdisjoint({"confidence_bp", "urgency_bp", "priority_override_bp"})
...
assert set(result.metrics) <= published
```

---

## 3 · The result, in full

The shipped `sales.deal_cooling_full` run, executed:

```text
ReasonerResult
    reasoner_id       core.tradeoff
    reasoner_version  1.0.0
    status            COMPLETED
    matched           True

    metrics           tension_bp       5301
                      margin_bp        1066
                      axis_count          1
                      contested_count     1

    findings          Finding
                          finding_id    tradeoff.risk_vs_reward
                          kind          tradeoff
                          matched       True
                          metrics       tension_bp 5301 · margin_bp 1066
                                        leading_bp 7000 · trailing_bp 5934
                          evidence_ids  ()
                          reason_codes  concedes.caution · favours.reward
                                        tradeoff.risk_vs_reward

    adjustments       ()
    checks            ()
    evidence_ids      ()
    missing_fields    ()
    reason_codes      concedes.caution · favours.reward
                      headline.concedes.caution · headline.favours.reward
                      tradeoff.risk_vs_reward · tradeoff_contested
```

Note where `leading_bp` and `trailing_bp` live: **only in the finding.** They are not unit metrics,
so they are invisible to any consumer scanning `result.metrics` by name. A renderer that wants to say
"the upside is 7,000 and the exposure we accepted is 5,934" must read the finding.

### 3.1 · Determinism

`test_the_same_situation_reasons_identically_twice` runs the unit twice on identical priors and
asserts three things:

```python
assert dict(first.metrics) == dict(second.metrics)
assert first.reason_codes == second.reason_codes
assert first.semantic_hash == second.semantic_hash
```

> *Replayability is the whole promise: no clock, no randomness, no iteration order.*

Four sorts underpin that hash and every one is load-bearing:

| Sort | Where | What it stabilises |
|---|---|---|
| `sorted(self.plugins, key=plugin_id)` | `unit.py:analyze` | Observation order |
| `_ranked`'s three-key sort | `calculate` and `evaluate_meaning` | Which axis is the headline, and finding order |
| `tuple(sorted(codes))` | `evaluate_meaning` | Reason code order |
| `tuple(sorted(set(...)))` | `Observation.__post_init__`, `Finding.__post_init__`, `ReasonerResult.__post_init__` | Every code and evidence tuple, at three levels |

The unit reads no clock, no environment, no randomness, and no database.
`test_unit_roster.py:test_no_unit_reaches_for_a_clock_or_a_database` scans the module's source for
the banned tokens and passes. It reads `evaluation_time` from nothing — unlike most units, it does
not even reach `request.evaluation_time`.

---

## 4 · Evidence attachment

```python
evidence = set(view.evidence_ids)
for observation in observations:
    evidence.update(observation.evidence_ids)
```

Both sides are empty for this unit on every shipped run:

- `view.evidence_ids` is `()` because `required_fields` is `()` — see [02-Retriever.md](02-Retriever.md).
- No plugin ever sets `evidence_ids` on an `Observation`. `_weigh` constructs the observation with
  `metrics` and `reason_codes` only, so the field takes its default `()`.

So **`result.evidence_ids == ()` and every `Finding.evidence_ids == ()`.**

The unit cites nothing, and there is a defensible reason: its evidence *is* other units' results, and
`ReasonerResult` has no field for citing another `ReasonerResult`. The evidence ids that ground
`opportunity_bp` live on `core.opportunity`'s result, where they belong. But the framework's
consumers cannot follow that chain — `core.validation` asks a much simpler question.

Two consequences, one live and one latent.

**Latent: the false citation.** Because the base retriever derives evidence from `required_fields`, a
capability author who declares a field on this unit attaches that field's evidence to claims the
arithmetic never touched. Verified with `required_fields=("deal.status",)`:

```text
result.evidence_ids   ('ev_status',)     ← attached by the base retriever
finding.evidence_ids  ()                  ← the plugin attached nothing
tension_bp            7,125               ← computed from opportunity_bp and risk_bp only
```

**Latent: the ungrounded-claim finding.** `core.validation`'s `EvidenceSufficiencyPlugin` counts a
result as asserting a claim when `matched is True` **or** any finding is not an explicit negative. A
contested tradeoff satisfies both and cites nothing, so it would produce:

```text
reason_codes = ("claim_without_evidence", "claimant:core.tradeoff")
```

It does not happen today only because `deal_cooling_v2` declares `core.validation`'s dependencies as
`("core.risk", "core.opportunity", "core.impact", "core.confidence")`. Adding `core.tradeoff` to that
tuple — an entirely reasonable edit — would add an ungrounded-claim finding and lower
`evidence_sufficiency_bp`. The right fix is for the plugins to forward the evidence ids of the
results they read; they currently forward none.

---

## 5 · Who consumes these metrics

**Nobody.** Verified by grep across the whole repository, excluding `System Design/`:

| Metric | Occurrences outside `tradeoff_unit.py` |
|---|---|
| `tension_bp` | `tests/test_unit_tradeoff_unit.py` (7), `tests/test_capability_deal_cooling_full.py:118` (`> 0`) |
| `margin_bp` | `tests/test_unit_tradeoff_unit.py` (3) |
| `axis_count` | `tests/test_unit_tradeoff_unit.py` (2) |
| `contested_count` | `tests/test_unit_tradeoff_unit.py` (2) |

No occurrence in `reason/decision_maker.py`, in any other unit, in `deliver/`, in `executive/`, or in
`feedback/`. The single production assertion is `tension_bp > 0`, which pins that the unit ran.

That is not a criticism of the unit — it is Category 3 doing its job in the wrong order. The unit was
built so that an explanation *could* name the tension and the concession; the explanation layer has
not yet been taught to look. Two channels are already wired and would need no new plumbing:

| Channel | How it would reach a consumer | What blocks it today |
|---|---|---|
| `reason_codes` → `core.recommendation` | `recommendation_unit.py:_claims` reads every completed prior unit's findings' reason codes and matches them against a play's `play_support_codes` table | `deal_cooling_v2` declares `core.recommendation`'s dependencies as `("core.validation", "core.dependency")`, and no capability authors `play_support_codes` at all |
| `findings` → the delivered card | A card renderer naming the headline lean and the concession | No renderer reads reasoner findings by kind |

The `headline.` prefix exists precisely to make the first of those cheap — *"so a renderer can name
one tension without re-deriving the ranking"* — and nothing has yet used it.

### 5.1 · What a consumer would need to know

If and when something reads this unit, three properties of the output need to be understood or it
will be misread:

1. **`matched=True` is not a recommendation.** It says a dilemma exists. Acting on `favours.reward`
   because `matched` was true would make the consumer the second decision authority the unit refused
   to be. `test_a_contested_reading_is_not_a_recommendation` states this as a contract.
2. **`tension_bp: 0` is ambiguous without `axis_count`.** It means either "the leading axis was a free
   move" or "nothing was measurable". Only `axis_count` separates them, and on the second case the
   result carries no reason codes at all — see [05-Evaluator.md](05-Evaluator.md) §4.
3. **Result-level reason codes lose the axis linkage.** `{favours.reward, favours.speed}` in one flat
   sorted tuple does not say which code belongs to which argument. The findings preserve the pairing;
   the roll-up does not.

---

## 6 · Edge cases

| Situation | `status` | `metrics` | `findings` | `evidence_ids` |
|---|---|---|---|---|
| One or more axes measured | `COMPLETED` | all four | one per axis, `_ranked` order | `()` |
| No axis measurable | `COMPLETED` | all four, at `0` | `()` | `()` |
| `required_fields` declared and absent | `INSUFFICIENT_CONTEXT` | **none — forbidden** | none | none |
| Malformed `tension_threshold_bp` | `FAILED` | none | none | none |
| Malformed `decisive_margin_bp`, at least one axis live | `FAILED` | none | none | none |
| Malformed `decisive_margin_bp`, no axis live | `COMPLETED` | all four, at `0` | `()` | `()` |
| Malformed source id, e.g. `risk_source: 7` | `FAILED` — **always**, even with no priors at all | none | none | none |

The last row differs from `decisive_margin_bp` because `_prior_bp` evaluates `_config_id` *before*
it looks at anything: `view.prior_metric(_config_id(view, key, default_unit), metric, _ABSENT)`. A
malformed source id therefore fails eagerly. Verified — `risk_source: 7` with an empty `prior` raises
`ValueError: risk_source must name a reasoning unit`. That is the right eagerness: a source id is a
manifest fault whether or not the situation happened to reach it.

Rows 3 through 7 all rely on `ReasonerResult.__post_init__`:

```python
if self.status != ResultStatus.COMPLETED and (
        self.matched is not None or self.metrics or self.findings or self.adjustments
        or self.checks or self.evidence_ids):
    raise ValueError("non-completed reasoner results cannot carry decision effects or evidence")
```

A unit that failed halfway cannot leave a partial claim behind for the Decision Maker to trip over.
For a `FAILED` tradeoff the exception type and message land in `diagnostics`, which is
`compare=False, repr=False` and outside `to_semantic_dict` — so a failure message can never move a
decision hash.

---

## Related

| Document | Covers |
|---|---|
| [README](README.md) | The unit's map, published metrics table, and the gap list |
| [05-Evaluator.md](05-Evaluator.md) | The `Verdict` this stage assembles, and the mute empty run |
| [02-Retriever.md](02-Retriever.md) | Why `view.evidence_ids` is empty, and the false-citation trap |
| [Part 2 · The Unit Framework](../../README.md) | §2.1 and §3.4 — the guard's placement and its one escape hatch |
| [Part 3 · Decision Maker](../../../03-Decision-Maker/README.md) | The consumer this unit was built to inform, which does not yet read it |
