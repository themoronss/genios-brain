# Authoring brief — read this, not the four big files

This exists for one reason. The full contract lives in `README.md`, `_schema/vocabulary.yaml`,
`<domain>/domain.yaml` and seven JSON Schemas — about **19,000 tokens**. A fleet of 61 authoring
agents each reading all four spent over a million tokens before writing a single line, and then
hit the quota wall with nothing to show. This file is the same contract in roughly a fifth of the
space.

**Read the JSON Schemas only if `validate.py` complains about a file you wrote.** They are the
authority; this is the working summary.

---

## What you are writing

Layer 3 domain expertise: **what the profession knows**. Not what one company does (Organization
Brain, a database), not runtime configuration (`genios_engine/packs/`). Human-authored YAML in
Git that a human reviews and only a human merges — Atlas Rule 06.

```
<Domain> Expertise/
├── objects/core/<n>.yaml                     loaded by >1 capability
├── objects/<capability>/<n>.yaml             loaded by exactly 1
├── playbooks|heuristics|mental-models|rules|decision-frameworks/
│     core/<n>.yaml  or  <capability>/<n>.yaml
├── terminology/<area>.yaml
└── capabilities/<NN-subdomain>/<capability>/
      capability.yaml     purpose, outcomes, failure modes, KPIs, handoffs — NO knowledge inline
      objects.yaml        which NOUNS to load.     references only
      knowledge.yaml      which EXPERTISE applies. references only
      situations/*.yaml
```

**Ids.** `<dom>.obj.<core|capability>.<name>` · `<dom>.pb|heu|mm|rule|df.<core|capability>.<name>`
· `<dom>.sit.<name>` · `<dom>.<subdomain>.<capability>`

**core vs capability scope is decided by the reference graph, not by taste.** Referenced by two
capabilities → must be `core`. By one → `capability`. `validate.py` errors both ways. Only invent
a scoped artifact or object when you are confident nothing else will load it.

---

## Ten hard rules

1. **Integer basis points.** Every score is an integer 0–10000 on a field ending `_bp`. Never
   `0.87` — write `8700`. Floats do not hash reproducibly, so a threshold met on one worker is
   missed on another and it surfaces months later as *"why did it not remind me?"*.
2. **`decision_factors` weights sum to exactly 10000.**
3. **The predicate grammar is closed** — see below. Nothing else evaluates.
4. **`IN` is uppercase.** The engine tests `op == "IN"`; a lowercase `in` evaluates False forever.
5. **Conditions in a list are ANDed. There is no OR** — write two entries.
6. **Pattern honesty.** `status: executable` only if every fact path and obs kind it names is in
   the substrate below. Otherwise `needs_signal` with `requires_signals`. A third to a half
   executable is realistic; inflating it is the worst thing you can do here.
7. **No numbers in `capability.yaml`.** Thresholds are Layer 4's arithmetic and live in the pack.
8. **Quote flow scalars containing a comma or colon.** `{signal: "role, seniority"}` — unquoted,
   the parser splits it into phantom keys. This has bitten us seven times.
9. **Write only your own files.** Never `domain.yaml`, `vocabulary.yaml`, a schema, a README, or
   another agent's folder. Others run in parallel.
10. **Industry-real.** MEDDICC, BANT, SPIN, Challenger, mutual action plans, forecast categories.
    If a working practitioner would not recognise a term, it belongs in the Organization Brain.

---

## The predicate grammar — all ten forms

```yaml
{exists: <fact_path>}          {absent: <fact_path>}
{has_obs: <obs_kind>}          {no_obs: <obs_kind>}
{neighbor_has_obs: <obs_kind>} {neighbor_no_obs: <obs_kind>}
{neighbor_fact: <fact_path>, op: <op>, value: <v>}
{fn: edge_count,               op: <op>, value: <v>}
{fn: days_since|hours_since, path: <fact_path>, op: <op>, value: <v>}
{path: <fact_path>,            op: <op>, value: <v>}
```

Ops, exactly: `"=" "!=" "IN" ">" ">=" "<" "<="`
Values may be literals or `{baseline: reply_cadence, mult: 2.5, floor: 10}`.

## The substrate — what the pipeline can evaluate TODAY

Anything outside this makes a pattern `needs_signal`.

**Fact paths (12)** `deal.status` `deal.last_inbound` `deal.value` `thread.last_inbound`
`thread.ball_in_court` `commitment.due_at` `commitment.action` `meeting.status`
`meeting.start_at` `derived.momentum` `derived.engagement` `derived.sentiment`

