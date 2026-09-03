# Layer 2 v2 — Build Order and Acceptance Gates

> Waves are prefixed **X** to distinguish them from Layer 1's **W** waves.
> Same discipline: units first, in isolation, fully tested. A parent is never built
> before its children are green. **A skip is not a pass.**

---

## Dependency on Layer 1

| L2 wave | Requires from L1 v2 | Why |
|---|---|---|
| X0–X2 | nothing | can start in parallel with L1 |
| X3 | — | — |
| **X5 (importance)** | **L1 W7 shipped** | without real signal importance, L2.7.4 has nothing to compose from and must refuse rather than fake a spread |
| X6 (patterns) | L1 W8 (QES publishing) | patterns read `signal_type` |
| X7 (pilot) | L1 W10 | end-to-end |

**X0 through X4 — including the entire analytic stratum — can be built while Layer 1 is
still in progress.** They read the existing graph. This is the largest piece of parallel
work available in Version 2 and it should start immediately.

---

## The eight waves

| Wave | Builds | Depends on | Gate |
|---|---|---|---|
| **X0** | L2 contracts (doc 08) | — | H0 |
| **X1** | **Metric history store + sampler** (L2.4.1, L2.4.2) | X0 | H1 |
| **X2** | **Trend computer + cohort builder** (L2.4.3, L2.4.4) | X1 | H2 |
| **X3** | **Comparator + peer baseline** (L2.4.5, L2.4.6) | X2 | H3 |
| **X4** | **Correlator + anomaly** (L2.4.7, L2.4.8) | X3 | H4 |
| **X5** | **Situation importance** (L2.7.4) | X4 **+ L1 W7** | **H5** |
| **X6** | Pattern registry (L2.6), typed absence (L2.5.5), **M-4 resolution**, **M-6/M-7 framing**, **loop guards** | X4 | H6 |
| **X7** | Authority view, point-in-time read, dependency chains, cross-timeline | X0 | H7 |
| **X8** | Pilot activation + BSO publishing on QES input | all + L1 W10 | H8 |

**X7 is independent of the analytic stratum** and can run on a second track from X0.

---

## Acceptance gates

### H0 — Contracts
```
pytest tests/contracts/test_l2_contracts.py -q
pytest tests/test_layer_topology.py -q
```
All 8 validators enforced; an old-shaped `BusinessSituationObject` still constructs.

### H1 — Metric history
```
pytest tests/context/analytic/test_history.py tests/context/analytic/test_sampler.py -q
python scripts/history_density_report.py --org <pilot>
```

| Metric | Gate |
|---|---|
| re-sampling a period twice creates duplicate rows | **0** |
| interpolated values | **0** |
| coverage gaps stored as `0` instead of unknown | **0** |
| points written per sweep on a 10k-node org | within declared budget |

### H2 — Trend and cohorts
```
pytest tests/context/analytic/test_trend.py tests/context/analytic/test_cohort.py -q
```
The decisive rows: a 6-point monotonic decline → `DECLINING`; **the same values with 3
gaps → `INSUFFICIENT_COVERAGE`, not `DECLINING`**; a decline of 5 on a base of 5000 →
`FLAT` while the same decline on a base of 8 → `DECLINING`; a cohort of 4 →
`insufficient_population`; no `sklearn` / clustering import anywhere.

### H3 — Comparison
```
pytest tests/context/analytic/test_comparator.py -q
```
Every returned `CohortPosition` carries `cohort_id` and `population_size`; nearest-rank
matches the existing `support_situations.percentile_bp` exactly.

### H4 — Correlation and anomaly
```
pytest tests/context/analytic/test_correlator.py tests/context/analytic/test_anomaly.py -q
```
`n < 20` refuses; `is_causal` is `False` on every object and cannot be set; a noisy series
with a spike is **not** flagged while a stable series with the same spike **is**.

### H5 — 🔴 Situation importance — **THE GATE THAT MATTERS**
```
pytest tests/context/test_situation_importance.py -q
python scripts/situation_importance_distribution.py --org <pilot> --since 30d
```

| Metric | Gate | Why |
|---|---|---|
| distinct `importance_bp` values | **> 50** | 5000-for-everything is the defect |
| p90 − p50 | **> 1500** | a flat distribution cannot rank |
| situations at exactly 5000 | **< 5%** | the constant is gone |
| one critical + four routine signals | **>= 9000** | proves `max` not `mean` |
| `importance_components` populated | 100% | explainability |
| identical input twice | byte-identical | reproducibility |

