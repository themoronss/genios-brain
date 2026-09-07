# Layer 2 v2 — What Was Built

> **Created:** 2026-09-06 · **Status:** Active

**Purpose:** the unit-by-unit record of what Layer 2 v2 actually is in code — every package, what
it does, why it exists, and how it was proven — plus the gates that are not met and exactly what
would close them.

**Specification of record:** `Rohit_Updates (Version 2)/Version 2 Updates/02-Layer-2-Plan/` (docs
00–14). That set is the *design*. `docs/plans/L2_MISSING_UNIT_SPECS.md` writes the unit specs the
plan promised in prose and never wrote, and records the 20 assumptions the code was built under.
**This file is the *result*.**

---

## 1. The one-paragraph version

Layer 2 turns a tenant's graph into `BusinessSituationObject` — a situation with the numbers behind
it. It does that in three new strata laid beside the graph engines that already existed: an
**analytic stratum** that remembers what a metric was in March and can therefore say a thing is
getting worse, is unlike its peers, or has moved away from itself; a **quality stratum** that types
an absence so "no reply" and "no mailbox connected" stop being the same fact; and a **situation
engine** that composes an importance instead of stamping 5000 on everything, carries six confidence
axes instead of one number, and publishes a verbatim quote re-verified against the source text
rather than an event id. Nine waves, 54 of 56 units, eight gates — seven met, **H8 open on a
tenant**.

```
graph ──► L2.4 analytic ──► L2.5 quality ──► L2.6 patterns ──► L2.7 situation ──► BSO ──► Layer 3
          (history,          (typed          (declared         (importance,
           trend, cohort,     absence,        subgraph          six axes,
           baseline,          coverage        matches,          verified
           correlation,       epoch)          per-condition     spans)
           anomaly)                           evidence)
```

---

## 2. Totals

| | |
|---|---|
| Waves | 9 of 9 built (X0–X8) |
| Units | **54 of 56** (`L2.4.7-U2`, `L2.4.8-U2` open — `scripts/unit_ledger.py`) |
| Gates | **H0–H7 met · H8 open** (needs a real tenant and seven days) |
| Tests | **8,323 passing · 0 failing · 0 skipped · 152 xfailed** (real Postgres) |
| Migrations | 10 new for this layer (`0094`–`0106`, with `0095`/`0102`/`0103` unused) |
| New packages | `context/analytic/` `context/patterns/` `context/quality/` `context/lifecycle/` `context/framing/` |

The suite number is only meaningful against a real database. The hermetic lane silently skips ~800
tests — see §8.

---

## 3. The four doctrines everything obeys

Each is enforced by a test or a grep in a gate, because each records a failure that actually
happened.

**1 · The model DESCRIBES, never SCORES.** `lifecycle/judge.py` asks a model whether a sentence
*states* a resolution; the decision about whether the situation closes is made by
`lifecycle/gate.py` from the description. M-4 and M-6 do not decide. The 46-fixture golden set
carries a WRONG model answer on half its fixtures for exactly this reason: if the model's verdict
were the decision, half of them would flip.

**2 · Integer basis points.** No float, no `round()`, no `statistics`, no `numpy`, anywhere in the
X0–X8 units. Verified by grep across `context/analytic` `context/patterns` `context/quality`
`context/lifecycle` `context/framing` `context/importance.py` `context/situation_bso.py`
`context/authority_view.py` `context/correlation_*.py` `contracts/` `platform/l2_activation.py`:
**zero hits** outside docstrings. (`context/support_situations.py`, `waiting.py`, `periodic.py`,
`health.py` and `document_register.py` predate the plan and still hold floats; they are not L2 v2
units and are named here so the grep's scope is not mistaken for the layer's.)

**3 · No claim without a receipt.** A `DECLINING` trend stores a pointer to the series it was
computed from and the H8 report resolves it back to the exact points; a cohort position must name a
cohort somebody defined and whose members can still be enumerated; a pattern fire that cannot say
which object satisfied each condition is treated as a failure by the matcher itself; and a quote L1
flagged verified that fails a repeatable recheck **loses the flag**.

