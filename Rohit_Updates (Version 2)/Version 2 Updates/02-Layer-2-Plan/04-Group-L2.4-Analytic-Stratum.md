# L2.4 — Analytic Stratum (NEW)

> **This group does not exist in the Globe spec and does not exist in the code.**
> It is the substrate every pattern the customer expects is made of, and its absence is
> why "this cohort shows early churn signals" is not merely hard today — it is
> *unrepresentable*.

**Group responsibility:** compute what is true **across entities** and **across time**.

**Group law:** *Every comparison names its population. A percentile without a stated
cohort is a number nobody can check.*

**Package:** `genios_engine/context/analytic/`
**Input:** the graph + `metric_history`
**Output:** comparative facts written back as `derived.*` facts and cohort memberships
**LLM sites:** **zero.**

---

## Why this group exists

Walk the founder's own examples and ask what each one needs:

| Customer expectation | Needs | Exists today? |
|---|---|---|
| *"this cohort shows early churn signals"* | cohort + trend | ❌ neither |
| *"these 3 leads share traits with your highest-LTV customers"* | cohort + comparison across population | ❌ neither |
| *"your pricing experiment underperforms on this cohort"* | cohort + comparison + segment split | ❌ neither |
| *"engagement is declining"* | metric history + trend | ❌ no history |
| *"at-risk flagged 30+ days early"* | trend + anomaly vs own baseline | ❌ neither |
| *"this deal is quietly stalling"* | trend on one thread | ⚠️ current value only |

**Six of six need this group. None of them need a language model.**

That is the central architectural claim of L2 v2: *"account X's engagement sits in the
bottom decile of its cohort and has fallen three months running"* is a **discovered
pattern** — nobody wrote a rule naming that account — and it is computed
deterministically, reproducibly, with every input citable.

---

## Component map

| # | Component | BLG | Units | Wave | Status |
|---|---|---|---|---|---|
| L2.4.1 | **Metric History Store** | — | 2 | X1 | 🆕 NEW |
| L2.4.2 | **Metric Sampler** | BLG-07 | 3 | X1 | 🆕 NEW |
| L2.4.3 | **Trend Computer** | BLG-08 | 3 | X2 | 🆕 NEW |
| L2.4.4 | **Cohort Builder** | BLG-09 | 3 | X2 | 🆕 NEW |
| L2.4.5 | **Population Comparator** | BLG-10 | 2 | X3 | 🆕 NEW |
| L2.4.6 | **Peer Baseline** | BLG-11 | 2 | X3 | 🆕 NEW |
| L2.4.7 | **Metric Correlator** | BLG-12 | 2 | X4 | 🆕 NEW |
| L2.4.8 | **Anomaly Detector** | BLG-13 | 2 | X4 | 🆕 NEW |

**Build order:** history must exist before trend; cohorts before comparison; both before
correlation and anomaly.

---

# L2.4.1 · Metric History Store

### L2.4.1-U1 · The append-only table

**WHAT** — A deliberately sampled, append-only time series of per-node metric values.

**WHY** — `context/derived.py:108-109` states the current behaviour exactly:

> *"a derived value is a **RECOMPUTE, not a new observation of history**: it overwrites
> its own deterministic version id rather than appending a row per drain."*

That decision was **correct for its stated reason** — appending per drain would grow the
table by three rows per node forever, and a reader picking "latest" would sift
duplicates. The fix is not to stop overwriting the current value. It is to add a
**separate, sampled** history table beside it.

> **The two-table rule:** `graph_facts` answers *"what is true now?"* and keeps
> overwriting. `metric_history` answers *"what was true then?"* and only ever appends.
> Conflating them is why "is this declining?" has no answer today.

**WHERE** — `genios_engine/context/analytic/history.py`
**WHEN** — X1. No dependencies.

**STORAGE**
```sql
create table if not exists metric_history (
    org_id          text not null,
    subject_node_id text not null,
    metric          text not null,        -- "engagement.touch_count", "deal.stage_age_days"
    value_bp        bigint not null,      -- integer. money in minor units, ratios in bp
    unit            text not null,        -- "count" | "days" | "bp" | "minor_units"
    currency        text,                 -- only when unit = minor_units
    observed_at     timestamptz not null, -- the period this value describes
    sampled_at      timestamptz not null default now(),
    sample_reason   text not null,        -- "scheduled" | "changepoint" | "backfill"
    coverage_ready  boolean,              -- from L1 v2 — absence vs zero
    primary key (org_id, subject_node_id, metric, observed_at)
);
create index mh_by_metric on metric_history (org_id, metric, observed_at desc);
create index mh_by_node   on metric_history (org_id, subject_node_id, metric, observed_at desc);
```