**Observation kinds (18)** `budget_approved` `budget_freeze` `champion_change`
`closed_lost_mention` `competitor` `contract_requested` `demo_requested` `discount_pressure`
`followup_sent` `introduction` `legal_review` `objection` `objection_price` `pricing_discussed`
`proposal_sent` `security_review_started` `timeline_slip` `verbal_yes`

**Baselines (1)** `reply_cadence`

**Values in practice** `deal.status = open` · `thread.ball_in_court = us|them|nobody` ·
`derived.*` are numbers (engagement/momentum ~0–1+, sentiment ~−1–1)

**Layer 2 situation types (26)** — a situation may bind ONLY these:
`stalled_deal` `objection_open` `buying_signal` `cooling_deal` `single_threaded_deal`
`competitor_in_live_deal` `going_dark_after_proposal` `deal_sentiment_negative` `deal_health`
`pricing_objection` `verbal_yes_not_closed` `contract_requested` `security_review_pending`
`champion_left` `budget_freeze` `discount_pressure` `legal_in_review` `timeline_slip`
`demo_requested` `proposal_no_response` `closed_lost_risk` `commitment_overdue`
`unanswered_email` `champion_quiet` `meeting_no_followup` `intro_followup`

---

## The 23-section object

Required: `identity` `purpose` `attributes` `relationships` `inference_patterns` `evidence`
`metadata`. Author all 23 — a thin object is worse than none because it looks finished.

| # | Section | Shape |
|---|---|---|
| 1 | `identity` | id · name · domain · scope · owner_capability · subdomain · version · status · aliases |
| 2 | `purpose` | statement · **discriminator** (the one sentence separating it from its nearest confusable neighbour — usually the best line in the file) · answers[] · not[] |
| 3 | `attributes` | ONE list. `type: composite` → `contains[]`; `value` → `data_type` (+allowed_values/unit/default/validation/constraints/required/source_paths); `derived` → `derived_from[]`; `reference` → `ref`. Each needs `name` + `purpose` + `type`. 12–24 total. |
| 4 | `states` | initial · terminal[] · values[{name, description, entered_when, implies}] · transitions[{from, to, when, trigger, reversible}] |
| 5 | `relationships` | target · type(verb) · direction · cardinality · **weight_bp** · **confidence_bp** · conditions[] · evidence[] · priority · description · metadata |
| 6 | `inference_patterns` | `{deterministic: [], heuristic: []}`; each id · statement · status · when OR requires_signals · yields{confidence_bp, attribute, value, corroborates} · evidence_fields · **false_positive** · note. 7–12 patterns. |
| 7 | `inputs` | source · signal · path · fills[] · reliability_bp |
| 8 | `outputs` | name · type · description · derived_from[] · consumed_by[] |
| 9 | `preconditions` | RECORDS: id · statement · requires[] · when[] · if_unmet (`block` vs `degrade`) |
| 10 | `constraints` | id · statement · when[] · hard · why |
| 11 | `business_rules` | OBJECT-LOCAL ONLY. Cross-object rules go in `rules/`. id · statement · when[] · then · severity · why |
| 12 | `decision_factors` | name · weight_bp · direction · reads[]. **Sum to 10000.** |
| 13 | `evidence` | source · strength_bp · **independent_of[]** · decays · description |
| 14 | `metrics` | name · unit · description · direction · owner_layer · calibrates[] |
| 15 | `events` | id · name · emitted_when[] · payload[] · severity · **invalidates[]** |
| 16 | `actions` | id · name · actor · preconditions[] (bare predicates) · effect · cost · reversible |
| 17 | `dependencies` | target · kind(requires\|enriches\|invalidated_by\|derived_from\|blocks) · strength |
| 18 | `exceptions` | Where the rules above are legitimately wrong. id · statement · overrides[] · when[] · why · frequency |
| 19 | `best_practices` | statement · why · applies_when · evidence |
| 20 | `anti_patterns` | statement · **why_it_happens** (the reasonable logic that leads there) · cost · instead · detectable_by[] |
| 21 | `examples` | {label, note, kind}. 4–6, including one `kind: misclassification` |
| 22 | `references` | title · kind · author · url · note |
| 23 | `metadata` | owner · created_by · reviewed_by · last_updated · review_status · confidence · completeness |

**Relationship verbs** `owns` `belongs_to` `member_of` `works_with` `reports_to` `approves`
`blocks` `influences` `requires` `produces` `attaches_to` `competes_with` `references`
`precedes` `supersedes` `gates`

