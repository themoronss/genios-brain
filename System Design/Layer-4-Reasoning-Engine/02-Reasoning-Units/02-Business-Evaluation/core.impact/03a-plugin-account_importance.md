# Plugin · `account_importance`

**Class:** `impact_unit.py:AccountImportancePlugin` (lines 135–184)
**`plugin_id`:** `account_importance` — **first** in execution order
**`Observation.kind`:** `impact.account_importance`
**Publishes into:** `relationship_exposure_bp` (via `_DIMENSIONS`), default weight **3,000**

---

## 1 · The claim

*How much relationship is riding on the outcome.*

> *"A named strategic account is a bigger loss than an equal-sized deal with a one-thread
> stranger."*

Two deals of identical value are not identical stakes. One sits inside an account the business has
designated strategic, with years of accumulated relationship capital behind it; the other is a
first transaction with a company nobody has met twice. Losing the first costs more than the money.

The plugin reads that in **two ways, in a fixed order of authority**.

| Priority | Reading | Reason code | Why it ranks where it does |
|---|---|---|---|
| 1 | An explicit tier classification, priced by the capability | `named_account_tier` | *"a company that has been designated strategic is strategic regardless of how many threads happen to be open today"* — it is a business statement, not an inference |
| 2 | Relationship breadth measured by `core.relationship` | `relationship_footprint` | *"a well-multithreaded account represents more accumulated relationship capital — more people, more history, more to lose in either direction"*. Defensible, but inference, so it is the fallback |
| 3 | Nothing | — | neither reading is available |

---

## 2 · The code

```python
class AccountImportancePlugin:
    plugin_id = "account_importance"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        tier_field = str(view.config.get("account_tier_field") or "").strip()
        weights = _mapping_config(view, "account_tier_bp")
        if tier_field and weights:
            tier = fact_value(view.request, tier_field)
            if tier is not None:
                table = {str(key).strip().lower(): weights[key] for key in sorted(weights)}
                label = str(tier).strip().lower()
                if label in table:
                    strength = _delta_bp(table[label], f"account_tier_bp.{label}")
                    if strength >= 0:
                        return (Observation(
                            plugin_id=self.plugin_id,
                            kind="impact.account_importance",
                            metrics={"strength_bp": clamp_bp(strength)},
                            evidence_ids=evidence_ids(view.request, tier_field),
                            reason_codes=("named_account_tier",),
                        ),)
        source = str(view.config.get("relationship_reasoner") or "core.relationship")
        coverage_bp = view.prior_metric(source, "coverage_bp", -1)
        if coverage_bp < 0:
            return ()                       # the dependency did not run; we have nothing to say
        return (Observation(
            plugin_id=self.plugin_id,
            kind="impact.account_importance",
            metrics={"strength_bp": clamp_bp(coverage_bp)},
            reason_codes=("relationship_footprint",),
        ),)
```

### 2.1 · Config keys

| Key | Type | Default | Validated by | Effect |
|---|---|---|---|---|
| `account_tier_field` | str | `""` | `str(... or "").strip()` | the fact holding the tier label. Empty/whitespace ⇒ tier path off |
| `account_tier_bp` | mapping label → int | `{}` | `_mapping_config`, then `_delta_bp` per matched key | the price of each tier. Empty ⇒ tier path off |
| `relationship_reasoner` | str | `"core.relationship"` | none | which prior unit's `coverage_bp` to fall back on |

**Both** tier keys are required for the tier path: `if tier_field and weights`. A field with no
table, or a table with no field, is treated as "not configured" and falls through silently —
verified: `account_tier_field="account.tier"` with no `account_tier_bp` and coverage 4,000 yields
`strength_bp = 4,000, reason_codes = ("relationship_footprint",)`.

### 2.2 · Two determinism details worth naming

**Normalisation on both sides.** Tier labels arrive from CRMs with arbitrary casing and padding —
`"Strategic"`, `" strategic "`, `"STRATEGIC"` — so both the table keys and the fact value are
`.strip().lower()`ed before comparison.

**Sorted iteration.** The table is built as `{... for key in sorted(weights)}`. Normalisation can
collide two distinct authored keys onto one normalised key, and without the sort the winner would
depend on dict insertion order, which depends on how the manifest happened to be written.
Iterating sorted keys makes the **last sorted key win, on every machine**:

```text
account_tier_bp = {"Strategic": 9000, "strategic": 3000}
sorted(keys)    = ["Strategic", "strategic"]      # 'S' (0x53) sorts before 's' (0x73)
table build     = {"strategic": 9000} → overwritten → {"strategic": 3000}
result          = strength_bp 3000
```

Verified against the live plugin. The behaviour is deterministic, and it is not obviously the
behaviour an author expects — a collision silently discards one of their two weights. Nothing warns.

---

## 3 · The arithmetic

There is none worth the name, and that is the point. Both paths are lookups.