**Design points that matter:**
- `value_bp` is `bigint` — money in minor units overflows `int` on large contracts.
- `observed_at` is the **period the value describes**, not when we computed it. Backfilled
  history and live sampling must be indistinguishable to a reader.
- The primary key makes re-sampling the same period **idempotent** — a re-run overwrites
  that period rather than creating a duplicate point.
- `coverage_ready` travels with every point. A gap in a series where coverage was false
  is **unknown**, not zero, and the trend computer must treat it differently.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Unbounded growth | table becomes the largest in the system | sampling policy (L2.4.2) caps points per node per metric; retention 24 months |
| Backfill and live sampling disagree on period boundaries | phantom changepoints | period boundaries are computed by one shared function, used by both paths |
| A metric renamed | series silently splits | metric names are a registered enum, not free strings; renaming requires a migration that rewrites history |

**ACCEPTANCE**
```
pytest tests/context/analytic/test_history.py -q
# same (node, metric, period) written twice -> one row, second wins
# a series with a coverage gap returns the gap as unknown, not 0
# 24-month retention prunes older points and leaves the series readable
```

### L2.4.1-U2 · Series reader

**WHAT** — `read_series(node, metric, since, until) -> list[MetricPoint]` with gaps
explicit.

**WHY** — Every consumer needs a gap-aware read. A naive reader that silently skips
missing periods turns a coverage gap into a false trend.

**HOW** — returns a dense series: every period in range present, with
`value_bp=None, known=False` for gaps. **Never interpolate.** An interpolated value is a
fabricated observation, and it would flow into a trend and then into a card.

---

# L2.4.2 · Metric Sampler (BLG-07)

### L2.4.2-U1 · The sampling policy

**WHAT** — Decides which metrics get a history point, for which nodes, how often.

**WHY** — Sampling everything is the unbounded-growth failure. Sampling too little makes
trends undetectable. This decision table is the difference.

**HOW** (BLG-07) — a metric is sampled if **any** row matches:

| # | Condition | Cadence | Rationale |
|---|---|---|---|
| 1 | metric is in `TRENDED_METRICS` and node is an account/deal/person with activity in 90d | **weekly** | the default trended set |
| 2 | node is in an **active** situation | **daily** | while something is live, resolution matters |
| 3 | value changed by more than the metric's `changepoint_bp` since the last point | **immediate** | a changepoint is the most informative sample |
| 4 | node was dormant and became active | **immediate** | revival is a signal |
| 5 | month boundary | **monthly, always** | guarantees a floor density for long-horizon trends |

Everything else is **not sampled.**

**`TRENDED_METRICS` — the initial registered set** (an enum, not free strings):
```
engagement.touch_count_28d      relationship.response_latency_hours
engagement.inbound_count_28d    deal.stage_age_days
engagement.outbound_count_28d   deal.value_minor_units
engagement.days_since_contact   account.open_commitment_count
account.contact_breadth         account.overdue_commitment_count
support.ticket_count_28d        support.backlog_age_p50_days
```

**Adding a metric to this set is a deliberate act** — it changes storage growth and it
changes what patterns become detectable. It requires a registry entry and a note saying
which customer question it serves.

**LLM** — no. **STORAGE** — writes `metric_history`.

**ACCEPTANCE**
```
pytest tests/context/analytic/test_sampler.py -q
# a dormant node with no activity is not sampled weekly
# a node in an active situation is sampled daily
# a value crossing changepoint_bp is sampled immediately, off-cadence
# every node gets at least one point per month regardless
# sampling a 10k-node org stays under the declared point budget
```

### L2.4.2-U2 · Backfill sampler

**WHAT** — Reconstructs history from existing `source_events` when a metric is first added.

**WHY** — Adding a metric with no history means waiting months before any trend exists.
Most trended metrics are re-computable from the event ledger, which already holds the
history.

