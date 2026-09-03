# L2.6 — Situation Candidate Generator

**Group responsibility:** where a graph pattern becomes a candidate business reality.

**Group law:** *Graph patterns, not text patterns.* **LLM forbidden for detection.**

**Status:** 0 of 3 built as specified. The code detects situations by **anchor type**; the
spec calls for **subgraph pattern matching**. These are materially different capabilities.

---

## Component map

| # | Component | BLG | Status |
|---|---|---|---|
| L2.6.1 | **Pattern Matcher** | BLG-16 | ⚠️ **anchor-based, no pattern registry** |
| L2.6.2 | Candidate Builder | — | ⚠️ partial |
| L2.6.3 | Candidate Scorer | — | ❌ missing |

---

## The gap, precisely

Today: `situations.py:83` — `situation_type(anchor_type, domain)`. The situation's type is
derived from **what kind of node the anchor is**.

Globe's worked example needs six conditions to co-occur:

> contract renewal **+** auto-renewal **+** high value **+** short cancellation window
> **+** active migration discussion **+** no scheduled decision

**An anchor type cannot express that.** Anchor-based detection asks *"what is this
about?"*; pattern matching asks *"do these six things hold together right now?"* The
second is what produces a situation worth interrupting someone for.

This is also why Globe's fifteen Admin surfaces cannot be built on the current L2 — each
one is a distinct **pattern**, and there is no registry to declare them in.

---

# L2.6.1 · Pattern Matcher (BLG-16)

### L2.6.1-U1 · The pattern registry

**WHAT** — Declarative subgraph patterns, one per detectable situation.

**WHY** — Adding a new detectable situation should be **a registry entry**, not an
engineering change. That is the same discipline as cohorts (L2.4.4) and expectation maps
(L2.5.5), and for the same reason: declared things are explainable, diffable and
correctable.

**WHERE** — `genios_engine/context/patterns/registry.py`

**HOW** (BLG-16) — a pattern is a typed conjunction over the graph:

```yaml
pattern_id: vendor_renewal_unowned
version: 1
domain: [admin, finance]
anchor: {node_type: contract}
conditions:
  - {kind: fact,       field: contract.auto_renews,        op: eq,      value: true}
  - {kind: fact,       field: contract.value_minor_units,  op: gte,     value: "@authority_threshold"}
  - {kind: temporal,   field: contract.cancellable_until,  op: within_days, value: 30}
  - {kind: absence,    field: decision.scheduled,          type: GENUINELY_ABSENT}
  - {kind: edge,       type: owns, from: "@anchor",        op: missing}
optional_signals:
  - {kind: observation, kind_name: migration_discussed,    weight_bp: 1500}
  - {kind: trend,       metric: engagement.touch_count_28d, direction: DECLINING, weight_bp: 1000}
emits:
  situation_type: vendor_renewal_decision
```

**Condition kinds** — each maps to a group already built or planned:

| kind | reads | from |
|---|---|---|
| `fact` | `graph_facts` | L2.1 |
| `edge` | `graph_edges` (present **or missing**) | L2.1 |
| `temporal` | date proximity | L2.1.3 |
| `absence` | **typed** absence | **L2.5.5** |
| `trend` | direction + confidence | **L2.4.3** |
| `cohort` | percentile position | **L2.4.5** |
| `anomaly` | deviation vs own baseline | **L2.4.8** |
| `observation` | `graph_observations` | L2.1 |

**The last four condition kinds are only expressible because L2.4 and L2.5.5 exist.**
That is the concrete payoff of the analytic stratum: patterns like *"engagement declining
AND bottom-decile in its cohort AND no owner"* become **declarable**, and that single
pattern is a churn detector nobody had to write code for.