**4 · No clocks in logic.** `eval_time` is a parameter everywhere; the clock is read once at the
process boundary. Grep over the same package set returns exactly three reads, all boundary:
`patterns/store.py:511` (documented as the package's only one), `platform/l2_activation.py:286,327`
(the control-plane writer), and `lifecycle/resolution.py:107` (`eval_time or now()` at the sweep's
entry point — the drain always passes it; `runner.py:619`).

---

## 4. The layer, wave by wave

### X0 · `contracts/` — the vocabulary · gate **H0**

`contracts/analytic.py` (`MetricPoint`, `Trend`, `CohortPosition`, `MetricCorrelation`, `Anomaly`,
the floors `MIN_TREND_POINTS=4` `MIN_COHORT_POPULATION=5` `MIN_CORRELATION_SAMPLES=20`
`MIN_ANOMALY_PERIODS=6`), `contracts/quality.py`, `contracts/authority.py`,
`contracts/dependency.py`, and `contracts/situation.py` — the v2 `BusinessSituationObject` with all
eight validators.

The laws that bite: `known=False` with a value is **refused** (an interpolated point is a fabricated
observation, and it inflates the coverage ratio that exists to reveal the gap); `is_causal=True` is
refused on every path including `model_copy(update=…)`; a `CohortPosition` below the population
floor is unconstructible; `pattern_id` without `matched_conditions` is refused.

> **`contracts/situation.py` has ZERO production importers.** See §5.2 — this is the largest open
> item in the layer and it is not a small one.

### X1 · `context/analytic/history.py` `sampler.py` — metric history · gate **H1**

`metric_history` (migration `0094`) is the append-only table that answers *"what was true then?"*,
**beside** `graph_facts` and never instead of it (doc 09 item 6). Period-keyed: re-sampling a period
writes no second row. `PostgresMetricHistory.to_row` refuses an unregistered metric and a value the
column cannot hold, so a fixture cannot seed a series the sampler could not have produced.
`prune_history_for_drain` enforces `RETENTION_MONTHS`; `backfill_history_for_drain` reconstructs
18 months from the L1 event ledger so a new tenant's every trend does not read
`INSUFFICIENT_HISTORY`.

### X2 · `trend.py` `cohort.py` — direction and peers · gate **H2**

`compute_trend` is doc 04's six ordered steps, pure and clock-free: a robust slope and a
least-squares slope, both relative to a base, a direction only where the two agree, a streak, a
dispersion, and a confidence that falls with coverage. `find_changepoint` locates the break.
`cohort.py` holds the predicate language (`parse_predicate`, a registered fact vocabulary, refusals
at DEFINITION time), `define_cohort`, the shipped quartile families, and
`refresh_cohorts_for_drain` with its write budget.

### X3 · `comparator.py` `peer_baseline.py` — position and ladder · gate **H3**

`position_from_values` gives a nearest-rank percentile and a band, `compare_in_cohort` is the
route's door, and `publishable_distribution` is the **disclosure gate**: below
`MIN_BASELINE_POPULATION=10` the p25/p50/p75 ladder is WITHHELD, not degraded, because on a
five-member cohort the ladder *is* three other members' exact readings. The **D8 fix** narrows the
band scheme to quartiles below eleven members, so "bottom decile" can no longer be said about a
population that cannot express one.

### X4 · `correlator.py` `anomaly.py` — co-movement and outliers · gate **H4**

Spearman on ranks, integer throughout, `n < 20` refused, degenerate series refused, and `is_causal`
that exists in order to be `False`. `detect_anomaly` uses a MAD so a noisy series with a spike is
not flagged while a stable series with the same spike is.

### X5 · `context/importance.py` — BLG-18 · gate **H5**

`compose_situation_importance` takes L1's own base and moves it: corroboration by distinct source,
modifiers for trend / cohort / anomaly / dependency / conflict / freshness, a `+4000` cap on the
modifier sum, a coverage penalty, a clamp. Every term is a stored field of `ComposedImportance`, so
*"why is this a 7400"* is answerable from data without recomputation. Migration `0099` stores it.

**The guard that makes it honest:** if more than 90% of incoming signals still carry exactly 5000,
the composer logs `L1_IMPORTANCE_NOT_ACTIVE` and **refuses to synthesize a spread**. A fake
distribution is worse than a flat one, because it looks like it works.

### X6 · `patterns/` `quality/` `lifecycle/` `framing/` · gate **H6**

* **`patterns/`** — the declarative registry (six seed patterns in YAML), the matcher with its
  seven condition kinds, `ConditionEvidence` per satisfied condition and `ConditionFailure` for the
  one that stopped a silent pattern, the fire log (`0100`) and the per-pattern activation guard with
  both fire-rate limits.
* **`quality/`** — typed absence (`PRESENT` / `STALE` / `NOT_EXPECTED` / `UNKNOWABLE` /
  `GENUINELY_ABSENT`), the coverage epoch (`0104`), and `may_infer_absent` — the negative-inference
  licence, which `packs/compiler/context_adapter` now **asks** (see §6).
* **`lifecycle/`** — M-4 resolution detection: a model describes, a gate decides,
  `situation_resolution_claims` (`0101`) records the claim, `STATUS_PARTIALLY_RESOLVED` exists
  because three of five commitments discharged is neither closed nor untouched.
* **`framing/`** — M-6/M-7, headline and timeline, which may not fabricate a fact or leak across a
  visibility scope.
* **loop safety** — `runner.MAX_PASSES=3`, the convergence hash (`0105`),
  `scripts/derivation_dag_check.py` as a CI-enforceable acyclicity check.

### X7 · authority, point-in-time, dependency, cross-timeline · gate **H7**

`authority_rules` (`0097`) as DATA not an `if`, with no inferred rule auto-applied.
`graph_store.read_graph(as_of=…)` — the version window that makes a March decision replayable, and
`analytic/publish.publish_derived_fact` which opens a new window instead of moving the old one.
`correlation_dependency.py` and `correlation_timeline.py`.

### X8 · the publisher, the pilot switch, the shadow diff · gate **H8**

* `context/situation_bso.py` — ALG-08 re-verification at the publish seam (`verify_evidence_spans`,
  `gather_span_sources`, a grading pool of 200 so a verified quote in position 34 is no longer
  truncated away before it is graded), conflict records instead of pointers, the six-axis
  confidence vector in basis points with a `-1` not-applicable sentinel, pattern fires read in bulk,
  and `metadata['importance_fallback']` plus one INFO line per fallback publish.
* `contracts/situation_evidence.py` — `VerifiedEvidenceSpan` with `verified` **derived** from
  verdict + verification state, never passed.
* `context/runner.py` — the L2.6 pattern pass wired into the drain as a shadow pass, gated on the
  `patterns` switch. Before this line, `evaluate_org` was reachable only from an HTTP route,
  `pattern_fires` was empty on every tenant, and H8's comparison was structurally impossible.
* `platform/l2_activation.py` + `api/admin_routes.py` + migration `0106` — the per-tenant pilot
  switch, two independent switches, each keeping its own `disabled_at` so a week containing a
  mid-week switch-off is readable.
* `scripts/l2_shadow_diff.py` — the H8 report, read-only at the server, window end an argument.

---

## 5. What is NOT done

### 5.1 H8 — the pilot gate · **open, and it needs a tenant**

Everything H8 needs is built and every row was **exercised** against a scratch org driven by the
real drain. What it needs now is **a real tenant and seven days**, which no amount of code can
substitute for. Layer 1's G10 is open for the same reason.

**What exists:**

| Piece | Where |
|---|---|
| Activation as a per-tenant **row**, two switches | `l2_v2_activation` (`0106`), `platform/l2_activation.py` |
| The routes that flip it | `GET/POST/DELETE /admin/l2-activation` — `api/admin_routes.py` |
| The pattern pass on the drain | `context/runner.process_pending`, gated on `patterns` |
| The shadow-diff runner | `scripts/l2_shadow_diff.py` — read-only, target via `scripts/_db.py` |
| The old anchor path | still present, deliberately — deleted *after* H8, never before |

**What H8 asks for, and what a seeded pilot could show:**

| Metric | Gate | Demonstrated on a seeded org | Measured on a tenant |
|---|---|---|---|
| situations produced by both paths | 100% | 3/3 (10000 bp) | **needs a tenant** |
| a `DECLINING` trend, series citable | ≥ 1 | 1 of 1, 12 points resolved | **needs a tenant** |
| a cohort position, population named | ≥ 1 | 8 of 8, population 8, members enumerable | **needs a tenant** |
| a pattern match, per-condition evidence | ≥ 1 | 3 of 3 fires, 2 conditions each, both with refs | **needs a tenant** |
| founder-visible regressions | 0 | 0 | **needs a tenant** |

A seeded org proves the **arithmetic and the plumbing**. It cannot prove that the six shipped
patterns cover a customer's situations, that a real account's history makes a real decline, or that
a card a founder is actually looking at survives the switch-over. Those are counts over one
tenant's week and the report prints them under NOT MEASURED on every run.

**One property of the window worth knowing before the run.** A derived fact's `occurred_at` is the
sweep instant that last CHANGED it, and `publish_derived_fact` opens a new version window when the
value moves. So the H8 window must contain the sweep that wrote the fact — on a live tenant sweeping
daily, `--days 7` always does; on a frozen fixture, running further sweeps after the fact was
written can move it out of a fixed `--as-of` window and the trend row will read 0. That is the
report being correct about the window it was given, not a defect, and it is why `--as-of` exists.

**How to run it, when a tenant is available:**

```bash
# 1. enable BOTH switches for ONE org — a row, never a global default
curl -X POST /admin/l2-activation \
     -d '{"org_id":"<pilot>","switch":"both","notes":"L2 v2 pilot"}'
#    (or genios_engine.platform.l2_activation.activate(engine, org, switch=..., by=...))

# 2. let both paths run side by side for seven days, with no mid-week switch-off.
#    The report NAMES a switch-off inside the window rather than silently averaging over it.

# 3. read the diff — every row with its receipt
GENIOS_TARGET_DATABASE_URL="<pilot db>" \
  python scripts/l2_shadow_diff.py --org <pilot> --days 7

# 4. the distribution rows of the L2.7 group gate, on real situations
GENIOS_TARGET_DATABASE_URL="<pilot db>" \
  python scripts/situation_importance_distribution.py --org <pilot> --since 30d
#    gate: distinct importance values > 50 · p90-p50 > 1500 · at exactly 5000 < 5%

# 5. the pattern fire report, for the activation decision doc 06 requires
GENIOS_TARGET_DATABASE_URL="<pilot db>" \
  python scripts/pattern_fire_report.py --org <pilot> --since 30d

# 6. only after every lost situation has an explanation, activate the patterns that
#    earned it and remove the anchor path.
```

**The activation rule, in the plan's own words:** *"Built but not enabled is not done."*

### 5.2 `contracts/situation.py` is unreached · **the largest open item**

X0 built the v2 `BusinessSituationObject` — `ImportanceAttribution` with no default at any level,
typed `trends` / `cohort_positions` / `anomalies` / `correlations`, `missing_facts`, `conflicts`,
`pattern_id` + `matched_conditions`, and eight validators including doc 08's own law that a
`pattern_id` with no `matched_conditions` is refused.

**Nothing in `genios_engine/` or `scripts/` imports it.** Measured:

| contract file | production importers | test importers |
|---|---|---|
| `contracts/analytic.py` | 15 | 21 |
| `contracts/quality.py` | 6 | 10 |
| `contracts/authority.py` | 2 | 3 |
| `contracts/dependency.py` | 1 | 3 |
| `contracts/situation_evidence.py` | 1 | 1 |
| **`contracts/situation.py`** | **0** | 3 (two are its own gate) |

The live publisher (`context/situation_bso.build_business_situation`) constructs the OLDER
`contracts/domain_expertise.BusinessSituationObject` — a frozen dataclass with no validators — and
routes every piece of v2 material into its free `metadata` mapping. So H0 passes 45 tests against a
type production never builds, and doc 08's `pattern_id` law has never fired on a published object.

**This is not sloppiness, and the honest half matters.** `MatchedCondition.evidence` requires
`tuple[EvidenceSpan, ...]` — quote and offsets — and a pattern fire records
`ref="fact:<fact_version_id>"`, which is a pointer, not a span. **The pair is structurally
unfillable today**, and filling it would mean fabricating receipts, which doctrine 3 forbids
outright. What is owed is either (a) `patterns/matcher` carrying real spans for the fact conditions
that have them, then a migration of the publisher onto the v2 type, or (b) a decision that
`contracts/situation.py` is a design record rather than a runtime type — **stated in the file**,
not left as a silence. Either is a wave; neither is an H8 fix.

### 5.3 Known-and-accepted

| Item | Status |
|---|---|
| **`L2.5.8-U1` — the ADMIT step** | not built. `publish_situation(...) -> BSO \| Held` puts admission BEFORE construction, so it cannot be bolted onto the builder later. Whole-unit gap; `L2_MISSING_UNIT_SPECS.md` gives it 1 owed, 0 built |
| **"BSOs with a verified span — 100%"** | not reachable by the publisher alone. Five other writers of `context_situations` (`periodic`, `meeting_touch`, `support_situations`, `outreach_situations`, `document_register`) mint situations with no L1 signal seam; on the live probe 2 of 5 published BSOs carried verified spans and 3 rested on no `qualified_signals` row at all. Closing it is L2.5.8's admission gate or a signal seam for those writers — **not** stamping "verified" on an unchecked receipt |
| **`domain_shadow._ACTIVE_SITUATIONS` filters `status='active'`** | so a `partial` situation never reaches Layer 3 on the live path, though the builder preserves `partial` correctly. Widening the WHERE clause changes WHICH situations reach Layer 3 — a product decision |
| **Per-situation read cost** | `domain_shadow` calls `gather_l1_signals` once per situation, now up to 2 extra indexed reads each — ~400 extra round trips at the 200-situation ceiling. The bulk readers exist; collapsing the loop onto them is a restructure |
| **`chunk:<doc_id>:<n>` spans** | cannot be re-verified at L2 (no chunk text store). They fall back to L1's verdict, labelled `l1_verified`, and are never counted as our own check |
| **`L2.4.7-U2` / `L2.4.8-U2`** | promised, unwritten. `scripts/unit_ledger.py --check` fails if the gap grows |
| **`peer_baseline.cross_org_baseline`** | explicitly deferred at `runner.py:799` — doc 04 calls it "the most valuable feature in this document and the most dangerous" |
| **`quality/lens.lens_from_epochs`** | deferred: `read_coverage_lens` is the live door (wired at `situations.py:768`); replaying a PAST coverage regime has no caller yet |
| **A pytest collection fragility, pre-existing** | the FULL suite is green on a virgin database, but a hand-picked subset can lose `tests/context/conftest.py`: `pytest tests/context/test_l2_shadow_diff.py tests/test_l2_pilot_activation.py tests/context/quality` reports 18 errors, all `fixture 'eval_time' not found`, while every pair of those three passes. Reproduced with this wave's new tests stripped out, so it predates them; not caused by the `sys.path.insert` in the shadow-diff test either (removing it changes nothing). It costs nothing on the full run and will waste somebody's afternoon on a subset — **always run the whole suite before believing a subset failure** |
| **`is_causal` via `model_construct`** | pydantic's documented bypass, deliberately left open by `contracts/analytic.py:220-223`; `model_copy`, the constructor and `setattr` are all closed |

---

## 6. How this was proven

Every wave ran build → gate → adversarial review → fix. This section is the H8 gate's own review,
and its value is the defects, not the green numbers.

### 6.1 The three bold rows, with their receipts

Doc 09: *"a row that counts 1 but cannot show the numbers has not met the gate."* Run against a
scratch org seeded with the right shapes and swept by `context/runner.process_pending` — the same
call every sync route makes — with `refresh_situations` driven at the same instant:

**`this is getting worse`** — `node_h8_acct_00`, `deal.stage_age_days`, confidence 7968 bp, relative
slope −1190 bp, streak 12. The trend fact's own series pointer resolved to exactly the 12 points it
claims, and they fall monotonically: 140 → 130 → 120 → 110 → 100 → 90 → 80 → 70 → 60 → 50 → 40 → 20
days. The direction is what the series supports.

**`this is unlike its peers`** — percentile 1250 bp, band **Q1**, cohort `coh_0245…` *"All active
accounts"* (`company`, by `system:default`), population 8, all 8 members enumerable at the window's
end. **The band is one the population can express**: eight members, so quartiles — X3's D8 fix
holds, and a "bottom decile" claim is unreachable here. Checked independently across every
population from 5 to 20: **0 empty bands, quartiles below 11, deciles at 11 and above.** The ladder
is `null` and that is correct — the disclosure gate withholds it below ten members and states why
in the row.

**`these facts hold together`** — `condition_now_satisfied@1` on three anchors, 6000 bp, shadow.
Each fire carries both required conditions with a recoverable ref:

```
#0 fact derived.timeline.condition_satisfied exists -> observed {'statement': 'we will send it
   once legal signs off'}   ref=fact:fv_…_derived.timeline.condition_satisfied
#1 fact thread.ball_in_court eq 'us' -> observed 'us'
   ref=fact:fv_…_thread.ball_in_court
```

### 6.2 Two defects the report itself had — found by running it, not by reading it

Both were invisible in the code and obvious in the output.

* **A withheld ladder printed as three blanks.** `comparator.position_fact_value` withholds the
  distribution below ten members and states the reason in the row *precisely* so that a reader
  cannot confuse "too small to describe" with "an older writer wrote this". The report dropped the
  sentence and printed `ladder p25=None p50=None p75=None`, re-opening that ambiguity at the one
  place it is read as evidence. Now prints `ladder WITHHELD — a distribution needs 10 members…`.
* **The patterns that did NOT fire were invisible.** Doc 06's second failure mode is a pattern that
  never fires, and `store.record_evaluation` writes a `pattern_runs` row for every pattern including
  the silent ones — the only reason the distinction is recoverable. The report ignored it, so a fire
  count of zero could not distinguish "this tenant has no such situation" from "condition 0 reads a
  field this tenant spells differently". Now printed, and never scored:

```
commitment_unresolved@1    0 anchors considered, 0 fires — nothing to match
founder_bottleneck@1       4 anchors considered, 0 fires — stopped at condition #0
                           (fact_missing) on authority.sole_approver_subject_count
relationship_going_cold@1  8 anchors considered, 0 fires — stopped at condition #0
                           (fact_missing) on account.status
```

### 6.3 The evidence upgrade, end to end and then broken

A BSO published through `run_sync → process_pending → run_all → shadow_compile →
build_business_situation`, with the offsets re-checked here against the stored
`prepared_content.clean_text` rather than trusted:

```
verified=True verification=l2_reverified verdict=verified [43:95]
  quote        = 'we can move forward with the $84,000 annual contract'
  source[43:95]= 'we can move forward with the $84,000 annual contract'   MATCHES: True
verified=True verification=l2_reverified verdict=verified [97:128]
  quote        = 'I still need Finance to confirm'
  source[97:128]='I still need Finance to confirm'                        MATCHES: True
confidence_vector = {evidence 3300, freshness 5000, consistency 10000,
                     identity 4000, coverage 5000, analytic -1}
```

Then the span was broken, two ways, and the two answers are both right:

* **offsets shifted +7** → `verdict=verified_relocated`, offsets **rewritten** to what ALG-08 found.
  The quote is still verbatim in the source, so the receipt still resolves.
* **the quote replaced with a sentence the email never contained** → `verified=False`,
  `verification=unverified`, `verdict=invalid_bounds`, and `evidence_verified_spans` **2 → 0**, even
  though L1 had stored `verified: true` on the row. A check we can repeat outranks a flag we cannot.

**Stated precisely, because the gate's wording invites a stronger claim than the code makes:**
publication does not refuse. The BSO is still published; the *claim* is refused — the flag is
stripped, the verdict is recorded, and the verified count goes to zero. Holding the situation back
entirely is `L2.5.8-U1` (§5.3), which is not built.

### 6.4 The seven must-not-regress rows, violated one at a time

Not taken on trust — each was broken in the source and the suite re-run.

| # | Must not regress | The violation | Tests red |
|---|---|---|---|
| 1 | No embeddings / edit distance in identity | `import difflib` added to `identity.py` | **1** |
| 2 | Governed merges — proposal, history, reversibility | `_snapshot` returns `{}` | **1** |
| 3 | The confidence VECTOR, never a scalar | `analytic_score` returns the overall number | **19** |
| 4 | Tenant node excluded from `ANCHOR_PRIORITY` | `"tenant"` appended to it | **2** |
| 5 | Correlation refuses to prioritise | `correlation.py` imports the composer | **1** |
| 6a | `graph_facts` keeps OVERWRITING | `derived.py`'s upsert becomes `do nothing` | **1** |
| 6b | …and the analytic writer's UNCHANGED branch | the short-circuit removed | **7** |
| 7 | Layer import direction | `situations.py` imports `reason.runner` | **2** |
| 8 | Tests never reach production | the resolver grows a `get_settings` fallback | **1** |

**Item 6 measured, not asserted** — this is the row doc 09 calls the one most likely to be got
wrong. Twelve sweeps of `process_pending` at twelve distinct instants over an unchanging value:

```
sweep    graph_facts   active   derived.*   metric_history
 seed             45       45          27               19
    1 … 12        45       45          27               19
```

**Flat. Zero growth, on both tables.** History lives in `metric_history` and it is period-keyed, so
re-sampling the same period writes no row either — H1's decisive number, measured on the same run.

### 6.5 The earlier gates, re-measured

| Gate | The decisive number | Result |
|---|---|---|
| **H0** | 8 validators enforced; an old-shaped BSO still constructs | 45 passed |
| **H1** | re-sampling a period twice → duplicate rows · interpolated values | **0 · 0** (contract refuses `known=False` with a value) |
| **H2** | 6-point monotonic decline → `DECLINING` | ✔ conf 6800 bp, coverage 10000 bp |
| | the same values with 3 gaps | **`INSUFFICIENT_HISTORY`** (only 3 known points) |
| | 6 readings scattered over 11 periods | **`INSUFFICIENT_COVERAGE`**, coverage 5454 bp |
| | decline of 5 on a base of 5000 / on a base of 8 | `FLAT` / `DECLINING` |
| | a cohort of 4 | `INSUFFICIENT_POPULATION` |
| **H3** | empty bands at any population 5…20 | **0**; quartiles < 11, deciles ≥ 11 |
| **H4** | `is_causal` set via kwarg / `model_copy` / `setattr` | **refused on all three**; `model_construct` open by documented decision |
| | `n < 20` | refused |
| **H5** | 223 situations · distinct values | **213** (gate > 50) |
| | p50 / p90 → spread | 5152 / 7268 → **2116 bp** (gate > 1500) |
| | at exactly 5000 | **2/223 = 0.89%** (gate < 5%) |
| | components populated · identical input twice | **100% · byte-identical** |
| **H6** | M-4 false-positive rate on the 46-fixture golden set | **0 bp** (ceiling 200 bp); 3 misses, each one unnecessary nudge |
| | Hinglish fixtures · patterns registered | **11** (gate ≥ 8) · **6** (gate ≥ 6) |
| | derivation graph acyclic | **PASS** — 38 derived products, 56 edges, no cycle |
| **H7** | `read_graph(as_of=April)` after a September sweep | returns **March's** row (`declining`), September's is `[Sep, ∞)` |
| | `read_graph(as_of=now)` vs `live_graph()` | **equal** |

### 6.6 Mutation testing of the X8 units

| Mutation | Tests red |
|---|---|
| span re-verification removed — L1's flag taken on trust | **9** |
| verified-first ordering dropped before the cap | **1** |
| the grading pool shrinks back to `MAX_EVIDENCE` (a verified quote past position 20 is lost) | **1** |
| the fallback log line silenced | **3** |
| `metadata['importance_fallback']` always `False` | **3** |
| re-activating a LIVE switch refreshes `enabled_at` (the pilot start date moves) | **1** |
| a revived switch keeps the ORIGINAL enabling instead of taking the new one | **11** |
| `require_switch` accepts any string (a column name from caller text) | **2** |
| the gate read stops failing CLOSED | **1** |
| the drain runs the pattern pass whether or not the switch is on | **2** |

*A note on method that cost an hour and is worth carrying:* three of these first reported **0
failed**, and all three were the harness's fault, not the code's — a `str.replace(…, 1)` that hit an
earlier identical line, and one patch that was a no-op the script reported as applied. A surviving
mutant is a claim about the tests and deserves the same scepticism as any other claim. Each was
re-cut against the exact line and killed.

### 6.7 The wiring audit — "a test calls it" is not a caller

597 public callables under `genios_engine/context/`, closed transitively from the drain, every
`api/` route module, `main.py`, `platform/wiring.py` and `scripts/`. **40 are unreached.** The X0–X8
ones, classified:

| Callable | Verdict |
|---|---|
| `quality/inference.may_infer_absent` | **defect — fixed.** The licence had no caller because its one consumer, `packs/compiler/context_adapter`, spelled the `in` out again. Two copies of one rule is how the next consumer gets a third; the adapter now asks |
| `correlation_timeline.satisfy` | **defect — fixed.** `correlate_timeline` rebuilt the `SatisfiedCondition` inline, leaving two definitions of "when has a dormant condition come true, and how strongly". It now calls `satisfy`, which takes an optional precomputed verdict so nothing is evaluated twice |
| `peer_baseline.cross_org_baseline` | correctly deferred — refused at `runner.py:799` with the reason |
| `quality/lens.lens_from_epochs` | correctly deferred — the past-regime lens; `read_coverage_lens` is the live door |
| `cohort.position_in_cohort` | correctly superseded — routes use `comparator.compare_in_cohort` and two route docstrings say why |
| `cohort.predicate_fingerprint`, `lifecycle/prompt.fence_markers` | spare accessors, no caller, no duplicate rule. Harmless; named so they are not rediscovered |
| `history.InMemoryMetricHistory`, `authority_view.InMemoryAuthorityRules` | in-memory implementations of a Protocol; correctly internal |

The remaining 31 are in `support_situations.py`, `outreach_situations.py`, `periodic.py`,
`canon.py`, `derived.py`, `projections.py`, `identity.py` and `extract/` — modules that predate this
plan. They are out of L2 v2's scope and are recorded here rather than fixed.

### 6.8 The recurring shape

Layer 1 shipped six units that nothing called. Layer 2 has now produced eight —
`backfill_org`, `membership_changes`, `correlate_series`, `load_baseline`, `compare_in_cohort`
(fixed in earlier waves), `patterns.evaluate_org` (fixed in X8 by wiring the drain), and
`may_infer_absent` / `satisfy` (fixed here) — plus the whole of `contracts/situation.py`, which is
the same defect at the scale of a file rather than a function (§5.2).

The technique that finds it is not code review. It is a reachability closure from the real entry
points, run as a report, with every unreached name **classified in writing** as correctly internal,
correctly deferred, or a defect. A name with no verdict beside it is a defect nobody has looked at
yet.

---

## 7. Database

10 new migrations, `0094`–`0106` (`0095`, `0102`, `0103` were never used):

| Migration | Table |
|---|---|
| `0094` | `metric_history` — *"what was true then?"*, append-only, period-keyed |
| `0096` | `cohort_definitions` + `cohort_membership` — WHO a tenant is compared against |
| `0097` | `authority_rules` — *"Arjun approves contracts > $50K"* as DATA |
| `0098` | `peer_baselines` — the cached p10/p25/p50/p75/p90 ladder per (cohort, metric) |
| `0099` | situation importance, STORED — the four columns that make H5 measurable |
| `0100` | `pattern_fires` + `pattern_runs` + `pattern_activation` — doc 06's two failure modes |
| `0101` | `situation_resolution_claims` — M-4, the third way a situation can end |
| `0104` | `situation_absences` + `coverage_epochs` — typed absence and its regime |
| `0105` | `l2_convergence` — the drain's convergence ledger |
| `0106` | `l2_v2_activation` — the pilot switch, two independent switches per tenant |

**Every one is in the tenant-erasure list at `api/account_routes.py`**, and that is not optional:
the list executes `delete from {tbl} where org_id=:o` with no try/except, so a table missing from it
breaks org deletion for every tenant. `pattern_fires`, `pattern_runs`, `pattern_activation` and
`l2_v2_activation` were added to it in X8.

**Two hazards worth carrying forward:**

1. **Nothing in a BSO's `metadata` may be derived from a clock.** `metadata` is hashed into the
   expertise package's content address, so a per-sweep value there mints a fresh ~238 kB row per
   situation per sweep — the exact mechanism that took the database read-only at 995 MB. No
   `eval_time`, no `fire_id`, no `evaluated_at`, no `detected_at`. Pinned by a
   same-hash-across-publishes test.
2. **`graph_facts` and `metric_history` are two tables answering two questions.** The instinct on
   reading "we need history" is to stop overwriting `graph_facts`; that would grow it by three rows
   per node per drain for ever and make every "latest" read sift duplicates. §6.4 measures that it
   has not happened.

---

## 8. Running it

```bash
cd genios-brain

# real-Postgres lane — ALWAYS use this. The hermetic lane skips ~800 tests silently.
dropdb --if-exists genios_scratch; createdb genios_scratch   # drop first: a dirty DB lies
GENIOS_TEST_DATABASE_URL="postgresql://$USER@localhost:5432/genios_scratch" \
  ./.venv/bin/python -m pytest -q -p no:randomly
# expect: 8323 passed, 0 failed, 0 skipped, 152 xfailed

# the L2 gate files, individually
… -m pytest tests/contracts/test_h0_gate.py                                   # H0
… -m pytest tests/context/analytic/test_history.py tests/context/analytic/test_sampler.py   # H1
… -m pytest tests/context/analytic/test_trend.py tests/context/analytic/test_cohort.py      # H2
… -m pytest tests/context/analytic/test_comparator.py                          # H3
… -m pytest tests/context/analytic/test_correlator.py tests/context/analytic/test_anomaly.py # H4
… -m pytest tests/context/test_situation_importance.py                         # H5
… -m pytest tests/context/patterns tests/context/quality tests/context/lifecycle # H6
… -m pytest tests/context/test_authority.py tests/context/test_point_in_time.py # H7
… -m pytest tests/context/test_l2_shadow_diff.py tests/test_l2_pilot_activation.py \
            tests/context/test_situation_publisher.py                          # H8
… -m pytest tests/context/test_l2_must_not_regress.py                          # doc 09's table

# the purity greps — gate criteria, not lint. All must return nothing.
grep -rnE '\bfloat\(|\bround\(|import numpy|from statistics' \
     genios_engine/context/{analytic,patterns,quality,lifecycle,framing} \
     genios_engine/context/{importance,situation_bso,authority_view}.py
grep -rn 'datetime\.now(\|utcnow(' \
     genios_engine/context/{analytic,quality,framing} genios_engine/contracts/analytic.py
grep -rn 'sklearn\|KMeans\|difflib\|SequenceMatcher' genios_engine/context/

# CI-enforceable structural checks
python scripts/derivation_dag_check.py      # the derivation graph is acyclic
python scripts/unit_ledger.py --check       # the promised-vs-written gap may only shrink

# gate reports — they never fall back to the configured database
GENIOS_TARGET_DATABASE_URL="<db>" python scripts/l2_shadow_diff.py --org <org> --days 7
GENIOS_TARGET_DATABASE_URL="<db>" python scripts/situation_importance_distribution.py --org <org> --since 30d
GENIOS_TARGET_DATABASE_URL="<db>" python scripts/pattern_fire_report.py --org <org> --since 30d
GENIOS_TARGET_DATABASE_URL="<db>" python scripts/history_density_report.py --org <org>
```

---

## 9. Where things live

| Concern | Module |
|---|---|
| The typed vocabulary | `contracts/{analytic,quality,authority,dependency,situation,situation_evidence}.py` |
| What a metric was in March | `context/analytic/{history,sampler}.py` · `metric_history` |
| Which way it is moving | `context/analytic/{trend,gap_reason}.py` |
| Who it is compared against | `context/analytic/{cohort,comparator,peer_baseline}.py` |
| Co-movement and outliers | `context/analytic/{correlator,anomaly}.py` |
| Writing a derived fact without losing March | `context/analytic/publish.py` |
| Typed absence and the licence to infer from it | `context/quality/{missing,epoch,lens,inference}.py` |
| Declared subgraph patterns | `context/patterns/` · `pattern_fires` |
| How a situation ends | `context/lifecycle/` · `situation_resolution_claims` |
| How much a situation matters | `context/importance.py` |
| Six confidence axes | `context/situations.py` |
| The published object | `context/situation_bso.py` → `reason/domain_shadow.py` |
| The graph as it stood | `context/graph_store.read_graph(as_of=…)` |
| The drain that runs all of it | `context/runner.process_pending` |
| The pilot switch | `platform/l2_activation.py` · `api/admin_routes.py` · `l2_v2_activation` |
| The gate reports | `scripts/l2_shadow_diff.py` and its four siblings |

---

## 10. Next

1. **Run H8 on a real tenant** (§5.1). Nothing else in this layer is waiting on code.
2. **Decide `contracts/situation.py`** (§5.2) — migrate the publisher onto it, or state in the file
   that it is a design record. Its current silence is the worst of the three options.
3. **`L2.5.8-U1`, the ADMIT step** — the only whole unit still owed, and the thing that would let
   "100% of BSOs carry a verified span" become reachable rather than aspirational.
4. **Widen `domain_shadow._ACTIVE_SITUATIONS` to `partial`** — an owner's decision, not an
   engineer's: it changes which situations a founder sees.
5. **Collapse `domain_shadow`'s per-situation reads onto the bulk readers** before a tenant with
   200 live situations meets the publisher.
6. **`L2.4.7-U2` and `L2.4.8-U2`** — the last two unwritten unit specs.