**And this is where L1 v2's backfill window pays off:** an 18-month event backfill
(L1.2.4-U1) becomes 18 months of *computable* metric history the moment this unit runs.
The two changes compound.

**HOW** — replay `source_events` in period buckets, compute the metric per period, write
with `sample_reason="backfill"`. Idempotent via the primary key.

### L2.4.2-U3 · Point budget guard

**WHAT** — Per-org cap on history points written per sweep.

**WHY** — A 50k-node org must not turn one sweep into a 500k-row insert.

---

# L2.4.3 · Trend Computer (BLG-08)

### L2.4.3-U1 · Direction and magnitude

**WHAT** — Turns a series into a typed trend.

**WHY** — *"Declining"* is the word in every customer expectation, and there is currently
no function in the system that can produce it.

**WHERE** — `genios_engine/context/analytic/trend.py`

**HOW** (BLG-08) — deterministic, integer arithmetic, no statistics library:
```
INPUT   series: list[MetricPoint]  (dense, gaps explicit)
        min_points = 4             (below this -> INSUFFICIENT_HISTORY)

1. COVERAGE   known = [p for p in series if p.known]
              if len(known) < min_points          -> INSUFFICIENT_HISTORY
              if known / len(series) < 0.6        -> INSUFFICIENT_COVERAGE
                 (a series more than 40% gaps cannot support a trend claim)

2. SLOPE      integer least-squares over (period_index, value_bp)
              slope_bp_per_period = (n*Sxy - Sx*Sy) * 10000 // (n*Sxx - Sx*Sx)

3. NORMALIZE  relative_slope_bp = slope_bp_per_period * 10000 // max(mean_value, 1)
              (a drop of 5 means nothing on a base of 5000, everything on a base of 8)

4. DIRECTION  relative_slope_bp >  +500  -> RISING
              relative_slope_bp <  -500  -> DECLINING
              otherwise                  -> FLAT

5. STREAK     consecutive periods moving in the trend direction
              (a 3-month streak is a far stronger claim than a noisy slope)

6. CONFIDENCE trend_confidence_bp = f(point_count, coverage_ratio, streak_length,
                                      residual_dispersion)
              capped at 8000 — a trend is never certain
```

**OUTPUT**
```python
@dataclass(frozen=True)
class Trend:
    metric: str
    direction: str            # RISING | DECLINING | FLAT | INSUFFICIENT_HISTORY
                              # | INSUFFICIENT_COVERAGE
    relative_slope_bp: int
    streak_periods: int
    point_count: int
    coverage_ratio_bp: int
    period_start: datetime
    period_end: datetime
    trend_confidence_bp: int  # <= 8000
    evidence_points: tuple[MetricPoint, ...]   # the actual series, for the card
```

**Design points:**
- **Step 3 is the one people skip.** An absolute slope is meaningless without a base;
  normalizing against the mean is what makes "declining" comparable across metrics.
- **Step 1 refuses rather than guesses.** `INSUFFICIENT_COVERAGE` is a first-class
  answer. A series full of gaps produces no trend — it does not produce a weak one.
- **Confidence is capped at 8000.** Four points and a slope is not certainty.
- `evidence_points` travels with the trend so a card can show the actual numbers.

**LLM** — no. **EMBEDDINGS** — no. **STORAGE** — pure; results written as `derived.*` facts.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Trend on 2 points | noise reported as a pattern | `min_points = 4`, hard |
| Coverage gap read as decline | **false churn signal — the worst output this group can produce** | step 1 coverage ratio; gaps are never zero |
| Seasonality read as trend | quarterly business rhythm looks like decline every Q1 | out of scope for v2; documented as a known limitation, and `streak_periods` gives the reader the raw fact |
| Integer division precision loss | slope rounds to zero on small values | multiply before divide, tested at the boundaries |

**ACCEPTANCE**
```
pytest tests/context/analytic/test_trend.py -q
```
Required rows: a monotonic decline over 6 points -> `DECLINING` with `streak=6`; the same
values with 3 gaps -> `INSUFFICIENT_COVERAGE`, **not** `DECLINING`; a flat series with one
outlier -> `FLAT`; 3 points -> `INSUFFICIENT_HISTORY`; a decline of 5 on a base of 5000
-> `FLAT`; the same decline of 5 on a base of 8 -> `DECLINING`; identical input twice ->
byte-identical output.