**`@authority_threshold`** resolves against the Authority view (L2.1.4) — so "high value"
means *this company's* approval threshold, not a hardcoded number.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Pattern too loose | fires constantly, becomes noise | every pattern declares an expected fire rate; exceeding it 10x blocks activation |
| Pattern too tight | never fires | a pattern with zero fires in 30 days is reported for review |
| Patterns overlap | three cards for one reality | L2.7.3 clustering merges by shared entity — patterns may overlap, situations must not |
| A condition references a missing capability | silent non-fire | conditions validate at **registration** time against available condition kinds |

**ACCEPTANCE**
```
pytest tests/context/patterns/test_registry.py -q
# a pattern with 5 conditions fires only when all 5 hold
# an optional_signal raises confidence but is not required to fire
# a pattern referencing an unavailable condition kind fails at REGISTRATION
# @authority_threshold resolves against the org's own Authority view
# the same graph state evaluated twice fires identically
```

**REVERSE PROMPT**
```
TASK: Build the subgraph pattern registry. This replaces anchor-type situation detection.
FILES: genios_engine/context/patterns/registry.py, matcher.py

THE GAP: situations.py:83 derives situation type from anchor_type. That cannot express
Globe's own worked example, which needs SIX conditions to co-occur: renewal + auto-renew
+ high value + short cancellation window + migration discussion + no scheduled decision.

PREREQUISITES: L2.4 (trend/cohort/anomaly conditions) and L2.5.5 (typed absence). Without
them, four of the eight condition kinds cannot be evaluated.

IMPLEMENT:
  - a YAML pattern schema per doc 06 section L2.6.1-U1
  - condition kinds: fact, edge, temporal, absence, trend, cohort, anomaly, observation
  - def match(pattern, graph_slice, *, eval_time) -> MatchResult | None   # PURE
  - registration-time validation of every condition against available kinds

HARD RULES:
1. DECLARATIVE ONLY. A pattern is data. Adding a detectable situation is a registry
   entry, not a code change. No pattern logic in Python beyond the evaluator.
2. NO LLM in detection. The model may later name the situation (LLM-6, cosmetic) and may
   not alter a single number in it.
3. `absence` conditions consume the TYPED absence from L2.5.5. GENUINELY_ABSENT satisfies
   an absence condition; UNKNOWABLE does NOT. Getting this backwards produces confident
   findings from missing connectors.
4. `@authority_threshold` and other @-references resolve against the graph at eval_time,
   never against a constant.
5. Conditions referencing an unavailable kind fail at REGISTRATION, loudly. A silently
   non-firing pattern is indistinguishable from a working one that found nothing.
6. Every pattern declares expected_fire_rate. Exceeding it 10x on a pilot blocks
   activation — a pattern that fires constantly is noise, not intelligence.

SHIP these patterns first (they are Globe's V1-reachable surfaces):
  commitment_unresolved · relationship_going_cold · meeting_preparation_gap ·
  founder_bottleneck · condition_now_satisfied · vendor_renewal_unowned

MIGRATE: keep anchor-based detection running alongside. Compare fire sets on a pilot for
7 days before switching. Do not delete the anchor path in this wave.

TEST tests/context/patterns/test_registry.py — every row in the ACCEPTANCE list.
```

### L2.6.2-U1 · Candidate Builder
Assembles a match into a provisional object: matched nodes, matched edges, the evidence
that satisfied **each** condition. **Per-condition evidence is required** — "this fired
because of these five facts" is what makes a situation explainable.

### L2.6.3-U1 · Candidate Scorer
Match strength (required conditions are binary; `optional_signals` contribute
`weight_bp`) plus quality carry-through from L2.5. **Still not a situation, still not a
decision** — the scorer only decides whether a candidate is worth promoting.

---

## Group acceptance gate

```
pytest tests/context/patterns -q
python scripts/pattern_fire_report.py --org <pilot> --since 30d
```

| Metric | Gate |
|---|---|
| registered patterns | >= 6 |
| patterns with zero fires in 30d | reported for review |
| patterns exceeding expected fire rate 10x | **0 activated** |
| candidates carrying per-condition evidence | 100% |
| `UNKNOWABLE` absences satisfying an absence condition | **0** |
