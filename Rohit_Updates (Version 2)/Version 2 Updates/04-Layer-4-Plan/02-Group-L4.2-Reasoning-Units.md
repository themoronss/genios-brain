# Group L4.2 — The Reasoning Units (the roster)

> **Globe names 17 units. The registry holds 21.** All 17 exist and are well built. This
> document is the unit-by-unit ground truth — what each one publishes, who reads it, what
> runs today, and exactly what changes.

---

## 1. The registry truth (verified by enumeration, not by memory)

| Class | Count | Ids |
|---|---|---|
| **Full plugin units** (Globe's 17) | **17** | context · timeline · dependency · constraint · policy · risk · opportunity · impact · cost · resource · scheduling · tradeoff · alternative · priority · confidence · validation · recommendation |
| **Thin shims** (not named in Globe, but **load-bearing**) | 4 | temporal · relationship · signal_composition · planning |
| **Legacy reasoners** | 2 | `legacy.rule` · `legacy.score_gate` |
| **Ghost** | 1 | **`core.effort` — referenced as a default, never registered** (§4 U4) |

**Alignment: Globe's 17 = the 17 full units, exactly.** No unit is missing as code. The
audit's finding is not absence — it is **reachability**.

---

## 2. Reachability today — and the finding underneath it

| Lane | Units that actually run |
|---|---|
| Legacy pack rules | fixed 10-unit DAG per rule |
| Native capabilities | `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)` — **one capability** |
| **Compiled (v2's lane)** | **6**: context → risk, constraint → priority, confidence, planning |

**Never running anywhere:** timeline · dependency · policy · opportunity · impact · cost ·
resource · scheduling · tradeoff · alternative · validation · recommendation.

### 🔴 The finding underneath: the units that DO run, run **half-blind**

The compiled DAG schedules `core.risk` — but **not** `core.temporal` or
`core.relationship`, which are the prior sources two of its three plugins read:

| `core.risk` plugin | Reads | On the compiled lane |
|---|---|---|
| MomentumDecayPlugin | `core.temporal` → `drop_bp` | **prior absent → silent** |
| RelationshipHealthPlugin | `core.relationship` → `coverage_bp` | **prior absent → silent** |
| PlayMitigationPlugin | the capability's plays | ✅ runs |

So the one evaluative unit on v2's lane observes **one of the three things it was built to
observe** — and correctly says nothing about the other two rather than guessing. The same
starvation hits `core.cost` (`delay_cost` reads `core.temporal`), `core.opportunity`
(StalledButOpen reads `core.temporal`), `core.alternative` (momentum), and
`core.impact` (`core.relationship`).

**The source itself records the consequence** (`adapters/expertise.py:118-122`):
> *"`core.risk` measures pressure; it does not RULE on priority, so the declared-override
> path found nothing and every compiled candidate fell back to a neutral 5000 utility —
> which is why every compiled card scored exactly 50."*

**Every compiled card scored exactly 50.** That is the deafness, written down in the
repository by the engineer who hit it. The patch was to hand the corpus's authored
priority to the unit as config — a correct stopgap, and the reason doc 04's E1 demotes
the override to a prior instead of deleting it.

---

## 3. The roster, unit by unit

Legend — **R?** = reachable on the compiled lane today. Metric names are the unit's real
`publishes` tuple (its contract with every downstream reader).

### Stage 1 — observation

| Unit | Computes | Publishes | Plugins | R? | v2 change |
|---|---|---|---|---|---|
| **core.context** | how complete, fresh and corroborated the situation is | `completeness_bp` `freshness_bp` `declared/known/missing_field_count` `evidence_age_hours` `corroboration_count` `conflict_count` … (12) | 3 | ✅ | + reads the L2 BSO projection (doc 06 S2) |
| **core.timeline** | the arrangement of events in time: cadence, gaps, acceleration | `event_count` `elapsed_hours` `gap_hours` `max_gap_hours` `cadence_hours` `cadence_breach_bp` `overdue_hours` `acceleration_bp` | 3 | ❌ | **schedule it** + **publish `urgency_bp`** (U5) |
| **core.dependency** | what blocks this work and how deep the chain is | `blocked_count` `blocking_depth` `unblocked_bp` `hard_blocked_count` `blocker_severity_bp` | 3 | ❌ | schedule it (recommendation's readiness reads it) |
| **core.temporal** *(shim)* | the clock: how much engagement has decayed | `drop_bp` | — | ❌ | **schedule it — it starves 5 units** (U2) |
| **core.relationship** *(shim)* | account coverage and concentration | `coverage_bp` `relationship_risk_bp` `relationship_count` | — | ❌ | **schedule it — risk and impact read it** (U2) |

### Stage 2 — evaluation

| Unit | Computes | Publishes | Plugins | R? | v2 change |
|---|---|---|---|---|---|
| **core.constraint** | which candidates are eliminated and why | `constraint_check_count` `constraint_elimination_count` | 4 | ✅ | + consumes L3 `compiled_constraints` (doc 06 S3) |
| **core.policy** | which org rules bind; who must approve | `compliance_bp` `policy_concerns` `policy_violations` `rules_triggered` | 3 | ❌ | **schedule it — the L2 Authority view's only consumer** |
| **core.risk** | pressure: decay, thin relationships, unmitigated plays | `risk_bp` | 3 | ⚠️ 1/3 | fed properly once temporal + relationship run |
| **core.opportunity** | unanswered inbound, stalled-but-open, unworked | `opportunity_bp` `opportunity_count` | 3 | ❌ | schedule + domain-vocab purge (U3) |
| **core.impact** | revenue exposure, account weight, strategic linkage | `impact_bp` `revenue_exposure_bp` `relationship_exposure_bp` `strategic_bp` | 3 | ❌ | schedule — the utility formula's impact term |
| **core.cost** | effort, delay cost, exposure, **cost of doing nothing** | `cost_bp` `effort_bp` `exposure_bp` `delay_cost_bp` **`do_nothing_cost_bp`** `cost_benefit_gap_bp` | 3 | ❌ | **schedule — E4 depends on it entirely** |
| **core.resource** | owner capacity, workload saturation, headroom | `capacity_bp` `load_bp` `headroom_bp` | 3 | ❌ | schedule when declared; vocab purge |
| **core.scheduling** | deadline pressure, cadence spacing, quiet windows | `deadline_pressure_bp` `timing_fit_bp` `wait_hours` `constraint_count` | 4 | ❌ | schedule when declared |

### Stage 3 — comparison

| Unit | Computes | Publishes | Plugins | R? | v2 change |
|---|---|---|---|---|---|
| **core.tradeoff** | speed-vs-certainty, risk-vs-reward, cost-vs-benefit tension | `tension_bp` `margin_bp` `axis_count` `contested_count` | 3 | ❌ | schedule + **fix the dead cost axis** (U4); feeds R-3 narration |
| **core.alternative** | viable options, distinctness, **do-nothing baseline** | `option_count` `viable_count` `distinct_count` `has_alternative` `do_nothing_baseline_bp` | 3 | ❌ | schedule — feeds `alternatives_rejected` narration |
| **core.priority** | urgency inputs and any authored override | `urgency_bp` `priority_override_bp` | 4 | ✅ | max-wins finally sees a real `urgency_bp` from timeline (U5) |
| **core.confidence** | source quality, corroboration, **independent evidence groups** | `confidence_bp` `source_quality_bp` `corroboration_bp` `evidence_coverage_bp` **`independent_evidence_groups`** | 3 | ✅ | **already publishes Rule 11's raw material** — doc 04 E2 consumes it |

### Stage 4 — conclusion

| Unit | Computes | Publishes | Plugins | R? | v2 change |
|---|---|---|---|---|---|
| **core.validation** | contradictions, ungrounded claims, staleness, safety | `contradiction_count` `evidence_sufficiency_bp` `ungrounded_claim_count` `staleness_bp` `safe_bp` | 3 | ❌ | **schedule — this is validation-as-silence** |
| **core.recommendation** | which plays the evidence supports and how ready they are | `declared_play_count` `supported_play_count` `support_strength_bp` `support_coverage_bp` `ready_play_count` | 3 | ❌ | schedule — support strength feeds the bundle |
| **core.planning** *(shim)* | are the outcomes observable | reason codes only | — | ✅ | keep as-is |
| **core.signal_composition** *(shim)* | composes member signals into one | `signal_score_bp` | — | ❌ | keep dormant — legacy-lane only (stated) |

> **A published metric is a contract.** No v2 work renames one. New metrics are *added*
> (`urgency_bp` on timeline); nothing existing is repurposed. That is why the roster can
> be turned on without touching a single unit's math.

---

## 4. The work

# U1 · Extend the compiled-lane DAG through the selector (the main event)

**WHAT** — `_default_dag` grows from 6 units to the full staged family:

```
stage 1  core.context · core.timeline · core.dependency · core.temporal · core.relationship
stage 2  core.constraint · core.policy · core.risk · core.opportunity · core.impact
         · core.cost · core.resource · core.scheduling
stage 3  core.tradeoff · core.alternative · core.priority · core.confidence
stage 4  core.validation · core.recommendation · core.planning
```
Globe's dependency shape is preserved: `tradeoff ← (risk, opportunity, impact, cost)`,
`validation ← (risk, opportunity, impact, confidence)` — already authored in
`packs/capabilities/deal_cooling_v2.py`, imported and never swept.

**WHY** — every downstream fix depends on units actually producing evidence: E4 needs
`core.cost`, R-3 needs `core.tradeoff` and `core.alternative`, the utility's impact term
needs `core.impact`, silence needs `core.validation`, and `core.risk` needs its two
starved priors.

**HOW — via the selector, not a hardcode** (doc 01 C1). Declare the full roster; mark
stage-2+ units OPTIONAL with their declared input fields; set
`context_aware_selection: true`. A situation with no money facts skips cost and impact —
receipted, deterministic, exactly Globe's *"run Risk and Priority, not Pricing."*

**REQUIRED stays**: context · constraint · priority · confidence. Everything else is
optional-with-cap, which preserves the degraded-confidence rule.

**WHEN** — plan build time; per-tenant via `l4_activation(org, 'roster_v2')`.

**FAILURE MODES** — latency blowup (the planner's refusal guards it; tune declared unit
budgets, never the refusal) · a thin situation dropping so much that confidence collapses
(correct behavior — it surfaces as a DEFER, not a bad card) · an optional unit with no
declared fields can never drop (declare them).

**ACCEPTANCE** — a money-bearing fixture schedules cost + impact; a moneyless one drops
both with receipts; `plan_hash` stable; latency refusal still fires; ≥10 units emit
Findings on a rich fixture.

**REVERSE PROMPT**
```
TASK: Wake the reasoning roster on the compiled lane.
READ FIRST: reason/plan.py (the dormant selector, :44-51 and :219-250),
  packs/capabilities/deal_cooling_v2.py (the authored full-roster DAG),
  reason/adapters/expertise.py::_default_dag (the 6-unit hardcode to replace, and the
  comment at :118-122 explaining why every compiled card scored exactly 50).
DO:
1. Replace _default_dag with the staged full-family DAG above, declared through the
   normal manifest schema - NOT a new mechanism.
2. Schedule core.temporal and core.relationship in stage 1. They are shims Globe does not
   name, but core.risk, core.cost, core.opportunity, core.alternative and core.impact all
   read their metrics as priors; without them those plugins are silent by design.
3. Mark stage-2+ units OPTIONAL with declared input fields; set context_aware_selection
   true. REQUIRED stays: context, constraint, priority, confidence.
4. Do not touch the planner or the resolver. If a plan is refused on latency, tune
   declared unit budgets, never the refusal.
5. Gate the whole roster behind l4_activation(org, 'roster_v2') - never a global flag.
RULES: rename no published metric; change no unit's math in this wave; every dropped
optional unit emits a skip receipt.
TESTS: pytest tests/reason/test_plan_selection.py -q  + a rich fixture producing Findings
from >= 10 distinct units + plan_hash determinism.
DO NOT: parallelize execution; weaken any plan validation; remove skip receipts.
```

# U2 · Schedule the two starved shims

Covered mechanically by U1, stated separately because it is the fix nobody would find by
reading Globe: **`core.temporal` and `core.relationship` are not in Globe's 17, and five
Globe units depend on them.** A roster built strictly from the spec would still leave
`core.risk` blind. Both are cheap (74 and 82 lines, no LLM, no I/O).

**ACCEPTANCE** — `core.risk` emits momentum and relationship observations on a fixture
where it emits none today.

# U3 · Purge domain vocabulary from core units

**WHAT** — `core.opportunity`, `core.risk` and `core.resource` hardcode sales vocabulary
(deal / champion / pipeline readings). Globe names this drift explicitly: *"domain
vocabulary leaking into a reasoning unit."*

**HOW** — the unit reads **declared manifest fields** (`opportunity_signals: [...]`); the
*naming* of what counts as an opportunity moves to the L3 manifest where it belongs. Unit
logic becomes threshold / compare / compose over declared inputs. One test per unit greps
its source for domain tokens (`deal`, `champion`, `pipeline`, `ticket`) and fails on a hit.

**WHY IT IS SAFE** — the config keys already exist on most units (`account_tier_bp`,
`strategic_goal_bp`, `unowned_strength_bp` …). This wave finishes a pattern the code
already follows; it does not invent one.

# U4 · Fix the dead tradeoff cost axis — **the `core.effort` ghost**

**VERIFIED** — `tradeoff_unit.py:171` reads
`_prior_bp(view, "cost_source", "core.effort", "effort_bp")`. **`core.effort` is not a
registered unit** — no file, no id, nothing publishes it. Meanwhile `effort_bp` *is*
published by **`core.cost`**. So the cost-vs-benefit axis has never had a reading, and
`core.tradeoff` has been quietly running on two axes instead of three.

**FIX** — default `cost_source` to `core.cost`, and add a **registration-time check: a
manifest naming an unregistered source unit fails at plan time**, not silently at run
time. That check is the general cure for this whole class of bug.

**ACCEPTANCE** — the cost-vs-benefit axis produces an observation on a fixture; a manifest
naming `core.nonexistent` is refused at registration with the unit named.

# U5 · Urgency derivation (DLG-04)

**WHAT** — `urgency_bp` computed from validated dates, ending the permanent neutral 5000.

**WHERE** — `core.timeline` (which U1 finally schedules) gains `urgency_bp` in its
`publishes` tuple. `core.priority`'s MaximumUrgencyPlugin then resolves max-wins across
sources exactly as it was designed to — **no change to priority.py**.

**HOW**
```
nearest material date = min over (deadlines, renewal dates, commitment due dates)
    from L1's ResolvedDate, honoring certainty:
    EXACT full weight · RANGE by earliest · RELATIVE halved   (L1's rule, carried through)

urgency_bp:  overdue 10000 · <=2d 9000 · <=7d 7500 · <=14d 6000
             · <=30d 4000 · <=90d 2000 · beyond 500 · NO DATE -> 0
```
**No date → 0, never neutral.** An undated situation is not half-urgent; it is *undated*,
and the ladder must not manufacture pressure that no evidence supports.

**FAILURE MODES** — a date in a different timezone (L1 normalizes; L4 never re-parses) ·
a RELATIVE date treated as EXACT (halving rule, tested) · dates from a stale evidence
payload (validation's staleness term catches it).

**ACCEPTANCE** — the pilot's `urgency_bp` distribution is **not a spike at 5000**; an
undated situation reads 0 and its card ranks accordingly.

# U6 · Roster hygiene (stated decisions)

| Item | Decision |
|---|---|
| `core.signal_composition` | stays dormant — legacy-lane only, no compiled consumer |
| `legacy.rule` / `legacy.score_gate` | untouched until the legacy lane retires |
| the 4 shims' absence from Globe | recorded as a **spec gap in Globe**, not a code defect — Globe should name them in its next revision |

---

## Group acceptance gate — G-L4.2

```
pytest tests/reason/test_plan_selection.py tests/reason/test_units_domain_free.py -q
python scripts/unit_reachability_report.py --org <pilot>
```

| Metric | Gate |
|---|---|
| distinct units producing Findings on the pilot over 7 days | **≥ 12** |
| `core.risk` emitting momentum + relationship observations | demonstrated (today: never) |
| skip receipts on every dropped optional unit | 100% |
| domain tokens in core unit sources | **0** |
| `urgency_bp` distribution | **not a spike at 5000** |
| a manifest naming an unregistered source unit | refused at registration |
| published metric names changed | **0** |
| plan determinism (same inputs → same `plan_hash`) | exact |