**REVERSE PROMPT**
```
TASK: Build the trend computer. This is the first function in GeniOS that can say
"declining".

FILE: genios_engine/context/analytic/trend.py
PREREQUISITE: L2.4.1 metric history store green.

Implement:
  def compute_trend(series: list[MetricPoint], *, min_points: int = 4) -> Trend

ALGORITHM: the 6 ordered steps in doc 04 section L2.4.3-U1.

HARD RULES:
1. PURE. No DB, no network, no clock, no LLM. The series is passed in.
2. INTEGER MATH ONLY. Integer least squares. No numpy, no statistics module, no float
   at any point including intermediates. Multiply before dividing to preserve precision.
   Source-grep test for "float(" and "import numpy" and "import statistics".
3. NEVER INTERPOLATE A GAP. A missing period is known=False and is excluded from the
   fit, and it counts against coverage_ratio. An interpolated value is a fabricated
   observation that would flow into a card.
4. Step 3 (normalize against the mean) is not optional. An absolute slope is meaningless
   without a base. Test the 5-on-5000 vs 5-on-8 pair explicitly.
5. INSUFFICIENT_HISTORY and INSUFFICIENT_COVERAGE are first-class return values, not
   exceptions and not FLAT. Refusing to answer is correct behaviour.
6. trend_confidence_bp is capped at 8000. A trend is never certain.
7. evidence_points carries the actual series so a card can show the numbers.

TEST tests/context/analytic/test_trend.py — table-driven, every row in the ACCEPTANCE
list of doc 04 L2.4.3-U1, plus:
  - a series that rises then falls (V shape) -> FLAT or DECLINING, documented which
  - all-zero series -> FLAT, not a division error
  - single huge outlier at the end -> does not flip a 10-point flat series to RISING
  - determinism: same input twice -> identical output
```

### L2.4.3-U2 · Changepoint detection
**WHAT** — The period where a trend's direction changed. **WHY** — *"since March"* is far
more useful than *"declining"*. **HOW** — scan for the longest suffix whose direction
differs from the prefix; require both segments >= `min_points`.

### L2.4.3-U3 · Trend as a graph fact
**WHAT** — Writes the trend back as `derived.trend.<metric>` on the node so L3/L4 read it
like any other fact. **Carries `trend_confidence_bp` and a pointer to the series.**

---

# L2.4.4 · Cohort Builder (BLG-09)

### L2.4.4-U1 · Declarative cohort definitions

**WHAT** — A cohort is a **predicate a human wrote**, evaluated over the graph.

**WHY — and this is a deliberate rejection of the obvious approach.** A cohort produced
by clustering is a cohort nobody can explain, that changes on every re-fit, and that a
founder cannot correct. A cohort defined as *"accounts with ARR 10k–50k, onboarded in the
last 2 quarters, on the Growth plan"* is explainable, stable, correctable, and citable on
a card.

**Law 3 of Layer 2: cohorts are declared, never clustered.**

**WHERE** — `genios_engine/context/analytic/cohort.py`

**STORAGE**
```sql
create table if not exists cohort_definitions (
    cohort_id    text primary key,
    org_id       text not null,
    name         text not null,          -- "Growth plan, mid-ARR, recent"
    node_type    text not null,          -- account | deal | person
    predicate    jsonb not null,         -- the typed predicate tree
    created_by   text not null,          -- a human, or "system:default"
    created_at   timestamptz not null default now(),
    active       boolean not null default true
);
create table if not exists cohort_membership (
    org_id       text not null,
    cohort_id    text not null,
    node_id      text not null,
    joined_at    timestamptz not null,
    left_at      timestamptz,            -- membership is HISTORICAL, not just current
    primary key (org_id, cohort_id, node_id, joined_at)
);
```

**`left_at` matters more than it looks.** *"Accounts that left this cohort last month"* is
itself a churn signal, and it is only askable if membership is historical.