**This gate and Layer 1's G7 are two halves of one fix.** G7 proves signals carry real
importance; H5 proves situations compose it instead of overwriting it with a constant.
**Passing G7 while failing H5 changes nothing for the customer** — the constant would
still flatten everything downstream.

If more than 90% of incoming signals still carry exactly 5000, this gate **fails by
design**: the guard logs `L1_IMPORTANCE_NOT_ACTIVE` and refuses to synthesize a spread. A
fake distribution is worse than a flat one, because it looks like it works.

### H6 — Patterns, typed absence, resolution and loop safety
```
pytest tests/context/patterns tests/context/quality -q
python scripts/pattern_fire_report.py --org <pilot> --since 30d
```
>= 6 patterns registered; **0** patterns activated while exceeding their expected fire
rate 10x; **0** negative inferences drawn from `UNKNOWABLE` facts.

**Plus the resolution and loop gates (doc 12, doc 13):**
```
pytest tests/context/lifecycle/test_resolution.py -q
pytest tests/context/test_convergence.py tests/context/test_coverage_epoch.py \
       tests/context/analytic/test_gap_reason.py -q
python scripts/derivation_dag_check.py
```

| Metric | Gate |
|---|---|
| M-4 false-positive rate on the 40-fixture golden set | **< 2%** — the strictest in the plan, because a false positive closes a live thread |
| Hinglish resolution fixtures in the golden set | **>= 8** |
| M-6 fabricated facts | **0 — hard fail** |
| M-6 visibility leaks | **0 — hard fail** |
| derivation graph acyclic | passes, CI-enforced |
| drains exceeding `MAX_PASSES` | **0** over 7 days |
| `DECLINING` trends across an org-wide silence window | **0** ← the false-churn test |

### H7 — Graph completeness
```
pytest tests/context/test_authority.py tests/context/test_point_in_time.py \
       tests/context/test_dependency_correlation.py -q
```
`read_graph(as_of=now)` equals the live graph exactly; **0** hard `DELETE` statements
against `graph_edges`; **0** inferred authority rules auto-applied.

### H8 — Pilot
```
python scripts/l2_shadow_diff.py --org <pilot> --days 7
```

| Metric | Gate |
|---|---|
| situations produced by both paths | 100% |
| **a `DECLINING` trend on a real account, series citable** | **>= 1** |
| **a cohort position on a real account, population named** | **>= 1** |
| **a pattern-matched situation with per-condition evidence** | **>= 1** |
| founder-visible regressions | 0 |

**The three bold rows are the point of Layer 2 v2.** They are the first time GeniOS can
say *"this is getting worse"*, *"this is unlike its peers"*, and *"these five facts hold
together"* — each with the numbers behind it.

---

## What must not regress

| # | Must not regress | Where |
|---|---|---|
| 1 | **No embeddings, no edit distance in identity** | `identity.py:25` |
| 2 | Governed entity merges — proposal, history, reversibility | `merge.py`, `merge_proposals` |
| 3 | **The confidence VECTOR** — never collapsed to a scalar | `situations.py:102-227` |
| 4 | **Tenant node excluded from `ANCHOR_PRIORITY`** | `correlation.py` — without it one node swallows every conversation |
| 5 | Correlation refuses to prioritise, score risk or recommend | `correlation.py:1-6` |
| 6 | `graph_facts` keeps overwriting the CURRENT value | `derived.py:105-118` — history is a **separate** table, not a change to this one |
| 7 | Layer import direction | `tests/test_layer_topology.py` |
| 8 | Tests never reach production | commits `ae63ef9`, `d860b8e` |

**Item 6 is the one most likely to be got wrong.** The instinct on reading "we need
history" is to stop overwriting `graph_facts`. That would grow the table by three rows per
node per drain forever and make every "latest" read sift duplicates — the exact failure
the current design avoids. **Two tables, two questions.**

---

## Activation

Same rule as Layer 1: **per-tenant, in a table.**

```sql
create table if not exists l2_v2_activation (
    org_id text primary key,
    analytic_enabled_at timestamptz,
    patterns_enabled_at timestamptz,
    enabled_by text not null
);
```

Two independent switches — the analytic stratum can run and be validated on a tenant long
before pattern matching replaces anchor-based detection for them.

**No global boolean in `platform/config.py`.** `use_domain_compiler=False` has been set in
no environment since it was written and has left 152 capabilities dark. Do not build a
second one.