```text
tier path      strength_bp = clamp_bp(account_tier_bp[normalise(tier_value)])
                             where the value has already passed _delta_bp (-10000..10000)
                             and the branch is only taken when it is >= 0
                             ⇒ clamp_bp is a no-op here; it is belt-and-braces

fallback path  strength_bp = clamp_bp(prior_metric(relationship_reasoner, "coverage_bp", -1))
                             taken only when that value is >= 0
```

`clamp_bp(value) = min(10_000, max(0, int(value)))`.

Both clamps are provably unreachable in a well-formed run: `_delta_bp` already caps the tier weight
at 10,000, and `contracts/reasoning.py:_bp` rejects a `coverage_bp` outside 0..10,000 (and rejects
`bool`) when `core.relationship` constructs its result. So a `coverage_bp` of 12,000 or `True`
cannot exist to be clamped. The defence is there because the plugin cannot see which unit actually
answers to `relationship_reasoner` — a capability may point it at anything.

### 3.1 · The negative sentinel

```python
coverage_bp = view.prior_metric(source, "coverage_bp", -1)
if coverage_bp < 0:
    return ()
```

> *"The fallback uses a negative sentinel rather than the usual 0 default, because 'the relationship
> reasoner did not run' and 'coverage is genuinely zero' are different facts and only one of them
> justifies an observation."*

`unit.py:UnitView.prior_metric` substitutes the default on **four** distinct conditions, all
silently:

```python
result = self.prior.get(reasoner_id)
if result is None or result.status != ResultStatus.COMPLETED:
    return default                       # (1) not declared as a dependency  (2) did not complete
value = result.metrics.get(name, default)
return default if isinstance(value, bool) or not isinstance(value, int) else value
                                         # (3) metric absent  (4) metric not an integer
```

With the default at `0`, all four would read as *"this account has no relationship footprint"* —
which is a claim, and a wrong one. With the default at `-1` they read as *"I cannot say"*, and the
plugin stays silent. **A genuine `coverage_bp = 0` still produces an observation**, with
`strength_bp = 0`: verified, `{'strength_bp': 0}, ('relationship_footprint',)`. That is correct —
a measured zero is evidence, an unmeasured one is not.

Condition (1) is the live defect: `deal_cooling_full_v2` declares `core.impact` with **no
dependencies**, and `orchestrator.py` passes a unit only the prior results it declared, so
`prior` is `{}` and the sentinel fires on every run even though `core.relationship` ran in the same
execution and published `coverage_bp = 6,666`. Three thousand of the ten thousand blend weight is
structurally unreachable in production, and the renormalisation in `calculate` hides it by
re-weighting the survivors to 100%.

---

## 4 · Exactly when it stays silent

| # | Condition | What it means |
|---|---|---|
| 1 | `account_tier_field` unauthored **and** `relationship_reasoner` not in `prior` | nothing configured, nothing measured |
| 2 | tier field authored but `account_tier_bp` empty, and no usable prior | half-configured; treated as unconfigured |
| 3 | tier fact is `None` or absent, and no usable prior | the classification was never synced |
| 4 | tier label is not a key of the normalised table, and no usable prior | *"A tier the author never priced is unknown; the proxy is a better answer than a guess"* |
| 5 | tier weight is **negative**, and no usable prior | see §6 — accepted then discarded |
| 6 | the named relationship unit is not a declared dependency | `prior_metric` → `-1` |
| 7 | the named relationship unit ran but is not `COMPLETED` | `prior_metric` → `-1` |
| 8 | it completed but published no `coverage_bp` | `prior_metric` → `-1` |

Note that conditions 3–5 are *not* silence on their own — they fall through to the fallback. Only
when the fallback is also unavailable does the plugin return `()`.

---

## 5 · Worked examples

### 5.1 · Tier beats breadth — the primary path

```text
config  account_tier_field = "account.tier"
        account_tier_bp    = {"strategic": 9000, "smb": 2000}
facts   account.tier       = "Strategic"          # CRM casing
prior   core.relationship  → coverage_bp 1000     # a thin account by thread count

tier_field truthy, weights truthy → tier path
table  = {"smb": 2000, "strategic": 9000}         # sorted, stripped, lowercased
label  = "strategic"  → in table → 9000
9000 >= 0 → emit

Observation(plugin_id="account_importance", kind="impact.account_importance",
            metrics={"strength_bp": 9000},
            evidence_ids=("ev_tier",),           # whatever cites account.tier
            reason_codes=("named_account_tier",))
```

The coverage of 1,000 is **never read** — the tier branch returns before the fallback line. Pinned
by `test_a_named_account_tier_outranks_inferred_relationship_breadth`:
*"If the business has designated the account strategic, thread count does not get a vote."*

### 5.2 · Breadth stands in — the fallback path