**HOW** (BLG-09) — a typed predicate tree, not free SQL:
```json
{"all": [
  {"fact": "account.arr_minor_units", "op": "between", "value": [1000000, 5000000]},
  {"fact": "account.plan", "op": "eq", "value": "growth"},
  {"fact": "account.onboarded_at", "op": "within_days", "value": 180}
]}
```
Operators: `eq · ne · in · lt · lte · gt · gte · between · within_days · exists · missing`.
Combinators: `all · any · none`.

**No free SQL, ever.** A predicate tree is safe, diffable, explainable on a card, and
cannot be an injection surface.

**Default cohorts shipped per domain** (so value exists before anyone authors one):
`all_active_accounts` · `accounts_by_arr_quartile` · `deals_by_stage` ·
`accounts_by_tenure_quartile` · `deals_by_size_quartile`

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Cohort too small | percentiles meaningless | **n >= 5 floor** — below it, `insufficient_population` (Law 2) |
| Cohort too broad | comparison says nothing | quartile cohorts by construction have balanced size |
| Predicate references a missing fact | silent empty cohort | `exists`/`missing` are explicit operators; a reference to an unregistered fact raises at definition time, not at evaluation |
| Membership churns every sweep | noisy joined/left events | hysteresis: a node must fail the predicate twice consecutively to leave |

**ACCEPTANCE**
```
pytest tests/context/analytic/test_cohort.py -q
# a predicate tree evaluates identically twice
# a node that fails once stays in the cohort; failing twice removes it with left_at set
# a cohort of 4 returns insufficient_population, not a percentile
# an unregistered fact name raises at DEFINITION time
# no code path constructs SQL from predicate strings (source-grep for f-string SQL)
```

**REVERSE PROMPT**
```
TASK: Build the cohort builder. Cohorts are DECLARED, never clustered.

FILE: genios_engine/context/analytic/cohort.py

WHY DECLARATIVE: a cohort from k-means cannot be explained on a card, changes on every
re-fit, and a founder cannot correct it. A cohort from a written predicate is
explainable, stable, correctable and citable. This is Law 3 of Layer 2.

Implement:
  - a typed predicate tree: operators eq/ne/in/lt/lte/gt/gte/between/within_days/
    exists/missing; combinators all/any/none
  - def evaluate(predicate, node_facts) -> bool          # PURE
  - def refresh_membership(conn, org_id, cohort_id, *, eval_time) -> MembershipDelta
  - migrations for cohort_definitions and cohort_membership (DDL in doc 04 L2.4.4-U1)

HARD RULES:
1. NO FREE SQL FROM PREDICATES. The predicate tree is interpreted in Python against
   loaded node facts, or compiled to parameterized SQL with a fixed operator whitelist.
   Never build a query by string interpolation. Add a source-grep test for f-string SQL.
2. NO CLUSTERING. No k-means, no embeddings, no "discovered segments". If you find
   yourself importing sklearn, stop — you are building the wrong thing.
3. Membership is HISTORICAL: left_at is set, rows are never deleted. "Accounts that left
   this cohort last month" is a churn signal and must be askable.
4. HYSTERESIS: a node must fail the predicate on two consecutive evaluations before
   left_at is set. Without it membership flaps and every sweep emits noise.
5. n >= 5 floor is enforced by the CONSUMER (L2.4.5), but the cohort API must expose
   population_size so the consumer can refuse.
6. A predicate referencing an unregistered fact name raises at DEFINITION time, not
   silently at evaluation time.

SHIP the 5 default cohorts named in doc 04 L2.4.4-U1 so value exists before a human
authors anything.

TEST tests/context/analytic/test_cohort.py — every row in the ACCEPTANCE list.
```

### L2.4.4-U2 · Quartile cohort generator
**WHAT** — Auto-generates quartile cohorts for registered numeric facts (ARR, deal size,
tenure). **WHY** — balanced populations by construction, and it gives every org usable
cohorts on day one with zero authoring.

### L2.4.4-U3 · Membership change events
**WHAT** — Emits `joined_cohort` / `left_cohort` observations. **WHY** — *"three accounts
dropped out of your healthy-engagement cohort this month"* is a pattern, and it is only
visible if membership transitions are recorded.

---

# L2.4.5 · Population Comparator (BLG-10)

### L2.4.5-U1 · Percentile within cohort

**WHAT** — Where does this node sit among its peers on this metric?

**WHY** — This is the primitive behind *"bottom decile"*, *"top quartile"*, *"unlike your
best customers"*. Every comparative statement the customer expects reduces to it.

