# L3.1 — Domain Compiler

**Group responsibility:** assemble exactly the expertise this situation needs — and
nothing else. Retrieve and bind; never decide.

**Status: 9/9 built, 1:1 with Globe. This group is overwhelmingly a PRESERVE list,
with three input-side changes.**

---

## Component map

| # | Component | File | Verdict |
|---|---|---|---|
| L3.1.1 | Capability Resolver | `capability_resolver.py` | ✅ preserve — admission-hash validation lives here |
| L3.1.2 | Object Resolver | `object_resolver.py` | ✅ preserve |
| L3.1.3 | Brain Resolver | `brain_resolver.py` | ✅ **preserve hard** — snapshot pinning is Law 2's mechanism |
| L3.1.4 | Knowledge Retriever | `knowledge_retriever.py` | ✅ preserve |
| L3.1.5 | Context Adapter | `context_adapter.py` | ⚠️ **extend** — U1 below |
| L3.1.6 | Evidence Aggregator | `evidence_aggregator.py` | ✅ preserve |
| L3.1.7 | Expertise Builder | `expertise_builder.py` | ✅ preserve |
| L3.1.8 | Expertise Publisher | `expertise_publisher.py` | ⚠️ extend — package additions (doc 05) |
| L3.1.9 | Capability Registry | generated reverse index | ⚠️ extend — U2 below |

**Preserve-hard list** (a PR touching these while doing something else is rejected):
snapshot pinning (`brain_resolver.py`) · admission-hash validation
(`capability_resolver.py:103-131`) · three-state predicate evaluation
(`context_adapter.py`) · the never-hand-edit rule on the generated registry ·
`expertise_packages` churn suppression (`e1a0c47`).

---

# L3.1-U1 · Context Adapter: consume the L2 v2 analytic facts

**WHAT** — New predicate input kinds so capability situations can condition on what the
Analytic Stratum now computes.

**WHY** — Today predicates read the situation slice's plain facts. L2 v2's
`BusinessSituationObject` additionally carries `trends`, `cohort_positions`, `anomalies`,
`missing_facts`, `conflicts`. Without adapter support, none of that knowledge-side
richness is expressible in a capability's situation file.

**HOW** — extend the predicate grammar (same whitelist discipline):

| New predicate kind | Example in a situation YAML |
|---|---|
| `trend` | `{kind: trend, metric: engagement.touch_count_28d, direction: DECLINING, min_confidence_bp: 5000}` |
| `cohort` | `{kind: cohort, metric: spend_growth, band: top_decile, min_population: 5}` |
| `anomaly` | `{kind: anomaly, metric: support.ticket_count_28d}` |
| `absence` | `{kind: absence, fact: decision.scheduled, type: GENUINELY_ABSENT}` |
| `conflict` | `{kind: conflict, field: contract.value}` |

**Three-state rule carries over exactly:** a `trend` predicate over
`INSUFFICIENT_HISTORY` evaluates **UNKNOWN** — never FALSE. An `absence` predicate is
satisfied only by `GENUINELY_ABSENT`, never by `UNKNOWABLE` (the same law as L2.6's
pattern conditions).

**ACCEPTANCE** — a situation YAML with a `trend` predicate matches only when the BSO
carries a qualifying trend; `UNKNOWABLE` never satisfies `absence`;
`INSUFFICIENT_HISTORY` yields UNKNOWN, receipted.

# L3.1-U2 · Routing on `pattern_id`

**WHAT** — The reverse index keys on L2 v2's `pattern_id` alongside situation type.

**WHY** — L2 v2's pattern registry (X6) emits `pattern_id` + `matched_conditions`; that
is a sharper routing key than anchor-derived situation types, and the per-condition
evidence flows into the package's evidence aggregation for free.

**HOW** — additive: `situation-capability-map.yaml` gains a `patterns:` section; the
resolver tries `pattern_id` first, falls back to situation type. Migration is
non-breaking — anchor-based routing keeps working until L2's X6 lands per tenant.

# L3.1-U3 · Stale-comment hygiene

Fix `deliver/pipeline.py:181` ("152 capabilities, 0 of them accepted" — stale; 153/153
are stamped) and re-verify the abstention gate reads the live admission state rather
than any cached assumption. **One test:** a stamped capability's signal passes abstention
un-downgraded; an unstamped draft's does not.

---

## Group acceptance gate

```
pytest tests/packs/compiler -q
```

| Metric | Gate |
|---|---|
| byte-identical package for identical (situation, snapshot) | **exact** — Law 2 regression test |
| `trend`/`cohort`/`anomaly`/`absence`/`conflict` predicates evaluable | all 5 |
| `UNKNOWABLE` satisfying an `absence` predicate | **0** |
| pattern_id routing with situation-type fallback | both paths tested |
| abstention gate vs live admission state | stamped passes, draft downgrades |