```text
config  (no tier keys)
facts   deal.status = "open"
prior   core.relationship → coverage_bp 6000

tier_field "" → falsy → skip the tier path entirely
source = "core.relationship"
coverage_bp = 6000  →  6000 >= 0 → emit

Observation(metrics={"strength_bp": 6000},
            evidence_ids=(),                     # nothing in THIS snapshot stands behind it
            reason_codes=("relationship_footprint",))
```

Pinned by `test_relationship_breadth_stands_in_when_no_tier_was_declared`. Note the empty
`evidence_ids` — defect 2 in the [README](README.md#6--known-defects-and-compromises). If this is
the only dimension that reports, the unit publishes `impact_bp = 6,000`, `matched = True` and
`result.evidence_ids = ()`, which `validation_unit.py:_asserts_a_claim` counts as an ungrounded
claim.

### 5.3 · An unpriced tier falls back rather than guessing

```text
config  account_tier_field = "account.tier"
        account_tier_bp    = {"strategic": 9000}
facts   account.tier       = "partner"
prior   core.relationship  → coverage_bp 4000

table  = {"strategic": 9000}
label  = "partner"  → NOT in table → fall through to the fallback
coverage 4000 → emit

Observation(metrics={"strength_bp": 4000}, reason_codes=("relationship_footprint",))
```

Pinned by `test_an_unmapped_tier_falls_back_instead_of_inventing_a_weight`. The alternative designs
were both worse: inventing a mid-scale weight for an unrecognised tier would price a classification
nobody authored, and refusing outright would throw away a perfectly good proxy.

### 5.4 · The dependency never ran

```text
config  (none)
prior   {}                                        # core.impact declared no dependencies

prior_metric("core.relationship", "coverage_bp", -1) → -1
-1 < 0 → return ()
```

Pinned by `test_a_relationship_reasoner_that_never_ran_contributes_nothing` —
*"'Dependency absent' and 'coverage is genuinely zero' are different facts."* And with the
dependency present but failed:

```text
prior   {"core.relationship": ReasonerResult(status=FAILED, metrics={})}
        status != COMPLETED → prior_metric returns -1 → ()
```

Pinned by `test_a_failed_relationship_reasoner_is_not_read_as_zero_coverage`.

### 5.5 · The blend effect, with real numbers

What the fallback is worth when it *is* reachable. Same deal, two runs:

```text
Run A — dependency declared, coverage 6,000, tier unconfigured, no strategic tag
  revenue      7,500 × 5,000 = 37,500,000
  relationship 6,000 × 3,000 = 18,000,000
  weighted_sum              = 55,500,000
  total_weight              =      8,000
  impact_bp = half_up(55,500,000 / 8,000) = 6,938

Run B — identical situation, dependency NOT declared (the shipped v2 shape)
  revenue      7,500 × 5,000 = 37,500,000
  total_weight              =      5,000
  impact_bp = half_up(37,500,000 / 5,000) = 7,500
```

A missing manifest line moved the reported stake by **562bp**, upward, with no error, no reason
code, and no telemetry. `impact_signal_count` drops from 2 to 1 — the only externally visible trace,
and nothing downstream reads it.

---

## 6 · Edge cases

| Input | Result | Note |
|---|---|---|
| `account_tier_bp = {"churned": -2000}`, tier `"churned"`, coverage 4,000 | `strength_bp 4000`, `relationship_footprint` | **Defect 3.** `_delta_bp` accepts the negative, then `if strength >= 0` discards it and drops to the fallback. No error, no reason code. The author's intent — "a churned account is worth less" — is silently unrepresentable |
| `account_tier_bp = {"strategic": 10001}`, tier `"strategic"` | `ValueError: account_tier_bp.strategic must be an integer between -10000 and 10000` → `FAILED` | the label in the message is the **normalised** one, not the authored one |
| `account_tier_bp = {"strategic": True}` | same `ValueError` | `_delta_bp` rejects `bool` before `int` |
| `account_tier_bp` not a mapping | `ValueError: account_tier_bp must be a mapping` | from `_mapping_config` |
| tier value is `0` or `False` | `str(tier).strip().lower()` → `"0"` / `"false"`; matched only if the table has that key. `tier is not None` is the guard, so falsy values still take the tier path | |
| tier value is a list | `str(["a"])` → `"['a']"` — will not match; falls through | Layer 2 does not emit lists for scalar classification fields today |
| `coverage_bp` exactly `0` | emits `strength_bp 0` | a measured zero is evidence — it counts as a reporting dimension and pulls the blend down |
| `relationship_reasoner = "core.context"` with only `core.relationship` in prior | `()` | verified — the plugin reads only the unit it was pointed at |
| Tier path taken, but no `EvidenceRef` cites the tier field | `evidence_ids = ()` — the observation still fires | the reading is real; the citation is what is missing |

---

| ← | → |
|---|---|
| [03 · Analyzer](03-Analyzer.md) | [03b · revenue_exposure](03b-plugin-revenue_exposure.md) |