**HOW** (BLG-10)
```
1. POPULATION  members = active cohort membership at eval_time
               values  = latest known metric value per member
               drop members whose value is unknown (coverage) — and RECORD how many

2. FLOOR       if len(values) < 5 -> INSUFFICIENT_POPULATION   (Law 2)
               if dropped/total > 0.4 -> INSUFFICIENT_COVERAGE

3. RANK        percentile_bp = nearest-rank, integer:
                   rank = count(v <= value)
                   percentile_bp = rank * 10000 // len(values)

4. BAND        decile / quartile label derived from percentile_bp

5. CITE        return population_size, cohort_id, computed_at, and the
               cohort's own p25/p50/p75 so a card can show the distribution
```

**Reuse, do not rewrite:** `context/support_situations.py:405 percentile_bp()` already
implements nearest-rank in Python (deliberately, because `percentile_cont` is
Postgres-only). Lift it into this module; do not write a second percentile.

**Law 2 enforced here:** the return value **always** carries `cohort_id` and
`population_size`. A percentile without its population is not returned at all.

**ACCEPTANCE**
```
pytest tests/context/analytic/test_comparator.py -q
# a cohort of 4 -> INSUFFICIENT_POPULATION
# a cohort where 50% have unknown values -> INSUFFICIENT_COVERAGE
# the lowest value in a cohort of 10 -> percentile_bp near 1000
# the returned object always carries cohort_id and population_size
# nearest-rank matches the existing support_situations implementation exactly
```

### L2.4.5-U2 · Lookalike comparison

**WHAT** — *"These 3 leads share traits with your highest-LTV customers."*

**HOW — deterministic, and deliberately not a similarity score:**
```
1. define the reference cohort  (e.g. accounts in the top ARR quartile)
2. compute the reference PROFILE: for each registered trait fact, the cohort's
   modal value (categorical) or interquartile range (numeric)
3. for a candidate node, count how many traits fall inside the reference profile
4. match_bp = matching_traits * 10000 // evaluated_traits
5. return the MATCHING TRAITS BY NAME, not just the score
```

**Step 5 is the point.** *"Matches on industry, company size and entry channel; differs
on region"* is actionable and checkable. *"0.87 similar"* is neither — and it is exactly
what `identity.py` refuses, for the same reason.

---

# L2.4.6 · Peer Baseline (BLG-11)

### L2.4.6-U1 · Per-cohort baseline ladder

**WHAT** — Cached p10/p25/p50/p75/p90 per (cohort, metric), recomputed nightly.

**WHY** — Every comparison would otherwise re-scan the whole population. It is also the
input to L1 v2's importance formula (`ALG-17` needs the org's p50 contract value —
`L1.6.7-U2` names this as its source).

**STORAGE**
```sql
create table if not exists peer_baselines (
    org_id      text not null,
    cohort_id   text not null,
    metric      text not null,
    p10_bp bigint, p25_bp bigint, p50_bp bigint, p75_bp bigint, p90_bp bigint,
    population  int not null,
    computed_at timestamptz not null,
    primary key (org_id, cohort_id, metric, computed_at)
);
```

Keyed by `computed_at` so baselines are **historical too** — a percentile computed in
March must be reproducible in September against March's ladder.

### L2.4.6-U2 · Cross-org baseline — **explicitly deferred**

**WHAT** — Comparing a tenant against other tenants.

**DECISION: not in v2.** It is the most tempting feature in this document and the most
dangerous. It requires a k-anonymity floor, an explicit opt-in, a legal review and a
privacy contract. A commit already exists adding *"pivot primitive, k-anonymity floor,
and subject-exclusion visibility"* (`c63def1`), which is the right foundation — but
cross-tenant comparison is a product decision with a compliance surface, not an
engineering task to slip into a layer plan.

**Every baseline in v2 is within one tenant.**

---

# L2.4.7 · Metric Correlator (BLG-12)

### L2.4.7-U1 · Pairwise metric association

**WHAT** — Does metric A move with metric B across a cohort?

**WHY** — *"customers who use Feature A in the first 7 days convert 2.3x better"* is the
"I didn't know we should be looking at this" moment Globe names as the product's highest
value. It is a correlation across a population.