**Evidence sources** `email` `calendar` `meeting_transcript` `call_recording` `crm` `slack`
`document` `contract` `website` `manual_entry` `derived`

**Consumers** `L4.reasoning_unit` `L4.decision_maker` `L5.execution_planning`
`L5.communication_planning` `"L5.2.channel_planner"` `L6.learning_unit`

---

## Knowledge artifacts

All five share `identity{id, name, kind, domain, scope, owner_capability, version, status}` ·
`purpose{statement, answers, not}` · `objects_used[]` · `limits[]` · `failure_modes[]` ·
`variants[]` · `references[]` · `metadata`. Then, per kind:

| kind | folder | prefix | also required |
|---|---|---|---|
| `playbook` | `playbooks/` | `pb` | `when_to_use` · `steps[{order, name, actor, produces, done_when}]` — a step nobody can tell is finished is a wish |
| `heuristic` | `heuristics/` | `heu` | `heuristic{statement, why, breaks_down_when, confidence_bp, reads, contradicts}` — breaks_down_when is the most useful field |
| `mental_model` | `mental-models/` | `mm` | `dimensions[{name, asks, objects, weak_signal, strong_signal}]` · `how_to_apply[]` |
| `rule` | `rules/` | `rule` | `rule{statement, spans[≥2 object ids], when[], then, severity, why, enforced_by}` — CROSS-OBJECT is the whole point |
| `decision_framework` | `decision-frameworks/` | `df` | `criteria[{name, weight_bp, reads, disqualifying}]` · `how_to_apply[]` |

`enforced_by` ∈ `L3_compile` `L4_constraint` `L5_validation` `L5_2_gate`. A rule nobody enforces
is a comment.

---

## Capability folder

**`capability.yaml`** identity(stub:false) · description · question (the ONE question, as an
operator asks it) · outcomes[4–6, including the negative one — a qualification capability that
never disqualifies is not running] · failure_modes[4–6: how a competent-seeming person does this
badly] · kpis[{name, unit, description, direction}] · handoffs{upstream, downstream, parallel} ·
applies_to{models, offerings} · metadata. **No knowledge keys, no numbers.**

**`objects.yaml`** `capability` · `core{required[], optional[]}` · `scoped{required[], optional[]}`
· optional `never_load[]` `load_order[]` `notes`. Be disciplined: 3–6 core required. The point of
a load-set is five objects, not forty. `optional` means absence lowers confidence rather than
blocking.

**`knowledge.yaml`** `capability` · `playbooks|heuristics|mental_models|rules|decision_frameworks:
{core: [], scoped: []}` · `terminology[]` · `primary_framework` · `notes`. Do not reference an
artifact to look thorough — an unused reference costs a compile.

**`situations/<n>.yaml`** identity{id, name, domain, **owner_capability**, version, status} ·
description · `matches{l2_situation_types[] from the 26 ONLY, scope, when[]}` · also_serves[] ·
`objects{load[], optional[], never_load[]}` · priority_bp · typical_duration_days ·
signals_of_progress[] / signals_of_decay[] (from the 18 obs kinds).

If no L2 type honestly applies — true for pre-deal and planning capabilities that no runtime
signal triggers — **author no situation and say why**. Do not invent a binding to look complete.

**`terminology/<area>.yaml`** `area` · `domain` · `terms[{term, definition, aliases,
not_to_be_confused_with[{term, difference}], object_ref, used_by[], register}]` · metadata.
`register` ∈ `internal` `customer_facing` `both` — Layer 5.2 renders cards in this vocabulary,
and "churn risk" said to a customer is a different conversation.

---

## Voice

Dense, declarative, specific. British spelling. No emoji. Every line earns its place by saying
something a mediocre operator would get wrong. State the reasoning, never the platitude.

> Bad — *"Qualification is important for pipeline health."*
> Good — *"A price objection is evidence a budget exists: buyers with no money disengage, they
> do not haggle."*

Comments in the YAML are encouraged and are where the reasoning lives.

## Before you finish

```
cd /Users/rohitswerashi/genios-brain && \
  .venv/bin/python "Domain Expertise/_tools/validate.py" 2>&1 | grep ERROR | grep <your-folder>
```

Fix every ERROR naming a file you wrote; re-run until empty. Ignore everything else — it belongs
to other agents. Warnings saying *"planned but not authored yet"* are expected and correct.