**HOW** (BLG-12) — integer rank correlation (Spearman-style, no float):
```
1. pairs   = members with BOTH metrics known    (require n >= 20 — higher than the
                                                 percentile floor; a correlation on 5
                                                 points is numerology)
2. rank both metrics independently, average ranks on ties
3. rho_bp = 10000 - (6 * sum(d^2) * 10000) // (n * (n^2 - 1))
4. label:  |rho_bp| < 3000  -> NONE
           3000..5000       -> WEAK
           5000..7000       -> MODERATE
           > 7000           -> STRONG
5. ALWAYS return n, and ALWAYS return direction with the strength
```

**The mandatory disclaimer, carried in the contract itself:**
```python
@dataclass(frozen=True)
class MetricCorrelation:
    ...
    is_causal: bool = False        # ALWAYS False. This field exists to make the
                                   # absence of a causal claim explicit in the data,
                                   # so no downstream card can imply one.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Correlation presented as cause | **a wrong prescription with a confident receipt** | `is_causal=False` in the contract; L4 rendering must not use causal verbs |
| Multiple comparisons | scan 12 metrics, find spurious pairs by chance | only **registered metric pairs** are tested, declared in advance. No open-ended scanning |
| Small n | numerology | `n >= 20`, hard |

**Registered pairs are declared, not discovered** — the same discipline as cohorts. An
open-ended scan across all metric pairs will always find something, and what it finds
will usually be noise.

---

# L2.4.8 · Anomaly Detector (BLG-13)

### L2.4.8-U1 · Deviation from own baseline

**WHAT** — Is this node behaving unlike **itself**?

**WHY** — The complement to cohort comparison. An account can be top-quartile against
peers and still be collapsing relative to its own six-month norm — and that is the
earlier signal. *"Flagged 30+ days early"* usually comes from this, not from the cohort.

**HOW** (BLG-13)
```
1. baseline = median of the node's own trailing 6 periods (excluding current)
2. dispersion = median absolute deviation (MAD) — integer, robust to outliers
3. deviation_bp = |current - baseline| * 10000 // max(baseline, 1)
4. z_like = |current - baseline| * 10000 // max(MAD, 1)
5. flag if z_like > 30000 (roughly 3 MADs) AND deviation_bp > 2000
   -> BOTH conditions: statistically unusual AND materially large
6. require >= 6 known periods, else INSUFFICIENT_HISTORY
```

**MAD rather than standard deviation, deliberately:** business metrics are spiky, and one
big month must not widen the band so far that a genuine collapse looks normal.

**Step 5 requiring both conditions** is what stops a metric that normally sits at 2 going
to 4 from firing as a crisis: statistically unusual, materially trivial.

**ACCEPTANCE**
```
pytest tests/context/analytic/test_anomaly.py -q
# a stable series with one 5x spike -> flagged
# a noisy series with the same spike -> NOT flagged (MAD is wide)
# a 2 -> 4 move on a small-magnitude metric -> NOT flagged (deviation_bp too small)
# 5 periods of history -> INSUFFICIENT_HISTORY
# a coverage gap is not read as a drop to zero
```

---

## Group acceptance gate

```
pytest tests/context/analytic -q
grep -rn "float(\|import numpy\|import statistics\|sklearn" genios_engine/context/analytic/
grep -rn "LLMClient\|anthropic" genios_engine/context/analytic/
```
Expected: suite passes with 0 skips; **both greps return nothing.**

Plus, on a pilot tenant with 18 months of L1 v2 backfill:

| Metric | Gate | Why |
|---|---|---|
| nodes with >= 6 history points | > 60% of active accounts | trends need history |
| distinct trend directions observed | all of RISING/DECLINING/FLAT present | a computer that only says FLAT is not working |
| cohorts with population >= 5 | >= 3 | comparison needs populations |
| percentiles returned without `cohort_id` | **0** | Law 2 |
| interpolated values in any series | **0** | never fabricate an observation |
| coverage gaps rendered as zero | **0** | Law 4 |
| **a `DECLINING` trend on a real account, with its series citable** | **>= 1** | **this is the gate that proves the stratum works** |

The last row is the one that matters. It is the first time in GeniOS's history that the
system can say *"this is getting worse"* and show the numbers behind it.
